"""Shared immutable validation primitives for the risk-domain contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


ISO_4217_CODES = frozenset(
    "AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BOV BRL BSD BTN BWP BYN BZD CAD CDF CHE CHF CHW CLF CLP CNY COP COU CRC CUC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HRK HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MXV MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS UAH UGX USD USN UYI UYU UYW UZS VED VES VND VUV WST XAD XAF XAG XAU XBA XBB XBC XBD XCD XCG XDR XOF XPD XPF XPT XSU XTS XUA XXX YER ZAR ZMW ZWG".split()
)

CurrencyCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
NonEmptyString = Annotated[str, Field(min_length=1, max_length=256)]


class ImmutableDomainModel(BaseModel):
    """Strict frozen base model for persisted risk-domain values."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


def normalize_utc(value: datetime) -> datetime:
    """Reject naive datetimes and normalize offset-aware values to UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC)


def decimal_value(value: Decimal) -> Decimal:
    """Reject non-finite financial values without converting precision."""
    if not value.is_finite():
        raise ValueError("financial values must be finite Decimal values")
    return value


def validate_currency(value: str) -> str:
    """Require an assigned ISO 4217 alphabetic code."""
    if value not in ISO_4217_CODES:
        raise ValueError("currency must be a supported ISO 4217 code")
    return value


class UtcTimestampModel(ImmutableDomainModel):
    """Mixin for contracts which carry a canonical observation timestamp."""

    @field_validator("observed_at", "as_of", check_fields=False)
    @classmethod
    def timestamps_are_utc(cls, value: datetime) -> datetime:
        return normalize_utc(value)
