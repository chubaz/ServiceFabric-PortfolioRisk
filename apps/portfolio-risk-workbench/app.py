"""Local synthetic Portfolio Risk Workbench adapter and server-rendered UI."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote, urlencode

import pyarrow.parquet as pq
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette import requests as starlette_requests
from starlette.formparsers import MultiPartException, MultiPartParser
from risk_agents import ACTIVE_AGENT_ROLE_IDS, AGENT_ROLES, DeterministicMonitoringOrchestrator, MonitoringRunRequest
from risk_capabilities import AlertDraft, AlertReviewRequest, AnomalyDetectionRequest, CapabilityResult, DEFAULT_CAPABILITY_REGISTRY, DecisionPoint, EventQueryCapabilityRequest, EvidenceReference, ExposureSummaryRequest, NewsClassificationRequest, PolicyEvaluationCapabilityRequest, PortfolioDataContextCapabilityRequest, PortfolioSnapshotRequest, PositionSpecification, SyntheticNewsEvent
from risk_data import FixedQueryRequest, LocalImportConfirmation, LocalImportError, NormalizedMarketRecord, PortfolioConfirmationRequest, PortfolioInputPreview, ingest_synthetic
from risk_data.pipeline import resolve_data_root
from risk_domain import CashBalance, MarketObservation, PortfolioSnapshot, Position
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
from data_workspace_service import (  # noqa: E402
    MAX_RESEARCH_UPLOAD_BYTES,
    ResearchDataWorkspace,
    ResearchWorkspaceRecordNotFound,
    action_envelope,
    confirmation_view as research_confirmation_view,
    preview_view as research_preview_view,
    provider_register_views,
    snapshot_view as research_snapshot_view,
)
from monitoring_service import (  # noqa: E402
    MAX_EVENT_UPLOAD_BYTES,
    ContextSelectionRequest,
    EventPreviewParameters,
    ExplicitConfirmation,
    MonitoringAdapterError,
    MonitoringCollection,
    MonitoringWorkspace,
    PolicyFields,
    ReplaySelectionRequest,
    RunSelectionRequest,
)


class HostedDataImportPreviewRequest(BaseModel):
    """Bounded JSON input for the canonical ServiceFabric capability adapter."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=MAX_RESEARCH_UPLOAD_BYTES)
    filename: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.csv$")
    provider_profile: Literal["synthetic_local", "licensed_local"]
    provider_id: str
    provider_name: str
    dataset_id: str
    dataset_kind: Literal["daily_market", "fundamentals_annual", "identifier_crosswalk"]
    dataset_description: str
    revision_id: str
    rights_state: Literal["reviewed_synthetic", "licensed_restricted"]
    publication_restriction: Literal[
        "synthetic_only",
        "internal_research_only",
        "no_publication",
    ]
    workbench_profile: Literal["research", "personal_portfolio"]
    retrieved_at: str


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


def research_workspace() -> ResearchDataWorkspace:
    return ResearchDataWorkspace(root(), REPOSITORY_ROOT)


def monitoring_workspace() -> MonitoringWorkspace:
    return MonitoringWorkspace(root(), REGISTRY)


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


def _research_upload_boundary_message(file: UploadFile) -> str | None:
    if not (file.filename or "").lower().endswith((".csv", ".parquet")):
        return "Only bounded CSV or Parquet uploads are accepted. No input was retained."
    if file.size is not None and file.size > MAX_RESEARCH_UPLOAD_BYTES:
        return f"The upload exceeds the reviewed maximum of {MAX_RESEARCH_UPLOAD_BYTES} bytes. No input was retained."
    return None


def research_uploaded_content(file: UploadFile) -> bytes:
    try:
        content = file.file.read(MAX_RESEARCH_UPLOAD_BYTES + 1)
    finally:
        file.file.close()
    if len(content) > MAX_RESEARCH_UPLOAD_BYTES:
        raise ValueError(f"The upload exceeds the reviewed maximum of {MAX_RESEARCH_UPLOAD_BYTES} bytes. No input was retained.")
    return content


def _create_research_preview(
    file: UploadFile,
    *,
    provider_profile: str,
    provider_id: str,
    provider_name: str,
    dataset_id: str,
    dataset_kind: str,
    dataset_description: str,
    revision_id: str,
    rights_state: str,
    publication_restriction: str,
    workbench_profile: str,
    retrieved_at: str,
) -> object:
    boundary_error = _research_upload_boundary_message(file)
    if boundary_error:
        raise ValueError(boundary_error)
    return research_workspace().create_preview(
        research_uploaded_content(file),
        file.filename or "",
        provider_profile=provider_profile,
        provider_id=provider_id,
        provider_name=provider_name,
        dataset_id=dataset_id,
        dataset_kind=dataset_kind,
        dataset_description=dataset_description,
        revision_id=revision_id,
        rights_state=rights_state,
        publication_restriction=publication_restriction,
        workbench_profile=workbench_profile,
        retrieved_at=retrieved_at,
    )


def _research_storage_error() -> str:
    return "The local research-data storage is unavailable. No server filesystem path is displayed."


def _research_error_message(error: Exception) -> str:
    return _research_storage_error() if isinstance(error, OSError) else str(error)


def _snapshot_has_licensed_data(snapshot: object) -> bool:
    return any(getattr(state, "value", state) == "licensed_restricted" for state in snapshot.rights_states)


def _governed_data_profile(requested_profile: str, snapshots: tuple[object, ...] = ()) -> str:
    selected = profile_view(requested_profile).profile_id
    return "personal_portfolio" if any(_snapshot_has_licensed_data(item) for item in snapshots) else selected


def _visible_research_snapshots(current: ResearchDataWorkspace, requested_profile: str) -> tuple[object, ...]:
    snapshots = current.snapshots()
    if profile_view(requested_profile).profile_id == "research":
        return tuple(item for item in snapshots if not _snapshot_has_licensed_data(item))
    return snapshots


