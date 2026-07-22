from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext

import pytest
from pydantic import ValidationError

from risk_analytics import AnalysisEvidence, AnalysisHorizon, AnalysisMethod, ReturnObservation, ReturnSeriesResult, SamplePeriod, ScenarioShock, annualized_volatility, apply_scenario, calculate_returns, historical_tail_risk, maximum_drawdown, render_report, summarize_contributions
from risk_domain import MarketObservation, PortfolioSnapshot, Position, QualityFlag


START = datetime(2026, 1, 2, 16, 0, tzinfo=UTC)
EVIDENCE = (
    AnalysisEvidence(
        evidence_id="synthetic-prices",
        reference="fixture://synthetic/prices",
        digest="sha256:" + "a" * 64,
        description="Reviewed synthetic price observations.",
    ),
)
HORIZON = AnalysisHorizon(label="daily", expected_interval_seconds=86_400)


def price(day: int, value: str | None, currency: str = "USD") -> MarketObservation:
    return MarketObservation(
        instrument_id="ALPHA",
        observed_at=START + timedelta(days=day),
        price=Decimal(value) if value is not None else None,
        currency=currency,
        synthetic=True,
        quality_flags=(QualityFlag.MISSING,) if value is None else (QualityFlag.COMPLETE,),
    )


def returns_result(values: tuple[str, ...], method: AnalysisMethod = AnalysisMethod.SIMPLE_RETURN) -> ReturnSeriesResult:
    return ReturnSeriesResult(
        analysis_id="returns-direct",
        snapshot_id="dataset-snapshot-a",
        methodology=method,
        return_method=method,
        horizon=HORIZON,
        sample_period=SamplePeriod(start=START, end=START + timedelta(days=len(values))),
        observation_count=len(values),
        assumptions=("Synthetic observations are reviewed fixtures.",),
        limitations=("Historical observations do not predict future outcomes.",),
        evidence=EVIDENCE,
        observations=tuple(
            ReturnObservation(observed_at=START + timedelta(days=index + 1), value=Decimal(value))
            for index, value in enumerate(values)
        ),
    )


def test_known_simple_returns_and_immutable_contract() -> None:
    result = calculate_returns(
        analysis_id="simple-a",
        snapshot_id="dataset-snapshot-a",
        prices=(price(0, "100"), price(1, "110"), price(2, "99")),
        method=AnalysisMethod.SIMPLE_RETURN,
        horizon=HORIZON,
        evidence=EVIDENCE,
    )

    assert [item.value for item in result.observations] == [Decimal("0.1"), Decimal("-0.1")]
    assert result.output_digest is not None
    with pytest.raises(ValidationError):
        result.analysis_id = "changed"  # type: ignore[misc]


def test_known_log_returns() -> None:
    result = calculate_returns(
        analysis_id="log-a",
        snapshot_id="dataset-snapshot-a",
        prices=(price(0, "100"), price(1, "110")),
        method=AnalysisMethod.LOG_RETURN,
        horizon=HORIZON,
        evidence=EVIDENCE,
    )
    with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
        expected = Decimal("1.1").ln()
    assert result.observations[0].value == expected


def test_returns_reject_duplicate_or_unordered_timestamps_and_nonpositive_prices() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        calculate_returns(analysis_id="a", snapshot_id="s", prices=(price(0, "100"), price(0, "101")), method=AnalysisMethod.SIMPLE_RETURN, horizon=HORIZON, evidence=EVIDENCE)
    with pytest.raises(ValueError, match="ordered"):
        calculate_returns(analysis_id="a", snapshot_id="s", prices=(price(1, "100"), price(0, "101")), method=AnalysisMethod.SIMPLE_RETURN, horizon=HORIZON, evidence=EVIDENCE)
    with pytest.raises(ValueError, match="positive"):
        calculate_returns(analysis_id="a", snapshot_id="s", prices=(price(0, "100"), price(1, "0")), method=AnalysisMethod.SIMPLE_RETURN, horizon=HORIZON, evidence=EVIDENCE)


def test_returns_reject_mixed_currencies() -> None:
    with pytest.raises(ValueError, match="exactly one currency"):
        calculate_returns(
            analysis_id="mixed-currency",
            snapshot_id="dataset-snapshot-a",
            prices=(price(0, "100", "USD"), price(1, "110", "EUR")),
            method=AnalysisMethod.SIMPLE_RETURN,
            horizon=HORIZON,
            evidence=EVIDENCE,
        )


