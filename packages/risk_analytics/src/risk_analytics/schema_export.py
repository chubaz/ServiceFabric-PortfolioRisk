"""Deterministic reviewed JSON Schema export for analytics contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, TypeAdapter

from .contracts import AnalysisEvidence, AnalysisHorizon, AnalysisMethod, AnalysisWarning, ContributionItem, ContributionSummary, DrawdownResult, HistoricalTailRiskResult, ReturnObservation, ReturnSeriesResult, RiskReport, SamplePeriod, ScenarioResult, ScenarioShock, VolatilityResult


BASE_ID = "https://schemas.servicefabric.ai/risk/analytics/v0.1"
SCHEMA_RESOURCES: dict[str, object] = {
    "analysis-method.schema.json": AnalysisMethod,
    "analysis-evidence.schema.json": AnalysisEvidence,
    "analysis-horizon.schema.json": AnalysisHorizon,
    "analysis-warning.schema.json": AnalysisWarning,
    "contribution-item.schema.json": ContributionItem,
    "contribution-summary.schema.json": ContributionSummary,
    "drawdown-result.schema.json": DrawdownResult,
    "historical-tail-risk-result.schema.json": HistoricalTailRiskResult,
    "return-observation.schema.json": ReturnObservation,
    "return-series-result.schema.json": ReturnSeriesResult,
    "risk-report.schema.json": RiskReport,
    "sample-period.schema.json": SamplePeriod,
    "scenario-result.schema.json": ScenarioResult,
    "scenario-shock.schema.json": ScenarioShock,
    "volatility-result.schema.json": VolatilityResult,
}


def canonical_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def resource_schema(model: object, schema_id: str) -> dict[str, object]:
    schema = model.model_json_schema() if isinstance(model, type) and issubclass(model, BaseModel) else TypeAdapter(model).json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = schema_id
    return schema


def write_schema_snapshot(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, str]] = []
    for filename, model in sorted(SCHEMA_RESOURCES.items()):
        schema_id = f"{BASE_ID}/{filename}"
        content = canonical_json(resource_schema(model, schema_id))
        (output_dir / filename).write_text(content, encoding="utf-8")
        entries.append(
            {
                "schema_id": schema_id,
                "schema_path": filename,
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            }
        )
    index = canonical_json({"api_version": "risk.servicefabric.ai/analytics/v0.1", "schemas": entries})
    (output_dir / "schema-index.json").write_text(index, encoding="utf-8")
    return output_dir / "schema-index.json"