def _structured_query_request(
    manifest_id: str,
    *,
    as_of: str = "",
    identifier_type: str = "",
    identifier: str = "",
    start_date: str = "",
    end_date: str = "",
    limit: int = 100,
) -> FixedQueryRequest:
    manifest = next((item for item in research_workspace().query_manifests() if item.manifest_id == manifest_id), None)
    if manifest is None:
        raise LocalImportError("unknown fixed query manifest ID; arbitrary SQL is prohibited")
    parameters: dict[str, str] = {}
    identifier_names = tuple(name for name in ("entity_id", "permno", "gvkey", "dataset_id") if name in manifest.parameter_names)
    if identifier:
        if identifier_type:
            if identifier_type not in identifier_names:
                raise LocalImportError("the selected identifier type is not reviewed for this fixed manifest")
            identifier_name = identifier_type
        elif len(identifier_names) == 1:
            identifier_name = identifier_names[0]
        else:
            raise LocalImportError("select one reviewed identifier type for this fixed manifest")
        parameters[identifier_name] = identifier
    if start_date and "start_at" in manifest.parameter_names:
        parameters["start_at"] = start_date
    if end_date and "end_at" in manifest.parameter_names:
        parameters["end_at"] = end_date
    request_values: dict[str, object] = {"manifest_id": manifest_id, "parameters": parameters, "limit": limit}
    if as_of:
        request_values["as_of"] = as_of
    return FixedQueryRequest.model_validate(request_values)


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
        governed_workspace = research_workspace()
        visible_snapshots = _visible_research_snapshots(governed_workspace, profile)
        return render_page(
            "data.html",
            active_page="data",
            profile=profile,
            observations=observations,
            summary=summary,
            dataset_files=[dumped(item) for item in dataset.files] if dataset is not None else (),
            manifests=[dumped(item) for item in current_workspace.query_manifests()],
            research_snapshots=[research_snapshot_view(governed_workspace, item) for item in visible_snapshots],
            research_manifests=[dumped(item) for item in governed_workspace.query_manifests()],
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError):
        return render_page("data.html", active_page="data", profile=profile, observations=(), summary=None, dataset_files=(), manifests=(), research_snapshots=(), research_manifests=(), error=_screen_error())


@app.get("/data/import")
def data_import(profile: str = "research") -> HTMLResponse:
    return render_page("data_import.html", active_page="data", profile=profile_view(profile).profile_id, maximum_upload_bytes=MAX_RESEARCH_UPLOAD_BYTES)


@app.post("/data/import")
async def data_import_preview(
    file: UploadFile = File(...),
    provider_profile: Annotated[str, Form()] = "synthetic_local",
    provider_id: Annotated[str, Form()] = "fictional-local-provider",
    provider_name: Annotated[str, Form()] = "Fictional Local Provider",
    dataset_id: Annotated[str, Form()] = "fictional-daily-market",
    dataset_kind: Annotated[str, Form()] = "daily_market",
    dataset_description: Annotated[str, Form()] = "Reviewed local research dataset",
    revision_id: Annotated[str, Form()] = "revision-1",
    rights_state: Annotated[str, Form()] = "",
    publication_restriction: Annotated[str, Form()] = "",
    retrieved_at: Annotated[str, Form()] = "",
    profile: str = "research",
) -> HTMLResponse:
    selected_profile = profile_view(profile).profile_id
    try:
        preview = _create_research_preview(file, provider_profile=provider_profile, provider_id=provider_id, provider_name=provider_name, dataset_id=dataset_id, dataset_kind=dataset_kind, dataset_description=dataset_description, revision_id=revision_id, rights_state=rights_state, publication_restriction=publication_restriction, workbench_profile=selected_profile, retrieved_at=retrieved_at)
    except (OSError, ValueError) as error:
        return render_page("data_import_preview.html", active_page="data", profile=selected_profile, preview=None, error=_research_error_message(error), status_code=422)
    view = research_preview_view(preview)
    rendered_profile = "personal_portfolio" if preview.provider.profile == "licensed_local" else selected_profile
    return render_page("data_import_preview.html", active_page="data", profile=rendered_profile, preview=view, error=None, status_code=200 if view["confirmable"] else 422)


@app.get("/data/import/previews/{preview_id}")
def data_import_preview_page(preview_id: str, profile: str = "research") -> HTMLResponse:
    try:
        preview_record = research_workspace().get_preview(preview_id)
        preview = research_preview_view(preview_record)
    except ResearchWorkspaceRecordNotFound as error:
        return render_page("data_import_preview.html", active_page="data", profile=profile, preview=None, error=str(error), status_code=404)
    rendered_profile = "personal_portfolio" if preview_record.provider.profile == "licensed_local" else profile_view(profile).profile_id
    return render_page("data_import_preview.html", active_page="data", profile=rendered_profile, preview=preview, error=None)


@app.post("/data/import/previews/{preview_id}/confirm")
def data_import_confirm(
    preview_id: str,
    preview_digest: Annotated[str, Form()] = "",
    source_digest: Annotated[str, Form()] = "",
    confirm_import: Annotated[str, Form()] = "",
    profile: str = "research",
) -> HTMLResponse:
    current = research_workspace()
    rendered_profile = profile_view(profile).profile_id
    try:
        preview_record = current.get_preview(preview_id)
        if preview_record.provider.profile == "licensed_local":
            rendered_profile = "personal_portfolio"
        result = current.confirm(preview_id, preview_digest=preview_digest, source_digest=source_digest, confirm=confirm_import == "confirmed")
    except (ResearchWorkspaceRecordNotFound, OSError, ValueError) as error:
        try:
            preview_record = current.get_preview(preview_id)
            preview = research_preview_view(preview_record)
            if preview_record.provider.profile == "licensed_local":
                rendered_profile = "personal_portfolio"
        except (ResearchWorkspaceRecordNotFound, OSError, ValueError):
            preview = None
        return render_page("data_import_preview.html", active_page="data", profile=rendered_profile, preview=preview, error=_research_error_message(error), status_code=422)
    location = f"/data/datasets/{quote(result.snapshot_id, safe='')}?{urlencode({'profile': rendered_profile, 'created': str(result.created).lower()})}"
    return RedirectResponse(location, status_code=303)


@app.get("/data/datasets")
def data_datasets(profile: str = "research") -> HTMLResponse:
    current = research_workspace()
    snapshots = [research_snapshot_view(current, item) for item in _visible_research_snapshots(current, profile)]
    return render_page("data_datasets.html", active_page="data", profile=profile_view(profile).profile_id, snapshots=snapshots, error=None)


@app.get("/data/datasets/{snapshot_id}")
def data_dataset(snapshot_id: str, profile: str = "research", created: str = "") -> HTMLResponse:
    current = research_workspace()
    try:
        snapshot_record = current.get_snapshot(snapshot_id)
        snapshot = research_snapshot_view(current, snapshot_record)
    except (ResearchWorkspaceRecordNotFound, OSError, ValueError) as error:
        return render_page("data_dataset.html", active_page="data", profile=profile, snapshot=None, error=_research_error_message(error), status_code=404)
    rendered_profile = _governed_data_profile(profile, (snapshot_record,))
    return render_page("data_dataset.html", active_page="data", profile=rendered_profile, snapshot=snapshot, created=created, error=None)


@app.get("/data/crosswalks")
def data_crosswalks(profile: str = "research") -> HTMLResponse:
    current = research_workspace()
    rendered_profile = _governed_data_profile(profile, current.snapshots())
    return render_page("data_crosswalks.html", active_page="data", profile=rendered_profile, crosswalks=[dumped(item) for item in current.crosswalks()], error=None)


@app.get("/data/query-manifests")
def data_query_manifests(profile: str = "research") -> HTMLResponse:
    return render_page("data_query_manifests.html", active_page="data", profile=profile, manifests=[dumped(item) for item in research_workspace().query_manifests()])


