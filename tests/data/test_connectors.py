"""Focused Day 0 tests for deterministic, provider-neutral ingestion."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from connectors import SyntheticCompustatLikeConnector, SyntheticCrspLikeConnector, WrdsCompustatConnector, WrdsCrspConnector
from risk_data import ConnectorDisabledError, QuerySpec
from risk_data.contracts import DatasetSnapshot, NormalizedMarketRecord
from risk_domain import InstrumentIdentifier, QualityFlag


START = datetime(2026, 5, 1, tzinfo=UTC)
END = datetime(2026, 7, 21, tzinfo=UTC)


def market_query(**changes: object) -> QuerySpec:
    values: dict[str, object] = {"dataset": "market", "instrument_ids": ("instrument-nova", "instrument-orbit", "instrument-quasar"), "start_at": START, "end_at": END}
    values.update(changes)
    return QuerySpec(**values)


def test_synthetic_market_output_is_deterministic_and_explicitly_labelled() -> None:
    connector = SyntheticCrspLikeConnector()
    first = connector.ingest(market_query())
    second = connector.ingest(market_query())

    assert first == second
    assert first.snapshot.digest == second.snapshot.digest
    assert all(record.synthetic and record.synthetic_label == "synthetic" for record in first.snapshot.records)
    assert first.snapshot.records[-2].price == Decimal("57.00")


def test_missing_value_maps_to_missing_domain_observation_not_zero() -> None:
    run = SyntheticCrspLikeConnector().ingest(market_query())
    missing = next(record for record in run.snapshot.records if record.instrument_id == "instrument-orbit")
    observation = missing.to_market_observation()

    assert missing.price is None
    assert observation.price is None
    assert QualityFlag.MISSING in observation.quality_flags


def test_normalized_fundamental_records_map_to_domain_contracts() -> None:
    run = SyntheticCompustatLikeConnector().ingest(QuerySpec(dataset="fundamental", instrument_ids=("instrument-nova", "instrument-orbit"), start_at=START, end_at=END))
    observation = run.snapshot.records[0].to_fundamental_observation()  # type: ignore[union-attr]

    assert observation.instrument_id == "instrument-nova"
    assert observation.synthetic is True
    assert observation.value == Decimal("1250000")


def test_duplicate_candidate_is_reported_for_rejection_and_stale_is_flagged() -> None:
    run = SyntheticCrspLikeConnector().ingest(market_query())
    codes = [issue.code.value for issue in run.validation.issues]

    assert run.validation.has_errors
    assert run.validation.duplicate_count == 1
    assert "duplicate" in codes
    assert "stale" in codes


@pytest.mark.parametrize("query", [market_query(instrument_ids=("instrument-unknown",)), market_query(start_at=datetime(2026, 7, 22, tzinfo=UTC), end_at=datetime(2026, 7, 23, tzinfo=UTC))])
def test_requested_instruments_with_no_observations_are_explicitly_missing(query: QuerySpec) -> None:
    run = SyntheticCrspLikeConnector().ingest(query)

    assert run.snapshot.records == ()
    assert {issue.record_key for issue in run.validation.issues} == {f"query:{instrument_id}" for instrument_id in query.instrument_ids}
    assert all(issue.code.value == "missing" for issue in run.validation.issues)


def test_identifier_validation_rejects_invalid_data_identifiers() -> None:
    with pytest.raises(ValidationError, match="ticker identifiers"):
        NormalizedMarketRecord(instrument_id="instrument-nova", identifier=InstrumentIdentifier(identifier_type="ticker", value="lower"), observed_at=END, price=Decimal("1"))
    with pytest.raises(ValidationError, match="instrument- prefix"):
        market_query(instrument_ids=("NOVA",))


def test_normalized_market_records_reject_invalid_currency_and_snapshots_require_synthetic_provenance() -> None:
    with pytest.raises(ValidationError, match="supported ISO 4217"):
        NormalizedMarketRecord(instrument_id="instrument-nova", identifier=InstrumentIdentifier(identifier_type="ticker", value="NOVA"), observed_at=END, price=Decimal("1"), currency="ZZZ")
    with pytest.raises(ValidationError, match="explicitly synthetic"):
        DatasetSnapshot(snapshot_id="invalid-provenance", created_at=END, records=(), synthetic=False)


@pytest.mark.parametrize("connector", [WrdsCrspConnector(), WrdsCompustatConnector()])
def test_wrds_connectors_are_disabled_without_network_access(connector: object) -> None:
    with pytest.raises(ConnectorDisabledError, match="disabled during Day 0"):
        connector.ingest(market_query())  # type: ignore[attr-defined]


def test_synthetic_connectors_write_nothing_outside_temporary_directory(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    before = list(tmp_path.iterdir())
    run = SyntheticCompustatLikeConnector().ingest(QuerySpec(dataset="fundamental", instrument_ids=("instrument-nova", "instrument-orbit"), start_at=START, end_at=END))

    assert run.snapshot.records
    assert list(tmp_path.iterdir()) == before
