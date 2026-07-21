from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from risk_domain import (
    CashBalance,
    FundamentalObservation,
    Instrument,
    InstrumentIdentifier,
    MarketObservation,
    PortfolioSnapshot,
    Position,
    QualityFlag,
    SourceReference,
)


NOW = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)


def position(instrument_id: str = "instrument-a") -> Position:
    return Position(
        instrument_id=instrument_id,
        quantity=Decimal("2.00000001"),
        price=Decimal("123.45678901"),
        market_value=Decimal("246.9135792546910001"),
        currency="USD",
    )


def test_valid_construction_preserves_all_domain_contracts() -> None:
    source = SourceReference(source_id="synthetic-fixture", source_type="fixture", reference="fixture://day0", retrieved_at=NOW)
    identifier = InstrumentIdentifier(identifier_type="ticker", value="ACME")
    instrument = Instrument(instrument_id="instrument-a", name="Acme Incorporated", identifiers=(identifier,))
    cash = CashBalance(currency="USD", amount=Decimal("10.01"))
    market = MarketObservation(instrument_id=instrument.instrument_id, observed_at=NOW, price=Decimal("123.45678901"), currency="USD", synthetic=True, quality_flags=(QualityFlag.COMPLETE,), sources=(source,))
    fundamental = FundamentalObservation(instrument_id=instrument.instrument_id, metric="revenue", observed_at=NOW, value=Decimal("100.00000001"), unit="USD", synthetic=True, quality_flags=(QualityFlag.COMPLETE,), sources=(source,))
    snapshot = PortfolioSnapshot(snapshot_id="snapshot-a", as_of=NOW, base_currency="USD", positions=(position(),), cash_balances=(cash,), market_observations=(market,), fundamental_observations=(fundamental,), sources=(source,))

    assert snapshot.digest.startswith("sha256:")
    assert market.synthetic is True
    assert fundamental.synthetic is True


def test_models_are_immutable_and_snapshot_inputs_are_tuples() -> None:
    snapshot = PortfolioSnapshot(snapshot_id="snapshot-a", as_of=NOW, base_currency="USD", positions=[position()])
    assert isinstance(snapshot.positions, tuple)
    with pytest.raises(ValidationError):
        snapshot.snapshot_id = "changed"  # type: ignore[misc]


def test_positions_are_sorted_for_deterministic_input_ordering() -> None:
    snapshot = PortfolioSnapshot(snapshot_id="snapshot-a", as_of=NOW, base_currency="USD", positions=(position("instrument-z"), position("instrument-a")))
    assert [item.instrument_id for item in snapshot.positions] == ["instrument-a", "instrument-z"]


def test_duplicate_positions_and_invalid_values_are_rejected() -> None:
    with pytest.raises(ValidationError, match="unique instrument IDs"):
        PortfolioSnapshot(snapshot_id="snapshot-a", as_of=NOW, base_currency="USD", positions=(position(), position()))
    with pytest.raises(ValidationError, match="supported ISO 4217"):
        CashBalance(currency="ZZZ", amount=Decimal("1"))
    with pytest.raises(ValidationError, match="equal quantity"):
        Position(instrument_id="instrument-a", quantity=Decimal("2"), price=Decimal("2"), market_value=Decimal("3"), currency="USD")


def test_naive_timestamps_and_empty_identifiers_are_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        SourceReference(source_id="source", source_type="fixture", reference="fixture://day0", retrieved_at=datetime(2026, 1, 1))
    with pytest.raises(ValidationError):
        InstrumentIdentifier(identifier_type="ticker", value="")


def test_missing_values_remain_missing_and_are_explicitly_flagged() -> None:
    missing = MarketObservation(instrument_id="instrument-a", observed_at=NOW, price=None, currency="USD", synthetic=True, quality_flags=(QualityFlag.MISSING,))
    assert missing.price is None
    with pytest.raises(ValidationError, match="missing quality flag"):
        MarketObservation(instrument_id="instrument-a", observed_at=NOW, price=None, currency="USD", synthetic=False)


def test_decimal_precision_is_not_coerced_to_float() -> None:
    value = Decimal("123.45678901234567890123456789")
    cash = CashBalance(currency="USD", amount=value)
    assert cash.amount == value
