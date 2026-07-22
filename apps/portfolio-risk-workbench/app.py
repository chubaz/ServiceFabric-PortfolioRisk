"""Local synthetic Portfolio Risk Workbench adapter and server-rendered UI."""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Annotated
from urllib.parse import quote, urlencode

import pyarrow.parquet as pq
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette import requests as starlette_requests
from starlette.formparsers import MultiPartException, MultiPartParser
from risk_agents import ACTIVE_AGENT_ROLE_IDS, AGENT_ROLES, DeterministicMonitoringOrchestrator, MonitoringRunRequest
from risk_capabilities import AlertDraft, AlertReviewRequest, AnomalyDetectionRequest, CapabilityResult, DEFAULT_CAPABILITY_REGISTRY, DecisionPoint, EvidenceReference, ExposureSummaryRequest, NewsClassificationRequest, PortfolioSnapshotRequest, PositionSpecification, SyntheticNewsEvent
from risk_data import NormalizedMarketRecord, PortfolioConfirmationRequest, PortfolioInputPreview, ingest_synthetic
from risk_data.pipeline import resolve_data_root
from risk_domain import CashBalance, MarketObservation, PortfolioSnapshot
from risk_domain.digests import sha256_digest
from risk_planning import load_day1_seed_catalog, load_notebook_catalogue, load_research_catalogue, load_seed_catalog


APPLICATION_STATUS = {
    "application_id": "portfolio-risk-workbench",
    "version": "0.1.0",
    "synthetic_mode": True,
    "external_providers": "disabled",
    "human_review": "required",
}
APPLICATION_ROOT = Path(__file__).resolve().parent
if str(APPLICATION_ROOT) not in sys.path:
    sys.path.insert(0, str(APPLICATION_ROOT))

from presentation import profile_view, render_page  # noqa: E402  (the hosted app directory is resolved above)
from analysis_service import (  # noqa: E402
    DEFAULT_CONFIDENCE_LEVEL,
    DEFAULT_SCENARIO_ID,
    METHOD_BY_ID,
    REVIEWED_CONFIDENCE_LEVELS,
    REVIEWED_METHODS,
    SCENARIO_CATALOGUE,
    AgentTimelineCollection,
    AgentTimelineEnvelope,
    ReportCollection,
    ReportEnvelope,
    ReviewedRiskAnalysisService,
    RiskAnalysisCollection,
    RiskAnalysisEnvelope,
)
from workspace_service import MAX_INPUT_BYTES, PortfolioWorkspace, WorkspaceRecordNotFound, provider_views  # noqa: E402


class BoundedPortfolioMultiPartParser(MultiPartParser):
    """Reject an oversized file part before Starlette queues or spools it."""

    spool_max_size = MAX_INPUT_BYTES
    max_file_size = MAX_INPUT_BYTES

    def on_part_begin(self) -> None:
        super().on_part_begin()
        self._current_file_size = 0

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self._current_part.file is not None:
            message_size = end - start
            if self._current_file_size + message_size > self.max_file_size:
                raise MultiPartException(f"File exceeded maximum size of {self.max_file_size} bytes.")
            self._current_file_size += message_size
        super().on_part_data(data, start, end)


# FastAPI resolves File()/Form() dependencies through Request.form(). Replace
# Starlette's request-level parser so the limit applies before UploadFile exists.
starlette_requests.MultiPartParser = BoundedPortfolioMultiPartParser


EVIDENCE = (
    EvidenceReference(
        evidence_id="synthetic-day0-evidence",
        reference="fixture://day0/20260721",
        source_type="synthetic-fixture",
    ),
)
REPOSITORY_ROOT = APPLICATION_ROOT.parents[1]
CATALOG_ROOT = APPLICATION_ROOT if (APPLICATION_ROOT / "seed" / "knowledge-products").is_dir() else REPOSITORY_ROOT
RESEARCH_CATALOG_PATH = (
    APPLICATION_ROOT / "catalog" / "research.yaml"
    if (APPLICATION_ROOT / "catalog" / "research.yaml").is_file()
    else REPOSITORY_ROOT / "docs" / "research" / "catalog.yaml"
)
NOTEBOOK_CATALOG_PATH = (
    APPLICATION_ROOT / "catalog" / "notebooks.yaml"
    if (APPLICATION_ROOT / "catalog" / "notebooks.yaml").is_file()
    else REPOSITORY_ROOT / "notebooks" / "catalog" / "catalog.yaml"
)
REGISTRY = DEFAULT_CAPABILITY_REGISTRY
app = FastAPI(title="Portfolio Risk Workbench", version="0.1.0")
app.mount("/static", StaticFiles(directory=APPLICATION_ROOT / "static"), name="static")


def root() -> Path:
    try:
        return resolve_data_root()
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


def dumped(value: object) -> object:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def files(kind: str) -> list[dict[str, object]]:
    path = root() / "workbench" / kind
    return [json.loads(item.read_text()) for item in sorted(path.glob("*.json"))] if path.is_dir() else []


def latest(kind: str) -> dict[str, object] | None:
    values = files(kind)
    return values[-1] if values else None


def store(kind: str, value: object) -> dict[str, object]:
    payload = dumped(value)
    if not isinstance(payload, dict):
        raise TypeError("stored Workbench values must be JSON objects")
    digest = sha256_digest(payload)
    path = root() / "workbench" / kind / f"{digest[7:]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    return payload


