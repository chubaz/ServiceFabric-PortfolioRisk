"""Generate the reviewable Day 2–3 JSON Schema snapshots from contracts."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import TypeAdapter

from .research_contracts import (
    CrosswalkRecord,
    CrosswalkSnapshot,
    DataQualityFlag,
    DataQualityMetric,
    DataQualityReport,
    DatasetDefinition,
    DatasetRevision,
    EntityIdentifier,
    FieldDefinition,
    FieldMapping,
    FixedQueryManifest,
    FixedQueryRequest,
    FixedQueryResult,
    LocalImportConfirmation,
    LocalImportIssue,
    LocalImportPreview,
    LocalImportResult,
    LocalMappingManifest,
    PointInTimePolicy,
    ProviderAccessState,
    ProviderDefinition,
    PublicationRestriction,
    ResearchDatasetSnapshot,
    RightsState,
    SourceFileReference,
    TransformationRecord,
)
from .events import EventDatasetSnapshot, EventImportIssue, EventImportPreview, EventMappingManifest, EventProviderProfile, EventQueryRequest, EventQueryResult, LocalEventRecord


CONTRACTS = (
    ProviderDefinition,
    ProviderAccessState,
    RightsState,
    PublicationRestriction,
    DatasetDefinition,
    DatasetRevision,
    SourceFileReference,
    FieldDefinition,
    FieldMapping,
    TransformationRecord,
    PointInTimePolicy,
    LocalMappingManifest,
    LocalImportPreview,
    LocalImportIssue,
    LocalImportConfirmation,
    LocalImportResult,
    DataQualityReport,
    DataQualityMetric,
    DataQualityFlag,
    EntityIdentifier,
    CrosswalkRecord,
    CrosswalkSnapshot,
    FixedQueryManifest,
    FixedQueryRequest,
    FixedQueryResult,
    ResearchDatasetSnapshot,
    EventProviderProfile,
    EventMappingManifest,
    LocalEventRecord,
    EventImportPreview,
    EventImportIssue,
    EventDatasetSnapshot,
    EventQueryRequest,
    EventQueryResult,
)


def _filename(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower() + ".schema.json"


def generate(output_directory: Path | None = None) -> tuple[Path, ...]:
    root = Path(__file__).resolve().parents[4]
    destination = output_directory or root / "data" / "schemas" / "day23"
    destination.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for contract in CONTRACTS:
        path = destination / _filename(contract.__name__)
        schema = TypeAdapter(contract).json_schema()
        path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        paths.append(path)
    return tuple(paths)


if __name__ == "__main__":
    for generated_path in generate():
        print(generated_path)
