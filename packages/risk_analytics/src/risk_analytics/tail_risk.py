"""Nearest-rank historical VaR and expected shortfall."""

from decimal import Context, Decimal, ROUND_CEILING, ROUND_HALF_EVEN, localcontext

from .contracts import AnalysisEvidence, AnalysisHorizon, AnalysisMethod, AnalysisWarning, HistoricalTailRiskResult, ReturnSeriesResult
from .policies import DECIMAL_PRECISION, INADEQUATE_TAIL_SAMPLE, MAX_CONFIDENCE_LEVEL, MIN_CONFIDENCE_LEVEL, TARGET_TAIL_OBSERVATIONS


TAIL_CONTEXT = Context(prec=DECIMAL_PRECISION, rounding=ROUND_HALF_EVEN)


def historical_tail_risk(
    *,
    analysis_id: str,
    returns: ReturnSeriesResult,
    confidence_level: Decimal,
    evidence: tuple[AnalysisEvidence, ...] | None = None,
    horizon: AnalysisHorizon | None = None,
    assumptions: tuple[str, ...] = (),
    limitations: tuple[str, ...] = (),
) -> HistoricalTailRiskResult:
    if not MIN_CONFIDENCE_LEVEL <= confidence_level <= MAX_CONFIDENCE_LEVEL:
        raise ValueError(
            f"confidence_level must be within reviewed bounds {MIN_CONFIDENCE_LEVEL} to {MAX_CONFIDENCE_LEVEL}"
        )
    if not returns.observations:
        raise ValueError("historical tail risk requires at least one return observation")
    losses = sorted((-item.value for item in returns.observations))
    count = len(losses)
    with localcontext(TAIL_CONTEXT):
        rank = int((confidence_level * Decimal(count)).to_integral_value(rounding=ROUND_CEILING))
        value_at_risk = losses[rank - 1]
        tail = losses[rank - 1 :]
        expected_shortfall = sum(tail, start=Decimal("0")) / Decimal(len(tail))
        reviewed_minimum = int(
            (Decimal(TARGET_TAIL_OBSERVATIONS) / (Decimal("1") - confidence_level)).to_integral_value(
                rounding=ROUND_CEILING
            )
        )
    warnings = list(returns.warnings)
    result_limitations = list(limitations or returns.limitations)
    if count < reviewed_minimum:
        warnings.append(
            AnalysisWarning(
                code=INADEQUATE_TAIL_SAMPLE,
                message=(
                    f"The {count}-observation sample is below the reviewed minimum of "
                    f"{reviewed_minimum} for confidence {format(confidence_level, 'f')}."
                ),
            )
        )
        result_limitations.append("The selected historical tail contains fewer than the target 10 observations.")
    return HistoricalTailRiskResult(
        analysis_id=analysis_id,
        snapshot_id=returns.snapshot_id,
        methodology=AnalysisMethod.HISTORICAL_TAIL_RISK,
        horizon=horizon or returns.horizon,
        sample_period=returns.sample_period,
        observation_count=count,
        confidence_level=confidence_level,
        assumptions=(
            *assumptions,
            "Loss is negative return: positive values are losses and negative values are gains.",
            "Historical VaR uses deterministic nearest rank ceil(confidence * observation_count).",
            "Historical expected shortfall is the arithmetic mean of losses at and beyond the selected rank.",
        ),
        warnings=tuple(warnings),
        limitations=tuple(result_limitations),
        evidence=evidence or returns.evidence,
        value_at_risk=value_at_risk,
        expected_shortfall=expected_shortfall,
        historical_rank=rank,
        tail_observation_count=len(tail),
        reviewed_minimum_observation_count=reviewed_minimum,
    )
