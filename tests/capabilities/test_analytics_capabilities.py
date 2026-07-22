from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from risk_analytics import AnalysisEvidence, AnalysisHorizon, AnalysisMethod, SamplePeriod, ScenarioShock
from risk_capabilities import (
    CapabilityRegistry,
    ContributionSummaryRequest,
    ContributionValue,
    DerivedReturnsRequest,
    HistoricalTailRiskRequest,
    ReportRequest,
    ReturnsRequest,
    ScenarioRequest,
    VolatilityRequest,
)
from risk_domain import MarketObservation, PortfolioSnapshot, Position, QualityFlag


START = datetime(2026, 7, 22, 12, tzinfo=UTC)
EVIDENCE = (
    AnalysisEvidence(
        evidence_id="reviewed-synthetic-prices",
        reference="fixture://synthetic/day1/prices",
        digest="sha256:" + "a" * 64,
        description="Reviewed synthetic price observations.",
    ),
)
HORIZON = AnalysisHorizon(label="daily", expected_interval_seconds=86_400)


def price(day: int, value: str) -> MarketObservation:
    return MarketObservation(
        instrument_id="ALPHA",
        observed_at=START + timedelta(days=day),
        price=Decimal(value),
        currency="USD",
        synthetic=True,
        quality_flags=(QualityFlag.COMPLETE,),
    )


def returns_request() -> ReturnsRequest:
    return ReturnsRequest(
        analysis_id="simple-capability",
        snapshot_id="prices-snapshot",
        prices=(price(0, "100"), price(1, "110"), price(2, "99")),
        horizon=HORIZON,
        evidence=EVIDENCE,
        limitations=("Historical observations do not predict future outcomes.",),
    )


def test_registered_analytics_preserve_exact_methodology_evidence_and_digests() -> None:
    registry = CapabilityRegistry()
    simple = registry.invoke("risk.returns.simple", returns_request())
    logarithmic = registry.invoke(
        "risk.returns.log",
        returns_request().model_copy(update={"analysis_id": "log-capability"}),
    )
    assert simple.status == logarithmic.status == "succeeded"
    assert simple.methodology is AnalysisMethod.SIMPLE_RETURN
    assert logarithmic.methodology is AnalysisMethod.LOG_RETURN
    assert simple.output_digest == simple.data.output_digest
    assert simple.evidence_references[0].digest == EVIDENCE[0].digest
    assert simple.evidence_references[0].description == EVIDENCE[0].description
    assert simple.effects == ()
    with pytest.raises(TypeError, match="ReturnsRequest"):
        registry.invoke("risk.returns.simple", object())
    with pytest.raises(ValidationError):
        ReturnsRequest.model_validate(
            {**returns_request().model_dump(mode="python"), "evidence": ()}
        )


def test_derived_analytics_delegate_and_preserve_tail_warning() -> None:
    registry = CapabilityRegistry()
    source = registry.invoke("risk.returns.simple", returns_request()).data
    common = {
        "analysis_id": "derived-analysis",
        "returns": source,
        "evidence": EVIDENCE,
        "limitations": ("Descriptive historical analysis only.",),
    }
    volatility = registry.invoke(
        "risk.volatility.annualized", VolatilityRequest(**common)
    )
    drawdown = registry.invoke(
        "risk.drawdown.maximum", DerivedReturnsRequest(**common)
    )
    tail_request = HistoricalTailRiskRequest(
        **common, confidence_level=Decimal("0.95")
    )
    var = registry.invoke("risk.var.historical", tail_request)
    expected_shortfall = registry.invoke(
        "risk.expected_shortfall.historical", tail_request
    )
    assert volatility.methodology is AnalysisMethod.ANNUALIZED_VOLATILITY
    assert drawdown.methodology is AnalysisMethod.MAXIMUM_DRAWDOWN
    assert var.methodology is expected_shortfall.methodology is AnalysisMethod.HISTORICAL_TAIL_RISK
    assert any(warning.startswith("inadequate-tail-sample:") for warning in var.warnings)
    assert var.warnings == expected_shortfall.warnings
    assert all(result.effects == () for result in (volatility, drawdown, var, expected_shortfall))


def test_scenario_is_descriptive_and_contributions_reconcile() -> None:
    registry = CapabilityRegistry()
    portfolio = PortfolioSnapshot(
        snapshot_id="portfolio-a",
        as_of=START,
        base_currency="USD",
        positions=(
            Position(instrument_id="ALPHA", quantity=Decimal("1"), price=Decimal("100"), market_value=Decimal("100"), currency="USD"),
            Position(instrument_id="BETA", quantity=Decimal("1"), price=Decimal("200"), market_value=Decimal("200"), currency="USD"),
        ),
    )
    scenario = registry.invoke(
        "risk.scenario.evaluate",
        ScenarioRequest(
            analysis_id="scenario-capability",
            portfolio=portfolio,
            shocks=(
                ScenarioShock(instrument_id="ALPHA", percentage_shock=Decimal("-0.10")),
                ScenarioShock(instrument_id="BETA", percentage_shock=Decimal("0.05")),
            ),
            horizon=AnalysisHorizon(label="instantaneous"),
            evidence=EVIDENCE,
        ),
    )
    assert scenario.data.portfolio_profit_and_loss == Decimal("0.00")
    assert "no pricing model" in " ".join(scenario.limitations)
    assert scenario.effects == ()

    contribution = registry.invoke(
        "risk.contribution.summarize",
        ContributionSummaryRequest(
            analysis_id="contribution-capability",
            snapshot_id=portfolio.snapshot_id,
            values=(
                ContributionValue(instrument_id="BETA", weight=Decimal("0.4"), instrument_return=Decimal("-0.05")),
                ContributionValue(instrument_id="ALPHA", weight=Decimal("0.6"), instrument_return=Decimal("0.10")),
            ),
            portfolio_return=Decimal("0.04"),
            horizon=HORIZON,
            sample_period=SamplePeriod(start=START, end=START + timedelta(days=1)),
            evidence=EVIDENCE,
        ),
    )
    assert contribution.data.contribution_sum == Decimal("0.040")
    assert contribution.data.reconciliation_difference == Decimal("0.000")
    assert contribution.effects == ()


def test_report_uses_reviewed_renderer_and_requires_human_review() -> None:
    registry = CapabilityRegistry()
    source = registry.invoke("risk.returns.simple", returns_request()).data
    report = registry.invoke(
        "risk.report.render",
        ReportRequest(analysis_id="report-capability", title="Synthetic review report", result=source),
    )
    assert report.methodology is AnalysisMethod.RISK_REPORT
    assert report.data.markdown.startswith("# Synthetic review report")
    assert report.data.html.startswith('<article class="risk-report"')
    assert report.data.source_output_digest == source.output_digest
    assert report.human_review_required is True
    assert report.effects == ()
    assert "pdf" not in report.data.model_dump()