def records() -> tuple[NormalizedMarketRecord, ...]:
    path = root() / "market" / "prices.parquet"
    if not path.is_file():
        try:
            ingest_synthetic(root())
        except FileExistsError:
            pass
    return tuple(
        NormalizedMarketRecord(
            instrument_id=row["instrument_id"],
            identifier={"identifier_type": row["identifier_type"], "value": row["identifier_value"]},
            observed_at=row["observed_at"],
            price=Decimal(str(row["price"])) if row["price"] is not None else None,
            currency=row["currency"],
        )
        for row in pq.read_table(path).to_pylist()
    )


def portfolio() -> PortfolioSnapshot:
    saved = latest("portfolio")
    if saved:
        return PortfolioSnapshot.model_validate(saved)
    market = records()
    as_of = max(item.observed_at for item in market)
    result = REGISTRY.invoke(
        "portfolio.snapshot.create",
        PortfolioSnapshotRequest(
            snapshot_id="synthetic-portfolio-20260717",
            as_of=as_of,
            positions=(
                PositionSpecification(instrument_id="instrument-alpha", quantity=Decimal("10")),
                PositionSpecification(instrument_id="instrument-beta", quantity=Decimal("20")),
            ),
            cash_balances=(CashBalance(currency="USD", amount=Decimal("1000")),),
            normalized_observations=market,
            evidence_references=EVIDENCE,
        ),
    )
    store("portfolio", result.data)
    return result.data


def current_exposure() -> dict[str, object]:
    exposure = latest("exposures")
    if exposure is None:
        result = REGISTRY.invoke(
            "portfolio.exposure.summarize",
            ExposureSummaryRequest(
                snapshot_id="dashboard-exposure",
                portfolio_snapshot=portfolio(),
                evidence_references=EVIDENCE,
            ),
        )
        exposure = store("exposures", result.data)
    return exposure


def monitoring() -> dict[str, object]:
    snapshot = portfolio()
    market = records()
    request = MonitoringRunRequest(
        portfolio_snapshot=snapshot,
        market_request=AnomalyDetectionRequest(
            normalized_observations=market,
            percentage_threshold=Decimal("0.10"),
            evidence_references=EVIDENCE,
        ),
        news_event=SyntheticNewsEvent(
            event_id="synthetic-news-20260717",
            instrument_id="instrument-alpha",
            headline="Synthetic issuer event",
            sentiment="negative",
            relevance="high",
        ),
        evidence_references=EVIDENCE,
    )
    run = DeterministicMonitoringOrchestrator(REGISTRY).run(request)
    payload = store("agent-runs", run)
    for output in run.outputs:
        for finding in output.findings:
            store("findings", finding)
    if run.alert_draft:
        store("alerts", run.alert_draft)
    return payload


def dashboard_cards() -> dict[str, object]:
    exposure = current_exposure()
    decisions = files("decisions")
    findings = files("findings")
    alerts = files("alerts")
    cash_balances = exposure["portfolio_snapshot"]["cash_balances"]
    return {
        "portfolio NAV": exposure["nav"],
        "cash": sum(Decimal(str(item["amount"])) for item in cash_balances),
        "largest position weight": exposure["largest_position_weight"],
        "concentration limit": "0.40",
        "anomaly count": len([item for item in findings if item["kind"] == "market_anomaly"]),
        "active finding count": len(findings),
        "alert draft count": len(alerts),
        "pending human review count": max(0, len(alerts) - len(decisions)),
    }


def _screen_error() -> str:
    return "The local evidence could not be loaded. Check the configured data root and try again."


def workspace() -> PortfolioWorkspace:
    return PortfolioWorkspace(root())


def preview_view(preview: PortfolioInputPreview) -> dict[str, object]:
    document = preview.document
    return {
        "preview_id": preview.preview_digest,
        "format": document.input_format.value if document is not None else "Not available",
        "digest": preview.preview_digest,
        "content_digest": document.content_digest if document is not None else None,
        "validation_state": "Valid" if preview.valid else "Invalid",
        "confirmable": preview.valid,
        "issues": [dumped(item) for item in preview.issues],
        "quality_flags": preview.quality_flags,
        "document": dumped(document) if document is not None else None,
    }


def snapshot_view(snapshot: PortfolioSnapshot) -> dict[str, object]:
    payload = dumped(snapshot)
    if not isinstance(payload, dict):
        raise TypeError("portfolio snapshot must render as an object")
    try:
        result = REGISTRY.invoke(
            "portfolio.exposure.summarize",
            ExposureSummaryRequest(
                snapshot_id=f"display-{snapshot.snapshot_id}",
                portfolio_snapshot=snapshot,
                evidence_references=(EvidenceReference(evidence_id=snapshot.snapshot_id, reference=f"local-private://{snapshot.snapshot_id}", source_type="local-private-snapshot"),),
            ),
        )
        exposure = dumped(result.data)
        payload["nav"] = exposure["nav"]
        payload["cash_weight"] = exposure["cash_weight"]
        payload["position_weights"] = {item["instrument_id"]: item["weight"] for item in exposure["position_exposures"]}
    except (ValueError, KeyError, TypeError):
        payload["nav"] = None
        payload["cash_weight"] = None
        payload["position_weights"] = {}
    payload["evidence"] = snapshot.digest
    return payload


def _upload_boundary_message(file: UploadFile) -> str | None:
    """Validate only the transport boundary; data parsing remains data-owned."""
    if not (file.filename or "").lower().endswith((".csv", ".yaml", ".yml")):
        return "Only CSV and YAML files are accepted. No input was retained."
    if file.size is not None and file.size > MAX_INPUT_BYTES:
        return f"The upload exceeds the reviewed maximum of {MAX_INPUT_BYTES} bytes. No input was retained."
    return None


