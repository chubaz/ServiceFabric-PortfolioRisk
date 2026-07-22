"""Annualized sample volatility using Decimal arithmetic."""

from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext

from .contracts import AnalysisEvidence, AnalysisHorizon, AnalysisMethod, ReturnSeriesResult, VolatilityResult
from .policies import DECIMAL_PRECISION, DEFAULT_PERIODS_PER_YEAR


VOLATILITY_CONTEXT = Context(prec=DECIMAL_PRECISION, rounding=ROUND_HALF_EVEN)


def annualized_volatility(
    *,
    analysis_id: str,
    returns: ReturnSeriesResult,
    evidence: tuple[AnalysisEvidence, ...] | None = None,
    horizon: AnalysisHorizon | None = None,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
    assumptions: tuple[str, ...] = (),
    limitations: tuple[str, ...] = (),
) -> VolatilityResult:
    if len(returns.observations) < 2:
        raise ValueError("annualized volatility requires at least two return observations")
    if periods_per_year < 1:
        raise ValueError("periods_per_year must be positive")
    values = [item.value for item in returns.observations]
    with localcontext(VOLATILITY_CONTEXT):
        mean = sum(values, start=Decimal("0")) / Decimal(len(values))
        sample_variance = sum(((value - mean) ** 2 for value in values), start=Decimal("0")) / Decimal(len(values) - 1)
        result = sample_variance.sqrt() * Decimal(periods_per_year).sqrt()
    return VolatilityResult(
        analysis_id=analysis_id,
        snapshot_id=returns.snapshot_id,
        methodology=AnalysisMethod.ANNUALIZED_VOLATILITY,
        horizon=horizon or returns.horizon,
        sample_period=returns.sample_period,
        observation_count=len(values),
        assumptions=(
            *assumptions,
            f"Sample standard deviation uses denominator n - 1 and is annualized by sqrt({periods_per_year}).",
            f"The annualization assumption is {periods_per_year} return periods per year.",
        ),
        warnings=returns.warnings,
        limitations=limitations or returns.limitations,
        evidence=evidence or returns.evidence,
        annualized_volatility=result,
        periods_per_year=periods_per_year,
    )
