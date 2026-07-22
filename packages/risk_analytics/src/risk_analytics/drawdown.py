"""Maximum drawdown over a cumulative Decimal wealth path."""

from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext

from .contracts import AnalysisEvidence, AnalysisHorizon, AnalysisMethod, DrawdownResult, ReturnSeriesResult
from .policies import DECIMAL_PRECISION


DRAWDOWN_CONTEXT = Context(prec=DECIMAL_PRECISION, rounding=ROUND_HALF_EVEN)


def maximum_drawdown(
    *,
    analysis_id: str,
    returns: ReturnSeriesResult,
    evidence: tuple[AnalysisEvidence, ...] | None = None,
    horizon: AnalysisHorizon | None = None,
    assumptions: tuple[str, ...] = (),
    limitations: tuple[str, ...] = (),
) -> DrawdownResult:
    if not returns.observations:
        raise ValueError("maximum drawdown requires at least one return observation")
    wealth = Decimal("1")
    peak_wealth = wealth
    peak_at = returns.sample_period.start
    maximum_loss = Decimal("0")
    maximum_peak_at = peak_at
    trough_at = peak_at
    with localcontext(DRAWDOWN_CONTEXT):
        for observation in returns.observations:
            if returns.return_method is AnalysisMethod.SIMPLE_RETURN:
                if observation.value <= Decimal("-1"):
                    raise ValueError("simple returns must be greater than -1 to form a wealth path")
                wealth *= Decimal("1") + observation.value
            else:
                wealth *= observation.value.exp()
            if wealth > peak_wealth:
                peak_wealth = wealth
                peak_at = observation.observed_at
            loss = (peak_wealth - wealth) / peak_wealth
            if loss > maximum_loss:
                maximum_loss = loss
                maximum_peak_at = peak_at
                trough_at = observation.observed_at
    return DrawdownResult(
        analysis_id=analysis_id,
        snapshot_id=returns.snapshot_id,
        methodology=AnalysisMethod.MAXIMUM_DRAWDOWN,
        horizon=horizon or returns.horizon,
        sample_period=returns.sample_period,
        observation_count=len(returns.observations),
        assumptions=(
            *assumptions,
            f"The cumulative wealth path uses {returns.return_method.value} observations and starts at 1.",
            "Drawdown is reported as a non-negative loss magnitude from the running peak.",
        ),
        warnings=returns.warnings,
        limitations=limitations or returns.limitations,
        evidence=evidence or returns.evidence,
        maximum_drawdown=maximum_loss,
        peak_at=maximum_peak_at,
        trough_at=trough_at,
        wealth_path_method=returns.return_method,
    )