def uploaded_content(file: UploadFile) -> bytes:
    try:
        # Read the bounded upload stream directly. This also keeps the adapter
        # testable with in-memory UploadFile instances without an async
        # threadpool dependency; no raw content is persisted.
        content = file.file.read(MAX_INPUT_BYTES + 1)
    finally:
        file.file.close()
    if len(content) > MAX_INPUT_BYTES:
        raise ValueError(f"The upload exceeds the reviewed maximum of {MAX_INPUT_BYTES} bytes. No input was retained.")
    return content


def market_observations() -> tuple[MarketObservation, ...]:
    return tuple(item.to_market_observation() for item in records())


def analysis_snapshots(profile: str) -> tuple[PortfolioSnapshot, ...]:
    selected_profile = profile_view(profile).profile_id
    if selected_profile == "personal_portfolio":
        return workspace().snapshots()
    return (portfolio(),)


def selected_analysis_snapshot(profile: str, snapshot_id: str = "") -> PortfolioSnapshot:
    snapshots = analysis_snapshots(profile)
    if not snapshots:
        raise ValueError("No immutable portfolio snapshot is available for the selected profile.")
    if not snapshot_id:
        return snapshots[-1]
    selected = next((item for item in snapshots if item.snapshot_id == snapshot_id), None)
    if selected is None:
        raise ValueError("The selected immutable portfolio snapshot is unavailable.")
    return selected


def risk_analysis_service(profile: str, snapshot_id: str = "") -> ReviewedRiskAnalysisService:
    return ReviewedRiskAnalysisService(REGISTRY, selected_analysis_snapshot(profile, snapshot_id), market_observations())


def analysis_envelope(profile: str, capability_result: object) -> RiskAnalysisEnvelope:
    selected_profile = profile_view(profile).profile_id
    return RiskAnalysisEnvelope(
        profile=selected_profile,
        data_state="synthetic-reviewed" if selected_profile == "research" else "local-private",
        capability_id=capability_result.capability_id,
        effects=capability_result.effects,
        analysis=capability_result.data,
    )


def _review(draft: AlertDraft, reviewer: str, decision: str, comment: str) -> dict[str, object]:
    if not reviewer.strip():
        raise HTTPException(422, "reviewer is required")
    if decision not in {"approve", "reject", "request_changes"}:
        raise HTTPException(422, "decision must be approve, reject, or request_changes")
    point = DecisionPoint(
        decision_id=f"decision:{draft.alert_id}:{decision}:{reviewer}",
        alert_id=draft.alert_id,
        decision=decision,
        rationale=comment or "No comment supplied.",
        human_reviewer_id=reviewer,
    )
    result = REGISTRY.invoke(
        "alert.draft.review",
        AlertReviewRequest(draft=draft, decision_point=point, evidence_references=EVIDENCE),
    )
    store("decisions", point)
    return dumped(result)


@app.get("/")
def home(profile: str = "research") -> HTMLResponse:
    try:
        exposure = current_exposure()
        return render_page(
            "dashboard.html",
            active_page="dashboard",
            profile=profile,
            cards=dashboard_cards(),
            currency_code=exposure["portfolio_snapshot"]["base_currency"],
            recent_findings=list(reversed(files("findings")))[:3],
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError):
        return render_page("dashboard.html", active_page="dashboard", profile=profile, error=_screen_error())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/api/status")
def api_status() -> dict[str, str | bool]:
    return APPLICATION_STATUS


@app.post("/actions/status")
def status_action() -> dict[str, str | bool]:
    return APPLICATION_STATUS


@app.post("/actions/portfolio-input-preview")
def portfolio_input_preview_action() -> dict[str, object]:
    """Expose one bounded synthetic preview through the canonical hosted tool path."""
    market = records()
    as_of = max(item.observed_at for item in market)
    content = (
        "instrument_id,quantity,currency,as_of\n"
        f"instrument-alpha,10,USD,{as_of.isoformat()}\n"
    ).encode("utf-8")
    preview = workspace().create_preview(
        content,
        "reviewed-synthetic-portfolio.csv",
        profile="research",
        base_currency="USD",
        as_of=as_of.isoformat(),
    )
    return dumped(
        CapabilityResult(
            capability_id="portfolio.input.preview",
            data=preview,
            evidence_references=EVIDENCE,
            assumptions=("The hosted smoke input is an explicitly reviewed synthetic CSV fixture.",),
            limitations=("Preview creates no snapshot until a separate explicit confirmation.",),
            human_review_required=True,
        )
    )


@app.post("/actions/provider-catalog-list")
def provider_catalog_list_action() -> dict[str, object]:
    """List immutable provider metadata without enabling or contacting a provider."""
    return {
        "capability_id": "provider.catalog.list",
        "status": "succeeded",
        "data": {
            "providers": [dumped(item) for item in workspace().providers()],
            "fixed_query_manifests": [dumped(item) for item in workspace().query_manifests()],
            "arbitrary_sql_available": False,
        },
        "evidence_references": [],
        "assumptions": ["Catalogue state is the reviewed local Day 1 configuration."],
        "warnings": [],
        "limitations": ["External providers are disabled and are not contacted by this capability."],
        "effects": [],
        "human_review_required": True,
    }


@app.post("/actions/portfolio-exposure-summarize")
def portfolio_exposure_summarize() -> dict[str, object]:
    result = REGISTRY.invoke(
        "portfolio.exposure.summarize",
        ExposureSummaryRequest(
            snapshot_id="workbench-exposure",
            portfolio_snapshot=portfolio(),
            evidence_references=EVIDENCE,
        ),
    )
    if result.data is not None:
        store("exposures", result.data)
    return dumped(result)


