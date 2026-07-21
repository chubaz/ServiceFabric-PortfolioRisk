"""Local synthetic Portfolio Risk Workbench adapter."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from risk_agents import ACTIVE_AGENT_ROLE_IDS, AGENT_ROLES
from risk_capabilities import (
    AnomalyDetectionRequest,
    DEFAULT_CAPABILITY_REGISTRY,
    EvidenceReference,
    ExposureSummaryRequest,
    PortfolioSnapshotRequest,
    PositionSpecification,
)
from risk_capabilities.registry import KnowledgeDueRequest, SyntheticIngestRequest
from risk_data import DatasetSnapshot as IngestionDatasetSnapshot, IngestionRun, NormalizedMarketRecord, QuerySpec, ValidationSummary, ingest_synthetic
from risk_data.pipeline import resolve_data_root
from risk_domain.digests import sha256_digest
from risk_domain import CashBalance, ExposureSnapshot, PortfolioSnapshot
from risk_planning import load_seed_catalog


APPLICATION_STATUS = {"application_id": "portfolio-risk-workbench", "version": "0.1.0", "synthetic_mode": True, "external_providers": "disabled", "human_review": "required"}
ROOT = Path(__file__).resolve().parents[2]
REGISTRY = DEFAULT_CAPABILITY_REGISTRY
EVIDENCE = (EvidenceReference(evidence_id="synthetic-day0-evidence", reference="fixture://day0/20260721", source_type="synthetic-fixture"),)

app = FastAPI(title="Portfolio Risk Workbench", version="0.1.0")


def data_root() -> Path:
    try:
        return resolve_data_root()
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def json_value(value: object) -> object:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def load_json(path: Path) -> dict[str, object] | None:
    return json.loads(path.read_text()) if path.is_file() else None


def latest_record(directory: Path) -> dict[str, object] | None:
    paths = sorted(directory.glob("*.json")) if directory.is_dir() else []
    return load_json(paths[-1]) if paths else None


def market_records(root: Path) -> tuple[NormalizedMarketRecord, ...]:
    path = root / "market" / "prices.parquet"
    if not path.is_file():
        raise HTTPException(status_code=409, detail="synthetic dataset is not ingested")
    return tuple(
        NormalizedMarketRecord(
            instrument_id=row["instrument_id"],
            identifier={"identifier_type": row["identifier_type"], "value": row["identifier_value"]},
            observed_at=row["observed_at"], price=Decimal(str(row["price"])), currency=row["currency"],
        )
        for row in pq.read_table(path).to_pylist()
    )


def save_immutable(root: Path, kind: str, digest: str, value: object) -> dict[str, object]:
    path = root / "workbench" / kind / f"{digest[7:]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(json_value(value), sort_keys=True, indent=2) + "\n")
    return json_value(value)


def page(section: str, payload: object) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Portfolio Risk Workbench</title></head><body><main><h1>Portfolio Risk Workbench</h1><h2>{section}</h2><p>Wave 0B is a local synthetic prototype. No live data, trading, broker connectivity, or investment advice is provided; human review is required.</p><pre>{json.dumps(json_value(payload), indent=2, sort_keys=True)}</pre></main></body></html>""")


@app.get("/")
def home() -> HTMLResponse:
    return page("Overview", APPLICATION_STATUS)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/api/status")
def api_status() -> dict[str, str | bool]:
    return APPLICATION_STATUS


@app.post("/actions/status")
def status_action() -> dict[str, str | bool]:
    return APPLICATION_STATUS


@app.get("/api/plan")
def api_plan() -> dict[str, object]:
    catalog = load_seed_catalog(ROOT)
    return {"knowledge_products": [item.model_dump(mode="json") for item in catalog.sorted_by_draft_deadline()]}


@app.post("/actions/planning-list-due")
def planning_list_due(offset_minutes: int = 0) -> dict[str, object]:
    result = REGISTRY.invoke("planning.knowledge.list_due", KnowledgeDueRequest(catalog=load_seed_catalog(ROOT), offset_minutes=offset_minutes, evidence_references=EVIDENCE))
    return json_value(result)