@app.get("/data/query/{manifest_id}")
def data_query(manifest_id: str, profile: str = "research") -> HTMLResponse:
    current = research_workspace()
    rendered_profile = _governed_data_profile(profile, current.snapshots())
    manifest = next((item for item in current.query_manifests() if item.manifest_id == manifest_id), None)
    if manifest is None:
        return render_page("data_query.html", active_page="data", profile=rendered_profile, manifest=None, result=None, error="Unknown reviewed fixed query manifest.", status_code=404)
    return render_page("data_query.html", active_page="data", profile=rendered_profile, manifest=dumped(manifest), result=None, error=None)


@app.post("/data/query/{manifest_id}")
def data_query_result(
    manifest_id: str,
    as_of: Annotated[str, Form()] = "",
    identifier_type: Annotated[str, Form()] = "",
    identifier: Annotated[str, Form()] = "",
    start_date: Annotated[str, Form()] = "",
    end_date: Annotated[str, Form()] = "",
    limit: Annotated[int, Form()] = 100,
    profile: str = "research",
) -> HTMLResponse:
    current = research_workspace()
    rendered_profile = _governed_data_profile(profile, current.snapshots())
    manifest = next((item for item in current.query_manifests() if item.manifest_id == manifest_id), None)
    try:
        request = _structured_query_request(manifest_id, as_of=as_of, identifier_type=identifier_type, identifier=identifier, start_date=start_date, end_date=end_date, limit=limit)
        result = current.run_query(request)
    except (OSError, ValueError) as error:
        return render_page("data_query.html", active_page="data", profile=rendered_profile, manifest=dumped(manifest) if manifest else None, result=None, error=_research_error_message(error), status_code=422)
    return render_page("data_query.html", active_page="data", profile=rendered_profile, manifest=dumped(manifest), result=dumped(result), error=None)


@app.post("/api/data/import/previews")
async def api_data_import_preview(
    file: UploadFile = File(...),
    provider_profile: Annotated[str, Form()] = "synthetic_local",
    provider_id: Annotated[str, Form()] = "fictional-local-provider",
    provider_name: Annotated[str, Form()] = "Fictional Local Provider",
    dataset_id: Annotated[str, Form()] = "fictional-daily-market",
    dataset_kind: Annotated[str, Form()] = "daily_market",
    dataset_description: Annotated[str, Form()] = "Reviewed local research dataset",
    revision_id: Annotated[str, Form()] = "revision-1",
    rights_state: Annotated[str, Form()] = "",
    publication_restriction: Annotated[str, Form()] = "",
    workbench_profile: Annotated[str, Form()] = "research",
    retrieved_at: Annotated[str, Form()] = "",
) -> dict[str, object]:
    try:
        preview = _create_research_preview(file, provider_profile=provider_profile, provider_id=provider_id, provider_name=provider_name, dataset_id=dataset_id, dataset_kind=dataset_kind, dataset_description=dataset_description, revision_id=revision_id, rights_state=rights_state, publication_restriction=publication_restriction, workbench_profile=workbench_profile, retrieved_at=retrieved_at)
    except (OSError, ValueError) as error:
        raise HTTPException(422, _research_error_message(error)) from error
    view = research_preview_view(preview)
    return {"preview_id": preview.preview_digest, "valid": view["confirmable"], "preview": view}


@app.get("/api/data/import/previews/{preview_id}")
def api_data_import_preview_get(preview_id: str) -> dict[str, object]:
    try:
        preview = research_workspace().get_preview(preview_id)
    except ResearchWorkspaceRecordNotFound as error:
        raise HTTPException(404, str(error)) from error
    view = research_preview_view(preview)
    return {"preview_id": preview.preview_digest, "valid": view["confirmable"], "preview": view}


@app.post("/api/data/import/previews/{preview_id}/confirm")
def api_data_import_confirm(preview_id: str, request: LocalImportConfirmation) -> dict[str, object]:
    current = research_workspace()
    try:
        result = current.confirm(preview_id, preview_digest=request.preview_digest, source_digest=request.source_digest, confirm=request.confirm)
        snapshot = research_snapshot_view(current, current.get_snapshot(result.snapshot_id))
    except ResearchWorkspaceRecordNotFound as error:
        raise HTTPException(404, str(error)) from error
    except (OSError, ValueError) as error:
        raise HTTPException(422, _research_error_message(error)) from error
    return {"confirmation": research_confirmation_view(result), "snapshot": snapshot}


@app.get("/api/data/datasets")
def api_data_datasets() -> dict[str, object]:
    current = research_workspace()
    datasets = [research_snapshot_view(current, item) for item in current.snapshots()]
    return {"datasets": datasets, "snapshots": datasets}


@app.get("/api/data/datasets/{snapshot_id}")
def api_data_dataset(snapshot_id: str) -> dict[str, object]:
    current = research_workspace()
    try:
        snapshot = current.get_snapshot(snapshot_id)
    except ResearchWorkspaceRecordNotFound as error:
        raise HTTPException(404, str(error)) from error
    return {"snapshot": research_snapshot_view(current, snapshot)}


@app.get("/api/data/crosswalks")
def api_data_crosswalks() -> dict[str, object]:
    return {"crosswalks": [dumped(item) for item in research_workspace().crosswalks()]}


@app.get("/api/data/query-manifests")
def api_data_query_manifests() -> dict[str, object]:
    return {"query_manifests": [dumped(item) for item in research_workspace().query_manifests()], "arbitrary_sql_available": False}


@app.post("/api/data/query/{manifest_id}")
def api_data_query(manifest_id: str, request: FixedQueryRequest) -> dict[str, object]:
    if request.manifest_id != manifest_id:
        raise HTTPException(422, "route manifest ID must match the typed request manifest ID")
    try:
        result = research_workspace().run_query(request)
    except (OSError, ValueError) as error:
        raise HTTPException(422, _research_error_message(error)) from error
    return {"result": dumped(result), "point_in_time_disclosure": "Eligible records satisfy available_at <= as_of; missing availability is excluded and never inferred."}


@app.get("/api/data/quality/{snapshot_id}")
def api_data_quality(snapshot_id: str) -> dict[str, object]:
    try:
        reports = research_workspace().quality(snapshot_id)
    except ResearchWorkspaceRecordNotFound as error:
        raise HTTPException(404, str(error)) from error
    return {"snapshot_id": snapshot_id, "quality_reports": [dumped(item) for item in reports]}


@app.post("/actions/data-provider-catalog")
def data_provider_catalog_action() -> dict[str, object]:
    return action_envelope("data.provider.catalog", {"providers": provider_register_views(workspace().providers())}, limitations=("Catalogue records do not enable or contact a provider.",))


@app.post("/actions/data-dataset-list")
def data_dataset_list_action() -> dict[str, object]:
    current = research_workspace()
    return action_envelope("data.dataset.list", {"snapshots": [research_snapshot_view(current, item) for item in current.snapshots()]}, limitations=("Only immutable local snapshot metadata is returned.",))


