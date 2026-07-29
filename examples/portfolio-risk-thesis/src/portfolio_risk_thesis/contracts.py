"""Immutable experiment-local contracts for Thesis Sprint Day 1."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"


def utc_datetime(value: datetime) -> datetime:
    """Require an explicit UTC timestamp; do not silently reinterpret offsets."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware UTC")
    if value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must use UTC")
    return value.astimezone(UTC)


def utc_time(value: time) -> time:
    """Require an explicit UTC review time."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("review_time must be timezone-aware UTC")
    if value.utcoffset() != timedelta(0):
        raise ValueError("review_time must use UTC")
    return value


def finite_decimal(value: Decimal | None) -> Decimal | None:
    if value is not None and not value.is_finite():
        raise ValueError("numeric values must be finite Decimals")
    return value


def _canonical_value(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _canonical_value(item) for key, item in value.items()}
    return value


def canonical_record_digest(value: dict[str, object]) -> str:
    payload = json.dumps(
        _canonical_value(value),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


class ThesisContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class HistoricalMarketObservation(ThesisContract):
    instrument_id: str = Field(min_length=1)
    timestamp: datetime
    available_at: datetime
    close: Decimal | None
    adjusted_close: Decimal | None
    volume: Decimal | None
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    source_id: str = Field(min_length=1)
    fixture_revision: str = Field(min_length=1)
    content_digest: str = Field(pattern=SHA256_PATTERN)
    units: tuple[str, ...] = Field(min_length=1)
    quality_state: Literal["complete", "warning", "missing"]
    limitations: tuple[str, ...] = Field(min_length=1)
    synthetic: Literal[True]
    evidence_ref: str = Field(min_length=1)

    _timestamp = field_validator("timestamp")(utc_datetime)
    _available_at = field_validator("available_at")(utc_datetime)
    _close = field_validator("close")(finite_decimal)
    _adjusted_close = field_validator("adjusted_close")(finite_decimal)
    _volume = field_validator("volume")(finite_decimal)

    @model_validator(mode="after")
    def validate_observation(self) -> "HistoricalMarketObservation":
        if self.available_at <= self.timestamp:
            raise ValueError("available_at must be later than timestamp")
        if self.close is None and self.quality_state != "missing":
            raise ValueError("a missing close requires quality_state=missing")
        if self.close is not None and self.close <= 0:
            raise ValueError("close must be positive when present")
        expected = canonical_record_digest(
            self.model_dump(mode="python", exclude={"content_digest"})
        )
        if self.content_digest != expected:
            raise ValueError("content_digest must equal the canonical market-record digest")
        return self


class HistoricalEventObservation(ThesisContract):
    event_id: str = Field(min_length=1)
    event_time: datetime
    available_at: datetime
    entity_id: str = Field(min_length=1)
    instrument_ids: tuple[str, ...] = Field(min_length=1)
    headline: str = Field(min_length=1)
    short_text: str = Field(min_length=1)
    sentiment: Literal["positive", "negative", "neutral"]
    relevance: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    source_id: str = Field(min_length=1)
    fixture_revision: str = Field(min_length=1)
    content_digest: str = Field(pattern=SHA256_PATTERN)
    units: tuple[str, ...] = Field(min_length=1)
    quality_state: Literal["complete", "warning", "missing"]
    limitations: tuple[str, ...] = Field(min_length=1)
    evidence_ref: str = Field(min_length=1)
    synthetic: Literal[True]

    _event_time = field_validator("event_time")(utc_datetime)
    _available_at = field_validator("available_at")(utc_datetime)
    _relevance = field_validator("relevance")(finite_decimal)

    @field_validator("instrument_ids")
    @classmethod
    def explicit_instruments(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("event instrument IDs must be distinct")
        return tuple(sorted(values))

    @model_validator(mode="after")
    def canonical_provenance_digest(self) -> "HistoricalEventObservation":
        expected = canonical_record_digest(
            self.model_dump(mode="python", exclude={"content_digest"})
        )
        if self.content_digest != expected:
            raise ValueError("content_digest must equal the canonical event-record digest")
        return self


class FixedPosition(ThesisContract):
    instrument_id: str = Field(min_length=1)
    quantity: Decimal

    _quantity = field_validator("quantity")(finite_decimal)

    @model_validator(mode="after")
    def positive_quantity(self) -> "FixedPosition":
        if self.quantity <= 0:
            raise ValueError("fixed position quantity must be positive")
        return self


class CashAmount(ThesisContract):
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    amount: Decimal = Field(ge=Decimal("0"))

    _amount = field_validator("amount")(finite_decimal)


class RiskThreshold(ThesisContract):
    threshold_id: str = Field(min_length=1)
    value: Decimal

    _value = field_validator("value")(finite_decimal)


class PortfolioDefinition(ThesisContract):
    portfolio_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    base_currency: str = Field(pattern=r"^[A-Z]{3}$")
    start_date: date
    positions: tuple[FixedPosition, ...] = Field(min_length=5, max_length=8)
    cash: tuple[CashAmount, ...] = Field(min_length=1)
    benchmark_id: str | None = Field(default=None, min_length=1)
    benchmark_unavailable: bool = False
    risk_thresholds: tuple[RiskThreshold, ...] = ()

    @field_validator("positions")
    @classmethod
    def unique_positions(cls, values: tuple[FixedPosition, ...]) -> tuple[FixedPosition, ...]:
        ids = [item.instrument_id for item in values]
        if len(ids) != len(set(ids)):
            raise ValueError("portfolio positions must be distinct")
        return tuple(sorted(values, key=lambda item: item.instrument_id))

    @field_validator("cash")
    @classmethod
    def unique_cash(cls, values: tuple[CashAmount, ...]) -> tuple[CashAmount, ...]:
        currencies = [item.currency for item in values]
        if len(currencies) != len(set(currencies)):
            raise ValueError("cash currencies must be distinct")
        return tuple(sorted(values, key=lambda item: item.currency))

    @model_validator(mode="after")
    def explicit_benchmark_state(self) -> "PortfolioDefinition":
        if (self.benchmark_id is None) == (not self.benchmark_unavailable):
            raise ValueError(
                "exactly one of benchmark_id or benchmark_unavailable=true is required"
            )
        return self


class CandidateArtifactReference(ThesisContract):
    path: Path
    sha256: str = Field(pattern=SHA256_PATTERN)
    artifact_id: str = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def absolute_candidate_artifact(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("candidate artifact path must be absolute")
        return value


class ReviewedPositionSelection(ThesisContract):
    candidate_id: str = Field(min_length=1)
    instrument_alias: str = Field(
        pattern=r"^[a-z][a-z0-9-]{2,63}$"
    )
    quantity: Decimal

    @field_validator("quantity", mode="before")
    @classmethod
    def decimal_quantity(cls, value: object) -> Decimal:
        if isinstance(value, bool) or isinstance(value, float):
            raise ValueError("quantity must be an explicit Decimal, not binary float")
        try:
            result = Decimal(str(value))
        except Exception as error:
            raise ValueError("quantity must be an explicit Decimal") from error
        if (
            not result.is_finite()
            or result <= 0
            or result != result.to_integral_value()
        ):
            raise ValueError("quantity must be a fixed positive integer")
        return result

    @model_validator(mode="after")
    def private_neutral_alias(self) -> "ReviewedPositionSelection":
        lowered = self.instrument_alias.casefold()
        if "permno" in lowered or "gvkey" in lowered:
            raise ValueError("instrument alias must be private-neutral")
        return self


class ReviewedPortfolioSelection(ThesisContract):
    portfolio_id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    title: str = Field(min_length=1)
    base_currency: str = Field(pattern=r"^[A-Z]{3}$")
    benchmark_id: str | None = Field(default=None, min_length=1)
    benchmark_unavailable: bool = False
    cash: tuple[CashAmount, ...] = Field(min_length=1)
    positions: tuple[ReviewedPositionSelection, ...] = Field(
        min_length=5, max_length=8
    )

    @field_validator("cash")
    @classmethod
    def explicit_unique_cash(
        cls, values: tuple[CashAmount, ...]
    ) -> tuple[CashAmount, ...]:
        currencies = [item.currency for item in values]
        if len(currencies) != len(set(currencies)):
            raise ValueError("cash currencies must be distinct")
        return tuple(sorted(values, key=lambda item: item.currency))

    @field_validator("positions")
    @classmethod
    def explicit_unique_positions(
        cls, values: tuple[ReviewedPositionSelection, ...]
    ) -> tuple[ReviewedPositionSelection, ...]:
        candidate_ids = [item.candidate_id for item in values]
        aliases = [item.instrument_alias for item in values]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("portfolio candidates must be distinct")
        if len(aliases) != len(set(aliases)):
            raise ValueError("portfolio instrument aliases must be distinct")
        return tuple(sorted(values, key=lambda item: item.instrument_alias))

    @model_validator(mode="after")
    def explicit_benchmark_state(self) -> "ReviewedPortfolioSelection":
        if (self.benchmark_id is None) == (not self.benchmark_unavailable):
            raise ValueError(
                "exactly one of benchmark_id or benchmark_unavailable=true is required"
            )
        return self


class RealPortfolioSelectionManifest(ThesisContract):
    selection_version: str = Field(pattern=r"^[0-9]+\.[0-9]+$")
    selection_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
    reviewed: Literal[True]
    reviewer_id: str = Field(min_length=1)
    reviewed_at: datetime
    candidate_artifact: CandidateArtifactReference
    source_snapshot_id: str = Field(min_length=1)
    as_of: datetime
    effective_at: datetime
    rationale: str = Field(min_length=1)
    warnings: tuple[str, ...] = Field(min_length=1)
    portfolios: tuple[ReviewedPortfolioSelection, ...] = Field(min_length=1)

    _reviewed_at = field_validator("reviewed_at")(utc_datetime)
    _as_of = field_validator("as_of")(utc_datetime)
    _effective_at = field_validator("effective_at")(utc_datetime)

    @field_validator("warnings")
    @classmethod
    def explicit_review_warnings(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("review warnings must be explicit non-empty statements")
        return values

    @field_validator("portfolios")
    @classmethod
    def unique_portfolios(
        cls, values: tuple[ReviewedPortfolioSelection, ...]
    ) -> tuple[ReviewedPortfolioSelection, ...]:
        ids = [item.portfolio_id for item in values]
        if len(ids) != len(set(ids)):
            raise ValueError("reviewed portfolio IDs must be distinct")
        return tuple(sorted(values, key=lambda item: item.portfolio_id))

    @model_validator(mode="after")
    def point_in_time_selection(self) -> "RealPortfolioSelectionManifest":
        if self.as_of > self.effective_at:
            raise ValueError("selection as_of must not be later than effective_at")
        return self


class PortfolioMaterializationReceipt(ThesisContract):
    receipt_version: Literal["1.0"] = "1.0"
    receipt_id: str = Field(pattern=r"^portfolio_receipt_[0-9a-f]{24}$")
    selection_id: str = Field(min_length=1)
    selection_digest: str = Field(pattern=SHA256_PATTERN)
    reviewer_id: str = Field(min_length=1)
    reviewed_at: datetime
    effective_at: datetime
    candidate_artifact: CandidateArtifactReference
    source_snapshot_id: str = Field(min_length=1)
    as_of: datetime
    rationale: str = Field(min_length=1)
    warnings: tuple[str, ...] = Field(min_length=1)
    output_directory: Path
    portfolio_definition_digests: dict[str, str] = Field(min_length=1)
    private_instrument_map_digest: str = Field(pattern=SHA256_PATTERN)
    portfolio_count: int = Field(ge=1)
    effects: tuple[str, ...] = Field(default=(), max_length=0)
    limitations: tuple[str, ...] = Field(min_length=1)

    _receipt_reviewed_at = field_validator("reviewed_at")(utc_datetime)
    _receipt_effective_at = field_validator("effective_at")(utc_datetime)
    _receipt_as_of = field_validator("as_of")(utc_datetime)

    @field_validator("output_directory")
    @classmethod
    def absolute_output_directory(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("receipt output directory must be absolute")
        return value

    @field_validator("portfolio_definition_digests")
    @classmethod
    def canonical_portfolio_digests(cls, values: dict[str, str]) -> dict[str, str]:
        import re

        if any(re.fullmatch(SHA256_PATTERN, value) is None for value in values.values()):
            raise ValueError("portfolio definition digests must use canonical SHA-256")
        return dict(sorted(values.items()))

    @field_validator("warnings")
    @classmethod
    def explicit_receipt_warnings(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("receipt warnings must be explicit non-empty statements")
        return values

    @model_validator(mode="after")
    def aligned_portfolio_count(self) -> "PortfolioMaterializationReceipt":
        if self.portfolio_count != len(self.portfolio_definition_digests):
            raise ValueError(
                "portfolio_count must match portfolio definition digests"
            )
        if self.as_of > self.effective_at:
            raise ValueError("receipt as_of must not be later than effective_at")
        return self


class DatasetMetadata(ThesisContract):
    dataset_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    profile: Literal["synthetic_local", "licensed_local"] = "synthetic_local"
    publication_state: Literal[
        "synthetic_reviewed", "private_local_only"
    ] = "synthetic_reviewed"
    synthetic: bool
    source_paths: tuple[str, ...] = Field(min_length=1)
    source_digests: tuple[str, ...] = Field(min_length=1)
    row_counts: tuple[int, ...] = Field(min_length=1)
    coverage_start: datetime
    coverage_end: datetime
    required_columns: tuple[str, ...] = Field(min_length=1)
    quality_warnings: tuple[str, ...] = ()

    _coverage_start = field_validator("coverage_start")(utc_datetime)
    _coverage_end = field_validator("coverage_end")(utc_datetime)

    @field_validator("source_digests")
    @classmethod
    def canonical_digests(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        import re

        if any(re.fullmatch(SHA256_PATTERN, value) is None for value in values):
            raise ValueError("source digests must use canonical SHA-256")
        return values

    @model_validator(mode="after")
    def aligned_sources(self) -> "DatasetMetadata":
        if not (len(self.source_paths) == len(self.source_digests) == len(self.row_counts)):
            raise ValueError("source paths, digests and row counts must align")
        if self.coverage_end < self.coverage_start:
            raise ValueError("dataset coverage is reversed")
        if self.profile == "synthetic_local" and (
            not self.synthetic or self.publication_state != "synthetic_reviewed"
        ):
            raise ValueError("synthetic_local requires reviewed synthetic disclosure")
        if self.profile == "licensed_local" and (
            self.synthetic or self.publication_state != "private_local_only"
        ):
            raise ValueError("licensed_local requires private_local_only non-synthetic data")
        return self


class ReplaySpecification(ThesisContract):
    experiment_id: str = Field(min_length=1)
    portfolio_id: str = Field(min_length=1)
    dataset_revision: str = Field(min_length=1)
    start: datetime
    end: datetime
    cadence: Literal["daily"]
    review_time: time
    lookback: int = Field(ge=1)
    no_look_ahead_rule: Literal["available_at <= as_of"]
    deterministic_seed: int = Field(ge=0)

    _start = field_validator("start")(utc_datetime)
    _end = field_validator("end")(utc_datetime)
    _review_time = field_validator("review_time")(utc_time)

    @model_validator(mode="after")
    def ordered_range(self) -> "ReplaySpecification":
        if self.end < self.start:
            raise ValueError("replay end must not precede start")
        return self


class HistoricalStep(ThesisContract):
    run_id: str = Field(pattern=SHA256_PATTERN)
    ordinal: int = Field(ge=0)
    previous_as_of: datetime | None
    as_of: datetime
    newly_eligible_market_records: tuple[HistoricalMarketObservation, ...] = ()
    newly_eligible_event_records: tuple[HistoricalEventObservation, ...] = ()
    latest_eligible_market_records: tuple[HistoricalMarketObservation, ...] = ()
    evidence_references: tuple[str, ...] = ()

    _previous_as_of = field_validator("previous_as_of")(lambda value: utc_datetime(value) if value else None)
    _as_of = field_validator("as_of")(utc_datetime)
