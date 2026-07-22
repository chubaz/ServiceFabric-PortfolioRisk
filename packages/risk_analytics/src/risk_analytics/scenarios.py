"""Reviewed deterministic linear market-value scenario shocks."""

from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext

from risk_domain import PortfolioSnapshot

from .contracts import AnalysisEvidence, AnalysisHorizon, AnalysisMethod, AnalysisWarning, SamplePeriod, ScenarioPositionResult, ScenarioResult, ScenarioShock
from .policies import DECIMAL_PRECISION, MISSING_SCENARIO_SHOCK


SCENARIO_CONTEXT = Context(prec=DECIMAL_PRECISION, rounding=ROUND_HALF_EVEN)


def apply_scenario(
    *,
    analysis_id: str,
    portfolio: PortfolioSnapshot,
    shocks: tuple[ScenarioShock, ...],
    horizon: AnalysisHorizon,
    evidence: tuple[AnalysisEvidence, ...],
    assumptions: tuple[str, ...] = (),
    limitations: tuple[str, ...] = (),
) -> ScenarioResult:
    shock_ids = [item.instrument_id for item in shocks]
    if len(shock_ids) != len(set(shock_ids)):
        raise ValueError("scenario shocks must have unique instrument identifiers")
    if any(position.currency != portfolio.base_currency for position in portfolio.positions):
        raise ValueError("scenario market values must use the portfolio base currency")
    by_instrument = {item.instrument_id: item for item in shocks}
    portfolio_ids = {position.instrument_id for position in portfolio.positions}
    if set(by_instrument) - portfolio_ids:
        raise ValueError("scenario shocks cannot reference instruments absent from the portfolio")

    warnings: list[AnalysisWarning] = []
    missing = sorted(portfolio_ids - set(by_instrument))
    if missing:
        warnings.append(
            AnalysisWarning(
                code=MISSING_SCENARIO_SHOCK,
                message=(
                    "Positions without a reviewed shock were omitted, not assigned a zero shock: "
                    + ", ".join(missing)
                    + "."
                ),
            )
        )
    with localcontext(SCENARIO_CONTEXT):
        position_results = tuple(
            ScenarioPositionResult(
                instrument_id=position.instrument_id,
                market_value=position.market_value,
                percentage_shock=by_instrument[position.instrument_id].percentage_shock,
                profit_and_loss=position.market_value * by_instrument[position.instrument_id].percentage_shock,
            )
            for position in portfolio.positions
            if position.instrument_id in by_instrument
        )
        total = sum((item.profit_and_loss for item in position_results), start=Decimal("0"))
    return ScenarioResult(
        analysis_id=analysis_id,
        snapshot_id=portfolio.snapshot_id,
        methodology=AnalysisMethod.DETERMINISTIC_SCENARIO,
        horizon=horizon,
        sample_period=SamplePeriod(start=portfolio.as_of, end=portfolio.as_of),
        observation_count=len(position_results),
        assumptions=(
            *assumptions,
            "Position profit and loss equals market value multiplied by the reviewed percentage shock.",
            "Portfolio profit and loss is the arithmetic sum of covered position profit and loss.",
        ),
        warnings=tuple(warnings),
        limitations=(
            *limitations,
            "This is a linear price/market-value shock with no pricing model, hedge recommendation, or transaction effect.",
        ),
        evidence=evidence,
        shocks=tuple(sorted(shocks, key=lambda item: item.instrument_id)),
        positions=position_results,
        portfolio_profit_and_loss=total,
        currency=portfolio.base_currency,
    )
