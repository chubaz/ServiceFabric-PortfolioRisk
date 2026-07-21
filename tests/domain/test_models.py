from datetime import UTC, datetime
from decimal import Decimal, localcontext

import pytest
from pydantic import ValidationError

from risk_domain import (
    CashBalance,
    ConcentrationMeasure,
    DatasetFile,
    DatasetProvenance,
    DatasetSnapshot,
    ExposureSnapshot,
    FundamentalObservation,
    Instrument,
    InstrumentIdentifier,
    MarketObservation,
    PortfolioSnapshot,
    Position,
    PositionExposure,
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


def test_dataset_snapshot_retains_files_run_and_query_lineage_and_synthetic_provenance() -> None:
    source = SourceReference(source_id="synthetic-fixture", source_type="fixture", reference="fixture://day0", retrieved_at=NOW)
    file_digest = "sha256:" + "a" * 64
    query_digest = "sha256:" + "b" * 64
    snapshot = DatasetSnapshot(
        snapshot_id="dataset-a",
        created_at=NOW,
        files=(DatasetFile(path="output/b.csv", media_type="text/csv", size=20, digest=file_digest, row_count=2), DatasetFile(path="output/a.csv", media_type="text/csv", size=10, digest=file_digest, row_count=1)),
        ingestion_run_ids=("run-b", "run-a"),
        source_query_digests=(query_digest,),
        provenance=DatasetProvenance(synthetic=True, synthetic_label="synthetic", synthetic_seed=20260721, sources=(source,)),
    )

    assert [item.path for item in snapshot.files] == ["output/a.csv", "output/b.csv"]
    assert snapshot.ingestion_run_ids == ("run-a", "run-b")
    assert snapshot.provenance.synthetic is True
    assert snapshot.digest is not None
    with pytest.raises(ValidationError, match="synthetic label and seed"):
        DatasetProvenance(synthetic=True)
    with pytest.raises(ValidationError, match="SHA-256 digests"):
        DatasetSnapshot(
            snapshot_id="invalid-query-digest",
            created_at=NOW,
            files=(DatasetFile(path="output.csv", media_type="text/csv", size=1, digest=file_digest, row_count=1),),
            ingestion_run_ids=("run-a",),
            source_query_digests=("sha256:" + "z" * 64,),
            provenance=DatasetProvenance(synthetic=True, synthetic_label="synthetic", synthetic_seed=20260721),
        )


def test_exposure_snapshot_for_fixed_demonstration_portfolio() -> None:
    portfolio = PortfolioSnapshot(
        snapshot_id="demo-portfolio",
        as_of=NOW,
        base_currency="USD",
        positions=(
            Position(instrument_id="GAMMA", quantity=Decimal("1"), price=Decimal("5000"), market_value=Decimal("5000"), currency="USD"),
            Position(instrument_id="ALPHA", quantity=Decimal("1"), price=Decimal("20000"), market_value=Decimal("20000"), currency="USD"),
            Position(instrument_id="BETA", quantity=Decimal("1"), price=Decimal("10000"), market_value=Decimal("10000"), currency="USD"),
        ),
        cash_balances=(CashBalance(currency="USD", amount=Decimal("5000")),),
    )
    exposure = ExposureSnapshot(
        snapshot_id="demo-exposure",
        as_of=NOW,
        portfolio_snapshot=portfolio,
        nav=Decimal("40000"),
        gross_exposure=Decimal("0.875"),
        net_exposure=Decimal("0.875"),
        largest_position_weight=Decimal("0.50"),
        cash_weight=Decimal("0.125"),
        position_exposures=(
            PositionExposure(instrument_id="GAMMA", market_value=Decimal("5000"), weight=Decimal("0.125")),
            PositionExposure(instrument_id="ALPHA", market_value=Decimal("20000"), weight=Decimal("0.50")),
            PositionExposure(instrument_id="BETA", market_value=Decimal("10000"), weight=Decimal("0.25")),
        ),
        concentration_measures=(ConcentrationMeasure(name="hhi", value=Decimal("0.328125")),),
    )

    assert exposure.nav == Decimal("40000")
    assert exposure.largest_position_weight == Decimal("0.50")
    assert exposure.cash_weight == Decimal("0.125")
    assert [item.instrument_id for item in exposure.position_exposures] == ["ALPHA", "BETA", "GAMMA"]


def test_exposure_snapshot_rejects_weights_or_market_values_inconsistent_with_portfolio() -> None:
    portfolio = PortfolioSnapshot(
        snapshot_id="portfolio-a",
        as_of=NOW,
        base_currency="USD",
        positions=(Position(instrument_id="ALPHA", quantity=Decimal("1"), price=Decimal("100"), market_value=Decimal("100"), currency="USD"),),
        cash_balances=(CashBalance(currency="USD", amount=Decimal("100")),),
    )
    with pytest.raises(ValidationError, match="position exposure weights and market values"):
        ExposureSnapshot(
            snapshot_id="exposure-a",
            as_of=NOW,
            portfolio_snapshot=portfolio,
            nav=Decimal("200"),
            gross_exposure=Decimal("0.5"),
            net_exposure=Decimal("0.5"),
            largest_position_weight=Decimal("0.5"),
            cash_weight=Decimal("0.5"),
            position_exposures=(PositionExposure(instrument_id="ALPHA", market_value=Decimal("101"), weight=Decimal("0.505")),),
        )


def test_exposure_snapshot_supports_a_cash_only_portfolio() -> None:
    portfolio = PortfolioSnapshot(
        snapshot_id="cash-only-portfolio",
        as_of=NOW,
        base_currency="USD",
        cash_balances=(CashBalance(currency="USD", amount=Decimal("100")),),
    )

    exposure = ExposureSnapshot(
        snapshot_id="cash-only-exposure",
        as_of=NOW,
        portfolio_snapshot=portfolio,
        nav=Decimal("100"),
        gross_exposure=Decimal("0"),
        net_exposure=Decimal("0"),
        largest_position_weight=Decimal("0"),
        cash_weight=Decimal("1"),
        position_exposures=(),
    )

    assert exposure.position_exposures == ()
    assert exposure.cash_weight == Decimal("1")


def test_exposure_weights_and_digest_ignore_callers_decimal_context() -> None:
    portfolio = PortfolioSnapshot(
        snapshot_id="repeating-weight-portfolio",
        as_of=NOW,
        base_currency="USD",
        positions=(Position(instrument_id="ALPHA", quantity=Decimal("1"), price=Decimal("100"), market_value=Decimal("100"), currency="USD"),),
        cash_balances=(CashBalance(currency="USD", amount=Decimal("200")),),
    )
    one_third = Decimal("0." + "3" * 34)
    two_thirds = Decimal("0." + "6" * 33 + "7")

    def exposure() -> ExposureSnapshot:
        return ExposureSnapshot(
            snapshot_id="repeating-weight-exposure",
            as_of=NOW,
            portfolio_snapshot=portfolio,
            nav=Decimal("300"),
            gross_exposure=one_third,
            net_exposure=one_third,
            largest_position_weight=one_third,
            cash_weight=two_thirds,
            position_exposures=(PositionExposure(instrument_id="ALPHA", market_value=Decimal("100"), weight=one_third),),
        )

    with localcontext() as decimal_context:
        decimal_context.prec = 6
        low_precision = exposure()
    with localcontext() as decimal_context:
        decimal_context.prec = 50
        high_precision = exposure()

    assert low_precision.digest == high_precision.digest
