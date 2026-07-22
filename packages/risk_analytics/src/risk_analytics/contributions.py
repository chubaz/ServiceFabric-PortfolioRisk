"""Deterministic weighted-return contribution summaries."""

from __future__ import annotations

from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from typing import Mapping

from risk_domain.common import decimal_value

from .contracts import AnalysisEvidence, AnalysisHorizon, AnalysisMethod, AnalysisWarning, ContributionItem, ContributionSummary, SamplePeriod
from .policies import DECIMAL_PRECISION, MISSING_CONSTITUENT_RETURN


CONTRIBUTION_CONTEXT = Context(prec=DECIMAL_PRECISION, rounding=ROUND_HALF_EVEN)


def summarize_contributions(
    *,
    analysis_id: str,
    snapshot_id: str,
    weights: Mapping[str, Decimal],
    instrument_returns: Mapping[str, Decimal | None],
    portfolio_return: Decimal | None,
    horizon: AnalysisHorizon,
    sample_period: SamplePeriod,
    evidence: tuple[AnalysisEvidence, ...],
    assumptions: tuple[str, ...] = (),
    limitations: tuple[str, ...] = (),
) -> ContributionSummary:
    if not weights:
        raise ValueError("contribution summaries require at least one constituent weight")
    unknown = set(instrument_returns) - set(weights)
    if unknown:
        raise ValueError("instrument returns cannot reference constituents without weights")
    items: list[ContributionItem] = []
    missing: list[str] = []
    with localcontext(CONTRIBUTION_CONTEXT):
        for instrument_id in sorted(weights):
            weight = decimal_value(weights[instrument_id])
            instrument_return = instrument_returns.get(instrument_id)
            if instrument_return is None:
                missing.append(instrument_id)
                items.append(ContributionItem(instrument_id=instrument_id, weight=weight))
                continue
            value = decimal_value(instrument_return)
            items.append(
                ContributionItem(
                    instrument_id=instrument_id,
                    weight=weight,
                    instrument_return=value,
                    contribution=weight * value,
                )
            )
        contribution_sum = sum(
            (item.contribution for item in items if item.contribution is not None), start=Decimal("0")
        )
    warnings: list[AnalysisWarning] = []
    if missing:
        warnings.append(
            AnalysisWarning(
                code=MISSING_CONSTITUENT_RETURN,
                message=(
                    "Constituents with missing returns were excluded from the sum and were not converted to zero: "
                    + ", ".join(missing)
                    + "."
                ),
            )
        )
    checked_portfolio_return = decimal_value(portfolio_return) if portfolio_return is not None else None
    with localcontext(CONTRIBUTION_CONTEXT):
        reconciliation = (
            contribution_sum - checked_portfolio_return if checked_portfolio_return is not None else None
        )
    return ContributionSummary(
        analysis_id=analysis_id,
        snapshot_id=snapshot_id,
        methodology=AnalysisMethod.CONTRIBUTION_SUMMARY,
        horizon=horizon,
        sample_period=sample_period,
        observation_count=len(items) - len(missing),
        assumptions=(*assumptions, "Each contribution equals weight multiplied by instrument return."),
        warnings=tuple(warnings),
        limitations=limitations,
        evidence=evidence,
        items=tuple(items),
        contribution_sum=contribution_sum,
        portfolio_return=checked_portfolio_return,
        reconciliation_difference=reconciliation,
    )
