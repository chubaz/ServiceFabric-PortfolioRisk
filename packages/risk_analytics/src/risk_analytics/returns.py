"""Deterministic simple and logarithmic return calculations."""

from __future__ import annotations

from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext

from risk_domain import MarketObservation

from .contracts import AnalysisEvidence, AnalysisHorizon, AnalysisMethod, AnalysisWarning, ReturnObservation, ReturnSeriesResult, SamplePeriod
from .policies import DECIMAL_PRECISION, MISSING_INTERVAL, MISSING_OBSERVATION


RETURN_CONTEXT = Context(prec=DECIMAL_PRECISION, rounding=ROUND_HALF_EVEN)


def calculate_returns(
    *,
    analysis_id: str,
    snapshot_id: str,
    prices: tuple[MarketObservation, ...],
    method: AnalysisMethod,
    horizon: AnalysisHorizon,
    evidence: tuple[AnalysisEvidence, ...],
    assumptions: tuple[str, ...] = (),
    limitations: tuple[str, ...] = (),
) -> ReturnSeriesResult:
    """Calculate returns without sorting, filling, or converting missing prices to zero."""
    if method not in {AnalysisMethod.SIMPLE_RETURN, AnalysisMethod.LOG_RETURN}:
        raise ValueError("return method must be simple-return or log-return")
    if len(prices) < 2:
        raise ValueError("return calculations require at least two price observations")
    timestamps = [item.observed_at for item in prices]
    if timestamps != sorted(timestamps):
        raise ValueError("price observations must already be ordered by time")
    if len(timestamps) != len(set(timestamps)):
        raise ValueError("duplicate price observation timestamps are not allowed")
    instrument_ids = {item.instrument_id for item in prices}
    if len(instrument_ids) != 1:
        raise ValueError("a return series must contain exactly one instrument")
    currencies = {item.currency for item in prices}
    if len(currencies) != 1:
        raise ValueError("a return series must contain exactly one currency")

    warnings: list[AnalysisWarning] = []
    if any(item.price is None for item in prices):
        warnings.append(
            AnalysisWarning(
                code=MISSING_OBSERVATION,
                message="Missing price observations were omitted and were not converted to zero.",
            )
        )
    if horizon.expected_interval_seconds is not None and any(
        (current.observed_at - previous.observed_at).total_seconds()
        > horizon.expected_interval_seconds
        for previous, current in zip(prices, prices[1:])
    ):
        warnings.append(
            AnalysisWarning(
                code=MISSING_INTERVAL,
                message="One or more expected intervals are missing; returns span only retained observations.",
            )
        )

    retained = [item for item in prices if item.price is not None]
    if len(retained) < 2:
        raise ValueError("return calculations require at least two present prices")
    if any(item.price <= 0 for item in retained if item.price is not None):
        raise ValueError("prices must be positive")

    observations: list[ReturnObservation] = []
    with localcontext(RETURN_CONTEXT):
        for previous, current in zip(retained, retained[1:]):
            assert previous.price is not None and current.price is not None
            ratio = current.price / previous.price
            value = ratio - Decimal("1") if method is AnalysisMethod.SIMPLE_RETURN else ratio.ln()
            observations.append(ReturnObservation(observed_at=current.observed_at, value=value))

    method_assumption = (
        "Simple return equals price_t / price_t_minus_1 - 1."
        if method is AnalysisMethod.SIMPLE_RETURN
        else "Log return equals ln(price_t / price_t_minus_1)."
    )
    return ReturnSeriesResult(
        analysis_id=analysis_id,
        snapshot_id=snapshot_id,
        methodology=method,
        return_method=method,
        horizon=horizon,
        sample_period=SamplePeriod(start=prices[0].observed_at, end=prices[-1].observed_at),
        observation_count=len(observations),
        assumptions=(*assumptions, method_assumption),
        warnings=tuple(warnings),
        limitations=limitations,
        evidence=evidence,
        observations=tuple(observations),
    )
