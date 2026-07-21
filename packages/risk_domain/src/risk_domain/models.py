"""Immutable Day 0 portfolio-risk domain contracts."""

from __future__ import annotations

from datetime import datetime
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from enum import Enum
import re
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .common import CurrencyCode, ImmutableDomainModel, NonEmptyString, UtcTimestampModel, decimal_value, normalize_utc, validate_currency
from .digests import sha256_digest


SHA256_DIGEST_PATTERN = r"sha256:[a-f0-9]{64}"
EXPOSURE_DECIMAL_CONTEXT = Context(prec=34, rounding=ROUND_HALF_EVEN)


class QualityFlag(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"
    STALE = "stale"
    ESTIMATED = "estimated"


class SourceReference(ImmutableDomainModel):
    source_id: NonEmptyString
    source_type: NonEmptyString
    reference: NonEmptyString
    retrieved_at: datetime

    _retrieved_at = field_validator("retrieved_at")(normalize_utc)


class InstrumentIdentifier(ImmutableDomainModel):
    identifier_type: Literal["ticker", "permno", "gvkey", "cusip", "cik"]
    value: NonEmptyString


class Instrument(ImmutableDomainModel):
    instrument_id: NonEmptyString
    name: NonEmptyString
    identifiers: tuple[InstrumentIdentifier, ...]

    @field_validator("identifiers")
    @classmethod
    def identifiers_are_present_and_distinct(
        cls, values: tuple[InstrumentIdentifier, ...]
    ) -> tuple[InstrumentIdentifier, ...]:
        if not values:
            raise ValueError("instruments require at least one identifier")
        kinds = [item.identifier_type for item in values]
        if len(kinds) != len(set(kinds)):
            raise ValueError("instrument identifier types must remain distinct")
        return tuple(sorted(values, key=lambda item: item.identifier_type))


class Position(ImmutableDomainModel):
    instrument_id: NonEmptyString
    quantity: Decimal
    price: Decimal
    market_value: Decimal
    currency: CurrencyCode

    _quantity = field_validator("quantity")(decimal_value)
    _price = field_validator("price")(decimal_value)
    _market_value = field_validator("market_value")(decimal_value)

    @field_validator("currency")
    @classmethod
    def supported_currency(cls, value: str) -> str:
        return validate_currency(value)

    @model_validator(mode="after")
    def market_value_matches_quantity_and_price(self) -> "Position":
        # Day 0 policy permits a cent-level difference in the position currency.
        if abs(self.market_value - (self.quantity * self.price)) > Decimal("0.01"):
            raise ValueError("market_value must equal quantity multiplied by price within 0.01")
        return self


class CashBalance(ImmutableDomainModel):
    currency: CurrencyCode
    amount: Decimal

    _amount = field_validator("amount")(decimal_value)
    _currency = field_validator("currency")(validate_currency)


class DatasetFile(ImmutableDomainModel):
    """A materialized dataset artifact referenced by an immutable snapshot."""

    path: NonEmptyString
    media_type: NonEmptyString
    size: int = Field(ge=0)
    digest: str = Field(pattern=rf"^{SHA256_DIGEST_PATTERN}$")
    row_count: int = Field(ge=0)


class DatasetProvenance(ImmutableDomainModel):
    """Origin metadata retained with a dataset, including synthetic lineage."""

    synthetic: bool
    synthetic_label: Literal["synthetic"] | None = None
    synthetic_seed: int | None = Field(default=None, ge=0)
    sources: tuple[SourceReference, ...] = ()

    @model_validator(mode="after")
    def synthetic_lineage_is_explicit(self) -> "DatasetProvenance":
        if self.synthetic and (self.synthetic_label != "synthetic" or self.synthetic_seed is None):
            raise ValueError("synthetic dataset provenance requires a synthetic label and seed")
        if not self.synthetic and (self.synthetic_label is not None or self.synthetic_seed is not None):
            raise ValueError("non-synthetic dataset provenance cannot include synthetic metadata")
        return self


class DatasetSnapshot(UtcTimestampModel):
    """Immutable dataset manifest linked to its ingestion runs and source queries."""

    snapshot_id: NonEmptyString
    created_at: datetime
    files: tuple[DatasetFile, ...]
    ingestion_run_ids: tuple[NonEmptyString, ...]
    source_query_digests: tuple[str, ...]
    provenance: DatasetProvenance
    digest: str | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    _created_at = field_validator("created_at")(normalize_utc)

    @field_validator("files")
    @classmethod
    def files_are_present_and_ordered(cls, values: tuple[DatasetFile, ...]) -> tuple[DatasetFile, ...]:
        if not values:
            raise ValueError("dataset snapshots require at least one file")
        paths = [item.path for item in values]
        if len(paths) != len(set(paths)):
            raise ValueError("dataset file paths must remain unique")
        return tuple(sorted(values, key=lambda item: item.path))

    @field_validator("ingestion_run_ids")
    @classmethod
    def ingestion_runs_are_present_and_ordered(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("dataset snapshots require at least one ingestion run reference")
        if len(values) != len(set(values)):
            raise ValueError("dataset ingestion run references must remain unique")
        return tuple(sorted(values))

    @field_validator("source_query_digests")
    @classmethod
    def source_queries_are_present_and_ordered(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("dataset snapshots require at least one source query digest")
        if any(not re.fullmatch(SHA256_DIGEST_PATTERN, value) for value in values):
            raise ValueError("source query digests must be SHA-256 digests")
        if len(values) != len(set(values)):
            raise ValueError("source query digests must remain unique")
        return tuple(sorted(values))

    @model_validator(mode="after")
    def content_addressed_digest(self) -> "DatasetSnapshot":
        expected = sha256_digest(self)
        if self.digest is not None and self.digest != expected:
            raise ValueError("digest must equal the canonical snapshot digest")
        object.__setattr__(self, "digest", expected)
        return self


class MarketObservation(UtcTimestampModel):
    instrument_id: NonEmptyString
    observed_at: datetime
    price: Decimal | None = None
    currency: CurrencyCode
    synthetic: bool
    quality_flags: tuple[QualityFlag, ...] = ()
    sources: tuple[SourceReference, ...] = ()

    @field_validator("price")
    @classmethod
    def price_is_finite_when_present(cls, value: Decimal | None) -> Decimal | None:
        return decimal_value(value) if value is not None else None

    _currency = field_validator("currency")(validate_currency)

    @model_validator(mode="after")
    def missing_price_is_explicit(self) -> "MarketObservation":
        if self.price is None and QualityFlag.MISSING not in self.quality_flags:
            raise ValueError("missing market observations require the missing quality flag")
        return self


class FundamentalObservation(UtcTimestampModel):
    instrument_id: NonEmptyString
    metric: NonEmptyString
    observed_at: datetime
    value: Decimal | None = None
    unit: NonEmptyString
    synthetic: bool
    quality_flags: tuple[QualityFlag, ...] = ()
    sources: tuple[SourceReference, ...] = ()

    @field_validator("value")
    @classmethod
    def fundamental_value_is_finite_when_present(cls, value: Decimal | None) -> Decimal | None:
        return decimal_value(value) if value is not None else None

    @model_validator(mode="after")
    def missing_value_is_explicit(self) -> "FundamentalObservation":
        if self.value is None and QualityFlag.MISSING not in self.quality_flags:
            raise ValueError("missing fundamental observations require the missing quality flag")
        return self


class PortfolioSnapshot(UtcTimestampModel):
    snapshot_id: NonEmptyString
    as_of: datetime
    base_currency: CurrencyCode
    positions: tuple[Position, ...] = ()
    cash_balances: tuple[CashBalance, ...] = ()
    market_observations: tuple[MarketObservation, ...] = ()
    fundamental_observations: tuple[FundamentalObservation, ...] = ()
    sources: tuple[SourceReference, ...] = ()
    digest: str | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    _base_currency = field_validator("base_currency")(validate_currency)

    @field_validator("positions")
    @classmethod
    def positions_are_unique_and_ordered(cls, values: tuple[Position, ...]) -> tuple[Position, ...]:
        ids = [position.instrument_id for position in values]
        if len(ids) != len(set(ids)):
            raise ValueError("portfolio positions must have unique instrument IDs")
        return tuple(sorted(values, key=lambda position: position.instrument_id))

    @field_validator("cash_balances")
    @classmethod
    def cash_is_unique_and_ordered(cls, values: tuple[CashBalance, ...]) -> tuple[CashBalance, ...]:
        currencies = [balance.currency for balance in values]
        if len(currencies) != len(set(currencies)):
            raise ValueError("cash balances must have unique currencies")
        return tuple(sorted(values, key=lambda balance: balance.currency))

    @model_validator(mode="after")
    def content_addressed_digest(self) -> "PortfolioSnapshot":
        expected = sha256_digest(self)
        if self.digest is not None and self.digest != expected:
            raise ValueError("digest must equal the canonical snapshot digest")
        object.__setattr__(self, "digest", expected)
        return self


class PositionExposure(ImmutableDomainModel):
    """A position market value and its signed share of portfolio NAV."""

    instrument_id: NonEmptyString
    market_value: Decimal
    weight: Decimal = Field(description="Signed market value divided by portfolio NAV, which includes cash.")

    _market_value = field_validator("market_value")(decimal_value)
    _weight = field_validator("weight")(decimal_value)


class ConcentrationMeasure(ImmutableDomainModel):
    """A named Decimal concentration statistic for an exposure snapshot."""

    name: NonEmptyString
    value: Decimal

    _value = field_validator("value")(decimal_value)


class ExposureSnapshot(UtcTimestampModel):
    """Immutable exposure calculation derived from exactly one portfolio snapshot.

    Gross exposure is the sum of absolute position market values divided by NAV.
    Net exposure is the sum of signed position market values divided by NAV.
    Cash is excluded from gross and net exposure but included in NAV and cash weight.
    """

    snapshot_id: NonEmptyString
    as_of: datetime
    portfolio_snapshot: PortfolioSnapshot
    nav: Decimal = Field(description="Portfolio NAV: positions plus cash, all in the portfolio base currency.")
    gross_exposure: Decimal = Field(description="Sum of absolute position market values divided by NAV; cash excluded.")
    net_exposure: Decimal = Field(description="Sum of signed position market values divided by NAV; cash excluded.")
    largest_position_weight: Decimal = Field(description="Largest absolute signed position weight; cash excluded.")
    cash_weight: Decimal = Field(description="Total cash divided by NAV.")
    position_exposures: tuple[PositionExposure, ...]
    concentration_measures: tuple[ConcentrationMeasure, ...] = ()
    digest: str | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    _nav = field_validator("nav")(decimal_value)
    _gross_exposure = field_validator("gross_exposure")(decimal_value)
    _net_exposure = field_validator("net_exposure")(decimal_value)
    _largest_position_weight = field_validator("largest_position_weight")(decimal_value)
    _cash_weight = field_validator("cash_weight")(decimal_value)

    @field_validator("position_exposures")
    @classmethod
    def position_exposures_are_unique_and_ordered(
        cls, values: tuple[PositionExposure, ...]
    ) -> tuple[PositionExposure, ...]:
        ids = [item.instrument_id for item in values]
        if len(ids) != len(set(ids)):
            raise ValueError("position exposures must have unique instrument IDs")
        return tuple(sorted(values, key=lambda item: item.instrument_id))

    @field_validator("concentration_measures")
    @classmethod
    def concentration_measures_are_unique_and_ordered(
        cls, values: tuple[ConcentrationMeasure, ...]
    ) -> tuple[ConcentrationMeasure, ...]:
        names = [item.name for item in values]
        if len(names) != len(set(names)):
            raise ValueError("concentration measure names must remain unique")
        return tuple(sorted(values, key=lambda item: item.name))

    @model_validator(mode="after")
    def values_match_portfolio_snapshot(self) -> "ExposureSnapshot":
        portfolio = self.portfolio_snapshot
        if self.as_of != portfolio.as_of:
            raise ValueError("exposure snapshot as_of must equal its portfolio snapshot as_of")
        if any(position.currency != portfolio.base_currency for position in portfolio.positions):
            raise ValueError("exposure calculations require position market values in the portfolio base currency")
        if any(balance.currency != portfolio.base_currency for balance in portfolio.cash_balances):
            raise ValueError("exposure calculations require cash balances in the portfolio base currency")

        position_values = {position.instrument_id: position.market_value for position in portfolio.positions}
        exposure_values = {exposure.instrument_id: exposure for exposure in self.position_exposures}
        if set(exposure_values) != set(position_values):
            raise ValueError("position exposures must reference exactly the source portfolio positions")

        # Use a fixed local context so validation and content digests are not
        # affected by a caller's mutable process-wide Decimal context.
        with localcontext(EXPOSURE_DECIMAL_CONTEXT):
            expected_nav = sum(position_values.values(), start=Decimal("0")) + sum(
                (balance.amount for balance in portfolio.cash_balances), start=Decimal("0")
            )
            expected_weights = {
                instrument_id: market_value / expected_nav
                for instrument_id, market_value in position_values.items()
            } if expected_nav > 0 else {}
            expected_gross = sum((abs(weight) for weight in expected_weights.values()), start=Decimal("0"))
            expected_net = sum(expected_weights.values(), start=Decimal("0"))
            expected_largest = max((abs(weight) for weight in expected_weights.values()), default=Decimal("0"))
            expected_cash_weight = sum(
                (balance.amount for balance in portfolio.cash_balances), start=Decimal("0")
            ) / expected_nav if expected_nav > 0 else Decimal("0")
        if expected_nav <= 0:
            raise ValueError("portfolio NAV must be positive for exposure calculations")
        if self.nav != expected_nav:
            raise ValueError("nav must equal source position market values plus cash")
        for instrument_id, exposure in exposure_values.items():
            if exposure.market_value != position_values[instrument_id] or exposure.weight != expected_weights[instrument_id]:
                raise ValueError("position exposure weights and market values must match the source portfolio")
        if (self.gross_exposure, self.net_exposure, self.largest_position_weight, self.cash_weight) != (
            expected_gross,
            expected_net,
            expected_largest,
            expected_cash_weight,
        ):
            raise ValueError("exposure summary weights must match the source portfolio and NAV")

        expected_digest = sha256_digest(self)
        if self.digest is not None and self.digest != expected_digest:
            raise ValueError("digest must equal the canonical snapshot digest")
        object.__setattr__(self, "digest", expected_digest)
        return self
