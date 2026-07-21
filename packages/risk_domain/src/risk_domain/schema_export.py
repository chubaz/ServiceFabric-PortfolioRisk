"""Deterministic JSON Schema export for the risk-domain contract snapshots."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel

from .models import CashBalance, FundamentalObservation, Instrument, InstrumentIdentifier, MarketObservation, PortfolioSnapshot, Position, SourceReference


SCHEMA_RESOURCES: dict[str, tuple[type[BaseModel], str]] = {
    "source-reference.schema.json": (SourceReference, "https://schemas.servicefabric.ai/risk/v0.1/source-reference.schema.json"),
    "instrument-identifier.schema.json": (InstrumentIdentifier, "https://schemas.servicefabric.ai/risk/v0.1/instrument-identifier.schema.json"),
    "instrument.schema.json": (Instrument, "https://schemas.servicefabric.ai/risk/v0.1/instrument.schema.json"),
    "position.schema.json": (Position, "https://schemas.servicefabric.ai/risk/v0.1/position.schema.json"),
    "cash-balance.schema.json": (CashBalance, "https://schemas.servicefabric.ai/risk/v0.1/cash-balance.schema.json"),
    "market-observation.schema.json": (MarketObservation, "https://schemas.servicefabric.ai/risk/v0.1/market-observation.schema.json"),
    "fundamental-observation.schema.json": (FundamentalObservation, "https://schemas.servicefabric.ai/risk/v0.1/fundamental-observation.schema.json"),
    "portfolio-snapshot.schema.json": (PortfolioSnapshot, "https://schemas.servicefabric.ai/risk/v0.1/portfolio-snapshot.schema.json"),
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
