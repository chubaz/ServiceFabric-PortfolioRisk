from datetime import UTC, datetime
from decimal import Decimal, localcontext

import pytest
from pydantic import ValidationError

from risk_domain import (
    AgentRun,
    AlertDraft,
    ArtifactReference,
    CashBalance,
    ConcentrationMeasure,
    DatasetFile,
    DatasetProvenance,
    DatasetSnapshot,
    DecisionPoint,
    ExposureSnapshot,
    FundamentalObservation,
    Instrument,
    InstrumentIdentifier,
    MarketObservation,
    NewsEvent,
    PortfolioSnapshot,
    Position,
    PositionExposure,
    QualityFlag,
    RiskFinding,
    RiskLimit,
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


def artifact(artifact_id: str) -> ArtifactReference:
    return ArtifactReference(
        artifact_id=artifact_id,
        digest="sha256:" + "a" * 64,
        media_type="application/json",
        reference=f"artifact://{artifact_id}",
    )


def finding(**changes: object) -> RiskFinding:
    values: dict[str, object] = {
        "finding_type": "risk_limit_breach",
        "severity": "high",
        "title": "Synthetic concentration threshold exceeded",
        "summary": "The synthetic demonstration portfolio exceeds its concentration threshold.",
        "snapshot_references": (artifact("snapshot-a"),),
        "evidence_references": (artifact("evidence-a"),),
        "assumptions": ("All values are synthetic.",),
        "warnings": ("This is not investment advice.",),
    }
    values.update(changes)
    return RiskFinding(**values)


def test_successful_draft_creation_and_review_only_defaults() -> None:
    alert = AlertDraft(
        alert_id="alert-a",
        findings=(finding(),),
        rationale="Evidence supports a human review of the synthetic concentration finding.",
        suggested_analytical_next_steps=("Review the evidence and assumptions.",),
    )
    event = NewsEvent(
        event_id="event-a",
        occurred_at=NOW,
        title="Synthetic event",
        summary="A deterministic synthetic event for contract coverage.",
        evidence_references=(artifact("news-a"),),
        synthetic=True,
    )
    limit = RiskLimit(limit_id="limit-a", limit_type="concentration", scope="portfolio", threshold=Decimal("0.50"))
    run = AgentRun(
        run_id="run-a",
        agent_role="risk.agent.portfolio_exposure",
        capability_invocations=("risk.capability.portfolio_exposure",),
        input_digest="sha256:" + "a" * 64,
        output_digest="sha256:" + "b" * 64,
        evidence_references=(artifact("run-a"),),
        observed_at=NOW,
    )

    assert alert.status == "draft"
    assert alert.human_review_required is True
    assert alert.effects == ()
    assert event.synthetic is True
    assert limit.threshold == Decimal("0.50")
    assert run.provider_disclosure == "deterministic-local"


def test_alert_cannot_claim_approval_and_effects_must_be_empty() -> None:
    values: dict[str, object] = {
        "alert_id": "alert-a",
        "findings": (finding(),),
        "rationale": "Evidence supports human review.",
        "suggested_analytical_next_steps": ("Review evidence.",),
    }
    with pytest.raises(ValidationError, match="draft"):
        AlertDraft(**values, status="approved")
    with pytest.raises(ValidationError):
        AlertDraft(**values, effects=("effect",))


def test_missing_evidence_is_rejected_and_finding_ids_are_deterministic() -> None:
    first = finding()
    second = finding()

    assert first.finding_id == second.finding_id
    with pytest.raises(ValidationError, match="at least 1 item"):
        finding(evidence_references=())


def test_decision_history_is_immutable() -> None:
    digest = "sha256:" + "d" * 64
    prior = DecisionPoint(
        decision="request_changes",
        reviewer_id="reviewer-a",
        decided_at=NOW,
        comment="Please clarify the synthetic-data assumption.",
        alert_digest_before_decision=digest,
    )
    decision = DecisionPoint(
        decision="approve",
        reviewer_id="reviewer-b",
        decided_at=datetime(2026, 7, 21, 13, 0, tzinfo=UTC),
        comment="The draft is approved for human review display only.",
        alert_digest_before_decision=digest,
        history=(prior,),
    )

    assert decision.history == (prior,)
    with pytest.raises(ValidationError):
        decision.history = ()  # type: ignore[misc]
