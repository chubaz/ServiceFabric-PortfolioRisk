from datetime import UTC, datetime
from decimal import Decimal

from risk_domain import PortfolioSnapshot, Position


NOW = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)


def test_snapshot_digest_is_deterministic_and_excludes_its_own_field() -> None:
    first = PortfolioSnapshot(snapshot_id="snapshot-a", as_of=NOW, base_currency="USD", positions=(Position(instrument_id="instrument-b", quantity=Decimal("1"), price=Decimal("2.50"), market_value=Decimal("2.50"), currency="USD"), Position(instrument_id="instrument-a", quantity=Decimal("1"), price=Decimal("3.00"), market_value=Decimal("3.00"), currency="USD")))
    second = PortfolioSnapshot.model_validate(first.model_dump())

    assert first.digest == second.digest
    assert first.digest is not None
