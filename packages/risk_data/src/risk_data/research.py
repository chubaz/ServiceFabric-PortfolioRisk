"""Local-only governed CSV/Parquet research import and fixed-query service."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from .pipeline import REPOSITORY_ROOT, resolve_data_root
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
    FixedQueryManifest,
    FixedQueryRequest,
    FixedQueryResult,
    LocalImportConfirmation,
    LocalImportIssue,
    LocalImportPreview,
    LocalImportResult,
    LocalMappingManifest,
    ProviderAccessState,
    ProviderDefinition,
    PublicationRestriction,
    ResearchDatasetSnapshot,
    RightsState,
    SourceFileReference,
)
from .serialization import manifest_json


SYNTHETIC_FIXTURE_ROOT = REPOSITORY_ROOT / "data" / "fixtures" / "synthetic"
ZONE_NAMES = ("landing", "normalized", "curated", "manifests", "quality", "evidence")
GENERIC_MISSING_VALUES = {"", "na", "n/a", "null", "none"}
NUMERIC_PROVIDER_MISSING_VALUES = {".", "b", "c"}
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class LocalImportError(ValueError):
    """A governed preview or confirmation failed without creating a snapshot."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _sha256_value(value: Any) -> str:
    return f"sha256:{hashlib.sha256(manifest_json(value).encode('utf-8')).hexdigest()}"