@app.post("/actions/data-query-fixed")
def data_query_fixed_action(request: FixedQueryRequest) -> dict[str, object]:
    try:
        result = research_workspace().run_query(request)
    except (OSError, ValueError) as error:
        raise HTTPException(422, _research_error_message(error)) from error
    return action_envelope("data.query.fixed", dumped(result), limitations=("Only a reviewed fixed manifest and bounded structured parameters are accepted.",))


@app.post("/actions/data-import-preview")
def data_import_preview_action(request: HostedDataImportPreviewRequest) -> dict[str, object]:
    """Preview bounded local bytes through the canonical JSON tool boundary."""
    try:
        preview = research_workspace().create_preview(
            request.content.encode("utf-8"),
            request.filename,
            provider_profile=request.provider_profile,
            provider_id=request.provider_id,
            provider_name=request.provider_name,
            dataset_id=request.dataset_id,
            dataset_kind=request.dataset_kind,
            dataset_description=request.dataset_description,
            revision_id=request.revision_id,
            rights_state=request.rights_state,
            publication_restriction=request.publication_restriction,
            workbench_profile=request.workbench_profile,
            retrieved_at=request.retrieved_at,
        )
    except (OSError, ValueError) as error:
        raise HTTPException(422, _research_error_message(error)) from error
    return action_envelope("data.import.preview", research_preview_view(preview), limitations=("A preview creates no dataset snapshot and raw bytes are not retained in the landing zone.",))


@app.get("/providers")
def providers(profile: str = "research") -> HTMLResponse:
    current_workspace = workspace()
    manifests = current_workspace.query_manifests()
    return render_page("providers.html", active_page="providers", profile=profile, providers=provider_views(current_workspace.providers(), manifests), provider_register=provider_register_views(current_workspace.providers()))


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


def _monitoring_error(template: str, active_page: str, profile: str, error: Exception) -> HTMLResponse:
    return render_page(
        template,
        active_page=active_page,
        profile=profile,
        error=str(error),
        status_code=422,
    )