def test_missing_data_and_intervals_warn_without_zero_fill() -> None:
    result = calculate_returns(
        analysis_id="missing-a",
        snapshot_id="dataset-snapshot-a",
        prices=(price(0, "100"), price(1, None), price(3, "120")),
        method=AnalysisMethod.SIMPLE_RETURN,
        horizon=HORIZON,
        evidence=EVIDENCE,
    )
    assert result.observations[0].value == Decimal("0.2")
    assert {item.code for item in result.warnings} == {"missing-observation", "missing-interval"}


def test_annualized_sample_volatility() -> None:
    source = returns_result(("0.1", "-0.1"))
    result = annualized_volatility(analysis_id="vol-a", returns=source)
    with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
        expected = Decimal("0.02").sqrt() * Decimal("252").sqrt()
    assert result.annualized_volatility == expected
    assert result.periods_per_year == 252
    assert any("n - 1" in item for item in result.assumptions)


def test_drawdown_peak_and_trough_on_simple_wealth_path() -> None:
    source = returns_result(("0.2", "-0.25", "0.2"))
    result = maximum_drawdown(analysis_id="drawdown-a", returns=source)
    assert result.maximum_drawdown == Decimal("0.25")
    assert result.peak_at == START + timedelta(days=1)
    assert result.trough_at == START + timedelta(days=2)
    assert result.wealth_path_method is AnalysisMethod.SIMPLE_RETURN


def test_historical_var_nearest_rank_and_expected_shortfall_tail_mean() -> None:
    # Corresponding sorted losses are -4,-3,-2,-1,0,1,2,3,4,5.
    source = returns_result(("4", "3", "2", "1", "0", "-1", "-2", "-3", "-4", "-5"))
    result = historical_tail_risk(
        analysis_id="tail-a",
        returns=source,
        confidence_level=Decimal("0.90"),
    )
    assert result.historical_rank == 9
    assert result.value_at_risk == Decimal("4")
    assert result.expected_shortfall == Decimal("4.5")
    assert result.tail_observation_count == 2


def test_inadequate_tail_sample_warns_but_preserves_signed_result() -> None:
    source = returns_result(("0.02", "0.01", "0", "-0.01", "-0.02"))
    result = historical_tail_risk(analysis_id="tail-small", returns=source, confidence_level=Decimal("0.95"))
    assert result.reviewed_minimum_observation_count == 200
    assert "inadequate-tail-sample" in {item.code for item in result.warnings}
    assert result.value_at_risk == Decimal("0.02")


def test_scenario_profit_and_loss_is_linear_and_has_no_effect() -> None:
    portfolio = PortfolioSnapshot(
        snapshot_id="portfolio-a",
        as_of=START,
        base_currency="USD",
        positions=(
            Position(instrument_id="BETA", quantity=Decimal("1"), price=Decimal("200"), market_value=Decimal("200"), currency="USD"),
            Position(instrument_id="ALPHA", quantity=Decimal("1"), price=Decimal("100"), market_value=Decimal("100"), currency="USD"),
        ),
    )
    result = apply_scenario(
        analysis_id="scenario-a",
        portfolio=portfolio,
        shocks=(ScenarioShock(instrument_id="BETA", percentage_shock=Decimal("0.05")), ScenarioShock(instrument_id="ALPHA", percentage_shock=Decimal("-0.10"))),
        horizon=AnalysisHorizon(label="instantaneous"),
        evidence=EVIDENCE,
    )
    assert [item.instrument_id for item in result.positions] == ["ALPHA", "BETA"]
    assert result.portfolio_profit_and_loss == Decimal("0.00")
    assert "effect" not in type(result).model_fields


def test_contribution_reconciliation_and_missing_constituent_warning() -> None:
    result = summarize_contributions(
        analysis_id="contribution-a",
        snapshot_id="portfolio-a",
        weights={"BETA": Decimal("0.4"), "ALPHA": Decimal("0.6"), "MISSING": Decimal("0.1")},
        instrument_returns={"ALPHA": Decimal("0.10"), "BETA": Decimal("-0.05")},
        portfolio_return=Decimal("0.04"),
        horizon=HORIZON,
        sample_period=SamplePeriod(start=START, end=START + timedelta(days=1)),
        evidence=EVIDENCE,
    )
    assert [item.instrument_id for item in result.items] == ["ALPHA", "BETA", "MISSING"]
    assert result.contribution_sum == Decimal("0.040")
    assert result.reconciliation_difference == Decimal("0.000")
    assert result.items[-1].instrument_return is None
    assert "missing-constituent-return" in {item.code for item in result.warnings}