def _iso_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def _read_source(path: Path) -> tuple[list[dict[str, Any]], tuple[FieldDefinition, ...]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames is None:
                raise LocalImportError("CSV source requires a header row")
            rows = [dict(row) for row in reader]
            schema = tuple(FieldDefinition(field_name=name, data_type="string") for name in reader.fieldnames)
            return rows, schema
    if path.suffix.lower() == ".parquet":
        table = pq.read_table(path)
        rows = [{key: _jsonable(value) for key, value in row.items()} for row in table.to_pylist()]
        types: dict[str, str] = {}
        for field in table.schema:
            if pa.types.is_integer(field.type):
                kind = "integer"
            elif pa.types.is_floating(field.type) or pa.types.is_decimal(field.type):
                kind = "decimal"
            elif pa.types.is_date(field.type):
                kind = "date"
            elif pa.types.is_timestamp(field.type):
                kind = "datetime"
            elif pa.types.is_boolean(field.type):
                kind = "boolean"
            else:
                kind = "string"
            types[field.name] = kind
        schema = tuple(FieldDefinition(field_name=name, data_type=types[name]) for name in table.column_names)
        return rows, schema
    raise LocalImportError("Phase 1 accepts CSV and Parquet sources only")


def load_mapping_manifest(path: Path | str) -> LocalMappingManifest:
    manifest_path = Path(path)
    if not manifest_path.is_file() or manifest_path.suffix.lower() != ".json":
        raise LocalImportError("mapping manifest must be an existing JSON file")
    try:
        return LocalMappingManifest.model_validate(json.loads(manifest_path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValueError) as exc:
        raise LocalImportError(f"invalid mapping manifest: {exc}") from exc


def fixed_query_manifests() -> tuple[FixedQueryManifest, ...]:
    return (
        FixedQueryManifest(manifest_id="security-master", view_name="security_master", columns=("entity_id", "permno", "gvkey", "cusip", "ticker", "cik", "provider_id", "dataset_id", "snapshot_id"), parameter_names=("entity_id", "permno", "gvkey"), point_in_time=False),
        FixedQueryManifest(manifest_id="daily-market-history", view_name="daily_market", columns=("entity_id", "permno", "observed_at", "available_at", "raw_price", "valuation_price", "return", "shares_outstanding", "volume", "cusip", "ticker", "provider_id", "dataset_id", "dataset_revision", "quality_flags", "snapshot_id"), parameter_names=("permno", "start_at", "end_at"), point_in_time=True),
        FixedQueryManifest(manifest_id="fundamentals-as-of", view_name="fundamentals_annual", columns=("entity_id", "gvkey", "observed_at", "available_at", "fyear", "assets", "liabilities", "sales", "net_income", "common_equity", "shares_outstanding", "fiscal_price", "currency", "cik", "cusip", "provider_id", "dataset_id", "dataset_revision", "quality_flags", "snapshot_id"), parameter_names=("gvkey",), point_in_time=True),
        FixedQueryManifest(manifest_id="linked-market-fundamentals-as-of", view_name="linked_market_fundamentals", columns=("entity_id", "permno", "gvkey", "market_observed_at", "market_available_at", "valuation_price", "fundamental_observed_at", "fundamental_available_at", "assets", "sales", "link_effective_from", "link_effective_to", "link_available_at", "snapshot_id"), parameter_names=("permno", "gvkey"), point_in_time=True),
        FixedQueryManifest(manifest_id="data-quality-summary", view_name="data_quality_summary", columns=("report_id", "dataset_id", "metric", "value", "unit", "blocking", "snapshot_id"), parameter_names=("dataset_id",), point_in_time=False),
    )


FIXED_MANIFESTS = {item.manifest_id: item for item in fixed_query_manifests()}


def _convert(value: Any, data_type: str) -> Any:
    if value is None:
        return None
    text = str(value).strip()
    lowered = text.lower()
    if lowered in GENERIC_MISSING_VALUES:
        return None
    if data_type in {"integer", "decimal"} and lowered in NUMERIC_PROVIDER_MISSING_VALUES:
        return None
    if data_type == "string":
        return text
    if data_type == "integer":
        return int(Decimal(text))
    if data_type == "decimal":
        return Decimal(text)
    if data_type == "boolean":
        if text.lower() not in {"true", "false", "1", "0"}:
            raise ValueError("invalid boolean")
        return text.lower() in {"true", "1"}
    if data_type == "date":
        return date.fromisoformat(text[:10])
    if data_type == "datetime":
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("datetime values must include a timezone offset")
        return parsed.astimezone(UTC)
    raise ValueError(f"unsupported mapping data type {data_type}")


def _normalize_rows(rows: list[dict[str, Any]], manifest: LocalMappingManifest) -> tuple[list[dict[str, Any]], list[LocalImportIssue]]:
    transformations = {item.transformation_id: item for item in manifest.transformations}
    normalized: list[dict[str, Any]] = []
    issues: list[LocalImportIssue] = []
    for row_number, source_row in enumerate(rows, start=2):
        target: dict[str, Any] = {}
        row_rejected = False
        row_flags: list[str] = []
        for mapping in manifest.fields:
            raw = source_row.get(mapping.source_field)
            try:
                value = _convert(raw, mapping.data_type)
                for transformation_id in mapping.transformation_ids:
                    transformation = transformations[transformation_id]
                    if value is not None and transformation.operation in {"absolute_value", "sign_normalization"}:
                        value = abs(value)
                    elif value is not None and transformation.operation == "scale":
                        value *= Decimal(transformation.parameters["factor"])
                    elif transformation.operation == "open_end_date" and value is None:
                        value = None
                target[mapping.target_field] = value
                if value is None and not mapping.nullable:
                    issues.append(LocalImportIssue(code="missing_required_field", severity="blocking", message="non-nullable mapped field is missing", row_number=row_number, field=mapping.source_field))
                    row_flags.append("missing_required_field")
                    row_rejected = True
                if mapping.target_field == "return" and value is None:
                    issues.append(LocalImportIssue(code="missing_return", severity="warning", message="missing or special return remains nullable", row_number=row_number, field=mapping.source_field))
                    row_flags.append("missing_return")
            except (ValueError, TypeError, InvalidOperation, ArithmeticError):
                severity = "blocking" if mapping.data_type in {"date", "datetime"} or not mapping.nullable else "warning"
                code = "invalid_date" if mapping.data_type in {"date", "datetime"} else "invalid_value"
                issues.append(LocalImportIssue(code=code, severity=severity, message=f"invalid {mapping.data_type} value", row_number=row_number, field=mapping.source_field))
                target[mapping.target_field] = None
                row_flags.append(code)
                row_rejected |= severity == "blocking"
        identifier_fields = ("permno",) if manifest.dataset_kind == "daily_market" else (("gvkey",) if manifest.dataset_kind == "fundamentals_annual" else (("gvkey", "permno") if manifest.dataset_kind == "identifier_crosswalk" else ("entity_id",)))
        for field in identifier_fields:
            if not target.get(field):
                issues.append(LocalImportIssue(code="missing_identifier", severity="blocking", message=f"required identifier {field} is missing", row_number=row_number, field=field))
                row_rejected = True
                row_flags.append("missing_identifier")
        available_field = manifest.point_in_time_policy.available_at_field
        if available_field and target.get(available_field) is None:
            severity = "blocking" if manifest.point_in_time_policy.missing_available_at == "block" else "warning"
            issues.append(LocalImportIssue(code="missing_available_at", severity=severity, message="availability is missing and was not inferred", row_number=row_number, field=available_field))
            row_rejected |= severity == "blocking"
            row_flags.append("missing_available_at")
        target["_source_values"] = {key: _jsonable(value) for key, value in source_row.items()}
        target["_quality_flags"] = sorted(set(row_flags))
        target["_row_number"] = row_number
        target["_rejected"] = row_rejected
        normalized.append(target)

    seen: dict[tuple[Any, ...], int] = {}
    for row in normalized:
        if row["_rejected"]:
            continue
        key = tuple(row.get(field) for field in manifest.key_fields)
        if key in seen:
            issues.append(LocalImportIssue(code="duplicate_key", severity="blocking", message=f"duplicate mapped key {key!r}", row_number=row["_row_number"]))
            row["_rejected"] = True
            row["_quality_flags"].append("duplicate_key")
        else:
            seen[key] = row["_row_number"]

    if manifest.dataset_kind == "identifier_crosswalk":
        candidates = [row for row in normalized if not row["_rejected"]]
        candidates.sort(key=lambda row: (str(row.get("gvkey")), row.get("effective_from") or date.min))
        for index, left in enumerate(candidates):
            for right in candidates[index + 1 :]:
                if left.get("gvkey") != right.get("gvkey"):
                    break
                left_end = left.get("effective_to") or date.max
                right_end = right.get("effective_to") or date.max
                if left.get("effective_from") <= right_end and right.get("effective_from") <= left_end:
                    if manifest.link_overlap_policy == "reject":
                        issues.append(LocalImportIssue(code="overlapping_link", severity="blocking", message="overlapping active identifier links require an explicit deterministic policy", row_number=right["_row_number"]))
                        right["_rejected"] = True
                    else:
                        issues.append(LocalImportIssue(code="overlapping_link_resolved", severity="warning", message="overlap resolved deterministically using latest effective_from", row_number=right["_row_number"]))
                        left["_rejected"] = True
                        left["_quality_flags"].append("overlapping_link_resolved")
    return normalized, issues


class ResearchDataPlane:
    """Governed external-storage data plane; it has no provider/network client."""

    def __init__(self, data_root: Path | str | None = None) -> None:
        self.data_root = resolve_data_root(data_root)

    def _validate_source_path(self, source_path: Path | str, profile: str) -> Path:
        supplied = Path(source_path)
        if not supplied.is_absolute():
            raise LocalImportError("source path must be absolute")
        path = supplied.resolve(strict=True)
        in_repository = path == REPOSITORY_ROOT or REPOSITORY_ROOT in path.parents
        reviewed_fixture = profile == "synthetic_local" and (path == SYNTHETIC_FIXTURE_ROOT or SYNTHETIC_FIXTURE_ROOT in path.parents)
        if in_repository and not reviewed_fixture:
            raise LocalImportError("source path must be outside the repository")
        if path.suffix.lower() not in {".csv", ".parquet"}:
            raise LocalImportError("Phase 1 accepts CSV and Parquet sources only")
        return path

    def preview_local_export(
        self,
        source_path: Path | str,
        *,
        provider: ProviderDefinition,
        dataset: DatasetDefinition,
        revision_id: str,
        rights_state: RightsState,
        publication_restriction: PublicationRestriction,
        mapping_manifest: LocalMappingManifest | Path | str,
        retrieved_at: datetime,
        retain_raw_source: bool = False,
    ) -> LocalImportPreview:
        provider = ProviderDefinition.model_validate(provider.model_dump(mode="python"))
        dataset = DatasetDefinition.model_validate(dataset.model_dump(mode="python"))
        if provider.access_state is not ProviderAccessState.AVAILABLE or provider.network_enabled:
            raise LocalImportError("provider access must be local and available; network access is disabled")
        if dataset.provider_id != provider.provider_id:
            raise LocalImportError("dataset provider does not match the explicit provider")
        expected_rights = RightsState.REVIEWED_SYNTHETIC if provider.profile == "synthetic_local" else RightsState.LICENSED_RESTRICTED
        if rights_state is not expected_rights:
            raise LocalImportError("an explicit rights state matching the local profile is required")
        if provider.profile == "synthetic_local" and publication_restriction is not PublicationRestriction.SYNTHETIC_ONLY:
            raise LocalImportError("synthetic_local requires the synthetic_only publication restriction")
        if provider.profile == "licensed_local" and publication_restriction is PublicationRestriction.SYNTHETIC_ONLY:
            raise LocalImportError("licensed_local requires a restrictive non-synthetic publication restriction")
        mapping = load_mapping_manifest(mapping_manifest) if isinstance(mapping_manifest, (Path, str)) else LocalMappingManifest.model_validate(mapping_manifest.model_dump(mode="python"))
        if mapping.dataset_kind != dataset.dataset_kind or mapping.target_dataset != dataset.dataset_kind:
            raise LocalImportError("mapping manifest dataset kind does not match the dataset definition")
        source = self._validate_source_path(source_path, provider.profile)
        source_digest = _sha256_file(source)
        file_format = "csv" if source.suffix.lower() == ".csv" else "parquet"
        rows, source_schema = _read_source(source)
        source_fields = {field.field_name for field in source_schema}
        missing_fields = sorted({item.source_field for item in mapping.fields} - source_fields)
        issues: list[LocalImportIssue] = [LocalImportIssue(code="missing_source_field", severity="blocking", message=f"mapped source field {field} is absent", field=field) for field in missing_fields]
        normalized, row_issues = _normalize_rows(rows, mapping) if not missing_fields else ([], [])
        issues.extend(row_issues)
        rejected = sum(bool(row["_rejected"]) for row in normalized)
        counts = {code: sum(issue.code == code for issue in issues) for code in ("missing_identifier", "missing_required_field", "duplicate_key", "invalid_date", "missing_available_at", "missing_return", "overlapping_link", "overlapping_link_resolved")}
        declared_units = sorted({f"{item.target_field}:{item.source_unit}->{item.target_unit}" for item in mapping.fields if item.source_unit or item.target_unit})
        revision = DatasetRevision(dataset_id=dataset.dataset_id, revision_id=revision_id, retrieved_at=retrieved_at, source_digest=source_digest)
        mapping_digest = _sha256_value(mapping)
        quality_identity = _sha256_value({"dataset_id": dataset.dataset_id, "revision": revision, "source_digest": source_digest, "mapping_digest": mapping_digest})
        quality_id = f"quality-{quality_identity.removeprefix('sha256:')[:32]}"
        metrics = (
            DataQualityMetric(metric="source_rows", value=len(rows)),
            DataQualityMetric(metric="accepted_rows", value=len(rows) - rejected if not missing_fields else 0),
            DataQualityMetric(metric="rejected_rows", value=rejected if not missing_fields else len(rows)),
            *(DataQualityMetric(metric=key, value=value) for key, value in counts.items()),
            DataQualityMetric(metric="declared_units", value=",".join(declared_units) or "none", unit="declaration"),
        )
        quality = DataQualityReport(report_id=quality_id, dataset_id=dataset.dataset_id, source_digest=source_digest, metrics=metrics, flags=tuple(DataQualityFlag(code=issue.code, severity=issue.severity, record_key=str(issue.row_number) if issue.row_number else None, message=issue.message) for issue in issues), blocking=any(issue.severity == "blocking" for issue in issues))
        source_reference = SourceFileReference(absolute_path=source, file_format=file_format, source_digest=source_digest, byte_count=source.stat().st_size, retained=False)
        payload = {"source": source_reference, "provider": provider, "dataset": dataset, "revision": revision, "rights_state": rights_state, "publication_restriction": publication_restriction, "mapping_manifest": mapping, "mapping_digest": mapping_digest, "source_schema": source_schema, "row_count": len(rows), "accepted_row_count": len(rows) - rejected if not missing_fields else 0, "rejected_row_count": rejected if not missing_fields else len(rows), "issues": tuple(issues), "quality_report": quality, "retain_raw_source": retain_raw_source}
        return LocalImportPreview(preview_digest=_sha256_value(payload), **payload)

    def confirm_local_export(self, preview: LocalImportPreview, confirmation: LocalImportConfirmation) -> LocalImportResult:
        if not confirmation.confirm:
            raise LocalImportError("explicit confirm=true is required")
        if confirmation.preview_digest != preview.preview_digest:
            raise LocalImportError("confirmation preview digest does not match")
        current_digest = _sha256_file(preview.source.absolute_path)
        if confirmation.source_digest != preview.source.source_digest or current_digest != preview.source.source_digest:
            raise LocalImportError("source digest does not match the preview")
        if preview.has_blocking_issues or preview.quality_report.blocking:
            raise LocalImportError("preview contains unresolved blocking issues")
        if preview.provider.profile == "synthetic_local" and preview.rights_state is not RightsState.REVIEWED_SYNTHETIC:
            raise LocalImportError("valid synthetic rights state is required")
        if preview.provider.profile == "licensed_local" and preview.rights_state is not RightsState.LICENSED_RESTRICTED:
            raise LocalImportError("valid licensed rights state is required")

        import_id = _sha256_value({"preview_digest": preview.preview_digest, "revision": preview.revision, "publication_restriction": preview.publication_restriction})
        receipt_path = self._data_path("manifests", "imports", f"{import_id.removeprefix('sha256:')}.json")
        if receipt_path.is_file():
            return LocalImportResult.model_validate(json.loads(receipt_path.read_text(encoding="utf-8"))).model_copy(update={"created": False})

        rows, _ = _read_source(preview.source.absolute_path)
        normalized, issues = _normalize_rows(rows, preview.mapping_manifest)
        if any(issue.severity == "blocking" for issue in issues):
            raise LocalImportError("source no longer matches its non-blocking preview")
        accepted = [row for row in normalized if not row["_rejected"]]
        catalog = self._read_catalog()
        active = dict(catalog.get("active_datasets", {}))
        snapshot_seed = {"import_id": import_id, "active": active, "dataset_id": preview.dataset.dataset_id}
        snapshot_id = f"research-{_sha256_value(snapshot_seed).removeprefix('sha256:')[:24]}"
        for zone in ZONE_NAMES:
            self._data_path(zone).mkdir(parents=True, exist_ok=True)
        normalized_dir = self._data_path("normalized", preview.dataset.dataset_kind)
        normalized_dir.mkdir(parents=True, exist_ok=True)
        normalized_path = normalized_dir / f"{snapshot_id}.parquet"

        persisted_rows = [self._persisted_row(row, preview, snapshot_id) for row in accepted]
        self._write_parquet_new(normalized_path, persisted_rows)
        landing_path: Path | None = None
        if preview.retain_raw_source:
            landing_dir = self._data_path("landing", preview.source.source_digest.removeprefix("sha256:"))
            landing_dir.mkdir(parents=True, exist_ok=True)
            landing_path = landing_dir / preview.source.absolute_path.name
            if not landing_path.exists():
                with preview.source.absolute_path.open("rb") as source_stream, landing_path.open("xb") as target_stream:
                    shutil.copyfileobj(source_stream, target_stream)

        source_reference = preview.source.model_copy(update={"retained": preview.retain_raw_source, "landing_path": landing_path})
        evidence_id = f"evidence-{snapshot_id}"
        crosswalk_snapshot_id: str | None = None
        if preview.dataset.dataset_kind == "identifier_crosswalk":
            crosswalk_snapshot_id = f"crosswalk-{snapshot_id}"
            crosswalk = crosswalk_snapshot_from_rows(crosswalk_snapshot_id, persisted_rows, source_digest=preview.source.source_digest, overlap_policy=preview.mapping_manifest.link_overlap_policy)
            self._write_json_new(self._data_path("manifests", "crosswalks", f"{crosswalk_snapshot_id}.json"), crosswalk)
        active[preview.dataset.dataset_id] = {
            "dataset_id": preview.dataset.dataset_id,
            "dataset_kind": preview.dataset.dataset_kind,
            "provider_id": preview.provider.provider_id,
            "provider": preview.provider.model_dump(mode="json"),
            "dataset": preview.dataset.model_dump(mode="json"),
            "revision": preview.revision.model_dump(mode="json"),
            "source": source_reference.model_dump(mode="json"),
            "source_schema": [item.model_dump(mode="json") for item in preview.source_schema],
            "mapping_manifest": preview.mapping_manifest.model_dump(mode="json"),
            "rights_state": preview.rights_state.value,
            "normalized_path": str(normalized_path),
            "quality_report_id": preview.quality_report.report_id,
            "publication_restriction": preview.publication_restriction.value,
            "evidence_id": evidence_id,
            "crosswalk_snapshot_id": crosswalk_snapshot_id,
        }
        security_path = self._data_path("normalized", "security_master", f"{snapshot_id}-aggregate.parquet")
        security_path.parent.mkdir(parents=True, exist_ok=True)
        security_rows = self._security_master_rows(active, snapshot_id)
        self._write_parquet_new(security_path, security_rows)
        curated_path = self._data_path("curated", f"{snapshot_id}.duckdb")
        self._create_curated_database(curated_path, active, security_path, snapshot_id, preview.quality_report)

        quality_path = self._data_path("quality", f"{preview.quality_report.report_id}.json")
        self._write_json_new(quality_path, preview.quality_report)
        evidence_path = self._data_path("evidence", f"{evidence_id}.json")
        self._write_json_new(evidence_path, {"evidence_id": evidence_id, "source": source_reference, "mapping_digest": preview.mapping_digest, "mapping_manifest": preview.mapping_manifest, "transformations": preview.mapping_manifest.transformations, "quality_report_id": preview.quality_report.report_id, "rights_state": preview.rights_state, "publication_restriction": preview.publication_restriction, "snapshot_id": snapshot_id})

        active_items = [active[key] for key in sorted(active)]
        active_paths = tuple(Path(item["normalized_path"]) for item in active_items) + (security_path,)
        revisions = tuple(DatasetRevision.model_validate(item["revision"]) for item in active_items)
        quality_ids = tuple(sorted({item["quality_report_id"] for item in active_items}))
        restrictions = tuple(sorted({PublicationRestriction(item["publication_restriction"]) for item in active_items}, key=lambda item: item.value))
        snapshot = ResearchDatasetSnapshot(snapshot_id=snapshot_id, created_at=preview.revision.retrieved_at, providers=tuple(ProviderDefinition.model_validate(item["provider"]) for item in active_items), datasets=tuple(DatasetDefinition.model_validate(item["dataset"]) for item in active_items), dataset_revisions=revisions, source_files=tuple(SourceFileReference.model_validate(item["source"]) for item in active_items), source_schemas={item["dataset_id"]: tuple(FieldDefinition.model_validate(field) for field in item["source_schema"]) for item in active_items}, mapping_manifests=tuple(LocalMappingManifest.model_validate(item["mapping_manifest"]) for item in active_items), rights_states=tuple(RightsState(item["rights_state"]) for item in active_items), point_in_time_policies=tuple(LocalMappingManifest.model_validate(item["mapping_manifest"]).point_in_time_policy for item in active_items), normalized_paths=active_paths, curated_path=curated_path, quality_report_ids=quality_ids, crosswalk_snapshot_ids=tuple(item["crosswalk_snapshot_id"] for item in active_items if item.get("crosswalk_snapshot_id")), fixed_query_manifest_ids=tuple(FIXED_MANIFESTS), publication_restrictions=restrictions, evidence_ids=tuple(item["evidence_id"] for item in active_items), supersedes_snapshot_id=catalog.get("latest_snapshot_id"))
        manifest_path = self._data_path("manifests", "snapshots", f"{snapshot_id}.json")
        self._write_json_new(manifest_path, snapshot)
        result = LocalImportResult(snapshot_id=snapshot_id, dataset_revision=preview.revision, normalized_paths=(normalized_path, security_path), curated_path=curated_path, manifest_path=manifest_path, quality_path=quality_path, evidence_ids=(evidence_id,), created=True)
        self._write_json_new(receipt_path, result)
        self._write_catalog({"latest_snapshot_id": snapshot_id, "active_datasets": active})
        return result

    def list_research_datasets(self) -> tuple[ResearchDatasetSnapshot, ...]:
        directory = self._data_path("manifests", "snapshots")
        if not directory.exists():
            return ()
        return tuple(ResearchDatasetSnapshot.model_validate(json.loads(path.read_text(encoding="utf-8"))) for path in sorted(directory.glob("*.json")))

    @staticmethod
    def create_portfolio_data_context(request):  # type: ignore[no-untyped-def]
        """Create the canonical point-in-time context from explicit local selections."""

        from risk_domain.monitoring import create_portfolio_data_context

        return create_portfolio_data_context(request)

    def show_data_quality(self, report_id: str | None = None) -> tuple[DataQualityReport, ...]:
        directory = self._data_path("quality")
        if not directory.exists():
            return ()
        if report_id is not None and SAFE_COMPONENT.fullmatch(report_id) is None:
            raise LocalImportError("quality report ID must be a path-safe identifier")
        paths = [directory / f"{report_id}.json"] if report_id else sorted(directory.glob("*.json"))
        return tuple(DataQualityReport.model_validate(json.loads(path.read_text(encoding="utf-8"))) for path in paths if path.is_file())

    def run_fixed_query(self, request: FixedQueryRequest) -> FixedQueryResult:
        manifest = FIXED_MANIFESTS.get(request.manifest_id)
        if manifest is None:
            raise LocalImportError("unknown fixed query manifest ID; arbitrary SQL is prohibited")
        unknown = set(request.parameters) - set(manifest.parameter_names)
        if unknown:
            raise LocalImportError(f"unsupported structured parameters: {sorted(unknown)}")
        if request.limit > manifest.maximum_limit:
            raise LocalImportError(f"limit exceeds maximum {manifest.maximum_limit}")
        if manifest.point_in_time and request.as_of is None:
            raise LocalImportError("as_of is required for this point-in-time manifest")
        catalog = self._read_catalog()
        snapshot_id = catalog.get("latest_snapshot_id")
        if not snapshot_id:
            raise LocalImportError("no research dataset snapshot is available")
        if SAFE_COMPONENT.fullmatch(snapshot_id) is None:
            raise LocalImportError("catalogue contains an invalid snapshot identifier")
        snapshot_path = self._data_path("manifests", "snapshots", f"{snapshot_id}.json")
        snapshot = ResearchDatasetSnapshot.model_validate(json.loads(snapshot_path.read_text(encoding="utf-8")))
        sql, values = self._fixed_sql(manifest, request)
        with duckdb.connect(str(snapshot.curated_path), read_only=True) as connection:
            cursor = connection.execute(sql, values)
            rows = tuple(dict(zip(manifest.columns, row, strict=True)) for row in cursor.fetchall())
        warnings = ("Records with missing available_at are excluded from point-in-time results.",) if manifest.point_in_time else ()
        return FixedQueryResult(manifest_id=manifest.manifest_id, as_of=request.as_of, columns=manifest.columns, rows=rows, snapshot_ids=(snapshot_id,), evidence_ids=snapshot.evidence_ids + tuple(f"quality:{item}" for item in snapshot.quality_report_ids), warnings=warnings)

    @staticmethod
    def _persisted_row(row: dict[str, Any], preview: LocalImportPreview, snapshot_id: str) -> dict[str, Any]:
        persisted = {key: _jsonable(value) for key, value in row.items() if not key.startswith("_")}
        if preview.dataset.dataset_kind == "daily_market":
            persisted["entity_id"] = f"security-permno-{persisted.get('permno')}"
        elif preview.dataset.dataset_kind == "fundamentals_annual":
            persisted["entity_id"] = f"company-gvkey-{persisted.get('gvkey')}"
        elif preview.dataset.dataset_kind == "identifier_crosswalk":
            persisted["entity_id"] = f"security-permno-{persisted.get('permno')}"
            persisted["open_ended"] = persisted.get("effective_to") is None
        persisted.update({"provider_id": preview.provider.provider_id, "dataset_id": preview.dataset.dataset_id, "dataset_revision": preview.revision.revision_id, "source_digest": preview.source.source_digest, "retrieved_at": _iso_datetime(preview.revision.retrieved_at), "rights_state": preview.rights_state.value, "publication_restriction": preview.publication_restriction.value, "mapping_digest": preview.mapping_digest, "source_values": json.dumps(row["_source_values"], sort_keys=True, separators=(",", ":")), "quality_flags": json.dumps(sorted(set(row["_quality_flags"]))), "snapshot_id": snapshot_id})
        return persisted

    @staticmethod
    def _write_parquet_new(path: Path, rows: list[dict[str, Any]]) -> None:
        if path.exists():
            raise FileExistsError(f"immutable normalized output already exists: {path}")
        if not rows:
            table = pa.table({"snapshot_id": pa.array([], type=pa.string())})
        else:
            keys = sorted({key for row in rows for key in row})
            table = pa.table({key: [row.get(key) for row in rows] for key in keys})
        pq.write_table(table, path)

    @staticmethod
    def _write_json_new(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            stream.write(manifest_json(value))

    def _data_path(self, *parts: str) -> Path:
        root = self.data_root.resolve()
        candidate = root.joinpath(*parts).resolve(strict=False)
        if candidate != root and root not in candidate.parents:
            raise LocalImportError("generated storage path escapes PORTFOLIO_RISK_DATA_ROOT")
        return candidate

    def _read_catalog(self) -> dict[str, Any]:
        path = self._data_path("manifests", "catalog.json")
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"active_datasets": {}}

    def _write_catalog(self, value: dict[str, Any]) -> None:
        path = self._data_path("manifests", "catalog.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(manifest_json(value), encoding="utf-8")
        os.replace(temporary, path)

    @staticmethod
    def _rows_from_active(active: dict[str, Any], kind: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in active.values():
            if item["dataset_kind"] == kind:
                rows.extend(pq.read_table(item["normalized_path"]).to_pylist())
        return rows

    def _security_master_rows(self, active: dict[str, Any], snapshot_id: str) -> list[dict[str, Any]]:
        entities: dict[str, dict[str, Any]] = {}
        columns = FIXED_MANIFESTS["security-master"].columns
        for row in self._rows_from_active(active, "security_master"):
            entity = row["entity_id"]
            entities[entity] = {column: row.get(column) for column in columns} | {"snapshot_id": snapshot_id}
        for row in self._rows_from_active(active, "daily_market"):
            entity = row["entity_id"]
            entities.setdefault(entity, {"entity_id": entity, "permno": row.get("permno"), "gvkey": None, "cusip": row.get("cusip"), "ticker": row.get("ticker"), "cik": None, "provider_id": row.get("provider_id"), "dataset_id": row.get("dataset_id"), "snapshot_id": snapshot_id})
            for field in ("permno", "cusip", "ticker"):
                if entities[entity].get(field) is None:
                    entities[entity][field] = row.get(field)
        for row in self._rows_from_active(active, "identifier_crosswalk"):
            entity = row["entity_id"]
            entities.setdefault(entity, {"entity_id": entity, "permno": row.get("permno"), "gvkey": row.get("gvkey"), "cusip": None, "ticker": None, "cik": None, "provider_id": row.get("provider_id"), "dataset_id": row.get("dataset_id"), "snapshot_id": snapshot_id})
            if entities[entity].get("gvkey") is None:
                entities[entity]["gvkey"] = row.get("gvkey")
        return sorted(entities.values(), key=lambda row: row["entity_id"])

    def _create_curated_database(self, path: Path, active: dict[str, Any], security_path: Path, snapshot_id: str, latest_quality: DataQualityReport) -> None:
        if path.exists():
            raise FileExistsError(f"immutable curated output already exists: {path}")
        schemas = {
            "security_master": ["entity_id", "permno", "gvkey", "cusip", "ticker", "cik", "provider_id", "dataset_id", "snapshot_id"],
            "daily_market": list(FIXED_MANIFESTS["daily-market-history"].columns),
            "fundamentals_annual": list(FIXED_MANIFESTS["fundamentals-as-of"].columns),
            "identifier_crosswalk": ["entity_id", "gvkey", "permno", "observed_at", "available_at", "effective_from", "effective_to", "open_ended", "link_type", "link_primary", "provider_id", "dataset_id", "dataset_revision", "quality_flags", "snapshot_id"],
        }
        data = {"security_master": pq.read_table(security_path).to_pylist(), "daily_market": self._rows_from_active(active, "daily_market"), "fundamentals_annual": self._rows_from_active(active, "fundamentals_annual"), "identifier_crosswalk": self._rows_from_active(active, "identifier_crosswalk")}
        reports: dict[str, DataQualityReport] = {latest_quality.report_id: latest_quality}
        for item in active.values():
            quality_path = self._data_path("quality", f"{item['quality_report_id']}.json")
            if quality_path.is_file():
                report = DataQualityReport.model_validate(json.loads(quality_path.read_text(encoding="utf-8")))
                reports[report.report_id] = report
        quality_rows = [{"report_id": report.report_id, "dataset_id": report.dataset_id, "metric": metric.metric, "value": str(metric.value), "unit": metric.unit, "blocking": str(report.blocking).lower(), "snapshot_id": snapshot_id} for report in reports.values() for metric in report.metrics]
        with duckdb.connect(str(path)) as connection:
            for name, columns in schemas.items():
                selected = [{column: None if row.get(column) is None else str(_jsonable(row.get(column))).lower() if isinstance(row.get(column), bool) else str(_jsonable(row.get(column))) for column in columns} for row in data[name]]
                table = pa.table({column: pa.array([row.get(column) for row in selected], type=pa.string()) for column in columns})
                connection.register(f"_{name}_arrow", table)
                connection.execute(f'CREATE TABLE "_{name}" AS SELECT * FROM "_{name}_arrow"')
                connection.execute(f'CREATE VIEW "{name}" AS SELECT * FROM "_{name}"')
            quality_columns = list(FIXED_MANIFESTS["data-quality-summary"].columns)
            quality_table = pa.table({column: pa.array([row.get(column) for row in quality_rows], type=pa.string()) for column in quality_columns})
            connection.register("_quality_arrow", quality_table)
            connection.execute("CREATE TABLE _data_quality_summary AS SELECT * FROM _quality_arrow")
            connection.execute("CREATE VIEW data_quality_summary AS SELECT * FROM _data_quality_summary")
            connection.execute("CREATE VIEW latest_available_market AS SELECT * EXCLUDE (rn) FROM (SELECT *, row_number() OVER (PARTITION BY permno ORDER BY available_at DESC, observed_at DESC) rn FROM daily_market WHERE available_at IS NOT NULL) WHERE rn=1")
            connection.execute("CREATE VIEW latest_available_fundamentals AS SELECT * EXCLUDE (rn) FROM (SELECT *, row_number() OVER (PARTITION BY gvkey ORDER BY available_at DESC, observed_at DESC) rn FROM fundamentals_annual WHERE available_at IS NOT NULL) WHERE rn=1")
            connection.execute("CREATE VIEW linked_market_fundamentals AS SELECT m.entity_id,m.permno,x.gvkey,m.observed_at market_observed_at,m.available_at market_available_at,m.valuation_price,f.observed_at fundamental_observed_at,f.available_at fundamental_available_at,f.assets,f.sales,x.effective_from link_effective_from,x.effective_to link_effective_to,x.available_at link_available_at,m.snapshot_id FROM daily_market m JOIN identifier_crosswalk x ON m.permno=x.permno AND m.observed_at>=x.effective_from AND (x.effective_to IS NULL OR m.observed_at<=x.effective_to) JOIN fundamentals_annual f ON f.gvkey=x.gvkey")

    @staticmethod
    def _fixed_sql(manifest: FixedQueryManifest, request: FixedQueryRequest) -> tuple[str, list[Any]]:
        values: list[Any] = []
        clauses: list[str] = []
        field_map = {"entity_id": "entity_id", "permno": "permno", "gvkey": "gvkey", "dataset_id": "dataset_id"}
        for parameter, field in field_map.items():
            if parameter in request.parameters:
                clauses.append(f"{field} = ?")
                values.append(request.parameters[parameter])
        if request.manifest_id == "daily-market-history":
            clauses.append("available_at IS NOT NULL AND available_at <= ?")
            values.append(_iso_datetime(request.as_of))
            if "start_at" in request.parameters:
                clauses.append("observed_at >= ?")
                values.append(request.parameters["start_at"])
            if "end_at" in request.parameters:
                clauses.append("observed_at <= ?")
                values.append(request.parameters["end_at"])
        elif request.manifest_id == "fundamentals-as-of":
            clauses.append("available_at IS NOT NULL AND available_at <= ?")
            values.append(_iso_datetime(request.as_of))
        elif request.manifest_id == "linked-market-fundamentals-as-of":
            clauses.extend(("market_available_at IS NOT NULL AND market_available_at <= ?", "fundamental_available_at IS NOT NULL AND fundamental_available_at <= ?", "link_available_at IS NOT NULL AND link_available_at <= ?"))
            cutoff = _iso_datetime(request.as_of)
            values.extend((cutoff, cutoff, cutoff))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        order = {"security-master": "entity_id", "daily-market-history": "permno, observed_at, available_at", "fundamentals-as-of": "gvkey, available_at, observed_at", "linked-market-fundamentals-as-of": "permno, market_observed_at, fundamental_available_at", "data-quality-summary": "dataset_id, metric"}[request.manifest_id]
        columns = ",".join(f'"{column}"' for column in manifest.columns)
        return f'SELECT {columns} FROM "{manifest.view_name}"{where} ORDER BY {order} LIMIT ?', values + [request.limit]


def crosswalk_snapshot_from_rows(snapshot_id: str, rows: Iterable[dict[str, Any]], *, source_digest: str, overlap_policy: str = "reject") -> CrosswalkSnapshot:
    records = tuple(CrosswalkRecord(source_identifier=EntityIdentifier(entity_id=f"company-gvkey-{row['gvkey']}", identifier_type="gvkey", identifier_value=str(row["gvkey"])), target_identifier=EntityIdentifier(entity_id=f"security-permno-{row['permno']}", identifier_type="permno", identifier_value=str(row["permno"])), effective_from=date.fromisoformat(str(row["effective_from"])[:10]), effective_to=date.fromisoformat(str(row["effective_to"])[:10]) if row.get("effective_to") else None, open_ended=not bool(row.get("effective_to")), observed_at=date.fromisoformat(str(row["observed_at"])[:10]), available_at=datetime.fromisoformat(str(row["available_at"]).replace("Z", "+00:00")), link_type=str(row.get("link_type", "")), link_primary=str(row.get("link_primary", ""))) for row in rows)
    return CrosswalkSnapshot(snapshot_id=snapshot_id, records=records, overlap_policy=overlap_policy, source_digest=source_digest)