@app.post("/actions/data-synthetic-ingest")
def data_synthetic_ingest() -> dict[str, object]:
    try:
        result = ingest_synthetic(data_root())
    except FileExistsError as error:
        raise HTTPException(status_code=409, detail="immutable synthetic ingestion already exists") from error
    records = market_records(result.data_root)
    run = IngestionRun(
        run_id="synthetic-ingestion-20260721",
        connector_id="synthetic-local-fixture",
        query=QuerySpec(dataset="market", instrument_ids=tuple(sorted({item.instrument_id for item in records})), start_at=min(item.observed_at for item in records), end_at=max(item.observed_at for item in records)),
        started_at=result.snapshot.created_at,
        completed_at=result.snapshot.created_at,
        snapshot=IngestionDatasetSnapshot(snapshot_id=result.snapshot.snapshot_id, created_at=result.snapshot.created_at, records=records),
        validation=ValidationSummary(),
    )
    return json_value(REGISTRY.invoke("data.synthetic.ingest", SyntheticIngestRequest(ingestion_run=run, evidence_references=EVIDENCE)))


@app.get("/api/datasets")
def api_datasets() -> dict[str, object]:
    root = data_root()
    manifest = load_json(root / "manifests" / "dataset-snapshot.json")
    run = load_json(root / "manifests" / "ingestion-run.json")
    if manifest is None or run is None:
        return {"status": "missing", "quality": "not_ingested", "datasets": []}
    return {"status": "available", "snapshot": manifest, "ingestion_run": run}


@app.post("/actions/portfolio-snapshot-create")
def portfolio_snapshot_create() -> dict[str, object]:
    records = market_records(data_root())
    as_of = max(item.observed_at for item in records)
    request = PortfolioSnapshotRequest(snapshot_id="synthetic-portfolio-20260717", as_of=as_of, positions=(PositionSpecification(instrument_id="instrument-alpha", quantity=Decimal("10")), PositionSpecification(instrument_id="instrument-beta", quantity=Decimal("20"))), cash_balances=(CashBalance(currency="USD", amount=Decimal("1000")),), normalized_observations=records, evidence_references=EVIDENCE)
    result = REGISTRY.invoke("portfolio.snapshot.create", request)
    save_immutable(data_root(), "portfolio", result.data.digest, result.data)
    return json_value(result)


@app.get("/api/portfolio/latest")
def api_portfolio_latest() -> dict[str, object]:
    value = latest_record(data_root() / "workbench" / "portfolio")
    return value or {"status": "missing", "quality": "snapshot_not_created"}


@app.post("/actions/portfolio-exposure-summarize")
def portfolio_exposure_summarize() -> dict[str, object]:
    value = latest_record(data_root() / "workbench" / "portfolio")
    if value is None:
        raise HTTPException(status_code=409, detail="portfolio snapshot is not created")
    portfolio = PortfolioSnapshot.model_validate(value)
    result = REGISTRY.invoke("portfolio.exposure.summarize", ExposureSummaryRequest(snapshot_id=portfolio.snapshot_id, portfolio_snapshot=portfolio, evidence_references=EVIDENCE))
    save_immutable(data_root(), "exposures", result.data.digest, result.data)
    return json_value(result)


@app.get("/api/exposures/latest")
def api_exposures_latest() -> dict[str, object]:
    value = latest_record(data_root() / "workbench" / "exposures")
    return value or {"status": "missing", "quality": "exposure_not_calculated"}


@app.post("/actions/market-anomaly-detect")
def market_anomaly_detect() -> dict[str, object]:
    result = REGISTRY.invoke("market.anomaly.detect", AnomalyDetectionRequest(normalized_observations=market_records(data_root()), percentage_threshold=Decimal("0.10"), evidence_references=EVIDENCE))
    report = {"report": json_value(result.data), "evidence_references": [item.model_dump(mode="json") for item in result.evidence_references], "assumptions": result.assumptions, "warnings": result.warnings, "limitations": result.limitations, "human_review_required": True}
    save_immutable(data_root(), "findings", sha256_digest(report), report)
    return json_value(result)


@app.get("/api/findings")
def api_findings() -> dict[str, object]:
    value = latest_record(data_root() / "workbench" / "findings")
    return value or {"status": "missing", "quality": "findings_not_calculated", "findings": []}


@app.get("/plan")
def plan() -> HTMLResponse: return page("Plan", api_plan())
@app.get("/data")
def data() -> HTMLResponse: return page("Data", api_datasets())
@app.get("/portfolio")
def portfolio() -> HTMLResponse: return page("Portfolio", api_portfolio_latest())
@app.get("/findings")
def findings() -> HTMLResponse: return page("Findings", api_findings())
@app.get("/agents")
def agents() -> HTMLResponse:
    return page("Agents", {"active": [role.model_dump(mode="json") for role in AGENT_ROLES if role.role_id in ACTIVE_AGENT_ROLE_IDS], "queued": [role.model_dump(mode="json") for role in AGENT_ROLES if role.role_id not in ACTIVE_AGENT_ROLE_IDS]})