def _iso_datetime(value: str, *, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise MonitoringAdapterError(
            f"{field_name} must be a timezone-aware ISO-8601 timestamp"
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MonitoringAdapterError(
            f"{field_name} must be a timezone-aware ISO-8601 timestamp"
        )
    return parsed.astimezone(UTC)


def _selected_monitoring_snapshot(profile: str, snapshot_id: str) -> PortfolioSnapshot:
    return selected_analysis_snapshot(profile, snapshot_id)


@app.get("/monitoring/context")
def monitoring_context_page(profile: str = "research") -> HTMLResponse:
    try:
        catalogue = monitoring_workspace().context_catalogue()
        return render_page(
            "monitoring_context.html",
            active_page="monitoring-context",
            profile=profile,
            snapshots=[snapshot_view(item) for item in analysis_snapshots(profile)],
            event_snapshots=monitoring_workspace().event_snapshots(),
            catalogue=catalogue,
            preview=None,
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_context.html", "monitoring-context", profile, error
        )


@app.post("/monitoring/context/preview")
def monitoring_context_preview_page(
    profile: str = Form("research"),
    portfolio_snapshot_id: str = Form(""),
    market_dataset_snapshot_id: str = Form(...),
    market_dataset_revision: str = Form(...),
    fundamental_dataset_snapshot_id: str = Form(""),
    fundamental_dataset_revision: str = Form(""),
    crosswalk_snapshot_id: str = Form(...),
    crosswalk_dataset_revision: str = Form(...),
    event_snapshot_id: str = Form(""),
    event_dataset_revision: str = Form(""),
    as_of: str = Form("2026-07-01T16:00:00Z"),
    stale_data_maximum_age_seconds: int = Form(604800),
) -> HTMLResponse:
    try:
        selection = ContextSelectionRequest(
            profile=profile,
            portfolio_snapshot_id=portfolio_snapshot_id,
            market_dataset_snapshot_id=market_dataset_snapshot_id,
            market_dataset_revision=market_dataset_revision,
            fundamental_dataset_snapshot_id=fundamental_dataset_snapshot_id or None,
            fundamental_dataset_revision=fundamental_dataset_revision or None,
            crosswalk_snapshot_id=crosswalk_snapshot_id,
            crosswalk_dataset_revision=crosswalk_dataset_revision,
            event_snapshot_id=event_snapshot_id or None,
            event_dataset_revision=event_dataset_revision or None,
            as_of=_iso_datetime(as_of, field_name="as_of"),
            stale_data_maximum_age_seconds=stale_data_maximum_age_seconds,
        )
        preview = monitoring_workspace().preview_context(
            _selected_monitoring_snapshot(profile, portfolio_snapshot_id), selection
        )
        return render_page(
            "monitoring_context.html",
            active_page="monitoring-context",
            profile=profile,
            snapshots=[snapshot_view(item) for item in analysis_snapshots(profile)],
            event_snapshots=monitoring_workspace().event_snapshots(),
            catalogue=monitoring_workspace().context_catalogue(),
            preview=preview,
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_context.html", "monitoring-context", profile, error
        )


@app.post("/monitoring/context/confirm")
def monitoring_context_confirm_page(
    preview_id: str = Form(...),
    confirm: str = Form(""),
    profile: str = Form("research"),
) -> Response:
    try:
        record = monitoring_workspace().confirm_context(
            ExplicitConfirmation(preview_id=preview_id, confirm=confirm == "true")
        )
        return RedirectResponse(
            f"/monitoring/contexts/{quote(str(record['context_id']))}?"
            + urlencode({"profile": profile}),
            status_code=303,
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_context.html", "monitoring-context", profile, error
        )


@app.get("/monitoring/contexts")
def monitoring_contexts_page(profile: str = "research") -> HTMLResponse:
    try:
        return render_page(
            "monitoring_contexts.html",
            active_page="monitoring-context",
            profile=profile,
            contexts=monitoring_workspace().contexts(),
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_contexts.html", "monitoring-context", profile, error
        )


@app.get("/monitoring/contexts/{context_id}")
def monitoring_context_detail_page(
    context_id: str, profile: str = "research"
) -> HTMLResponse:
    try:
        record = monitoring_workspace().context(context_id)
        return render_page(
            "monitoring_context_detail.html",
            active_page="monitoring-context",
            profile=str(record["profile"]),
            record=record,
            context=record["context"],
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_context_detail.html", "monitoring-context", profile, error
        )


@app.get("/monitoring/events")
def monitoring_events_page(profile: str = "research") -> HTMLResponse:
    try:
        return render_page(
            "monitoring_events.html",
            active_page="monitoring-events",
            profile=profile,
            snapshots=monitoring_workspace().event_snapshots(),
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_events.html", "monitoring-events", profile, error
        )


@app.get("/monitoring/events/import")
def monitoring_event_import_page(profile: str = "research") -> HTMLResponse:
    return render_page(
        "monitoring_event_import.html",
        active_page="monitoring-events",
        profile=profile,
        maximum_upload_bytes=MAX_EVENT_UPLOAD_BYTES,
        error=None,
    )


async def _event_preview_from_upload(
    file: UploadFile,
    *,
    provider_profile: str,
    provider_id: str,
    provider_name: str,
    dataset_revision: str,
    publication_restriction: str,
    retrieved_at: str,
) -> dict[str, object]:
    boundary_error = _research_upload_boundary_message(file)
    if boundary_error:
        raise MonitoringAdapterError(boundary_error)
    parameters = EventPreviewParameters(
        provider_profile=provider_profile,
        provider_id=provider_id,
        provider_name=provider_name,
        dataset_revision=dataset_revision,
        publication_restriction=publication_restriction,
        retrieved_at=_iso_datetime(retrieved_at, field_name="retrieved_at"),
    )
    return monitoring_workspace().preview_events(
        research_uploaded_content(file), file.filename or "", parameters
    )


@app.post("/monitoring/events/import/preview")
async def monitoring_event_preview_page(
    file: Annotated[UploadFile, File(...)],
    provider_profile: Annotated[str, Form()] = "synthetic_local",
    provider_id: Annotated[str, Form()] = "workbench-local-events",
    provider_name: Annotated[str, Form()] = "Workbench local events",
    dataset_revision: Annotated[str, Form()] = "local-event-revision-1",
    publication_restriction: Annotated[str, Form()] = "synthetic_only",
    retrieved_at: Annotated[str, Form()] = "2026-07-01T16:00:00Z",
    profile: Annotated[str, Form()] = "research",
) -> HTMLResponse:
    try:
        preview = await _event_preview_from_upload(
            file,
            provider_profile=provider_profile,
            provider_id=provider_id,
            provider_name=provider_name,
            dataset_revision=dataset_revision,
            publication_restriction=publication_restriction,
            retrieved_at=retrieved_at,
        )
        return render_page(
            "monitoring_event_preview.html",
            active_page="monitoring-events",
            profile=profile,
            preview=preview,
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_event_preview.html", "monitoring-events", profile, error
        )


@app.get("/monitoring/events/previews/{preview_id}")
def monitoring_event_preview_detail_page(
    preview_id: str, profile: str = "research"
) -> HTMLResponse:
    try:
        return render_page(
            "monitoring_event_preview.html",
            active_page="monitoring-events",
            profile=profile,
            preview=monitoring_workspace().event_preview(preview_id),
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_event_preview.html", "monitoring-events", profile, error
        )


@app.post("/monitoring/events/previews/{preview_id}/confirm")
def monitoring_event_confirm_page(
    preview_id: str,
    confirm: str = Form(""),
    preview_digest: str = Form(...),
    source_digest: str = Form(...),
    profile: str = Form("research"),
) -> Response:
    try:
        snapshot = monitoring_workspace().confirm_events(
            preview_id,
            confirm=confirm == "true",
            preview_digest=preview_digest,
            source_digest=source_digest,
        )
        return RedirectResponse(
            f"/monitoring/events/snapshots/{quote(str(snapshot['snapshot_id']))}?"
            + urlencode({"profile": profile}),
            status_code=303,
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_event_preview.html", "monitoring-events", profile, error
        )


@app.get("/monitoring/events/snapshots/{snapshot_id}")
def monitoring_event_snapshot_page(
    snapshot_id: str, profile: str = "research"
) -> HTMLResponse:
    try:
        snapshot = monitoring_workspace().event_snapshot(snapshot_id)
        selected_profile = "personal_portfolio" if snapshot["private"] else profile
        return render_page(
            "monitoring_event_snapshot.html",
            active_page="monitoring-events",
            profile=selected_profile,
            snapshot=snapshot,
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_event_snapshot.html", "monitoring-events", profile, error
        )


@app.get("/monitoring/policies")
def monitoring_policies_page(profile: str = "research") -> HTMLResponse:
    try:
        return render_page(
            "monitoring_policies.html",
            active_page="monitoring-policies",
            profile=profile,
            policies=monitoring_workspace().policies(),
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_policies.html", "monitoring-policies", profile, error
        )


@app.get("/monitoring/policies/new")
def monitoring_policy_new_page(profile: str = "research") -> HTMLResponse:
    return render_page(
        "monitoring_policy_form.html",
        active_page="monitoring-policies",
        profile=profile,
        preview=None,
        error=None,
    )


def _policy_fields(
    policy_id: str,
    daily_percentage_move_threshold: str,
    concentration_threshold: str,
    event_relevance_minimum: str,
    negative_sentiment_threshold: str,
    stale_data_maximum_age_seconds: int,
    historical_var_limit: str,
    scenario_loss_limit: str,
    cadence: str,
    cadence_metadata: str,
    reviewed_by: str,
    reviewed_at: str,
) -> PolicyFields:
    return PolicyFields(
        policy_id=policy_id,
        daily_percentage_move_threshold=daily_percentage_move_threshold,
        concentration_threshold=concentration_threshold,
        event_relevance_minimum=event_relevance_minimum,
        negative_sentiment_threshold=negative_sentiment_threshold,
        stale_data_maximum_age_seconds=stale_data_maximum_age_seconds,
        historical_var_limit=historical_var_limit or None,
        scenario_loss_limit=scenario_loss_limit or None,
        cadence=cadence,
        cadence_metadata=cadence_metadata,
        reviewed_by=reviewed_by,
        reviewed_at=_iso_datetime(reviewed_at, field_name="reviewed_at"),
    )


@app.post("/monitoring/policies/preview")
def monitoring_policy_preview_page(
    policy_id: str = Form("workbench-monitoring-policy"),
    daily_percentage_move_threshold: str = Form("0.05"),
    concentration_threshold: str = Form("0.40"),
    event_relevance_minimum: str = Form("0.60"),
    negative_sentiment_threshold: str = Form("-0.50"),
    stale_data_maximum_age_seconds: int = Form(86400),
    historical_var_limit: str = Form(""),
    scenario_loss_limit: str = Form(""),
    cadence: str = Form("manual"),
    cadence_metadata: str = Form("Metadata only; every run is explicitly invoked."),
    reviewed_by: str = Form("workbench-human-reviewer"),
    reviewed_at: str = Form("2026-07-01T16:00:00Z"),
    profile: str = Form("research"),
) -> HTMLResponse:
    try:
        preview = monitoring_workspace().preview_policy(
            _policy_fields(
                policy_id,
                daily_percentage_move_threshold,
                concentration_threshold,
                event_relevance_minimum,
                negative_sentiment_threshold,
                stale_data_maximum_age_seconds,
                historical_var_limit,
                scenario_loss_limit,
                cadence,
                cadence_metadata,
                reviewed_by,
                reviewed_at,
            )
        )
        return render_page(
            "monitoring_policy_form.html",
            active_page="monitoring-policies",
            profile=profile,
            preview=preview,
            error=None,
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_policy_form.html", "monitoring-policies", profile, error
        )


@app.post("/monitoring/policies/confirm")
def monitoring_policy_confirm_page(
    preview_id: str = Form(...),
    confirm: str = Form(""),
    profile: str = Form("research"),
) -> Response:
    try:
        policy = monitoring_workspace().confirm_policy(
            ExplicitConfirmation(preview_id=preview_id, confirm=confirm == "true")
        )
        return RedirectResponse(
            f"/monitoring/policies/{quote(str(policy['policy_id']))}?"
            + urlencode({"profile": profile}),
            status_code=303,
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_policy_form.html", "monitoring-policies", profile, error
        )


@app.get("/monitoring/policies/{policy_id}")
def monitoring_policy_detail_page(
    policy_id: str, profile: str = "research"
) -> HTMLResponse:
    try:
        record = monitoring_workspace().policy(policy_id)
        return render_page(
            "monitoring_policy_detail.html",
            active_page="monitoring-policies",
            profile=profile,
            record=record,
            policy=record["policy"],
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_policy_detail.html", "monitoring-policies", profile, error
        )


@app.get("/monitoring/runs")
def monitoring_runs_page(profile: str = "research") -> HTMLResponse:
    try:
        return render_page(
            "monitoring_runs.html",
            active_page="monitoring-runs",
            profile=profile,
            runs=monitoring_workspace().runs(),
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_runs.html", "monitoring-runs", profile, error
        )


@app.get("/monitoring/run")
def monitoring_run_page(profile: str = "research") -> HTMLResponse:
    try:
        return render_page(
            "monitoring_run_form.html",
            active_page="monitoring-runs",
            profile=profile,
            contexts=monitoring_workspace().contexts(),
            policies=monitoring_workspace().policies(),
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_run_form.html", "monitoring-runs", profile, error
        )


@app.post("/monitoring/run")
def monitoring_run_submit_page(
    context_id: str = Form(...),
    policy_id: str = Form(...),
    run_at: str = Form("2026-07-01T16:00:00Z"),
    profile: str = Form("research"),
) -> Response:
    try:
        record = monitoring_workspace().run(
            RunSelectionRequest(
                context_id=context_id,
                policy_id=policy_id,
                run_at=_iso_datetime(run_at, field_name="run_at"),
            )
        )
        return RedirectResponse(
            f"/monitoring/runs/{quote(str(record['run_id']))}?"
            + urlencode({"profile": profile}),
            status_code=303,
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_run_form.html", "monitoring-runs", profile, error
        )


@app.get("/monitoring/runs/{run_id}")
def monitoring_run_detail_page(run_id: str, profile: str = "research") -> HTMLResponse:
    try:
        record = monitoring_workspace().run_record(run_id)
        return render_page(
            "monitoring_run_detail.html",
            active_page="monitoring-runs",
            profile=str(record["profile"]),
            record=record,
            run=record["run"],
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_run_detail.html", "monitoring-runs", profile, error
        )


@app.get("/monitoring/replay")
def monitoring_replay_page(profile: str = "research") -> HTMLResponse:
    try:
        return render_page(
            "monitoring_replay.html",
            active_page="monitoring-replay",
            profile=profile,
            contexts=monitoring_workspace().contexts(),
            policies=monitoring_workspace().policies(),
            replays=monitoring_workspace().replays(),
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_replay.html", "monitoring-replay", profile, error
        )


@app.post("/monitoring/replay")
def monitoring_replay_submit_page(
    context_id: str = Form(...),
    policy_id: str = Form(...),
    start: str = Form("2026-07-01T16:00:00Z"),
    end: str = Form("2026-07-02T16:00:00Z"),
    cadence: str = Form("daily"),
    outcome_label_snapshot_id: str = Form("reviewed-synthetic-outcomes"),
    lookback_seconds: int = Form(259200),
    evaluation_horizon_seconds: int = Form(86400),
    profile: str = Form("research"),
) -> Response:
    try:
        record = monitoring_workspace().replay(
            ReplaySelectionRequest(
                context_id=context_id,
                policy_id=policy_id,
                start=_iso_datetime(start, field_name="start"),
                end=_iso_datetime(end, field_name="end"),
                cadence=cadence,
                outcome_label_snapshot_id=outcome_label_snapshot_id,
                lookback_seconds=lookback_seconds,
                evaluation_horizon_seconds=evaluation_horizon_seconds,
            )
        )
        return RedirectResponse(
            f"/monitoring/replays/{quote(str(record['replay_id']))}?"
            + urlencode({"profile": profile}),
            status_code=303,
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_replay.html", "monitoring-replay", profile, error
        )


@app.get("/monitoring/replays/{replay_id}")
def monitoring_replay_detail_page(
    replay_id: str, profile: str = "research"
) -> HTMLResponse:
    try:
        record = monitoring_workspace().replay_record(replay_id)
        return render_page(
            "monitoring_replay_detail.html",
            active_page="monitoring-replay",
            profile=str(record["profile"]),
            record=record,
            replay=record["replay"],
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_replay_detail.html", "monitoring-replay", profile, error
        )


@app.get("/monitoring/evaluations/{evaluation_id}")
def monitoring_evaluation_page(
    evaluation_id: str, profile: str = "research"
) -> HTMLResponse:
    try:
        record = monitoring_workspace().evaluation(evaluation_id)
        return render_page(
            "monitoring_evaluation.html",
            active_page="monitoring-evaluation",
            profile=profile,
            record=record,
            evaluation=record["evaluation"],
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_evaluation.html", "monitoring-evaluation", profile, error
        )


@app.get("/monitoring/reports/{source_id}.md")
def monitoring_markdown_report(source_id: str) -> Response:
    try:
        record = monitoring_workspace().report_record(source_id)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(404, str(error)) from error
    return Response(
        content=record["report"]["markdown"],
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{source_id}-local-review.md"'
        },
    )


@app.get("/monitoring/reports/{source_id}")
def monitoring_report_page(source_id: str, profile: str = "research") -> HTMLResponse:
    try:
        record = monitoring_workspace().report_record(source_id)
        return render_page(
            "monitoring_report.html",
            active_page="monitoring-runs",
            profile=str(record["profile"]),
            record=record,
            report=record["report"],
            error=None,
        )
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        return _monitoring_error(
            "monitoring_report.html", "monitoring-runs", profile, error
        )


@app.post("/api/monitoring/contexts")
def api_monitoring_context_create(
    request: ContextSelectionRequest,
) -> dict[str, object]:
    try:
        if not request.confirm:
            raise MonitoringAdapterError("explicit confirm=true is required")
        preview = monitoring_workspace().preview_context(
            _selected_monitoring_snapshot(
                request.profile, request.portfolio_snapshot_id
            ),
            request,
        )
        return monitoring_workspace().confirm_context(
            ExplicitConfirmation(preview_id=str(preview["preview_id"]), confirm=True)
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(422, str(error)) from error


@app.get("/api/monitoring/contexts", response_model=MonitoringCollection)
def api_monitoring_contexts() -> MonitoringCollection:
    return MonitoringCollection(items=monitoring_workspace().contexts())


@app.get("/api/monitoring/contexts/{context_id}")
def api_monitoring_context(context_id: str) -> dict[str, object]:
    try:
        return monitoring_workspace().context(context_id)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(404, str(error)) from error


@app.post("/api/events/previews")
async def api_event_preview(
    file: Annotated[UploadFile, File(...)],
    provider_profile: Annotated[str, Form()] = "synthetic_local",
    provider_id: Annotated[str, Form()] = "workbench-local-events",
    provider_name: Annotated[str, Form()] = "Workbench local events",
    dataset_revision: Annotated[str, Form()] = "local-event-revision-1",
    publication_restriction: Annotated[str, Form()] = "synthetic_only",
    retrieved_at: Annotated[str, Form()] = "2026-07-01T16:00:00Z",
) -> dict[str, object]:
    try:
        return await _event_preview_from_upload(
            file,
            provider_profile=provider_profile,
            provider_id=provider_id,
            provider_name=provider_name,
            dataset_revision=dataset_revision,
            publication_restriction=publication_restriction,
            retrieved_at=retrieved_at,
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(422, str(error)) from error


@app.post("/api/events/previews/{preview_id}/confirm")
def api_event_confirm(
    preview_id: str, request: LocalImportConfirmation
) -> dict[str, object]:
    try:
        return monitoring_workspace().confirm_events(
            preview_id,
            confirm=request.confirm,
            preview_digest=request.preview_digest,
            source_digest=request.source_digest,
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(422, str(error)) from error


@app.get("/api/events/snapshots", response_model=MonitoringCollection)
def api_event_snapshots() -> MonitoringCollection:
    return MonitoringCollection(items=monitoring_workspace().event_snapshots())


@app.post("/api/monitoring/policies")
def api_monitoring_policy_create(request: PolicyFields) -> dict[str, object]:
    try:
        if not request.confirm:
            raise MonitoringAdapterError("explicit confirm=true is required")
        preview = monitoring_workspace().preview_policy(request)
        return monitoring_workspace().confirm_policy(
            ExplicitConfirmation(preview_id=str(preview["preview_id"]), confirm=True)
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(422, str(error)) from error


@app.get("/api/monitoring/policies", response_model=MonitoringCollection)
def api_monitoring_policies() -> MonitoringCollection:
    return MonitoringCollection(items=monitoring_workspace().policies())


@app.post("/api/monitoring/runs")
def api_monitoring_run_create(request: RunSelectionRequest) -> dict[str, object]:
    try:
        return monitoring_workspace().run(request)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(422, str(error)) from error


@app.get("/api/monitoring/runs", response_model=MonitoringCollection)
def api_monitoring_runs() -> MonitoringCollection:
    return MonitoringCollection(items=monitoring_workspace().runs())


@app.post("/api/monitoring/replays")
def api_monitoring_replay_create(
    request: ReplaySelectionRequest,
) -> dict[str, object]:
    try:
        return monitoring_workspace().replay(request)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(422, str(error)) from error


@app.get("/api/monitoring/replays", response_model=MonitoringCollection)
def api_monitoring_replays() -> MonitoringCollection:
    return MonitoringCollection(items=monitoring_workspace().replays())


@app.get("/api/monitoring/evaluations/{evaluation_id}")
def api_monitoring_evaluation(evaluation_id: str) -> dict[str, object]:
    try:
        return monitoring_workspace().evaluation(evaluation_id)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(404, str(error)) from error


@app.get("/api/monitoring/reports/{source_id}")
def api_monitoring_report(source_id: str) -> dict[str, object]:
    try:
        return monitoring_workspace().report_record(source_id)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(404, str(error)) from error


def _hosted_monitoring_records() -> tuple[dict[str, object], dict[str, object]]:
    service = monitoring_workspace()
    contexts = service.contexts()
    if contexts:
        context_record = contexts[-1]
    else:
        snapshot, selection = _hosted_monitoring_fixture(service)
        preview = service.preview_context(
            snapshot,
            selection,
        )
        context_record = service.confirm_context(
            ExplicitConfirmation(preview_id=str(preview["preview_id"]), confirm=True)
        )
    policies = service.policies()
    if policies:
        policy_record = policies[-1]
    else:
        preview = service.preview_policy(PolicyFields(confirm=True))
        policy_record = service.confirm_policy(
            ExplicitConfirmation(preview_id=str(preview["preview_id"]), confirm=True)
        )
    return context_record, policy_record


def _hosted_monitoring_fixture(
    service: MonitoringWorkspace,
) -> tuple[PortfolioSnapshot, ContextSelectionRequest]:
    research = research_workspace()
    imports = (
            (
                "crsp_like_daily.csv",
                "hosted-synthetic-market",
                "daily_market",
                "Hosted reviewed synthetic daily market observations.",
                "hosted-market-revision-1",
            ),
            (
                "compustat_like_annual.csv",
                "hosted-synthetic-fundamentals",
                "fundamentals_annual",
                "Hosted reviewed synthetic annual fundamentals.",
                "hosted-fundamental-revision-1",
            ),
            (
                "crsp_compustat_link.csv",
                "hosted-synthetic-crosswalk",
                "identifier_crosswalk",
                "Hosted reviewed synthetic identifier crosswalk.",
                "hosted-crosswalk-revision-1",
            ),
    )
    snapshots = research.snapshots()
    superseded = {
        item.supersedes_snapshot_id
        for item in snapshots
        if item.supersedes_snapshot_id is not None
    }
    current = next(
        (item for item in snapshots if item.snapshot_id not in superseded),
        None,
    )
    active_revisions = (
        {
            (item.dataset_id, item.revision_id)
            for item in current.dataset_revisions
        }
        if current is not None
        else set()
    )
    fixture_root = (
        REPOSITORY_ROOT / "data" / "fixtures" / "synthetic" / "day23"
    )
    for filename, dataset_id, kind, description, revision_id in imports:
        if (dataset_id, revision_id) in active_revisions:
            continue
        preview = research.create_preview(
            (fixture_root / filename).read_bytes(),
            filename,
            provider_profile="synthetic_local",
            provider_id="hosted-reviewed-synthetic",
            provider_name="Hosted reviewed synthetic fixtures",
            dataset_id=dataset_id,
            dataset_kind=kind,
            dataset_description=description,
            revision_id=revision_id,
            rights_state="reviewed_synthetic",
            publication_restriction="synthetic_only",
            retrieved_at="2026-07-01T00:00:00Z",
        )
        research.confirm(
            preview.preview_digest,
            preview_digest=preview.preview_digest,
            source_digest=preview.source.source_digest,
            confirm=True,
        )
    catalogue = service.context_catalogue()
    market = next(
        item
        for item in catalogue["market"]
        if item["dataset_id"] == "hosted-synthetic-market"
        and item["revision_id"] == "hosted-market-revision-1"
    )
    selected_research_snapshot = service.research.get_snapshot(
        market["snapshot_id"]
    )
    selected_crosswalk_revision = next(
        item
        for item in selected_research_snapshot.dataset_revisions
        if item.dataset_id == "hosted-synthetic-crosswalk"
        and item.revision_id == "hosted-crosswalk-revision-1"
    )
    crosswalk_option = next(
        item
        for item in catalogue["crosswalk"]
        if item["research_snapshot_id"] == market["snapshot_id"]
        and item["revision_id"] == selected_crosswalk_revision.source_digest
    )
    crosswalk = next(
        item
        for item in service.research.crosswalks()
        if item.snapshot_id == crosswalk_option["snapshot_id"]
    )
    context_as_of = datetime(2026, 7, 1, 16, tzinfo=UTC)
    result = service.research.run_query(
        FixedQueryRequest(
            manifest_id="daily-market-history",
            as_of=context_as_of,
            limit=1_000,
        )
    )
    prices: dict[str, Decimal] = {}
    for row in result.rows:
        if (
            row.get("dataset_id") == market["dataset_id"]
            and row.get("dataset_revision") == market["revision_id"]
            and row.get("valuation_price") is not None
        ):
            prices[str(row["entity_id"])] = Decimal(str(row["valuation_price"]))
    instrument_ids = sorted(
        {
            item.target_identifier.entity_id
            for item in crosswalk.records
            if item.target_identifier.entity_id in prices
        }
    )
    positions = tuple(
        Position(
            instrument_id=instrument_id,
            quantity=Decimal("1"),
            price=prices[instrument_id],
            market_value=prices[instrument_id],
            currency="USD",
        )
        for instrument_id in instrument_ids
    )
    snapshot = PortfolioSnapshot(
        snapshot_id="hosted-reviewed-monitoring-portfolio",
        as_of=datetime(2026, 6, 30, 21, tzinfo=UTC),
        base_currency="USD",
        positions=positions,
    )
    fundamental = next(
        (
            item
            for item in catalogue["fundamental"]
            if item["snapshot_id"] == market["snapshot_id"]
            and item["dataset_id"] == "hosted-synthetic-fundamentals"
            and item["revision_id"] == "hosted-fundamental-revision-1"
        ),
        None,
    )
    return snapshot, ContextSelectionRequest(
        portfolio_snapshot_id=snapshot.snapshot_id,
        market_dataset_snapshot_id=market["snapshot_id"],
        market_dataset_revision=market["revision_id"],
        fundamental_dataset_snapshot_id=(
            fundamental["snapshot_id"] if fundamental else None
        ),
        fundamental_dataset_revision=(
            fundamental["revision_id"] if fundamental else None
        ),
        crosswalk_snapshot_id=crosswalk_option["snapshot_id"],
        crosswalk_dataset_revision=crosswalk_option["revision_id"],
        as_of=context_as_of,
        confirm=True,
    )


@app.post("/actions/portfolio-data-context-create")
def portfolio_data_context_create_action() -> dict[str, object]:
    context_record, _ = _hosted_monitoring_records()
    from risk_domain.monitoring import PortfolioDataContextRequest

    result = REGISTRY.invoke(
        "portfolio.data_context.create",
        PortfolioDataContextCapabilityRequest(
            request=PortfolioDataContextRequest.model_validate(
                context_record["request"]
            ),
            evidence_references=monitoring_workspace().capability_evidence(
                str(context_record["profile"])
            ),
        ),
    )
    return dumped(result)


@app.post("/actions/events-query-as-of")
def events_query_as_of_action() -> dict[str, object]:
    result = REGISTRY.invoke(
        "events.query.as_of",
        EventQueryCapabilityRequest(
            as_of=datetime(2026, 7, 1, 16, tzinfo=UTC),
            evidence_references=monitoring_workspace().capability_evidence(),
        ),
    )
    return dumped(result)


@app.post("/actions/monitoring-policy-evaluate")
def monitoring_policy_evaluate_action() -> dict[str, object]:
    context_record, policy_record = _hosted_monitoring_records()
    service = monitoring_workspace()
    context = service.context(str(context_record["context_id"]))["context"]
    from risk_domain.monitoring import (
        MonitoringPolicyVersion,
        PolicyEvaluationRequest,
        PortfolioDataContext,
    )

    result = REGISTRY.invoke(
        "monitoring.policy.evaluate",
        PolicyEvaluationCapabilityRequest(
            request=PolicyEvaluationRequest(
                evaluation_id="hosted-policy-evaluation",
                policy_version=MonitoringPolicyVersion.model_validate(
                    policy_record["policy"]
                ),
                context=PortfolioDataContext.model_validate(context),
                evaluated_at=datetime(2026, 7, 1, 16, tzinfo=UTC),
                evidence=monitoring_workspace().evidence(),
            ),
            evidence_references=monitoring_workspace().capability_evidence(),
        ),
    )
    return dumped(result)


@app.post("/actions/monitoring-run-contextual")
def monitoring_run_contextual_action() -> dict[str, object]:
    context_record, policy_record = _hosted_monitoring_records()
    record = monitoring_workspace().run(
        RunSelectionRequest(
            context_id=str(context_record["context_id"]),
            policy_id=str(policy_record["policy_id"]),
        )
    )
    return {
        "capability_id": "monitoring.run.contextual",
        "status": record["run"]["status"],
        "data": record["run"],
        "effects": [],
        "human_review_required": True,
    }


def _hosted_replay_record() -> dict[str, object]:
    context_record, policy_record = _hosted_monitoring_records()
    return monitoring_workspace().replay(
        ReplaySelectionRequest(
            context_id=str(context_record["context_id"]),
            policy_id=str(policy_record["policy_id"]),
            start=datetime(2026, 7, 1, 16, tzinfo=UTC),
            end=datetime(2026, 7, 2, 16, tzinfo=UTC),
        )
    )


@app.post("/actions/monitoring-replay")
def monitoring_replay_action() -> dict[str, object]:
    record = _hosted_replay_record()
    return {
        "capability_id": "monitoring.replay",
        "status": "succeeded",
        "data": record["replay"],
        "effects": [],
        "human_review_required": True,
    }


@app.post("/actions/monitoring-evaluate")
def monitoring_evaluate_action() -> dict[str, object]:
    replay_record = _hosted_replay_record()
    evaluation = monitoring_workspace().evaluation(
        str(replay_record["evaluation_id"])
    )
    return {
        "capability_id": "monitoring.evaluate",
        "status": "succeeded",
        "data": evaluation["evaluation"],
        "effects": [],
        "human_review_required": True,
    }


@app.post("/actions/monitoring-report-render")
def monitoring_report_render_action() -> dict[str, object]:
    context_record, policy_record = _hosted_monitoring_records()
    run_record = monitoring_workspace().run(
        RunSelectionRequest(
            context_id=str(context_record["context_id"]),
            policy_id=str(policy_record["policy_id"]),
        )
    )
    report = monitoring_workspace().report(str(run_record["run_id"]))
    return {
        "capability_id": "monitoring.report.render",
        "status": "succeeded",
        "data": report["report"],
        "effects": [],
        "human_review_required": True,
    }
