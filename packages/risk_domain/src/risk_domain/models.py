"""Immutable Day 0 portfolio-risk domain contracts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .common import CurrencyCode, ImmutableDomainModel, NonEmptyString, UtcTimestampModel, decimal_value, normalize_utc, validate_currency
from .digests import sha256_digest


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
    digest: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")

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
