"""Local synthetic Portfolio Risk Workbench adapter for reviewed Day 0 APIs."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from risk_agents import ACTIVE_AGENT_ROLE_IDS, AGENT_ROLES, DeterministicMonitoringOrchestrator, MonitoringRunRequest
from risk_capabilities import AlertDraft, AlertReviewRequest, AnomalyDetectionRequest, DEFAULT_CAPABILITY_REGISTRY, DecisionPoint, EvidenceReference, ExposureSummaryRequest, NewsClassificationRequest, PortfolioSnapshotRequest, PositionSpecification, SyntheticNewsEvent
from risk_data import NormalizedMarketRecord, ingest_synthetic
from risk_data.pipeline import resolve_data_root
from risk_domain import CashBalance, PortfolioSnapshot
from risk_domain.digests import sha256_digest
from risk_planning import load_seed_catalog


APPLICATION_STATUS = {"application_id": "portfolio-risk-workbench", "version": "0.1.0", "synthetic_mode": True, "external_providers": "disabled", "human_review": "required"}
APPLICATION_ROOT = Path(__file__).resolve().parent
# The hosted artifact contains the reviewed catalogue alongside the adapter.
# Source-tree execution keeps the repository root fallback for local use.
ROOT = APPLICATION_ROOT.parents[2]
CATALOG_ROOT = APPLICATION_ROOT if (APPLICATION_ROOT / "seed" / "knowledge-products").is_dir() else ROOT
EVIDENCE = (EvidenceReference(evidence_id="synthetic-day0-evidence", reference="fixture://day0/20260721", source_type="synthetic-fixture"),)
REGISTRY = DEFAULT_CAPABILITY_REGISTRY
app = FastAPI(title="Portfolio Risk Workbench", version="0.1.0")


def root() -> Path:
    try: return resolve_data_root()
    except ValueError as error: raise HTTPException(409, str(error)) from error


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
    digest = sha256_digest(payload)
    path = root() / "workbench" / kind / f"{digest[7:]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists(): path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    return payload


def records() -> tuple[NormalizedMarketRecord, ...]:
    path = root() / "market" / "prices.parquet"
    if not path.is_file():
        try: ingest_synthetic(root())
        except FileExistsError: pass
    return tuple(NormalizedMarketRecord(instrument_id=row["instrument_id"], identifier={"identifier_type": row["identifier_type"], "value": row["identifier_value"]}, observed_at=row["observed_at"], price=Decimal(str(row["price"])), currency=row["currency"]) for row in pq.read_table(path).to_pylist())


def portfolio() -> PortfolioSnapshot:
    saved = latest("portfolio")
    if saved: return PortfolioSnapshot.model_validate(saved)
    market = records(); as_of = max(item.observed_at for item in market)
    result = REGISTRY.invoke("portfolio.snapshot.create", PortfolioSnapshotRequest(snapshot_id="synthetic-portfolio-20260717", as_of=as_of, positions=(PositionSpecification(instrument_id="instrument-alpha", quantity=Decimal("10")), PositionSpecification(instrument_id="instrument-beta", quantity=Decimal("20"))), cash_balances=(CashBalance(currency="USD", amount=Decimal("1000")),), normalized_observations=market, evidence_references=EVIDENCE))
    store("portfolio", result.data)
    return result.data


def monitoring() -> dict[str, object]:
    snapshot = portfolio(); market = records()
    request = MonitoringRunRequest(portfolio_snapshot=snapshot, market_request=AnomalyDetectionRequest(normalized_observations=market, percentage_threshold=Decimal("0.10"), evidence_references=EVIDENCE), news_event=SyntheticNewsEvent(event_id="synthetic-news-20260717", instrument_id="instrument-alpha", headline="Synthetic issuer event", sentiment="negative", relevance="high"), evidence_references=EVIDENCE)
    run = DeterministicMonitoringOrchestrator(REGISTRY).run(request)
    payload = store("agent-runs", run)
    for output in run.outputs:
        for finding in output.findings: store("findings", finding)
    if run.alert_draft: store("alerts", run.alert_draft)
    return payload


def dashboard_cards() -> dict[str, object]:
    exposure = latest("exposures")
    if exposure is None:
        result = REGISTRY.invoke("portfolio.exposure.summarize", ExposureSummaryRequest(snapshot_id="dashboard-exposure", portfolio_snapshot=portfolio(), evidence_references=EVIDENCE))
        exposure = store("exposures", result.data)
    decisions = files("decisions")
    return {"portfolio NAV": exposure["nav"], "cash": sum(Decimal(item["amount"]) for item in exposure["portfolio_snapshot"]["cash_balances"]), "largest position weight": exposure["largest_position_weight"], "concentration limit": "0.40", "anomaly count": len([item for item in files("findings") if item["kind"] == "market_anomaly"]), "active finding count": len(files("findings")), "alert draft count": len(files("alerts")), "pending human review count": max(0, len(files("alerts")) - len(decisions))}


def page(title: str, value: object) -> HTMLResponse:
    return HTMLResponse(f"<!doctype html><html><body><h1>Portfolio Risk Workbench</h1><h2>{title}</h2><p>Wave 0C is a local synthetic prototype. No live data, broker connectivity, trading, or investment advice; explicit human review is required.</p><pre>{json.dumps(dumped(value), indent=2, default=str)}</pre></body></html>")


@app.get("/")
def home() -> HTMLResponse: return page("Dashboard cards", dashboard_cards())
@app.get("/health")
def health() -> dict[str, str]: return {"status": "healthy"}
@app.get("/api/status")
def api_status() -> dict[str, str | bool]: return APPLICATION_STATUS
@app.post("/actions/status")
def status_action() -> dict[str, str | bool]: return APPLICATION_STATUS
@app.post("/actions/portfolio-exposure-summarize")
def portfolio_exposure_summarize() -> dict[str, object]:
    result = REGISTRY.invoke("portfolio.exposure.summarize", ExposureSummaryRequest(snapshot_id="workbench-exposure", portfolio_snapshot=portfolio(), evidence_references=EVIDENCE))
    if result.data is not None: store("exposures", result.data)
    return dumped(result)
@app.post("/actions/market-anomaly-detect")
def market_anomaly_detect() -> dict[str, object]:
    result = REGISTRY.invoke("market.anomaly.detect", AnomalyDetectionRequest(normalized_observations=records(), percentage_threshold=Decimal("0.10"), evidence_references=EVIDENCE))
    for finding in result.findings: store("findings", finding)
    return dumped(result)
@app.get("/api/findings")
def api_findings() -> dict[str, object]: return {"findings": files("findings"), "synthetic": True, "human_review_required": True}
@app.get("/api/alerts")
def api_alerts() -> dict[str, object]: return {"alerts": files("alerts"), "human_review_required": True}
@app.get("/api/alerts/{alert_id}")
def api_alert(alert_id: str) -> dict[str, object]:
    alert = next((item for item in files("alerts") if item["alert_id"] == alert_id), None)
    if alert is None: raise HTTPException(404, "alert not found")
    return {"alert": alert, "decisions": [item for item in files("decisions") if item["alert_id"] == alert_id]}
@app.get("/api/agent-runs")
def api_agent_runs() -> dict[str, object]: return {"agent_runs": files("agent-runs"), "human_review_required": True}
@app.post("/actions/news-event-classify")
def news_event_classify() -> dict[str, object]:
    result = REGISTRY.invoke("news.event.classify", NewsClassificationRequest(event=SyntheticNewsEvent(event_id="synthetic-news-20260717", instrument_id="instrument-alpha", headline="Synthetic issuer event", sentiment="negative", relevance="high"), evidence_references=EVIDENCE))
    for finding in result.findings: store("findings", finding)
    return dumped(result)
@app.post("/actions/alert-draft-synthesize")
def alert_draft_synthesize() -> dict[str, object]: return monitoring()
@app.post("/actions/monitoring-run")
def monitoring_run() -> dict[str, object]: return monitoring()
@app.post("/actions/alert-draft-review")
def alert_draft_review(reviewer: str = "", decision: str = "", comment: str = "") -> dict[str, object]:
    if not reviewer.strip(): raise HTTPException(422, "reviewer is required")
    if decision not in {"approve", "reject", "request_changes"}: raise HTTPException(422, "decision must be approve, reject, or request_changes")
    alert = latest("alerts")
    if alert is None: raise HTTPException(409, "an alert draft is required before review")
    draft = AlertDraft.model_validate(alert)
    point = DecisionPoint(decision_id=f"decision:{draft.alert_id}:{decision}:{reviewer}", alert_id=draft.alert_id, decision=decision, rationale=comment or "No comment supplied.", human_reviewer_id=reviewer)
    result = REGISTRY.invoke("alert.draft.review", AlertReviewRequest(draft=draft, decision_point=point, evidence_references=EVIDENCE))
    store("decisions", point)
    return dumped(result)
@app.get("/findings")
def findings() -> HTMLResponse: return page("Findings", api_findings())
@app.get("/plan")
def plan() -> HTMLResponse: return page("Plan", {"items": [item.model_dump(mode="json") for item in load_seed_catalog(CATALOG_ROOT).knowledge_products]})
@app.get("/data")
def data() -> HTMLResponse: return page("Data", {"synthetic": True, "data_root": str(root())})
@app.get("/portfolio")
def portfolio_page() -> HTMLResponse: return page("Portfolio", dumped(portfolio()))
@app.get("/alerts")
def alerts() -> HTMLResponse: return page("Alerts", api_alerts())
@app.get("/alerts/{alert_id}")
def alert_page(alert_id: str) -> HTMLResponse: return page("Alert detail", api_alert(alert_id))
@app.get("/agents")
def agents() -> HTMLResponse: return page("Agents", {"active": [dumped(role) for role in AGENT_ROLES if role.role_id in ACTIVE_AGENT_ROLE_IDS], "queued": [dumped(role) for role in AGENT_ROLES if role.role_id not in ACTIVE_AGENT_ROLE_IDS]})
@app.get("/agent-runs")
def agent_runs() -> HTMLResponse: return page("Agent runs", api_agent_runs())
@app.get("/research")
def research() -> HTMLResponse: return page("Research catalogue", {"items": [item.model_dump(mode="json") for item in load_seed_catalog(CATALOG_ROOT).knowledge_products], "execution": "catalogue only"})
@app.get("/notebooks")
def notebooks() -> HTMLResponse: return page("Notebook catalogue", {"items": [], "execution": "notebooks are not executed"})
