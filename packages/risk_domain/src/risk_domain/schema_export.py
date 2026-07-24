"""Deterministic JSON Schema export for the risk-domain contract snapshots."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel

from .models import AgentRun, AlertDraft, ArtifactReference, CashBalance, ConcentrationMeasure, DatasetFile, DatasetProvenance, DatasetSnapshot, DecisionPoint, ExposureSnapshot, FundamentalObservation, Instrument, InstrumentIdentifier, MarketObservation, NewsEvent, PortfolioSnapshot, Position, PositionExposure, RiskFinding, RiskLimit, SourceReference
from .monitoring import AlertOutcomeMatch, ContextQualityIssue, ContextualMonitoringRequest, ContextualMonitoringRun, DataVintageSelection, EvaluationWarning, InstrumentDataBinding, MappingCoverage, MonitoringEvaluation, MonitoringEvidenceBundle, MonitoringFindingSet, MonitoringPolicy, MonitoringPolicyVersion, OutcomeLabel, PolicyBreach, PolicyEvaluationRequest, PolicyEvaluationResult, PortfolioDataContext, PortfolioDataContextRequest, ReplayRun, ReplaySpecification, ReplayStep


SCHEMA_RESOURCES: dict[str, tuple[type[BaseModel], str]] = {
    "agent-run.schema.json": (AgentRun, "https://schemas.servicefabric.ai/risk/v0.1/agent-run.schema.json"),
    "alert-draft.schema.json": (AlertDraft, "https://schemas.servicefabric.ai/risk/v0.1/alert-draft.schema.json"),
    "artifact-reference.schema.json": (ArtifactReference, "https://schemas.servicefabric.ai/risk/v0.1/artifact-reference.schema.json"),
    "concentration-measure.schema.json": (ConcentrationMeasure, "https://schemas.servicefabric.ai/risk/v0.1/concentration-measure.schema.json"),
    "dataset-file.schema.json": (DatasetFile, "https://schemas.servicefabric.ai/risk/v0.1/dataset-file.schema.json"),
    "dataset-provenance.schema.json": (DatasetProvenance, "https://schemas.servicefabric.ai/risk/v0.1/dataset-provenance.schema.json"),
    "dataset-snapshot.schema.json": (DatasetSnapshot, "https://schemas.servicefabric.ai/risk/v0.1/dataset-snapshot.schema.json"),
    "decision-point.schema.json": (DecisionPoint, "https://schemas.servicefabric.ai/risk/v0.1/decision-point.schema.json"),
    "exposure-snapshot.schema.json": (ExposureSnapshot, "https://schemas.servicefabric.ai/risk/v0.1/exposure-snapshot.schema.json"),
    "source-reference.schema.json": (SourceReference, "https://schemas.servicefabric.ai/risk/v0.1/source-reference.schema.json"),
    "instrument-identifier.schema.json": (InstrumentIdentifier, "https://schemas.servicefabric.ai/risk/v0.1/instrument-identifier.schema.json"),
    "instrument.schema.json": (Instrument, "https://schemas.servicefabric.ai/risk/v0.1/instrument.schema.json"),
    "position.schema.json": (Position, "https://schemas.servicefabric.ai/risk/v0.1/position.schema.json"),
    "position-exposure.schema.json": (PositionExposure, "https://schemas.servicefabric.ai/risk/v0.1/position-exposure.schema.json"),
    "cash-balance.schema.json": (CashBalance, "https://schemas.servicefabric.ai/risk/v0.1/cash-balance.schema.json"),
    "market-observation.schema.json": (MarketObservation, "https://schemas.servicefabric.ai/risk/v0.1/market-observation.schema.json"),
    "news-event.schema.json": (NewsEvent, "https://schemas.servicefabric.ai/risk/v0.1/news-event.schema.json"),
    "fundamental-observation.schema.json": (FundamentalObservation, "https://schemas.servicefabric.ai/risk/v0.1/fundamental-observation.schema.json"),
    "portfolio-snapshot.schema.json": (PortfolioSnapshot, "https://schemas.servicefabric.ai/risk/v0.1/portfolio-snapshot.schema.json"),
    "risk-finding.schema.json": (RiskFinding, "https://schemas.servicefabric.ai/risk/v0.1/risk-finding.schema.json"),
    "risk-limit.schema.json": (RiskLimit, "https://schemas.servicefabric.ai/risk/v0.1/risk-limit.schema.json"),
    "portfolio-data-context-request.schema.json": (PortfolioDataContextRequest, "https://schemas.servicefabric.ai/risk/v0.1/portfolio-data-context-request.schema.json"),
    "portfolio-data-context.schema.json": (PortfolioDataContext, "https://schemas.servicefabric.ai/risk/v0.1/portfolio-data-context.schema.json"),
    "instrument-data-binding.schema.json": (InstrumentDataBinding, "https://schemas.servicefabric.ai/risk/v0.1/instrument-data-binding.schema.json"),
    "mapping-coverage.schema.json": (MappingCoverage, "https://schemas.servicefabric.ai/risk/v0.1/mapping-coverage.schema.json"),
    "data-vintage-selection.schema.json": (DataVintageSelection, "https://schemas.servicefabric.ai/risk/v0.1/data-vintage-selection.schema.json"),
    "context-quality-issue.schema.json": (ContextQualityIssue, "https://schemas.servicefabric.ai/risk/v0.1/context-quality-issue.schema.json"),
    "monitoring-policy.schema.json": (MonitoringPolicy, "https://schemas.servicefabric.ai/risk/v0.1/monitoring-policy.schema.json"),
    "monitoring-policy-version.schema.json": (MonitoringPolicyVersion, "https://schemas.servicefabric.ai/risk/v0.1/monitoring-policy-version.schema.json"),
    "policy-evaluation-request.schema.json": (PolicyEvaluationRequest, "https://schemas.servicefabric.ai/risk/v0.1/policy-evaluation-request.schema.json"),
    "policy-evaluation-result.schema.json": (PolicyEvaluationResult, "https://schemas.servicefabric.ai/risk/v0.1/policy-evaluation-result.schema.json"),
    "policy-breach.schema.json": (PolicyBreach, "https://schemas.servicefabric.ai/risk/v0.1/policy-breach.schema.json"),
    "contextual-monitoring-request.schema.json": (ContextualMonitoringRequest, "https://schemas.servicefabric.ai/risk/v0.1/contextual-monitoring-request.schema.json"),
    "contextual-monitoring-run.schema.json": (ContextualMonitoringRun, "https://schemas.servicefabric.ai/risk/v0.1/contextual-monitoring-run.schema.json"),
    "monitoring-finding-set.schema.json": (MonitoringFindingSet, "https://schemas.servicefabric.ai/risk/v0.1/monitoring-finding-set.schema.json"),
    "monitoring-evidence-bundle.schema.json": (MonitoringEvidenceBundle, "https://schemas.servicefabric.ai/risk/v0.1/monitoring-evidence-bundle.schema.json"),
    "outcome-label.schema.json": (OutcomeLabel, "https://schemas.servicefabric.ai/risk/v0.1/outcome-label.schema.json"),
    "replay-specification.schema.json": (ReplaySpecification, "https://schemas.servicefabric.ai/risk/v0.1/replay-specification.schema.json"),
    "replay-step.schema.json": (ReplayStep, "https://schemas.servicefabric.ai/risk/v0.1/replay-step.schema.json"),
    "replay-run.schema.json": (ReplayRun, "https://schemas.servicefabric.ai/risk/v0.1/replay-run.schema.json"),
    "alert-outcome-match.schema.json": (AlertOutcomeMatch, "https://schemas.servicefabric.ai/risk/v0.1/alert-outcome-match.schema.json"),
    "monitoring-evaluation.schema.json": (MonitoringEvaluation, "https://schemas.servicefabric.ai/risk/v0.1/monitoring-evaluation.schema.json"),
    "evaluation-warning.schema.json": (EvaluationWarning, "https://schemas.servicefabric.ai/risk/v0.1/evaluation-warning.schema.json"),
}


def canonical_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def resource_schema(model: type[BaseModel], schema_id: str) -> dict[str, object]:
    schema = model.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = schema_id
    return schema


def write_schema_snapshot(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, str]] = []
    for filename, (model, schema_id) in sorted(SCHEMA_RESOURCES.items()):
        content = canonical_json(resource_schema(model, schema_id))
        (output_dir / filename).write_text(content, encoding="utf-8")
        entries.append({"schema_id": schema_id, "schema_path": filename, "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()})
    (output_dir / "schema-index.json").write_text(canonical_json({"api_version": "risk.servicefabric.ai/v0.1", "schemas": entries}), encoding="utf-8")
    return output_dir / "portfolio-snapshot.schema.json"
