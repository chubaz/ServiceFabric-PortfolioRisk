"""Immutable contracts for the bounded CRSP/Compustat local-export bridge."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
SAFE_IDENTIFIER_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]{0,127}$"
SAFE_REVISION_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"

LicensedSourceKind = Literal[
    "crsp_daily",
    "crsp_monthly",
    "ccm_links",
    "compustat_annual",
    "compustat_quarterly",
    "crsp_delist",
    "crsp_stock_names",
]
SourceFrequency = Literal["daily", "monthly", "annual", "quarterly", "event", "date_effective"]
CanonicalType = Literal[
    "VARCHAR",
    "BIGINT",
    "INTEGER",
    "SMALLINT",
    "DECIMAL",
    "DATE",
    "TIMESTAMPTZ",
    "BOOLEAN",
]
TransformationOperation = Literal[
    "rename",
    "typed_cast",
    "absolute_value",
    "scale",
    "trim",
    "uppercase",
    "null_map",
    "date_conversion",
    "timestamp_at_utc",
    "next_observed_session_availability",
    "literal_value",
    "explicit_ordered_coalesce",
]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware UTC")
    if value.utcoffset().total_seconds() != 0:
        raise ValueError("timestamps must use UTC")
    return value.astimezone(UTC)


def _utc_time(value: time) -> time:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("review_time must be timezone-aware UTC")
    if value.utcoffset().total_seconds() != 0:
        raise ValueError("review_time must use UTC")
    return value


class LicensedContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class SourceSchemaColumn(LicensedContract):
    name: str = Field(pattern=SAFE_IDENTIFIER_PATTERN)
    logical_type: str = Field(min_length=1, max_length=128)
    nullable: bool = True


class SchemaFingerprint(LicensedContract):
    digest: str = Field(pattern=SHA256_PATTERN)
    algorithm: Literal["external_arrow_v1", "duckdb_logical_v1"] = "external_arrow_v1"
    columns: tuple[SourceSchemaColumn, ...] = Field(min_length=1)

    @field_validator("columns")
    @classmethod
    def unique_columns(cls, values: tuple[SourceSchemaColumn, ...]) -> tuple[SourceSchemaColumn, ...]:
        names = [item.name.casefold() for item in values]
        if len(names) != len(set(names)):
            raise ValueError("schema columns must be distinct")
        return values


class WhitelistedTransformation(LicensedContract):
    transformation_id: str = Field(pattern=SAFE_IDENTIFIER_PATTERN)
    operation: TransformationOperation
    version: str = Field(pattern=SAFE_REVISION_PATTERN)
    source_columns: tuple[str, ...] = ()
    target_type: CanonicalType | None = None
    scale_factor: Decimal | None = None
    scale_column: str | None = Field(default=None, pattern=SAFE_IDENTIFIER_PATTERN)
    scale_direction: Literal["multiply", "divide"] | None = None
    null_values: tuple[str, ...] = ()
    date_format: Literal["iso8601", "yyyymmdd"] | None = None
    literal: str | int | Decimal | bool | date | datetime | None = None
    disclosure: str = Field(min_length=1)

    @field_validator("source_columns")
    @classmethod
    def safe_sources(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        import re

        if any(re.fullmatch(SAFE_IDENTIFIER_PATTERN, item) is None for item in values):
            raise ValueError("transformation source columns must be safe identifiers")
        return values

    @model_validator(mode="after")
    def parameters_match_operation(self) -> "WhitelistedTransformation":
        if self.operation == "typed_cast" and self.target_type is None:
            raise ValueError("typed_cast requires target_type")
        if self.operation == "scale":
            factors = (self.scale_factor is not None) + (self.scale_column is not None)
            if factors != 1 or self.scale_direction is None:
                raise ValueError("scale requires exactly one reviewed factor and a direction")
            if self.scale_factor == 0:
                raise ValueError("scale factor must not be zero")
        if self.operation == "null_map" and not self.null_values:
            raise ValueError("null_map requires explicit null_values")
        if self.operation == "date_conversion" and self.date_format is None:
            raise ValueError("date_conversion requires an explicit date_format")
        if self.operation == "literal_value" and self.source_columns:
            raise ValueError("literal_value cannot read source columns")
        if self.operation == "explicit_ordered_coalesce" and len(self.source_columns) < 2:
            raise ValueError("explicit_ordered_coalesce requires at least two ordered columns")
        if self.operation == "next_observed_session_availability" and len(self.source_columns) != 1:
            raise ValueError("next-session availability requires exactly one market-date column")
        return self


class SourceColumnMapping(LicensedContract):
    canonical_name: str = Field(pattern=SAFE_IDENTIFIER_PATTERN)
    source_columns: tuple[str, ...] = ()
    canonical_type: CanonicalType
    required: bool = False
    unit: str | None = Field(default=None, min_length=1, max_length=64)
    transformation_ids: tuple[str, ...] = ()

    @field_validator("source_columns", "transformation_ids")
    @classmethod
    def safe_identifiers(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        import re

        if any(re.fullmatch(SAFE_IDENTIFIER_PATTERN, item) is None for item in values):
            raise ValueError("mapping values must be safe identifiers")
        if len(values) != len(set(values)):
            raise ValueError("mapping values must be distinct")
        return values


class AvailabilityPolicy(LicensedContract):
    policy_id: str = Field(pattern=SAFE_IDENTIFIER_PATTERN)
    version: str = Field(pattern=SAFE_REVISION_PATTERN)
    mode: Literal["next_distinct_market_observation", "explicit_publication_field", "not_applicable"]
    observed_at_field: str | None = Field(default=None, pattern=SAFE_IDENTIFIER_PATTERN)
    available_at_field: str | None = Field(default=None, pattern=SAFE_IDENTIFIER_PATTERN)
    review_time: time | None = None
    missing_available_at: Literal["exclude", "retain_with_warning"] = "exclude"
    terminal_rule: Literal["unavailable", "explicit_reviewed_timestamp"] = "unavailable"
    research_timing_model: Literal[True] = True
    disclosure: str = Field(min_length=1)

    _review_time = field_validator("review_time")(
        lambda value: _utc_time(value) if value is not None else None
    )

    @model_validator(mode="after")
    def mode_requirements(self) -> "AvailabilityPolicy":
        if self.mode == "next_distinct_market_observation":
            if self.observed_at_field is None or self.review_time is None:
                raise ValueError("market availability requires an observed field and UTC review time")
            if self.terminal_rule != "unavailable":
                raise ValueError("a terminal timestamp requires a separately reviewed policy version")
        if self.mode == "explicit_publication_field" and self.available_at_field is None:
            raise ValueError("fundamental availability requires an explicit publication field")
        return self


class LinkSelectionPolicy(LicensedContract):
    policy_id: str = Field(pattern=SAFE_IDENTIFIER_PATTERN)
    version: str = Field(pattern=SAFE_REVISION_PATTERN)
    allowed_link_types: tuple[str, ...] = Field(min_length=1)
    allowed_primary_values: tuple[str, ...] = Field(min_length=1)
    ambiguous_eligible_links: Literal["reject"] = "reject"
    join_keys: Literal["gvkey_permno"] = "gvkey_permno"
    date_rule: Literal["link_start <= market_date <= coalesce(link_end, infinity)"] = (
        "link_start <= market_date <= coalesce(link_end, infinity)"
    )
    ticker_fallback: Literal[False] = False
    name_fallback: Literal[False] = False
    cusip_fallback: Literal[False] = False
    fuzzy_matching: Literal[False] = False
    nearest_date_fallback: Literal[False] = False

    @field_validator("allowed_link_types", "allowed_primary_values")
    @classmethod
    def distinct_values(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("link-policy allowlists must be distinct")
        return values


class LicensedSourceDefinition(LicensedContract):
    source_name: LicensedSourceKind
    filename: Literal[
        "dsf.parquet",
        "msf.parquet",
        "ccm_lookup.parquet",
        "ccmxpf_linktable.parquet",
        "funda.parquet",
        "fundq.parquet",
        "dsedelist.parquet",
        "stocknames.parquet",
    ]
    source_path: Path
    source_digest: str = Field(pattern=SHA256_PATTERN)
    source_kind: LicensedSourceKind
    schema_fingerprint: SchemaFingerprint
    revision: str = Field(pattern=SAFE_REVISION_PATTERN)
    retrieved_at: datetime
    frequency: SourceFrequency
    mappings: tuple[SourceColumnMapping, ...] = Field(min_length=1)
    declared_units: dict[str, str]
    transformations: tuple[WhitelistedTransformation, ...] = ()
    availability_policy: AvailabilityPolicy

    _retrieved_at = field_validator("retrieved_at")(_utc)

    @field_validator("source_path")
    @classmethod
    def absolute_source(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("licensed source paths must be absolute")
        return value

    @field_validator("declared_units")
    @classmethod
    def safe_unit_keys(cls, value: dict[str, str]) -> dict[str, str]:
        import re

        if any(re.fullmatch(SAFE_IDENTIFIER_PATTERN, key) is None for key in value):
            raise ValueError("declared-unit keys must be safe identifiers")
        return value

    @model_validator(mode="after")
    def source_is_consistent(self) -> "LicensedSourceDefinition":
        if self.source_name != self.source_kind:
            raise ValueError("source_name and source_kind must match")
        expected_filename = {
            "crsp_daily": "dsf.parquet",
            "crsp_monthly": "msf.parquet",
            "ccm_links": ("ccm_lookup.parquet", "ccmxpf_linktable.parquet"),
            "compustat_annual": "funda.parquet",
            "compustat_quarterly": "fundq.parquet",
            "crsp_delist": "dsedelist.parquet",
            "crsp_stock_names": "stocknames.parquet",
        }[self.source_name]
        expected_filenames = (
            (expected_filename,)
            if isinstance(expected_filename, str)
            else expected_filename
        )
        if self.filename not in expected_filenames or self.source_path.name != self.filename:
            raise ValueError("source filename must match its frozen source kind")
        target_names = [item.canonical_name for item in self.mappings]
        if len(target_names) != len(set(target_names)):
            raise ValueError("canonical mapping targets must be distinct")
        transforms = {item.transformation_id: item for item in self.transformations}
        if len(transforms) != len(self.transformations):
            raise ValueError("transformation IDs must be distinct")
        referenced = {item for mapping in self.mappings for item in mapping.transformation_ids}
        if not referenced.issubset(transforms):
            raise ValueError("every referenced transformation must be declared")
        provenance_literals = {
            mapping.canonical_name: transforms[mapping.transformation_ids[-1]].literal
            for mapping in self.mappings
            if mapping.canonical_name in {"source_revision", "source_digest"}
            and mapping.transformation_ids
        }
        if provenance_literals.get("source_revision") != self.revision:
            raise ValueError("source_revision literal must match the reviewed revision")
        if provenance_literals.get("source_digest") != self.source_digest:
            raise ValueError("source_digest literal must match the reviewed digest")
        for mapping in self.mappings:
            coalesces = [
                transforms[item]
                for item in mapping.transformation_ids
                if transforms[item].operation == "explicit_ordered_coalesce"
            ]
            if len(mapping.source_columns) > 1 and not coalesces:
                raise ValueError("multi-source mappings require explicit ordered coalesce")
        required_join_keys = {
            "crsp_daily": ("permno", "observed_at"),
            "crsp_monthly": ("permno", "observed_at"),
            "ccm_links": ("gvkey", "permno", "link_start"),
            "compustat_annual": ("gvkey", "observed_at"),
            "compustat_quarterly": ("gvkey", "observed_at"),
            "crsp_delist": ("permno", "delisting_date"),
            "crsp_stock_names": ("permno", "valid_from"),
        }[self.source_name]
        mapping_by_target = {item.canonical_name: item for item in self.mappings}
        invalid_keys = [
            key
            for key in required_join_keys
            if key not in mapping_by_target
            or not mapping_by_target[key].required
            or not mapping_by_target[key].source_columns
        ]
        if invalid_keys:
            raise ValueError(
                "required source join keys must remain explicitly mapped: "
                + ", ".join(invalid_keys)
            )
        return self


class LicensedSourceManifest(LicensedContract):
    manifest_id: str = Field(pattern=SAFE_IDENTIFIER_PATTERN)
    manifest_version: str = Field(pattern=SAFE_REVISION_PATTERN)
    profile: Literal["licensed_local"]
    publication_state: Literal["private_local_only"]
    rights: Literal["licensed_restricted"]
    reviewed: Literal[True]
    sources: tuple[LicensedSourceDefinition, ...] = Field(min_length=1)
    link_policy: LinkSelectionPolicy
    limitations: tuple[str, ...] = Field(min_length=1)

    @field_validator("sources")
    @classmethod
    def distinct_sources(
        cls, values: tuple[LicensedSourceDefinition, ...]
    ) -> tuple[LicensedSourceDefinition, ...]:
        names = [item.source_name for item in values]
        if len(names) != len(set(names)):
            raise ValueError("licensed sources must be distinct")
        return tuple(sorted(values, key=lambda item: item.source_name))


class DatasetBuildSpecification(LicensedContract):
    manifest_path: Path
    data_root: Path
    mode: Literal["daily_primary", "monthly_smoke"] = "daily_primary"
    memory_limit: str = Field(default="2GB", pattern=r"^[1-9][0-9]*(?:MB|GB)$")
    threads: int = Field(default=2, ge=1, le=64)
    temp_directory: Path
    code_revision: str = Field(pattern=SAFE_REVISION_PATTERN)
    compression: Literal["ZSTD"] = "ZSTD"
    annual_partitions: Literal[True] = True
    overwrite_sources: Literal[False] = False
    allow_network: Literal[False] = False
    allow_repository_writes: Literal[False] = False

    @field_validator("manifest_path", "data_root", "temp_directory")
    @classmethod
    def absolute_paths(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("build paths must be absolute")
        return value


class JoinQualityReport(LicensedContract):
    report_id: str = Field(pattern=SAFE_IDENTIFIER_PATTERN)
    snapshot_id: str = Field(pattern=SAFE_IDENTIFIER_PATTERN)
    eligible_link_rows: int = Field(ge=0)
    ambiguous_market_dates: int = Field(ge=0)
    unlinked_market_rows: int | None = Field(default=None, ge=0)
    missing_fundamental_availability_rows: int | None = Field(default=None, ge=0)
    stock_name_overlap_rows: int = Field(ge=0)
    blocked: bool
    warnings: tuple[str, ...] = ()


class DatasetAdmissionReceipt(LicensedContract):
    receipt_id: str = Field(pattern=SAFE_IDENTIFIER_PATTERN)
    snapshot_id: str = Field(pattern=SAFE_IDENTIFIER_PATTERN)
    created_at: datetime
    source_digests: dict[str, str]
    schema_fingerprints: dict[str, str]
    mapping_digest: str = Field(pattern=SHA256_PATTERN)
    transformation_versions: dict[str, str]
    output_row_counts: dict[str, int]
    partitions: dict[str, tuple[str, ...]]
    output_digests: dict[str, str]
    catalogue_digest: str = Field(pattern=SHA256_PATTERN)
    rights: Literal["licensed_restricted"]
    publication_state: Literal["private_local_only"]
    quality: dict[str, int | str | bool]
    coverage: dict[str, str | None]
    availability_policy: dict[str, str]
    link_policy: LinkSelectionPolicy
    code_revision: str = Field(pattern=SAFE_REVISION_PATTERN)
    limitations: tuple[str, ...] = Field(min_length=1)

    _created_at = field_validator("created_at")(_utc)

    @field_validator("source_digests", "schema_fingerprints", "output_digests")
    @classmethod
    def canonical_digest_values(cls, values: dict[str, str]) -> dict[str, str]:
        import re

        if any(re.fullmatch(SHA256_PATTERN, value) is None for value in values.values()):
            raise ValueError("receipt digests must use canonical SHA-256")
        return values


class DatasetBuildResult(LicensedContract):
    snapshot_id: str = Field(pattern=SAFE_IDENTIFIER_PATTERN)
    created: bool
    snapshot_root: Path
    catalogue_path: Path
    receipt_path: Path
    quality_path: Path
    evidence_path: Path
    receipt: DatasetAdmissionReceipt
    join_quality: JoinQualityReport