def test_output_digest_and_markdown_html_are_stable() -> None:
    first = returns_result(("0.1", "-0.1"))
    second = ReturnSeriesResult.model_validate(first.model_dump())
    assert first.output_digest == second.output_digest

    first_report = render_report(analysis_id="report-a", title="Synthetic risk report", result=first)
    second_report = render_report(analysis_id="report-a", title="Synthetic risk report", result=second)
    assert first_report.markdown == second_report.markdown
    assert first_report.html == second_report.html
    assert first_report.output_digest == second_report.output_digest
    assert first_report.markdown.startswith("# Synthetic risk report")
    assert first_report.html.startswith('<article class="risk-report"')
    assert "<section><h2>Evidence</h2>" in first_report.html


def test_reports_include_each_result_specific_outcome() -> None:
    source = returns_result(("0.1", "-0.1"))
    volatility = annualized_volatility(analysis_id="vol-report", returns=source)
    drawdown = maximum_drawdown(analysis_id="drawdown-report", returns=source)
    tail = historical_tail_risk(
        analysis_id="tail-report", returns=source, confidence_level=Decimal("0.90")
    )
    portfolio = PortfolioSnapshot(
        snapshot_id="portfolio-report",
        as_of=START,
        base_currency="USD",
        positions=(
            Position(
                instrument_id="ALPHA",
                quantity=Decimal("1"),
                price=Decimal("100"),
                market_value=Decimal("100"),
                currency="USD",
            ),
        ),
    )
    scenario = apply_scenario(
        analysis_id="scenario-report",
        portfolio=portfolio,
        shocks=(ScenarioShock(instrument_id="ALPHA", percentage_shock=Decimal("-0.10")),),
        horizon=AnalysisHorizon(label="instantaneous"),
        evidence=EVIDENCE,
    )
    contribution = summarize_contributions(
        analysis_id="contribution-report",
        snapshot_id="portfolio-report",
        weights={"ALPHA": Decimal("1")},
        instrument_returns={"ALPHA": Decimal("0.1")},
        portfolio_return=Decimal("0.1"),
        horizon=HORIZON,
        sample_period=SamplePeriod(start=START, end=START + timedelta(days=1)),
        evidence=EVIDENCE,
    )

    cases = (
        (source, "Return observations", "0.1"),
        (volatility, "Annualized volatility", format(volatility.annualized_volatility, "f")),
        (drawdown, "Maximum drawdown", format(drawdown.maximum_drawdown, "f")),
        (tail, "Historical value at risk", format(tail.value_at_risk, "f")),
        (scenario, "Portfolio profit and loss", "-10.00 USD"),
        (contribution, "Constituent contributions", "ALPHA"),
    )
    for index, (result, label, value) in enumerate(cases):
        report = render_report(analysis_id=f"outcome-report-{index}", title="Outcome", result=result)
        assert "## Analysis outcome" in report.markdown
        assert label in report.markdown and value in report.markdown
        assert "<section><h2>Analysis outcome</h2>" in report.html
        assert label in report.html and value in report.html


def test_specialized_results_reject_contradictory_methodologies() -> None:
    source = returns_result(("0.1", "-0.1"))
    portfolio = PortfolioSnapshot(
        snapshot_id="portfolio-methodology",
        as_of=START,
        base_currency="USD",
        positions=(
            Position(
                instrument_id="ALPHA",
                quantity=Decimal("1"),
                price=Decimal("100"),
                market_value=Decimal("100"),
                currency="USD",
            ),
        ),
    )
    scenario = apply_scenario(
        analysis_id="scenario-methodology",
        portfolio=portfolio,
        shocks=(ScenarioShock(instrument_id="ALPHA", percentage_shock=Decimal("-0.10")),),
        horizon=AnalysisHorizon(label="instantaneous"),
        evidence=EVIDENCE,
    )
    contribution = summarize_contributions(
        analysis_id="contribution-methodology",
        snapshot_id="portfolio-methodology",
        weights={"ALPHA": Decimal("1")},
        instrument_returns={"ALPHA": Decimal("0.1")},
        portfolio_return=Decimal("0.1"),
        horizon=HORIZON,
        sample_period=SamplePeriod(start=START, end=START + timedelta(days=1)),
        evidence=EVIDENCE,
    )
    specialized_results = (
        annualized_volatility(analysis_id="vol-methodology", returns=source),
        maximum_drawdown(analysis_id="drawdown-methodology", returns=source),
        historical_tail_risk(
            analysis_id="tail-methodology", returns=source, confidence_level=Decimal("0.90")
        ),
        scenario,
        contribution,
        render_report(analysis_id="report-methodology", title="Methodology", result=source),
    )
    for result in specialized_results:
        payload = result.model_dump()
        payload["methodology"] = AnalysisMethod.SIMPLE_RETURN
        payload["output_digest"] = None
        with pytest.raises(ValidationError):
            type(result).model_validate(payload)
