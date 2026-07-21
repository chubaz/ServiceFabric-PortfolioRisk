"""Local synthetic Portfolio Risk Workbench adapter and server-rendered UI."""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Annotated
from urllib.parse import quote, urlencode

import pyarrow.parquet as pq
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from risk_agents import ACTIVE_AGENT_ROLE_IDS, AGENT_ROLES, DeterministicMonitoringOrchestrator, MonitoringRunRequest
from risk_capabilities import AlertDraft, AlertReviewRequest, AnomalyDetectionRequest, DEFAULT_CAPABILITY_REGISTRY, DecisionPoint, EvidenceReference, ExposureSummaryRequest, NewsClassificationRequest, PortfolioSnapshotRequest, PositionSpecification, SyntheticNewsEvent
from risk_data import NormalizedMarketRecord, ingest_synthetic
from risk_data.pipeline import resolve_data_root
from risk_domain import CashBalance, PortfolioSnapshot
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
        return render_page("portfolio.html", active_page="portfolio", profile=profile, snapshot=dumped(portfolio()), error=None)
    except (HTTPException, OSError, ValueError, KeyError, TypeError):
        return render_page("portfolio.html", active_page="portfolio", profile=profile, snapshot=None, error=_screen_error())


@app.get("/risk")
def risk(profile: str = "research") -> HTMLResponse:
    try:
        return render_page("risk.html", active_page="risk", profile=profile, exposure=current_exposure(), error=None)
    except (HTTPException, OSError, ValueError, KeyError, TypeError):
        return render_page("risk.html", active_page="risk", profile=profile, exposure=None, error=_screen_error())


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
        return render_page("data.html", active_page="data", profile=profile, observations=observations, summary=summary, error=None)
    except (HTTPException, OSError, ValueError, KeyError, TypeError):
        return render_page("data.html", active_page="data", profile=profile, observations=(), summary=None, error=_screen_error())


@app.get("/providers")
def providers(profile: str = "research") -> HTMLResponse:
    return render_page("providers.html", active_page="providers", profile=profile)


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
        return render_page("agents.html", active_page="agents", profile=profile, roles=roles, error=None)
    except (HTTPException, OSError, ValueError, KeyError, TypeError):
        return render_page("agents.html", active_page="agents", profile=profile, roles=(), error=_screen_error())


@app.get("/agent-runs")
def agent_runs(profile: str = "research") -> HTMLResponse:
    try:
        return render_page("agent_runs.html", active_page="agents", profile=profile, runs=files("agent-runs"), error=None)
    except (HTTPException, OSError, ValueError, KeyError, TypeError):
        return render_page("agent_runs.html", active_page="agents", profile=profile, runs=(), error=_screen_error())


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
