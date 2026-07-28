from datetime import UTC, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from portfolio_risk_thesis.contracts import (
    HistoricalMarketObservation,
    ReplaySpecification,
    canonical_record_digest,
)


def market(**updates):  # type: ignore[no-untyped-def]
    values = {
        "instrument_id": "instrument-fiction",
        "timestamp": datetime(2024, 1, 2, 16, tzinfo=UTC),
        "available_at": datetime(2024, 1, 2, 17, tzinfo=UTC),
        "close": Decimal("12.3400"),
        "adjusted_close": Decimal("12.3400"),
        "volume": Decimal("100"),
        "currency": "USD",
        "source_id": "synthetic-source",
        "fixture_revision": "fixture-revision",
        "units": ("close:USD", "adjusted_close:USD", "volume:shares"),
        "quality_state": "complete",
        "limitations": ("Synthetic fixture observation.",),
        "synthetic": True,
        "evidence_ref": "fixture://fiction",
    }
    values.update(updates)
    values["content_digest"] = canonical_record_digest(values)
    return HistoricalMarketObservation(**values)


def test_contracts_are_frozen_and_preserve_decimal() -> None:
    value = market()
    assert value.close == Decimal("12.3400")
    assert isinstance(value.close, Decimal)
    with pytest.raises(ValidationError):
        value.close = Decimal("0")  # type: ignore[misc]


@pytest.mark.parametrize(
    "timestamp",
    [datetime(2024, 1, 2, 16), datetime(2024, 1, 2, 17, tzinfo=timezone(timedelta(hours=1)))],
)
def test_non_utc_or_naive_timestamp_is_rejected(timestamp: datetime) -> None:
    with pytest.raises(ValidationError, match="UTC"):
        market(timestamp=timestamp)


def test_replay_contract_requires_frozen_no_look_ahead_rule() -> None:
    with pytest.raises(ValidationError):
        ReplaySpecification(
            experiment_id="experiment",
            portfolio_id="portfolio",
            dataset_revision="revision",
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2024, 1, 2, tzinfo=UTC),
            cadence="daily",
            review_time=time(18, 0, tzinfo=UTC),
            lookback=60,
            no_look_ahead_rule="timestamp <= as_of",
            deterministic_seed=1,
        )


def test_per_record_provenance_and_digest_are_mandatory() -> None:
    value = market()
    assert value.fixture_revision == "fixture-revision"
    assert value.units
    assert value.quality_state == "complete"
    assert value.limitations
    with pytest.raises(ValidationError, match="canonical market-record digest"):
        HistoricalMarketObservation.model_validate(
            value.model_dump(mode="python") | {"content_digest": "sha256:" + "0" * 64}
        )
