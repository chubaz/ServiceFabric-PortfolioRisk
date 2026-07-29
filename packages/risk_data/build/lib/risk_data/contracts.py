"""Immutable, provider-neutral contracts for Day 0 data ingestion."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from risk_domain import FundamentalObservation, InstrumentIdentifier, MarketObservation, QualityFlag, SourceReference
from risk_domain.common import validate_currency
from risk_domain.digests import sha256_digest


FIXTURE_SEED = 20260721
SYNTHETIC_LABEL = "synthetic"


class ConnectorDisabledError(RuntimeError):
    """Raised when a connector is intentionally unavailable in the current wave."""


class PortfolioInputFormat(str, Enum):
    CSV = "csv"
    YAML = "yaml"


def _portfolio_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC)


class PortfolioInputContract(BaseModel):
    """Strict frozen base for Day 1 portfolio-input contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class PortfolioInputIssue(PortfolioInputContract):
    """A visible parsing, validation, or data-quality issue for a portfolio preview."""

    code: str
    message: str
    severity: Literal["warning", "error"]
    location: str | None = None


class PortfolioInputPosition(PortfolioInputContract):
    """An unvalued user-supplied holding; a price is deliberately absent."""

    instrument_id: str
    quantity: Decimal
    currency: str | None = None

    @field_validator("instrument_id")
    @classmethod
    def instrument_id_is_present(cls, value: str) -> str:
        if not value or len(value) > 128:
            raise ValueError("instrument_id must be present and at most 128 characters")
        return value

    @field_validator("quantity")
    @classmethod
    def quantity_is_finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("quantity must be a finite Decimal")
        return value

    @field_validator("currency")
    @classmethod
    def optional_currency_is_valid(cls, value: str | None) -> str | None:
        return validate_currency(value) if value is not None else None


class PortfolioInputCashBalance(PortfolioInputContract):
    currency: str
    amount: Decimal

    _currency = field_validator("currency")(validate_currency)

    @field_validator("amount")
    @classmethod
    def amount_is_finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("cash amount must be a finite Decimal")
        return value


class PortfolioInputDocument(PortfolioInputContract):
    """Normalized input only: it intentionally retains no raw personal bytes."""

    input_format: PortfolioInputFormat
    profile: Literal["research", "personal_portfolio"]
    as_of: datetime
    base_currency: str
    positions: tuple[PortfolioInputPosition, ...]
    cash_balances: tuple[PortfolioInputCashBalance, ...] = ()
    content_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")

    _as_of = field_validator("as_of")(_portfolio_utc)
    _base_currency = field_validator("base_currency")(validate_currency)

    @field_validator("positions")
    @classmethod
    def positions_are_unique_and_ordered(cls, values: tuple[PortfolioInputPosition, ...]) -> tuple[PortfolioInputPosition, ...]:
        ids = [value.instrument_id for value in values]
        if not values:
            raise ValueError("portfolio input requires at least one position")
        if len(ids) != len(set(ids)):
            raise ValueError("portfolio input positions must have distinct instrument IDs")
        return tuple(sorted(values, key=lambda value: value.instrument_id))

    @field_validator("cash_balances")
    @classmethod
    def cash_is_unique_and_ordered(cls, values: tuple[PortfolioInputCashBalance, ...]) -> tuple[PortfolioInputCashBalance, ...]:
        currencies = [value.currency for value in values]
        if len(currencies) != len(set(currencies)):
            raise ValueError("cash balances must have distinct currencies")
        return tuple(sorted(values, key=lambda value: value.currency))


class PortfolioInputPreview(PortfolioInputContract):
    document: PortfolioInputDocument | None = None
    issues: tuple[PortfolioInputIssue, ...] = ()
    quality_flags: tuple[str, ...] = ()
    preview_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")

    @property
    def valid(self) -> bool:
        return self.document is not None and not any(issue.severity == "error" for issue in self.issues)


class PortfolioConfirmationRequest(PortfolioInputContract):
    confirm: bool
    preview_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")


class PortfolioConfirmationResult(PortfolioInputContract):
    snapshot_id: str
    snapshot_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    created: bool
    quality_flags: tuple[str, ...] = ()


