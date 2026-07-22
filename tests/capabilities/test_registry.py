from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from risk_capabilities import AnomalyDetectionRequest, CapabilityRegistry, EvidenceReference, ExposureSummaryRequest, PortfolioSnapshotRequest, PositionSpecification
from risk_data import NormalizedMarketRecord
from risk_domain import CashBalance, InstrumentIdentifier


NOW = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
EVIDENCE = (EvidenceReference(evidence_id="synthetic-evidence", reference="fixture://synthetic/wave-0b", source_type="synthetic_fixture"),)


def record(instrument_id: str, ticker: str, days_before: int, price: str | None) -> NormalizedMarketRecord:
    return NormalizedMarketRecord(instrument_id=instrument_id, identifier=InstrumentIdentifier(identifier_type="ticker", value=ticker), observed_at=NOW - timedelta(days=days_before), price=Decimal(price) if price is not None else None)


def snapshot_request() -> PortfolioSnapshotRequest:
    return PortfolioSnapshotRequest(snapshot_id="portfolio-20260721", as_of=NOW, positions=(PositionSpecification(instrument_id="instrument-alpha", quantity=Decimal("200")), PositionSpecification(instrument_id="instrument-beta", quantity=Decimal("100"))), cash_balances=(CashBalance(currency="USD", amount=Decimal("10000")),), normalized_observations=(record("instrument-alpha", "ALPHA", 0, "100"), record("instrument-beta", "BETA", 0, "100")), evidence_references=EVIDENCE)


def test_registry_has_exactly_the_required_unique_capability_ids() -> None:
    registry = CapabilityRegistry()
    assert registry.capability_ids == (
        "alert.draft.review", "alert.draft.synthesize", "data.synthetic.ingest",
        "market.anomaly.detect", "news.event.classify", "planning.knowledge.list_due",
        "portfolio.exposure.summarize", "portfolio.snapshot.create",
        "risk.contribution.summarize", "risk.drawdown.maximum",
        "risk.expected_shortfall.historical", "risk.report.render",
        "risk.returns.log", "risk.returns.simple", "risk.scenario.evaluate",
        "risk.var.historical", "risk.volatility.annualized",
    )
    with pytest.raises(TypeError, match="PortfolioSnapshotRequest"):
        registry.invoke("portfolio.snapshot.create", object())


def test_snapshot_creation_requires_explicit_timestamp_and_retains_evidence() -> None:
    registry = CapabilityRegistry()
    outcome = registry.invoke("portfolio.snapshot.create", snapshot_request())
    assert outcome.data.as_of == NOW
    assert outcome.evidence_references == EVIDENCE
    assert outcome.effects == ()
    failed = registry.invoke("portfolio.snapshot.create", snapshot_request().model_copy(update={"normalized_observations": (record("instrument-alpha", "ALPHA", 0, None), record("instrument-beta", "BETA", 0, "100"))}))
    assert failed.status == "failed"
    assert "missing price" in failed.warnings[0]


def test_exposure_summary_calculates_fixed_nav_and_largest_position_weight() -> None:
    registry = CapabilityRegistry()
    portfolio = registry.invoke("portfolio.snapshot.create", snapshot_request()).data
    result = registry.invoke("portfolio.exposure.summarize", ExposureSummaryRequest(snapshot_id="exposure-20260721", portfolio_snapshot=portfolio, evidence_references=EVIDENCE))
    assert result.data.nav == Decimal("40000")
    assert result.data.largest_position_weight == Decimal("0.50")
    assert result.effects == ()


def test_anomaly_detection_flags_seeded_alpha_move_and_does_not_impute_missing_values() -> None:
    registry = CapabilityRegistry()
    observations = (record("instrument-alpha", "ALPHA", 3, "100"), record("instrument-alpha", "ALPHA", 2, "101"), record("instrument-alpha", "ALPHA", 1, "100"), record("instrument-alpha", "ALPHA", 0, "57"), record("instrument-missing", "MISS", 1, "10"), record("instrument-missing", "MISS", 0, None))
    result = registry.invoke("market.anomaly.detect", AnomalyDetectionRequest(normalized_observations=observations, percentage_threshold=Decimal("0.20"), z_score_threshold=Decimal("1"), evidence_references=EVIDENCE))
    assert any(item.instrument_id == "instrument-alpha" and item.simple_return == Decimal("-0.43") for item in result.data.anomalies)
    assert result.evidence_references == EVIDENCE
    assert result.effects == ()
    assert any("no return was inferred" in warning for warning in result.warnings)