@app.post("/actions/market-anomaly-detect")
def market_anomaly_detect() -> dict[str, object]:
    result = REGISTRY.invoke(
        "market.anomaly.detect",
        AnomalyDetectionRequest(
            normalized_observations=records(),
            percentage_threshold=Decimal("0.10"),
            evidence_references=EVIDENCE,
        ),
    )
    for finding in result.findings:
        store("findings", finding)
    return dumped(result)


@app.get("/api/findings")
def api_findings() -> dict[str, object]:
    return {"findings": files("findings"), "synthetic": True, "human_review_required": True}


@app.get("/api/alerts")
def api_alerts() -> dict[str, object]:
    return {"alerts": files("alerts"), "human_review_required": True}


@app.get("/api/alerts/{alert_id}")
def api_alert(alert_id: str) -> dict[str, object]:
    alert = next((item for item in files("alerts") if item["alert_id"] == alert_id), None)
    if alert is None:
        raise HTTPException(404, "alert not found")
    return {
        "alert": alert,
        "decisions": [item for item in files("decisions") if item["alert_id"] == alert_id],
    }


@app.get("/api/agent-runs")
def api_agent_runs() -> dict[str, object]:
    return {"agent_runs": files("agent-runs"), "human_review_required": True}


@app.post("/actions/news-event-classify")
def news_event_classify() -> dict[str, object]:
    result = REGISTRY.invoke(
        "news.event.classify",
        NewsClassificationRequest(
            event=SyntheticNewsEvent(
                event_id="synthetic-news-20260717",
                instrument_id="instrument-alpha",
                headline="Synthetic issuer event",
                sentiment="negative",
                relevance="high",
            ),
            evidence_references=EVIDENCE,
        ),
    )
    for finding in result.findings:
        store("findings", finding)
    return dumped(result)


@app.post("/actions/alert-draft-synthesize")
def alert_draft_synthesize() -> dict[str, object]:
    return monitoring()


@app.post("/actions/monitoring-run")
def monitoring_run() -> dict[str, object]:
    return monitoring()


@app.post("/actions/alert-draft-review")
def alert_draft_review(reviewer: str = "", decision: str = "", comment: str = "") -> dict[str, object]:
    alert = latest("alerts")
    if alert is None:
        raise HTTPException(409, "an alert draft is required before review")
    return _review(AlertDraft.model_validate(alert), reviewer, decision, comment)


@app.get("/portfolio")
def portfolio_page(profile: str = "research") -> HTMLResponse:
    try:
        selected_profile = profile_view(profile).profile_id
        if selected_profile == "personal_portfolio":
            personal_snapshots = workspace().snapshots()
            current = snapshot_view(personal_snapshots[-1]) if personal_snapshots else None
            history = tuple(snapshot_view(item) for item in personal_snapshots)
        else:
            current = snapshot_view(portfolio())
            history = (current,)
        return render_page("portfolio.html", active_page="portfolio", profile=selected_profile, snapshot=current, snapshots=history, error=None)
    except (HTTPException, OSError, ValueError, KeyError, TypeError):
        return render_page("portfolio.html", active_page="portfolio", profile=profile, snapshot=None, snapshots=(), error=_screen_error())


@app.get("/portfolio/import")
def portfolio_import(profile: str = "personal_portfolio") -> HTMLResponse:
    return render_page("portfolio_import.html", active_page="portfolio", profile="personal_portfolio", maximum_upload_bytes=MAX_INPUT_BYTES)


@app.post("/portfolio/import/preview")
async def portfolio_import_preview(
    file: UploadFile = File(...),
    base_currency: Annotated[str, Form()] = "USD",
    as_of: Annotated[str, Form()] = "",
    profile: str = "personal_portfolio",
) -> HTMLResponse:
    boundary_error = _upload_boundary_message(file)
    if boundary_error:
        return render_page("portfolio_preview.html", active_page="portfolio", profile="personal_portfolio", preview=None, error=boundary_error, status_code=422)
    try:
        preview = workspace().create_preview(uploaded_content(file), file.filename or "", base_currency=base_currency, as_of=as_of)
    except (OSError, ValueError) as error:
        return render_page("portfolio_preview.html", active_page="portfolio", profile="personal_portfolio", preview=None, error=str(error), status_code=422)
    return render_page("portfolio_preview.html", active_page="portfolio", profile="personal_portfolio", preview=preview_view(preview), error=None, status_code=200 if preview.valid else 422)


@app.get("/portfolio/import/preview/{preview_id}")
def portfolio_preview(preview_id: str, profile: str = "personal_portfolio") -> HTMLResponse:
    try:
        preview = workspace().get_preview(preview_id)
    except WorkspaceRecordNotFound as error:
        return render_page("portfolio_preview.html", active_page="portfolio", profile="personal_portfolio", preview=None, preview_id=preview_id, error=str(error), status_code=404)
    return render_page("portfolio_preview.html", active_page="portfolio", profile="personal_portfolio", preview=preview_view(preview), error=None)