class SnapshotPositionChange(PortfolioInputContract):
    instrument_id: str
    change_type: Literal["added", "removed", "changed"]
    left_quantity: Decimal | None = None
    right_quantity: Decimal | None = None


class SnapshotComparison(PortfolioInputContract):
    left_snapshot_id: str
    right_snapshot_id: str
    position_changes: tuple[SnapshotPositionChange, ...]
    cash_changes: tuple[PortfolioInputCashBalance, ...] = ()
    valuation_context: str
    evidence: tuple[str, ...]
    limitations: tuple[str, ...]


class DataQualityCode(str, Enum):
    DUPLICATE = "duplicate"
    STALE = "stale"
    MISSING = "missing"
    INVALID_IDENTIFIER = "invalid_identifier"


class DataContract(BaseModel):
    """Strict, frozen base model for persisted ingestion values."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC)


def _validate_identifier(value: InstrumentIdentifier) -> InstrumentIdentifier:
    if value.identifier_type == "ticker" and (not value.value.isupper() or not value.value.isalnum() or len(value.value) > 10):
        raise ValueError("ticker identifiers must be uppercase alphanumeric values of at most 10 characters")
    if value.identifier_type in {"permno", "gvkey"} and (not value.value.isdigit() or len(value.value) != 6):
        raise ValueError(f"{value.identifier_type} identifiers must contain exactly six digits")
    return value


class QuerySpec(DataContract):
    """A bounded provider-neutral request; it never carries credentials."""

    dataset: Literal["market", "fundamental"]
    instrument_ids: tuple[str, ...]
    start_at: datetime
    end_at: datetime
    include_duplicate_candidates: bool = True

    _start_at = field_validator("start_at")(_utc)
    _end_at = field_validator("end_at")(_utc)

    @field_validator("instrument_ids")
    @classmethod
    def instrument_ids_are_present_and_distinct(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("at least one instrument identifier is required")
        if any(not value.startswith("instrument-") or len(value) > 64 for value in values):
            raise ValueError("instrument identifiers must use the instrument- prefix")
        if len(values) != len(set(values)):
            raise ValueError("instrument identifiers must be distinct")
        return tuple(sorted(values))

    @model_validator(mode="after")
    def date_range_is_ordered(self) -> "QuerySpec":
        if self.start_at > self.end_at:
            raise ValueError("start_at must not be after end_at")
        return self


class DataQualityIssue(DataContract):
    code: DataQualityCode
    record_key: str
    message: str
    severity: Literal["warning", "error"]


class ValidationSummary(DataContract):
    issues: tuple[DataQualityIssue, ...] = ()

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    @property
    def duplicate_count(self) -> int:
        return sum(issue.code is DataQualityCode.DUPLICATE for issue in self.issues)


class NormalizedMarketRecord(DataContract):
    """A market candidate normalized without provider-specific fields."""

    instrument_id: str
    identifier: InstrumentIdentifier
    observed_at: datetime
    price: Decimal | None = None
    currency: str = "USD"
    synthetic: bool = True
    synthetic_label: Literal["synthetic"] = SYNTHETIC_LABEL
    fixture_seed: int = FIXTURE_SEED
    source_id: str = "synthetic-crsp-like"

    _observed_at = field_validator("observed_at")(_utc)
    _identifier = field_validator("identifier")(_validate_identifier)
    _currency = field_validator("currency")(validate_currency)

    @field_validator("instrument_id")
    @classmethod
    def valid_instrument_id(cls, value: str) -> str:
        if not value.startswith("instrument-"):
            raise ValueError("instrument identifiers must use the instrument- prefix")
        return value

    @field_validator("price")
    @classmethod
    def finite_price(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not value.is_finite():
            raise ValueError("price must be finite when present")
        return value

    @model_validator(mode="after")
    def synthetic_metadata_is_preserved(self) -> "NormalizedMarketRecord":
        if not self.synthetic or self.synthetic_label != SYNTHETIC_LABEL:
            raise ValueError("Day 0 fixture records must be explicitly synthetic")
        return self

    @property
    def record_key(self) -> str:
        return f"market:{self.instrument_id}:{self.observed_at.isoformat()}"

    def to_market_observation(self, flags: tuple[QualityFlag, ...] = ()) -> MarketObservation:
        quality_flags = flags or ((QualityFlag.MISSING,) if self.price is None else (QualityFlag.COMPLETE,))
        source = SourceReference(source_id=self.source_id, source_type="synthetic-fixture", reference=f"fixture://{self.source_id}/{self.fixture_seed}", retrieved_at=self.observed_at)
        return MarketObservation(instrument_id=self.instrument_id, observed_at=self.observed_at, price=self.price, currency=self.currency, synthetic=self.synthetic, quality_flags=quality_flags, sources=(source,))


class NormalizedFundamentalRecord(DataContract):
    """A fundamental candidate normalized without provider-specific fields."""

    instrument_id: str
    identifier: InstrumentIdentifier
    metric: str
    observed_at: datetime
    value: Decimal | None = None
    unit: str = "USD"
    synthetic: bool = True
    synthetic_label: Literal["synthetic"] = SYNTHETIC_LABEL
    fixture_seed: int = FIXTURE_SEED
    source_id: str = "synthetic-compustat-like"

    _observed_at = field_validator("observed_at")(_utc)
    _identifier = field_validator("identifier")(_validate_identifier)

    @field_validator("instrument_id")
    @classmethod
    def valid_instrument_id(cls, value: str) -> str:
        if not value.startswith("instrument-"):
            raise ValueError("instrument identifiers must use the instrument- prefix")
        return value

    @field_validator("value")
    @classmethod
    def finite_value(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not value.is_finite():
            raise ValueError("value must be finite when present")
        return value

    @model_validator(mode="after")
    def synthetic_metadata_is_preserved(self) -> "NormalizedFundamentalRecord":
        if not self.synthetic or self.synthetic_label != SYNTHETIC_LABEL:
            raise ValueError("Day 0 fixture records must be explicitly synthetic")
        return self

    @property
    def record_key(self) -> str:
        return f"fundamental:{self.instrument_id}:{self.metric}:{self.observed_at.isoformat()}"

    def to_fundamental_observation(self, flags: tuple[QualityFlag, ...] = ()) -> FundamentalObservation:
        quality_flags = flags or ((QualityFlag.MISSING,) if self.value is None else (QualityFlag.COMPLETE,))
        source = SourceReference(source_id=self.source_id, source_type="synthetic-fixture", reference=f"fixture://{self.source_id}/{self.fixture_seed}", retrieved_at=self.observed_at)
        return FundamentalObservation(instrument_id=self.instrument_id, metric=self.metric, observed_at=self.observed_at, value=self.value, unit=self.unit, synthetic=self.synthetic, quality_flags=quality_flags, sources=(source,))


NormalizedRecord = NormalizedMarketRecord | NormalizedFundamentalRecord


class DatasetSnapshot(DataContract):
    """Immutable, content-addressed set of normalized candidate records."""

    snapshot_id: str
    created_at: datetime
    records: tuple[NormalizedRecord, ...]
    synthetic: bool = True
    synthetic_label: Literal["synthetic"] = SYNTHETIC_LABEL
    digest: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")

    _created_at = field_validator("created_at")(_utc)

    @model_validator(mode="after")
    def content_addressed_digest(self) -> "DatasetSnapshot":
        if not self.synthetic or self.synthetic_label != SYNTHETIC_LABEL:
            raise ValueError("Day 0 dataset snapshots must be explicitly synthetic")
        expected = sha256_digest(self)
        if self.digest is not None and self.digest != expected:
            raise ValueError("digest must equal the canonical snapshot digest")
        object.__setattr__(self, "digest", expected)
        return self


class IngestionRun(DataContract):
    run_id: str
    connector_id: str
    query: QuerySpec
    started_at: datetime
    completed_at: datetime
    snapshot: DatasetSnapshot
    validation: ValidationSummary

    _started_at = field_validator("started_at")(_utc)
    _completed_at = field_validator("completed_at")(_utc)

    @model_validator(mode="after")
    def run_is_ordered(self) -> "IngestionRun":
        if self.completed_at < self.started_at:
            raise ValueError("completed_at must not be before started_at")
        return self


@runtime_checkable
class ConnectorProtocol(Protocol):
    """A provider adapter that returns normalized, immutable ingestion runs."""

    connector_id: str

    def ingest(self, query: QuerySpec) -> IngestionRun:
        """Collect a bounded query without exposing provider implementation details."""
