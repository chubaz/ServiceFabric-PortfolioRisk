"""Typed, effect-free capability adapters for the reviewed risk analytics."""

from __future__ import annotations

from decimal import Decimal
from pydantic import Field, field_validator

from risk_analytics import (
    AnalysisEvidence,
    AnalysisHorizon,
    AnalysisMethod,
    ContributionSummary,
    DrawdownResult,
    HistoricalTailRiskResult,
    ReturnSeriesResult,
    RiskReport,
    SamplePeriod,
    ScenarioResult,
    ScenarioShock,
    VolatilityResult,
    annualized_volatility,
    apply_scenario,
    calculate_returns,
    historical_tail_risk,
    maximum_drawdown,
    render_report,
    summarize_contributions,
)
from risk_domain import MarketObservation, PortfolioSnapshot

from .contracts import CapabilityContract, EvidenceReference


AnalysisSourceResult = (
    ReturnSeriesResult
    | VolatilityResult
    | DrawdownResult
    | HistoricalTailRiskResult
    | ScenarioResult
    | ContributionSummary
)


class AnalyticsRequest(CapabilityContract):
    """Common evidence and disclosure inputs for an analytics invocation."""

    analysis_id: str = Field(min_length=1, max_length=256)
    evidence: tuple[AnalysisEvidence, ...] = Field(min_length=1)
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    @field_validator("assumptions", "limitations")
    @classmethod
    def metadata_is_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("analytics request metadata must be unique")
        return values

    @property
    def evidence_references(self) -> tuple[EvidenceReference, ...]:
        return evidence_references(self.evidence)


class ReturnsRequest(AnalyticsRequest):
    snapshot_id: str = Field(min_length=1, max_length=256)
    prices: tuple[MarketObservation, ...] = Field(min_length=2)
    horizon: AnalysisHorizon


class DerivedReturnsRequest(AnalyticsRequest):
    returns: ReturnSeriesResult
    horizon: AnalysisHorizon | None = None


class VolatilityRequest(DerivedReturnsRequest):
    periods_per_year: int = Field(default=252, ge=1)


class HistoricalTailRiskRequest(DerivedReturnsRequest):
    confidence_level: Decimal


class ScenarioRequest(AnalyticsRequest):
    portfolio: PortfolioSnapshot
    shocks: tuple[ScenarioShock, ...] = Field(min_length=1)
    horizon: AnalysisHorizon


class ContributionValue(CapabilityContract):
    instrument_id: str = Field(min_length=1, max_length=256)
    weight: Decimal
    instrument_return: Decimal | None = None


class ContributionSummaryRequest(AnalyticsRequest):
    snapshot_id: str = Field(min_length=1, max_length=256)
    values: tuple[ContributionValue, ...] = Field(min_length=1)
    portfolio_return: Decimal | None = None
    horizon: AnalysisHorizon
    sample_period: SamplePeriod

    @field_validator("values")
    @classmethod
    def values_are_unique_and_ordered(
        cls, values: tuple[ContributionValue, ...]
    ) -> tuple[ContributionValue, ...]:
        identifiers = [item.instrument_id for item in values]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("contribution instruments must be unique")
        return tuple(sorted(values, key=lambda item: item.instrument_id))


class ReportRequest(CapabilityContract):
    analysis_id: str = Field(min_length=1, max_length=256)
    title: str = Field(min_length=1, max_length=256)
    result: AnalysisSourceResult

    @property
    def evidence_references(self) -> tuple[EvidenceReference, ...]:
        return evidence_references(self.result.evidence)


def evidence_references(
    evidence: tuple[AnalysisEvidence, ...],
) -> tuple[EvidenceReference, ...]:
    """Retain complete analytics evidence in the capability envelope."""
    return tuple(
        EvidenceReference(
            evidence_id=item.evidence_id,
            reference=item.reference,
            source_type="analysis_evidence",
            digest=item.digest,
            description=item.description,
        )
        for item in evidence
    )


def simple_returns(request: ReturnsRequest) -> ReturnSeriesResult:
    return calculate_returns(
        analysis_id=request.analysis_id,
        snapshot_id=request.snapshot_id,
        prices=request.prices,
        method=AnalysisMethod.SIMPLE_RETURN,
        horizon=request.horizon,
        evidence=request.evidence,
        assumptions=request.assumptions,
        limitations=request.limitations,
    )


def log_returns(request: ReturnsRequest) -> ReturnSeriesResult:
    return calculate_returns(
        analysis_id=request.analysis_id,
        snapshot_id=request.snapshot_id,
        prices=request.prices,
        method=AnalysisMethod.LOG_RETURN,
        horizon=request.horizon,
        evidence=request.evidence,
        assumptions=request.assumptions,
        limitations=request.limitations,
    )


def volatility(request: VolatilityRequest) -> VolatilityResult:
    return annualized_volatility(
        analysis_id=request.analysis_id,
        returns=request.returns,
        evidence=request.evidence,
        horizon=request.horizon,
        periods_per_year=request.periods_per_year,
        assumptions=request.assumptions,
        limitations=request.limitations,
    )


def drawdown(request: DerivedReturnsRequest) -> DrawdownResult:
    return maximum_drawdown(
        analysis_id=request.analysis_id,
        returns=request.returns,
        evidence=request.evidence,
        horizon=request.horizon,
        assumptions=request.assumptions,
        limitations=request.limitations,
    )


def tail_risk(request: HistoricalTailRiskRequest) -> HistoricalTailRiskResult:
    return historical_tail_risk(
        analysis_id=request.analysis_id,
        returns=request.returns,
        confidence_level=request.confidence_level,
        evidence=request.evidence,
        horizon=request.horizon,
        assumptions=request.assumptions,
        limitations=request.limitations,
    )


def scenario(request: ScenarioRequest) -> ScenarioResult:
    return apply_scenario(
        analysis_id=request.analysis_id,
        portfolio=request.portfolio,
        shocks=request.shocks,
        horizon=request.horizon,
        evidence=request.evidence,
        assumptions=request.assumptions,
        limitations=request.limitations,
    )


def contributions(request: ContributionSummaryRequest) -> ContributionSummary:
    return summarize_contributions(
        analysis_id=request.analysis_id,
        snapshot_id=request.snapshot_id,
        weights={item.instrument_id: item.weight for item in request.values},
        instrument_returns={
            item.instrument_id: item.instrument_return for item in request.values
        },
        portfolio_return=request.portfolio_return,
        horizon=request.horizon,
        sample_period=request.sample_period,
        evidence=request.evidence,
        assumptions=request.assumptions,
        limitations=request.limitations,
    )


def report(request: ReportRequest) -> RiskReport:
    return render_report(
        analysis_id=request.analysis_id,
        title=request.title,
        result=request.result,
    )