@app.post("/portfolio/import/confirm/{preview_id}")
def portfolio_confirm(
    preview_id: str,
    confirm_digest: Annotated[str, Form()] = "",
    confirm_snapshot: Annotated[str, Form()] = "",
    profile: str = "personal_portfolio",
) -> HTMLResponse:
    current_workspace = workspace()
    try:
        result, snapshot = current_workspace.confirm(preview_id, preview_digest=confirm_digest, confirm=confirm_snapshot == "confirmed", observations=market_observations())
    except (WorkspaceRecordNotFound, OSError, ValueError) as error:
        try:
            preview = current_workspace.get_preview(preview_id)
        except (WorkspaceRecordNotFound, OSError, ValueError):
            preview = None
        return render_page("portfolio_preview.html", active_page="portfolio", profile="personal_portfolio", preview=preview_view(preview) if preview else None, preview_id=preview_id, error=str(error), status_code=422)
    location = f"/portfolio/snapshots/{quote(snapshot.snapshot_id, safe='')}?{urlencode({'profile': 'personal_portfolio', 'created': str(result.created).lower()})}"
    return RedirectResponse(location, status_code=303)


@app.get("/portfolio/snapshots")
def portfolio_snapshots(profile: str = "personal_portfolio") -> HTMLResponse:
    try:
        snapshots = tuple(snapshot_view(item) for item in workspace().snapshots())
        return render_page("portfolio_snapshots.html", active_page="portfolio", profile="personal_portfolio", snapshots=snapshots, error=None)
    except (HTTPException, OSError, ValueError, TypeError):
        return render_page("portfolio_snapshots.html", active_page="portfolio", profile="personal_portfolio", snapshots=(), error=_screen_error(), status_code=409)


@app.get("/portfolio/snapshots/{snapshot_id}")
def portfolio_snapshot(snapshot_id: str, profile: str = "personal_portfolio", created: str = "") -> HTMLResponse:
    try:
        snapshot = snapshot_view(workspace().get_snapshot(snapshot_id))
    except WorkspaceRecordNotFound as error:
        return render_page("portfolio_snapshot.html", active_page="portfolio", profile="personal_portfolio", snapshot=None, snapshot_id=snapshot_id, created=None, error=str(error), status_code=404)
    return render_page("portfolio_snapshot.html", active_page="portfolio", profile="personal_portfolio", snapshot=snapshot, snapshot_id=snapshot_id, created=created, error=None)


@app.get("/portfolio/compare")
def portfolio_compare(profile: str = "personal_portfolio") -> HTMLResponse:
    try:
        snapshots = tuple(snapshot_view(item) for item in workspace().snapshots())
        return render_page("portfolio_compare.html", active_page="portfolio", profile="personal_portfolio", comparison=None, snapshots=snapshots, error=None)
    except (HTTPException, OSError, ValueError, TypeError):
        return render_page("portfolio_compare.html", active_page="portfolio", profile="personal_portfolio", comparison=None, snapshots=(), error=_screen_error(), status_code=409)


@app.post("/portfolio/compare/result")
def portfolio_compare_result(
    left_snapshot_id: Annotated[str, Form()],
    right_snapshot_id: Annotated[str, Form()],
    profile: str = "personal_portfolio",
) -> HTMLResponse:
    try:
        comparison = workspace().compare(left_snapshot_id, right_snapshot_id)
    except (WorkspaceRecordNotFound, OSError, ValueError) as error:
        return render_page("portfolio_compare.html", active_page="portfolio", profile="personal_portfolio", comparison=None, snapshots=(), left_snapshot_id=left_snapshot_id, right_snapshot_id=right_snapshot_id, error=str(error), status_code=422)
    return render_page("portfolio_compare.html", active_page="portfolio", profile="personal_portfolio", comparison=dumped(comparison), snapshots=(), left_snapshot_id=left_snapshot_id, right_snapshot_id=right_snapshot_id, error=None)


@app.post("/api/portfolio/previews")
async def api_portfolio_preview(
    file: UploadFile = File(...),
    profile: Annotated[str, Form()] = "personal_portfolio",
    base_currency: Annotated[str, Form()] = "USD",
    as_of: Annotated[str, Form()] = "",
) -> dict[str, object]:
    if profile != "personal_portfolio":
        raise HTTPException(422, "portfolio input is available only in the personal_portfolio profile")
    boundary_error = _upload_boundary_message(file)
    if boundary_error:
        raise HTTPException(422, boundary_error)
    try:
        preview = workspace().create_preview(uploaded_content(file), file.filename or "", profile=profile, base_currency=base_currency, as_of=as_of)
    except (OSError, ValueError) as error:
        raise HTTPException(422, str(error)) from error
    return {"preview_id": preview.preview_digest, "valid": preview.valid, "preview": dumped(preview)}


@app.get("/api/portfolio/previews/{preview_id}")
def api_portfolio_preview_get(preview_id: str) -> dict[str, object]:
    try:
        preview = workspace().get_preview(preview_id)
    except WorkspaceRecordNotFound as error:
        raise HTTPException(404, str(error)) from error
    return {"preview_id": preview.preview_digest, "valid": preview.valid, "preview": dumped(preview)}


@app.post("/api/portfolio/previews/{preview_id}/confirm")
def api_portfolio_preview_confirm(preview_id: str, request: PortfolioConfirmationRequest) -> dict[str, object]:
    try:
        result, snapshot = workspace().confirm(preview_id, preview_digest=request.preview_digest, confirm=request.confirm, observations=market_observations())
    except WorkspaceRecordNotFound as error:
        raise HTTPException(404, str(error)) from error
    except (OSError, ValueError) as error:
        raise HTTPException(422, str(error)) from error
    return {"confirmation": dumped(result), "snapshot": dumped(snapshot)}


@app.get("/api/portfolio/snapshots")
def api_portfolio_snapshots() -> dict[str, object]:
    return {"snapshots": [dumped(item) for item in workspace().snapshots()]}


