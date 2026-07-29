"""Frozen contracts for the Day 2–3 governed local research data plane."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Digest = str
DatasetKind = Literal["security_master", "daily_market", "fundamentals_annual", "identifier_crosswalk"]
SAFE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"


class ResearchContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC)


class ProviderAccessState(str, Enum):
    AVAILABLE = "available"
    DISABLED = "disabled"


class RightsState(str, Enum):
    REVIEWED_SYNTHETIC = "reviewed_synthetic"
    LICENSED_RESTRICTED = "licensed_restricted"


class PublicationRestriction(str, Enum):
    SYNTHETIC_ONLY = "synthetic_only"
    INTERNAL_RESEARCH_ONLY = "internal_research_only"
    NO_PUBLICATION = "no_publication"


class ProviderDefinition(ResearchContract):
    provider_id: str = Field(pattern=SAFE_ID_PATTERN)
    display_name: str
    profile: Literal["synthetic_local", "licensed_local"]
    access_state: ProviderAccessState = ProviderAccessState.AVAILABLE
    network_enabled: Literal[False] = False
    credential_reference: str | None = Field(default=None, pattern=r"^secret-ref:[a-z0-9/_-]+$")


class DatasetDefinition(ResearchContract):
    dataset_id: str = Field(pattern=SAFE_ID_PATTERN)
    provider_id: str = Field(pattern=SAFE_ID_PATTERN)
    dataset_kind: DatasetKind
    description: str


class DatasetRevision(ResearchContract):
    dataset_id: str = Field(pattern=SAFE_ID_PATTERN)
    revision_id: str = Field(pattern=SAFE_ID_PATTERN)
    retrieved_at: datetime
    source_digest: Digest = Field(pattern=r"^sha256:[a-f0-9]{64}$")

    _retrieved_at = field_validator("retrieved_at")(_utc)


class SourceFileReference(ResearchContract):
    absolute_path: Path
    file_format: Literal["csv", "parquet"]
    source_digest: Digest = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    byte_count: int = Field(ge=0)
    retained: bool = False
    landing_path: Path | None = None

    @field_validator("absolute_path")
    @classmethod
    def path_is_absolute(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("source path must be absolute")
        return value


class FieldDefinition(ResearchContract):
    field_name: str
    data_type: Literal["string", "integer", "decimal", "date", "datetime", "boolean"]
    nullable: bool = True
    unit: str | None = None
    description: str = ""


class FieldMapping(ResearchContract):
    source_field: str
    target_field: str
    data_type: Literal["string", "integer", "decimal", "date", "datetime", "boolean"]
    nullable: bool = True
    source_unit: str | None = None
    target_unit: str | None = None
    transformation_ids: tuple[str, ...] = ()


class TransformationRecord(ResearchContract):
    transformation_id: str = Field(pattern=SAFE_ID_PATTERN)
    operation: Literal["identity", "absolute_value", "scale", "sign_normalization", "open_end_date"]
    source_field: str
    target_field: str
    parameters: dict[str, str] = Field(default_factory=dict)
    disclosure: str


class PointInTimePolicy(ResearchContract):
    observed_at_field: str
    available_at_field: str | None
    missing_available_at: Literal["block", "warn"] = "block"
    query_filter: Literal["available_at_lte_as_of"] = "available_at_lte_as_of"


class LocalMappingManifest(ResearchContract):
    manifest_id: str = Field(pattern=SAFE_ID_PATTERN)
    dataset_kind: DatasetKind
    target_dataset: DatasetKind
    fields: tuple[FieldMapping, ...]
    field_definitions: tuple[FieldDefinition, ...]
    key_fields: tuple[str, ...]
    transformations: tuple[TransformationRecord, ...] = ()
    point_in_time_policy: PointInTimePolicy
    link_overlap_policy: Literal["reject", "latest_start"] = "reject"

    @model_validator(mode="after")
    def mappings_are_consistent(self) -> "LocalMappingManifest":
        targets = [mapping.target_field for mapping in self.fields]
        if len(targets) != len(set(targets)):
            raise ValueError("mapping target fields must be distinct")
        if not set(self.key_fields).issubset(targets):
            raise ValueError("key fields must be mapped target fields")
        transformation_ids = {item.transformation_id for item in self.transformations}
        referenced = {item for mapping in self.fields for item in mapping.transformation_ids}
        if not referenced.issubset(transformation_ids):
            raise ValueError("every referenced transformation must be declared")
        return self


class LocalImportIssue(ResearchContract):
    code: str
    severity: Literal["warning", "blocking"]
    message: str
    row_number: int | None = Field(default=None, ge=1)
    field: str | None = None


class DataQualityFlag(ResearchContract):
    code: str
    severity: Literal["info", "warning", "blocking"]
    record_key: str | None = None
    message: str


class DataQualityMetric(ResearchContract):
    metric: str
    value: int | str
    unit: str = "count"


class DataQualityReport(ResearchContract):
    report_id: str = Field(pattern=SAFE_ID_PATTERN)
    dataset_id: str = Field(pattern=SAFE_ID_PATTERN)
    source_digest: Digest = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    metrics: tuple[DataQualityMetric, ...]
    flags: tuple[DataQualityFlag, ...] = ()
    blocking: bool


class LocalImportPreview(ResearchContract):
    preview_digest: Digest = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    source: SourceFileReference
    provider: ProviderDefinition
    dataset: DatasetDefinition
    revision: DatasetRevision
    rights_state: RightsState
    publication_restriction: PublicationRestriction
    mapping_manifest: LocalMappingManifest
    mapping_digest: Digest = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    source_schema: tuple[FieldDefinition, ...]
    row_count: int = Field(ge=0)
    accepted_row_count: int = Field(ge=0)
    rejected_row_count: int = Field(ge=0)
    issues: tuple[LocalImportIssue, ...] = ()
    quality_report: DataQualityReport
    retain_raw_source: bool = False

    @property
    def has_blocking_issues(self) -> bool:
        return any(issue.severity == "blocking" for issue in self.issues)


class LocalImportConfirmation(ResearchContract):
    confirm: bool
    preview_digest: Digest = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    source_digest: Digest = Field(pattern=r"^sha256:[a-f0-9]{64}$")


class LocalImportResult(ResearchContract):
    snapshot_id: str
    dataset_revision: DatasetRevision
    normalized_paths: tuple[Path, ...]
    curated_path: Path
    manifest_path: Path
    quality_path: Path
    evidence_ids: tuple[str, ...]
    created: bool


class EntityIdentifier(ResearchContract):
    entity_id: str
    identifier_type: Literal["permno", "gvkey", "cusip", "cik", "ticker"]
    identifier_value: str
    valid_from: date | None = None
    valid_to: date | None = None


class CrosswalkRecord(ResearchContract):
    source_identifier: EntityIdentifier
    target_identifier: EntityIdentifier
    effective_from: date
    effective_to: date | None = None
    open_ended: bool = False
    observed_at: date
    available_at: datetime
    link_type: str
    link_primary: str

    _available_at = field_validator("available_at")(_utc)

    @model_validator(mode="after")
    def dates_and_open_end_are_consistent(self) -> "CrosswalkRecord":
        if self.open_ended != (self.effective_to is None):
            raise ValueError("open-ended links must be represented explicitly")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not precede effective_from")
        return self


class CrosswalkSnapshot(ResearchContract):
    snapshot_id: str
    records: tuple[CrosswalkRecord, ...]
    overlap_policy: Literal["reject", "latest_start"]
    source_digest: Digest = Field(pattern=r"^sha256:[a-f0-9]{64}$")


class FixedQueryManifest(ResearchContract):
    manifest_id: Literal["security-master", "daily-market-history", "fundamentals-as-of", "linked-market-fundamentals-as-of", "data-quality-summary"]
    view_name: Literal["security_master", "daily_market", "fundamentals_annual", "linked_market_fundamentals", "data_quality_summary"]
    columns: tuple[str, ...]
    parameter_names: tuple[str, ...]
    point_in_time: bool
    default_limit: int = Field(default=100, ge=1, le=1000)
    maximum_limit: int = Field(default=1000, ge=1, le=10000)


class FixedQueryRequest(ResearchContract):
    manifest_id: str
    parameters: dict[str, str] = Field(default_factory=dict)
    as_of: datetime | None = None
    limit: int = Field(default=100, ge=1)

    _as_of = field_validator("as_of")(_utc)

    @model_validator(mode="after")
    def rejects_query_language(self) -> "FixedQueryRequest":
        forbidden = {"sql", "query", "expression", "where", "order_by"}
        if forbidden.intersection(key.lower() for key in self.parameters):
            raise ValueError("SQL and expression input are prohibited")
        return self


class FixedQueryResult(ResearchContract):
    manifest_id: str
    as_of: datetime | None
    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    snapshot_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()


class ResearchDatasetSnapshot(ResearchContract):
    snapshot_id: str
    created_at: datetime
    providers: tuple[ProviderDefinition, ...]
    datasets: tuple[DatasetDefinition, ...]
    dataset_revisions: tuple[DatasetRevision, ...]
    source_files: tuple[SourceFileReference, ...]
    source_schemas: dict[str, tuple[FieldDefinition, ...]]
    mapping_manifests: tuple[LocalMappingManifest, ...]
    rights_states: tuple[RightsState, ...]
    point_in_time_policies: tuple[PointInTimePolicy, ...]
    normalized_paths: tuple[Path, ...]
    curated_path: Path
    quality_report_ids: tuple[str, ...]
    crosswalk_snapshot_ids: tuple[str, ...] = ()
    fixed_query_manifest_ids: tuple[str, ...]
    publication_restrictions: tuple[PublicationRestriction, ...]
    evidence_ids: tuple[str, ...]
    supersedes_snapshot_id: str | None = None

    _created_at = field_validator("created_at")(_utc)
