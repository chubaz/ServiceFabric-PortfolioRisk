"""Browser-safe adapter for the package-owned governed research data plane."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from risk_data import (
    CrosswalkSnapshot,
    DatasetDefinition,
    FixedQueryRequest,
    LocalImportConfirmation,
    LocalImportError,
    LocalImportPreview,
    LocalImportResult,
    ProviderAccessState,
    ProviderDefinition,
    PublicationRestriction,
    ResearchDataPlane,
    ResearchDatasetSnapshot,
    RightsState,
    fixed_query_manifests,
    load_mapping_manifest,
)


MAX_RESEARCH_UPLOAD_BYTES = 1_000_000
PREVIEW_ID = re.compile(r"^sha256:[a-f0-9]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MAPPING_FILES = {
    "daily_market": "crsp_like_daily.mapping.json",
    "fundamentals_annual": "compustat_like_annual.mapping.json",
    "identifier_crosswalk": "crsp_compustat_link.mapping.json",
}


class ResearchWorkspaceRecordNotFound(LookupError):
    """A requested governed research record does not exist."""


def _json(value: object) -> object:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def _safe_component(value: str, label: str) -> str:
    if SAFE_ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a path-safe identifier")
    return value


def _timestamp(value: str) -> datetime:
    if not value.strip():
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("retrieved_at must be a timezone-aware ISO-8601 timestamp")
    return parsed.astimezone(UTC)


class ResearchDataWorkspace:
    """Translate HTTP bytes and forms into typed, package-owned operations."""

    def __init__(self, data_root: Path, repository_root: Path) -> None:
        self.data_root = data_root
        self.repository_root = repository_root
        self.plane = ResearchDataPlane(data_root)
        self.preview_root = data_root / "web-import-previews"

    @property
    def mapping_root(self) -> Path:
        return Path(__file__).resolve().parent / "catalog" / "data-mappings"

    def create_preview(
        self,
        content: bytes,
        filename: str,
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
        workbench_profile: str = "research",
        retrieved_at: str = "",
    ) -> LocalImportPreview:
        suffix = Path(filename).suffix.lower()
        if suffix not in {".csv", ".parquet"}:
            raise ValueError("Only bounded CSV or Parquet uploads are accepted. No input was retained.")
        if len(content) > MAX_RESEARCH_UPLOAD_BYTES:
            raise ValueError(f"The upload exceeds the reviewed maximum of {MAX_RESEARCH_UPLOAD_BYTES} bytes. No input was retained.")
        if not content:
            raise ValueError("The uploaded file is empty. No input was retained.")
        if dataset_kind not in MAPPING_FILES:
            raise ValueError("The selected dataset kind has no reviewed mapping manifest")
        if provider_profile not in {"synthetic_local", "licensed_local"}:
            raise ValueError("Only reviewed synthetic local or licensed local exports are accepted")
        if not rights_state:
            raise ValueError("An explicit rights selection is required")
        if not publication_restriction:
            raise ValueError("An explicit publication restriction is required")
        if workbench_profile not in {"research", "personal_portfolio"}:
            raise ValueError("The selected Workbench profile is unavailable")
        if provider_profile == "licensed_local" and workbench_profile != "personal_portfolio":
            raise ValueError("Licensed local exports require the private personal portfolio profile")

        provider = ProviderDefinition(
            provider_id=_safe_component(provider_id, "provider_id"),
            display_name=provider_name,
            profile=provider_profile,
            access_state=ProviderAccessState.AVAILABLE,
            network_enabled=False,
        )
        dataset = DatasetDefinition(
            dataset_id=_safe_component(dataset_id, "dataset_id"),
            provider_id=provider.provider_id,
            dataset_kind=dataset_kind,
            description=dataset_description,
        )
        _safe_component(revision_id, "revision_id")
        retrieved = _timestamp(retrieved_at)
        staging_metadata = {
            "provider_profile": provider_profile,
            "provider_id": provider_id,
            "provider_name": provider_name,
            "dataset_id": dataset_id,
            "dataset_kind": dataset_kind,
            "dataset_description": dataset_description,
            "revision_id": revision_id,
            "rights_state": rights_state,
            "publication_restriction": publication_restriction,
            "workbench_profile": workbench_profile,
            "retrieved_at": retrieved.isoformat(),
            "file_format": suffix,
        }
        source_identity = hashlib.sha256(
            content + b"\0" + json.dumps(staging_metadata, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        source_path = self.preview_root / "sources" / f"{source_identity}{suffix}"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        if not source_path.exists():
            source_path.write_bytes(content)
        try:
            preview = self.plane.preview_local_export(
                source_path,
                provider=provider,
                dataset=dataset,
                revision_id=revision_id,
                rights_state=RightsState(rights_state),
                publication_restriction=PublicationRestriction(publication_restriction),
                mapping_manifest=load_mapping_manifest(self.mapping_root / MAPPING_FILES[dataset_kind]),
                retrieved_at=retrieved,
                retain_raw_source=False,
            )
        except Exception:
            source_path.unlink(missing_ok=True)
            raise
        record = self._preview_path(preview.preview_digest)
        record.parent.mkdir(parents=True, exist_ok=True)
        if not record.exists():
            record.write_text(preview.model_dump_json(indent=2), encoding="utf-8")
        if preview.has_blocking_issues or preview.quality_report.blocking:
            source_path.unlink(missing_ok=True)
        return preview

    def get_preview(self, preview_id: str) -> LocalImportPreview:
        path = self._preview_path(preview_id)
        if not path.is_file():
            raise ResearchWorkspaceRecordNotFound("research import preview not found")
        return LocalImportPreview.model_validate_json(path.read_text(encoding="utf-8"))

    def confirm(self, preview_id: str, *, preview_digest: str, source_digest: str, confirm: bool) -> LocalImportResult:
        preview = self.get_preview(preview_id)
        confirmation = LocalImportConfirmation(
            confirm=confirm,
            preview_digest=preview_digest,
            source_digest=source_digest,
        )
        if not confirmation.confirm:
            raise LocalImportError("explicit confirm=true is required")
        if confirmation.preview_digest != preview.preview_digest:
            raise LocalImportError("confirmation preview digest does not match")
        if confirmation.source_digest != preview.source.source_digest:
            raise LocalImportError("source digest does not match the preview")
        confirmed_path = self._confirmation_path(preview_id)
        if confirmed_path.is_file():
            preview.source.absolute_path.unlink(missing_ok=True)
            return LocalImportResult.model_validate_json(confirmed_path.read_text(encoding="utf-8")).model_copy(update={"created": False})
        result = self.plane.confirm_local_export(preview, confirmation)
        confirmed_path.parent.mkdir(parents=True, exist_ok=True)
        confirmed_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        preview.source.absolute_path.unlink(missing_ok=True)
        return result

    def snapshots(self) -> tuple[ResearchDatasetSnapshot, ...]:
        return self.plane.list_research_datasets()

    def get_snapshot(self, snapshot_id: str) -> ResearchDatasetSnapshot:
        _safe_component(snapshot_id, "snapshot_id")
        selected = next((item for item in self.snapshots() if item.snapshot_id == snapshot_id), None)
        if selected is None:
            raise ResearchWorkspaceRecordNotFound("research dataset snapshot not found")
        return selected

    def quality(self, snapshot_id: str) -> tuple[object, ...]:
        snapshot = self.get_snapshot(snapshot_id)
        reports = []
        for report_id in snapshot.quality_report_ids:
            reports.extend(self.plane.show_data_quality(report_id))
        return tuple(reports)

    def crosswalks(self) -> tuple[CrosswalkSnapshot, ...]:
        identifiers = sorted({identifier for snapshot in self.snapshots() for identifier in snapshot.crosswalk_snapshot_ids})
        values = []
        for identifier in identifiers:
            _safe_component(identifier, "crosswalk snapshot ID")
            path = self.data_root / "manifests" / "crosswalks" / f"{identifier}.json"
            if path.is_file():
                values.append(CrosswalkSnapshot.model_validate_json(path.read_text(encoding="utf-8")))
        return tuple(values)

    def query_manifests(self) -> tuple[object, ...]:
        return fixed_query_manifests()

    def run_query(self, request: FixedQueryRequest) -> object:
        return self.plane.run_fixed_query(request)

    def _preview_path(self, preview_id: str) -> Path:
        if PREVIEW_ID.fullmatch(preview_id) is None:
            raise ResearchWorkspaceRecordNotFound("research import preview not found")
        return self.preview_root / "records" / f"{preview_id.removeprefix('sha256:')}.json"

    def _confirmation_path(self, preview_id: str) -> Path:
        if PREVIEW_ID.fullmatch(preview_id) is None:
            raise ResearchWorkspaceRecordNotFound("research import preview not found")
        return self.preview_root / "confirmations" / f"{preview_id.removeprefix('sha256:')}.json"


def preview_view(preview: LocalImportPreview) -> dict[str, Any]:
    """Return governed preview metadata without any server filesystem path."""
    return {
        "preview_id": preview.preview_digest,
        "preview_digest": preview.preview_digest,
        "source": {
            "file_format": preview.source.file_format,
            "source_digest": preview.source.source_digest,
            "byte_count": preview.source.byte_count,
            "retained": preview.source.retained,
        },
        "provider": _json(preview.provider),
        "dataset": _json(preview.dataset),
        "revision": _json(preview.revision),
        "rights_state": preview.rights_state.value,
        "publication_restriction": preview.publication_restriction.value,
        "mapping_manifest": _json(preview.mapping_manifest),
        "mapping_digest": preview.mapping_digest,
        "source_schema": [_json(item) for item in preview.source_schema],
        "row_count": preview.row_count,
        "accepted_row_count": preview.accepted_row_count,
        "rejected_row_count": preview.rejected_row_count,
        "issues": [_json(item) for item in preview.issues],
        "quality_report": _json(preview.quality_report),
        "confirmable": not preview.has_blocking_issues and not preview.quality_report.blocking,
        "raw_source_retained": False,
    }


def confirmation_view(result: LocalImportResult) -> dict[str, Any]:
    """Return an immutable import receipt without server storage paths."""
    return {
        "snapshot_id": result.snapshot_id,
        "dataset_revision": _json(result.dataset_revision),
        "evidence_ids": list(result.evidence_ids),
        "created": result.created,
        "immutable": True,
        "raw_source_retained": False,
    }


def snapshot_view(workspace: ResearchDataWorkspace, snapshot: ResearchDatasetSnapshot) -> dict[str, Any]:
    """Present immutable snapshot metadata while suppressing storage paths."""
    reports = workspace.quality(snapshot.snapshot_id)
    row_count = sum(
        int(metric.value)
        for report in reports
        for metric in report.metrics
        if metric.metric == "source_rows" and isinstance(metric.value, int)
    )
    evidence: list[dict[str, Any]] = []
    for evidence_id in snapshot.evidence_ids:
        if SAFE_ID.fullmatch(evidence_id) is None:
            continue
        path = workspace.data_root / "evidence" / f"{evidence_id}.json"
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            evidence.append({
                "evidence_id": evidence_id,
                "mapping_digest": payload.get("mapping_digest"),
                "quality_report_id": payload.get("quality_report_id"),
            })
    files = [
        {
            "file_role": "uploaded source metadata",
            "file_format": source.file_format,
            "source_digest": source.source_digest,
            "byte_count": source.byte_count,
            "retained": source.retained,
        }
        for source in snapshot.source_files
    ]
    files.extend(
        {"file_role": "normalized immutable data", "file_format": "parquet", "logical_name": path.name}
        for path in snapshot.normalized_paths
    )
    files.append({"file_role": "curated immutable view", "file_format": "duckdb", "logical_name": snapshot.curated_path.name})
    return {
        "snapshot_id": snapshot.snapshot_id,
        "created_at": snapshot.created_at.isoformat(),
        "providers": [_json(item) for item in snapshot.providers],
        "datasets": [_json(item) for item in snapshot.datasets],
        "dataset_revisions": [_json(item) for item in snapshot.dataset_revisions],
        "files": files,
        "row_count": row_count,
        "columns": {dataset_id: [_json(field) for field in fields] for dataset_id, fields in snapshot.source_schemas.items()},
        "source_digests": [item.source_digest for item in snapshot.source_files],
        "mapping_digests": [item.get("mapping_digest") for item in evidence if item.get("mapping_digest")],
        "retrieval_times": [item.retrieved_at.isoformat() for item in snapshot.dataset_revisions],
        "observed_range": "Not recorded in the immutable snapshot metadata",
        "availability_range": "Not inferred; missing availability remains missing",
        "quality": [_json(item) for item in reports],
        "evidence": evidence,
        "rights_states": [item.value for item in snapshot.rights_states],
        "publication_restrictions": [item.value for item in snapshot.publication_restrictions],
        "crosswalk_snapshot_ids": list(snapshot.crosswalk_snapshot_ids),
        "fixed_query_manifest_ids": list(snapshot.fixed_query_manifest_ids),
        "supersedes_snapshot_id": snapshot.supersedes_snapshot_id,
        "immutable": True,
    }


def provider_register_views(day1_providers: tuple[object, ...]) -> tuple[dict[str, Any], ...]:
    local = ({
        "provider_id": "reviewed-synthetic-local",
        "provider_class": "Reviewed synthetic local",
        "access_state": "available",
        "rights_state": "reviewed_synthetic",
        "publication_restriction": "synthetic_only",
        "network_state": "disabled",
        "import_state": "Available through bounded local upload",
    }, {
        "provider_id": "licensed-local-export",
        "provider_class": "Locally licensed export",
        "access_state": "importable_after_review",
        "rights_state": "explicit_confirmation_required",
        "publication_restriction": "explicit_restrictive_selection_required",
        "network_state": "disabled",
        "import_state": "Bounded browser preview; CLI for large files",
    })
    network = tuple({
        "provider_id": item.provider_id,
        "provider_class": "Network-disabled provider",
        "access_state": "disabled",
        "rights_state": item.rights_state,
        "publication_restriction": item.publication_restriction,
        "network_state": "disabled",
        "import_state": "No provider enablement or network call",
    } for item in day1_providers if not item.enabled)
    return local + network


def action_envelope(capability_id: str, data: object, *, limitations: tuple[str, ...]) -> dict[str, object]:
    return {
        "capability_id": capability_id,
        "status": "succeeded",
        "data": data,
        "evidence_references": [],
        "assumptions": ["The operation uses reviewed local contracts and local-only storage."],
        "warnings": ["Rights and publication restrictions travel with every confirmed snapshot."],
        "limitations": list(limitations) + ["No network, provider enablement, broker, order, trade, or rebalance effect is available."],
        "effects": [],
        "human_review_required": True,
    }


__all__ = [
    "MAX_RESEARCH_UPLOAD_BYTES",
    "ResearchDataWorkspace",
    "ResearchWorkspaceRecordNotFound",
    "action_envelope",
    "confirmation_view",
    "preview_view",
    "provider_register_views",
    "snapshot_view",
]