@app.get("/api/portfolio/snapshots/{snapshot_id}")
def api_portfolio_snapshot(snapshot_id: str) -> dict[str, object]:
    try:
        snapshot = workspace().get_snapshot(snapshot_id)
    except WorkspaceRecordNotFound as error:
        raise HTTPException(404, str(error)) from error
    return {"snapshot": dumped(snapshot)}


@app.get("/api/portfolio/comparisons")
def api_portfolio_comparisons(left_snapshot_id: str = "", right_snapshot_id: str = "") -> dict[str, object]:
    try:
        comparison = workspace().compare(left_snapshot_id, right_snapshot_id)
    except WorkspaceRecordNotFound as error:
        raise HTTPException(404, str(error)) from error
    return {"comparison": dumped(comparison)}


@app.get("/risk")
def risk(
    profile: str = "research",
    snapshot_id: str = "",
    method: str = "simple_returns",
    confidence: str = DEFAULT_CONFIDENCE_LEVEL,
    scenario: str = DEFAULT_SCENARIO_ID,
) -> HTMLResponse:
    try:
        selected_profile = profile_view(profile).profile_id
        service = risk_analysis_service(selected_profile, snapshot_id)
        result = service.analyze(method, confidence_level=confidence, scenario_id=scenario)
        source = result.data if method in {"simple_returns", "log_returns"} else service.analyze("simple_returns").data
        store("risk-analyses", result.data)
        return render_page(
            "risk.html",
            active_page="risk",
            profile=selected_profile,
            snapshots=[dumped(item) for item in analysis_snapshots(selected_profile)],
            selected_snapshot_id=service.snapshot.snapshot_id,
            methods=REVIEWED_METHODS,
            selected_method=method,
            selected_method_label=METHOD_BY_ID[method][0],
            confidence_levels=REVIEWED_CONFIDENCE_LEVELS,
            selected_confidence=confidence,
            scenarios=SCENARIO_CATALOGUE,
            selected_scenario=scenario,
            capability_id=result.capability_id,
            analysis=dumped(result.data),
            series=getattr(source, "observations", ()),
            effects=result.effects,
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        message = str(error) if isinstance(error, ValueError) else _screen_error()
        return render_page(
            "risk.html",
            active_page="risk",
            profile=profile,
            snapshots=(),
            methods=REVIEWED_METHODS,
            confidence_levels=REVIEWED_CONFIDENCE_LEVELS,
            scenarios=SCENARIO_CATALOGUE,
            error=message,
            status_code=422 if isinstance(error, ValueError) else 200,
        )


@app.get("/api/risk/analyses", response_model=RiskAnalysisCollection)
def api_risk_analyses(
    profile: str = "research",
    snapshot_id: str = "",
    confidence: str = DEFAULT_CONFIDENCE_LEVEL,
    scenario: str = DEFAULT_SCENARIO_ID,
) -> RiskAnalysisCollection:
    try:
        service = risk_analysis_service(profile, snapshot_id)
        analyses = tuple(
            analysis_envelope(
                profile,
                service.analyze(method_id, confidence_level=confidence, scenario_id=scenario),
            )
            for method_id, _, _ in REVIEWED_METHODS
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return RiskAnalysisCollection(analyses=analyses)


@app.get("/api/risk/analyses/{method_id}", response_model=RiskAnalysisEnvelope)
def api_risk_analysis(
    method_id: str,
    profile: str = "research",
    snapshot_id: str = "",
    confidence: str = DEFAULT_CONFIDENCE_LEVEL,
    scenario: str = DEFAULT_SCENARIO_ID,
) -> RiskAnalysisEnvelope:
    try:
        result = risk_analysis_service(profile, snapshot_id).analyze(
            method_id, confidence_level=confidence, scenario_id=scenario
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return analysis_envelope(profile, result)


def _reviewed_action(method_id: str, confidence: str, scenario: str) -> dict[str, object]:
    result = risk_analysis_service("research").analyze(
        method_id, confidence_level=confidence, scenario_id=scenario
    )
    store("risk-analyses", result.data)
    return dumped(result)


@app.post("/actions/risk-returns-simple")
def risk_returns_simple_action() -> dict[str, object]:
    return _reviewed_action("simple_returns", DEFAULT_CONFIDENCE_LEVEL, DEFAULT_SCENARIO_ID)


@app.post("/actions/risk-returns-log")
def risk_returns_log_action() -> dict[str, object]:
    return _reviewed_action("log_returns", DEFAULT_CONFIDENCE_LEVEL, DEFAULT_SCENARIO_ID)


@app.post("/actions/risk-volatility-annualized")
def risk_volatility_annualized_action() -> dict[str, object]:
    return _reviewed_action("annualized_volatility", DEFAULT_CONFIDENCE_LEVEL, DEFAULT_SCENARIO_ID)


@app.post("/actions/risk-drawdown-maximum")
def risk_drawdown_maximum_action() -> dict[str, object]:
    return _reviewed_action("maximum_drawdown", DEFAULT_CONFIDENCE_LEVEL, DEFAULT_SCENARIO_ID)


@app.post("/actions/risk-var-historical")
def risk_var_historical_action(confidence: str = DEFAULT_CONFIDENCE_LEVEL) -> dict[str, object]:
    return _reviewed_action("historical_var", confidence, DEFAULT_SCENARIO_ID)


@app.post("/actions/risk-expected-shortfall-historical")
def risk_expected_shortfall_historical_action(confidence: str = DEFAULT_CONFIDENCE_LEVEL) -> dict[str, object]:
    return _reviewed_action("historical_expected_shortfall", confidence, DEFAULT_SCENARIO_ID)


@app.post("/actions/risk-scenario-evaluate")
def risk_scenario_evaluate_action(scenario: str = DEFAULT_SCENARIO_ID) -> dict[str, object]:
    return _reviewed_action("fixed_scenario", DEFAULT_CONFIDENCE_LEVEL, scenario)


@app.post("/actions/risk-contribution-summarize")
def risk_contribution_summarize_action() -> dict[str, object]:
    return _reviewed_action("contribution_summary", DEFAULT_CONFIDENCE_LEVEL, DEFAULT_SCENARIO_ID)


@app.get("/findings")
def findings(profile: str = "research") -> HTMLResponse:
    try:
        return render_page("findings.html", active_page="findings", profile=profile, findings=files("findings"), error=None)
    except (HTTPException, OSError, ValueError, KeyError, TypeError):
        return render_page("findings.html", active_page="findings", profile=profile, findings=(), error=_screen_error())


@app.get("/alerts")
def alerts(profile: str = "research") -> HTMLResponse:
    try:
        return render_page("alerts.html", active_page="alerts", profile=profile, alerts=files("alerts"), error=None)
    except (HTTPException, OSError, ValueError, KeyError, TypeError):
        return render_page("alerts.html", active_page="alerts", profile=profile, alerts=(), error=_screen_error())


@app.get("/alerts/{alert_id}")
def alert_page(alert_id: str, profile: str = "research") -> HTMLResponse:
    try:
        payload = api_alert(alert_id)
    except HTTPException as error:
        not_found = error.status_code == 404
        return render_page(
            "error.html",
            active_page="alerts",
            profile=profile,
            status_code=error.status_code,
            title="Alert not found" if not_found else "Alert evidence unavailable",
            message=(
                "No stored alert matches this identifier. Missing alert evidence is not represented as an empty or approved draft."
                if not_found
                else "The local alert store could not be accessed. Unavailable evidence is not represented as an absent or approved alert."
            ),
        )
    return render_page(
        "alert_detail.html",
        active_page="alerts",
        profile=profile,
        alert=payload["alert"],
        decisions=payload["decisions"],
        evidence=[dumped(item) for item in EVIDENCE],
    )


@app.post("/alerts/{alert_id}/review")
def alert_review_form(
    alert_id: str,
    reviewer: Annotated[str, Form()],
    decision: Annotated[str, Form()],
    comment: Annotated[str, Form()] = "",
    profile: str = "research",
) -> RedirectResponse:
    payload = api_alert(alert_id)
    _review(AlertDraft.model_validate(payload["alert"]), reviewer, decision, comment)
    location = f"/alerts/{quote(alert_id, safe='')}?{urlencode({'profile': profile})}"
    return RedirectResponse(location, status_code=303)


@app.get("/data")
def data(profile: str = "research") -> HTMLResponse:
    try:
        observations = [dumped(item) for item in records()]
        if not observations:
            raise ValueError("the dataset returned no observations")
        observed_times = [item["observed_at"] for item in observations]
        summary = {
            "record_count": len(observations),
            "instrument_count": len({item["instrument_id"] for item in observations}),
            "latest_observation": max(observed_times) if observed_times else None,
            "missing_count": sum(item["price"] is None for item in observations),
        }
        current_workspace = workspace()
        dataset = current_workspace.dataset_snapshot()
        return render_page(
            "data.html",
            active_page="data",
            profile=profile,
            observations=observations,
            summary=summary,
            dataset_files=[dumped(item) for item in dataset.files] if dataset is not None else (),
            manifests=[dumped(item) for item in current_workspace.query_manifests()],
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError):
        return render_page("data.html", active_page="data", profile=profile, observations=(), summary=None, dataset_files=(), manifests=(), error=_screen_error())


@app.get("/providers")
def providers(profile: str = "research") -> HTMLResponse:
    current_workspace = workspace()
    manifests = current_workspace.query_manifests()
    return render_page("providers.html", active_page="providers", profile=profile, providers=provider_views(current_workspace.providers(), manifests))


@app.get("/research")
def research(profile: str = "research") -> HTMLResponse:
    selected_profile = profile_view(profile).profile_id
    try:
        catalogue = load_research_catalogue(RESEARCH_CATALOG_PATH)
        items = [
            dumped(item)
            for item in catalogue.ordered_items()
            if selected_profile in {item_profile.value for item_profile in item.profiles}
        ]
        return render_page("research.html", active_page="research", profile=selected_profile, items=items, error=None)
    except (OSError, ValueError, KeyError, TypeError):
        return render_page("research.html", active_page="research", profile=selected_profile, items=(), error=_screen_error())


@app.get("/notebooks")
def notebooks(profile: str = "research") -> HTMLResponse:
    selected_profile = profile_view(profile).profile_id
    try:
        catalogue = load_notebook_catalogue(NOTEBOOK_CATALOG_PATH)
        items = [
            dumped(item)
            for item in catalogue.ordered_items()
            if selected_profile in {item_profile.value for item_profile in item.profiles}
        ]
        return render_page("notebooks.html", active_page="notebooks", profile=selected_profile, items=items, error=None)
    except (OSError, ValueError, KeyError, TypeError):
        return render_page("notebooks.html", active_page="notebooks", profile=selected_profile, items=(), error=_screen_error())


@app.get("/agents")
def agents(profile: str = "research") -> HTMLResponse:
    try:
        selected_profile = profile_view(profile).profile_id
        timeline = risk_analysis_service(selected_profile).timeline()
        store("agent-timelines", timeline)
        runs = files("agent-runs")
        roles = []
        for role in AGENT_ROLES:
            if role.role_id not in ACTIVE_AGENT_ROLE_IDS:
                continue
            item = dumped(role)
            summaries = []
            for run in runs:
                for output in run.get("outputs", []):
                    if output.get("capability_id") in role.allowed_capability_ids:
                        evidence_count = len(output.get("evidence_references", []))
                        summaries.append(f"{output['capability_id']} — {output.get('status', 'unknown')}; {evidence_count} evidence reference(s).")
            item["name"] = role.objective.split(":", 1)[0]
            item["evidence_summaries"] = summaries
            roles.append(item)
        return render_page("agents.html", active_page="agents", profile=selected_profile, roles=roles, timeline=dumped(timeline), error=None)
    except (HTTPException, OSError, ValueError, KeyError, TypeError):
        return render_page("agents.html", active_page="agents", profile=profile, roles=(), timeline=None, error=_screen_error())


@app.get("/api/agent-timelines", response_model=AgentTimelineCollection)
def api_agent_timelines(profile: str = "research", snapshot_id: str = "") -> AgentTimelineCollection:
    selected_profile = profile_view(profile).profile_id
    try:
        timeline = risk_analysis_service(selected_profile, snapshot_id).timeline()
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    store("agent-timelines", timeline)
    return AgentTimelineCollection(
        agent_timelines=(
            AgentTimelineEnvelope(
                profile=selected_profile,
                data_state="synthetic-reviewed" if selected_profile == "research" else "local-private",
                timeline=timeline,
            ),
        )
    )


@app.get("/agent-runs")
def agent_runs(profile: str = "research") -> HTMLResponse:
    try:
        return render_page("agent_runs.html", active_page="agents", profile=profile, runs=files("agent-runs"), timelines=files("agent-timelines"), error=None)
    except (HTTPException, OSError, ValueError, KeyError, TypeError):
        return render_page("agent_runs.html", active_page="agents", profile=profile, runs=(), timelines=(), error=_screen_error())


def _report_values(profile: str, snapshot_id: str, method_id: str, confidence: str, scenario: str):
    selected_profile = profile_view(profile).profile_id
    service = risk_analysis_service(selected_profile, snapshot_id)
    analysis, report = service.report(method_id, confidence_level=confidence, scenario_id=scenario)
    store("risk-analyses", analysis.data)
    store("reports", report.data)
    return selected_profile, analysis, report


@app.get("/reports/{method_id}.md")
def markdown_report(
    method_id: str,
    profile: str = "research",
    snapshot_id: str = "",
    confidence: str = DEFAULT_CONFIDENCE_LEVEL,
    scenario: str = DEFAULT_SCENARIO_ID,
) -> Response:
    try:
        _, _, report = _report_values(profile, snapshot_id, method_id, confidence, scenario)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    filename = f"{method_id}-review-report.md"
    return Response(
        content=report.data.markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/reports/{method_id}")
def report_page(
    method_id: str,
    profile: str = "research",
    snapshot_id: str = "",
    confidence: str = DEFAULT_CONFIDENCE_LEVEL,
    scenario: str = DEFAULT_SCENARIO_ID,
) -> HTMLResponse:
    try:
        selected_profile, analysis, report = _report_values(
            profile, snapshot_id, method_id, confidence, scenario
        )
        return render_page(
            "report.html",
            active_page="risk",
            profile=selected_profile,
            report=dumped(report.data),
            source=dumped(analysis.data),
            method_id=method_id,
            snapshot_id=analysis.data.snapshot_id,
            confidence=confidence,
            scenario=scenario,
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        return render_page(
            "report.html",
            active_page="risk",
            profile=profile,
            report=None,
            source=None,
            error=str(error),
            status_code=422,
        )


@app.get("/api/reports", response_model=ReportCollection)
def api_reports(
    profile: str = "research",
    snapshot_id: str = "",
    method: str = "simple_returns",
    confidence: str = DEFAULT_CONFIDENCE_LEVEL,
    scenario: str = DEFAULT_SCENARIO_ID,
) -> ReportCollection:
    try:
        selected_profile, _, result = _report_values(
            profile, snapshot_id, method, confidence, scenario
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return ReportCollection(
        reports=(
            ReportEnvelope(
                profile=selected_profile,
                data_state="synthetic-reviewed" if selected_profile == "research" else "local-private",
                report=result.data,
            ),
        )
    )


@app.post("/actions/risk-report-render")
def risk_report_render_action() -> dict[str, object]:
    _, _, result = _report_values(
        "research", "", "simple_returns", DEFAULT_CONFIDENCE_LEVEL, DEFAULT_SCENARIO_ID
    )
    return dumped(result)


@app.get("/plan")
def plan(profile: str = "research") -> HTMLResponse:
    try:
        day0 = load_seed_catalog(CATALOG_ROOT).sorted_by_draft_deadline()
        day1 = load_day1_seed_catalog(CATALOG_ROOT).sorted_by_draft_deadline()
        return render_page(
            "plan.html",
            active_page="plan",
            profile=profile,
            day0_items=[dumped(item) for item in day0],
            day1_items=[dumped(item) for item in day1],
            error=None,
        )
    except (OSError, ValueError, KeyError, TypeError):
        return render_page("plan.html", active_page="plan", profile=profile, day0_items=(), day1_items=(), error=_screen_error())


@app.get("/settings")
def settings(profile: str = "research") -> HTMLResponse:
    try:
        root()
        data_root_state = "Configured for local private state; the filesystem path is intentionally not published in page content."
    except HTTPException:
        data_root_state = "Not configured. Missing local data remains unavailable and is never displayed as zero."
    return render_page("settings.html", active_page="settings", profile=profile, data_root_state=data_root_state)
