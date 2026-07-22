"""Immutable contracts shared by the bounded risk analytics package."""

from __future__ import annotations

from datetime import datetime
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from risk_domain.common import ImmutableDomainModel, NonEmptyString, decimal_value, normalize_utc
from risk_domain.digests import sha256_digest
from risk_domain.models import SHA256_DIGEST_PATTERN

from .policies import DECIMAL_PRECISION, MAX_CONFIDENCE_LEVEL, MIN_CONFIDENCE_LEVEL


ANALYTICS_CONTEXT = Context(prec=DECIMAL_PRECISION, rounding=ROUND_HALF_EVEN)


class AnalysisMethod(str, Enum):
    SIMPLE_RETURN = "simple-return"
    LOG_RETURN = "log-return"
    ANNUALIZED_VOLATILITY = "annualized-volatility"
    MAXIMUM_DRAWDOWN = "maximum-drawdown"
    HISTORICAL_TAIL_RISK = "historical-tail-risk"
    DETERMINISTIC_SCENARIO = "deterministic-scenario"
    CONTRIBUTION_SUMMARY = "contribution-summary"
    RISK_REPORT = "risk-report"


class AnalysisHorizon(ImmutableDomainModel):
    label: NonEmptyString
    periods: int = Field(default=1, ge=1)
    expected_interval_seconds: int | None = Field(default=None, ge=1)


class SamplePeriod(ImmutableDomainModel):
    start: datetime
    end: datetime

    _start = field_validator("start")(normalize_utc)
    _end = field_validator("end")(normalize_utc)

    @model_validator(mode="after")
    def end_is_not_before_start(self) -> "SamplePeriod":
        if self.end < self.start:
            raise ValueError("sample period end cannot precede its start")
        return self


class AnalysisWarning(ImmutableDomainModel):
    code: NonEmptyString
    message: NonEmptyString


class AnalysisEvidence(ImmutableDomainModel):
    evidence_id: NonEmptyString
    reference: NonEmptyString
    digest: str = Field(pattern=rf"^{SHA256_DIGEST_PATTERN}$")
    description: NonEmptyString


class ReturnObservation(ImmutableDomainModel):
    observed_at: datetime
    value: Decimal

    _observed_at = field_validator("observed_at")(normalize_utc)
    _value = field_validator("value")(decimal_value)


class AnalysisResult(ImmutableDomainModel):
    """Common metadata and digest rules for every persisted analysis result."""

    analysis_id: NonEmptyString
    snapshot_id: NonEmptyString
    methodology: AnalysisMethod
    horizon: AnalysisHorizon
    sample_period: SamplePeriod
    observation_count: int = Field(ge=0)
    assumptions: tuple[NonEmptyString, ...] = ()
    warnings: tuple[AnalysisWarning, ...] = ()
    limitations: tuple[NonEmptyString, ...] = ()
    evidence: tuple[AnalysisEvidence, ...] = Field(min_length=1)
    output_digest: str | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    @field_validator("assumptions", "limitations")
    @classmethod
    def text_is_unique_and_ordered(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("analysis metadata entries must remain unique")
        return tuple(sorted(values))

    @field_validator("warnings")
    @classmethod
    def warnings_are_unique_and_ordered(
        cls, values: tuple[AnalysisWarning, ...]
    ) -> tuple[AnalysisWarning, ...]:
        keys = [(item.code, item.message) for item in values]
        if len(keys) != len(set(keys)):
            raise ValueError("analysis warnings must remain unique")
        return tuple(sorted(values, key=lambda item: (item.code, item.message)))

    @field_validator("evidence")
    @classmethod
    def evidence_is_unique_and_ordered(
        cls, values: tuple[AnalysisEvidence, ...]
    ) -> tuple[AnalysisEvidence, ...]:
        ids = [item.evidence_id for item in values]
        if len(ids) != len(set(ids)):
            raise ValueError("analysis evidence identifiers must remain unique")
        return tuple(sorted(values, key=lambda item: item.evidence_id))

    @model_validator(mode="after")
    def deterministic_output_digest(self) -> "AnalysisResult":
        expected = sha256_digest(self.model_dump(mode="python", exclude={"output_digest"}))
        if self.output_digest is not None and self.output_digest != expected:
            raise ValueError("output_digest must equal the canonical analysis digest")
        object.__setattr__(self, "output_digest", expected)
        return self


class ReturnSeriesResult(AnalysisResult):
    return_method: AnalysisMethod
    observations: tuple[ReturnObservation, ...]

    @model_validator(mode="after")
    def return_contract_is_consistent(self) -> "ReturnSeriesResult":
        if self.methodology not in {AnalysisMethod.SIMPLE_RETURN, AnalysisMethod.LOG_RETURN}:
            raise ValueError("return series methodology must be simple-return or log-return")
        if self.return_method != self.methodology:
            raise ValueError("return_method must match methodology")
        if self.observation_count != len(self.observations):
            raise ValueError("observation_count must match return observations")
        timestamps = [item.observed_at for item in self.observations]
        if timestamps != sorted(timestamps) or len(timestamps) != len(set(timestamps)):
            raise ValueError("return observations must be strictly ordered by time")
        return self


class VolatilityResult(AnalysisResult):
    methodology: Literal[AnalysisMethod.ANNUALIZED_VOLATILITY]
    annualized_volatility: Decimal = Field(ge=Decimal("0"))
    periods_per_year: int = Field(ge=1)

    _annualized_volatility = field_validator("annualized_volatility")(decimal_value)


class DrawdownResult(AnalysisResult):
    methodology: Literal[AnalysisMethod.MAXIMUM_DRAWDOWN]
    maximum_drawdown: Decimal = Field(ge=Decimal("0"))
    peak_at: datetime
    trough_at: datetime
    wealth_path_method: AnalysisMethod

    _maximum_drawdown = field_validator("maximum_drawdown")(decimal_value)
    _peak_at = field_validator("peak_at")(normalize_utc)
    _trough_at = field_validator("trough_at")(normalize_utc)

    @model_validator(mode="after")
    def drawdown_timestamps_and_method_are_consistent(self) -> "DrawdownResult":
        if self.wealth_path_method not in {AnalysisMethod.SIMPLE_RETURN, AnalysisMethod.LOG_RETURN}:
            raise ValueError("wealth path must use simple or log returns")
        if self.trough_at < self.peak_at:
            raise ValueError("drawdown trough cannot precede its peak")
        return self


ConfidenceLevel = Annotated[Decimal, Field(ge=MIN_CONFIDENCE_LEVEL, le=MAX_CONFIDENCE_LEVEL)]


class HistoricalTailRiskResult(AnalysisResult):
    methodology: Literal[AnalysisMethod.HISTORICAL_TAIL_RISK]
    confidence_level: ConfidenceLevel
    value_at_risk: Decimal
    expected_shortfall: Decimal
    historical_rank: int = Field(ge=1)
    tail_observation_count: int = Field(ge=1)
    reviewed_minimum_observation_count: int = Field(ge=1)

    _confidence_level = field_validator("confidence_level")(decimal_value)
    _value_at_risk = field_validator("value_at_risk")(decimal_value)
    _expected_shortfall = field_validator("expected_shortfall")(decimal_value)

    @model_validator(mode="after")
    def tail_metadata_is_consistent(self) -> "HistoricalTailRiskResult":
        if self.methodology is not AnalysisMethod.HISTORICAL_TAIL_RISK:
            raise ValueError("tail-risk methodology must be historical-tail-risk")
        if self.historical_rank > self.observation_count:
            raise ValueError("historical rank cannot exceed observation_count")
        if self.tail_observation_count != self.observation_count - self.historical_rank + 1:
            raise ValueError("tail_observation_count must include observations at and beyond the rank")
        return self


class ScenarioShock(ImmutableDomainModel):
    instrument_id: NonEmptyString
    percentage_shock: Decimal = Field(ge=Decimal("-1"), le=Decimal("1"))

    _percentage_shock = field_validator("percentage_shock")(decimal_value)


class ScenarioPositionResult(ImmutableDomainModel):
    instrument_id: NonEmptyString
    market_value: Decimal
    percentage_shock: Decimal
    profit_and_loss: Decimal

    _market_value = field_validator("market_value")(decimal_value)
    _percentage_shock = field_validator("percentage_shock")(decimal_value)
    _profit_and_loss = field_validator("profit_and_loss")(decimal_value)

    @model_validator(mode="after")
    def profit_and_loss_is_linear(self) -> "ScenarioPositionResult":
        with localcontext(ANALYTICS_CONTEXT):
            expected = self.market_value * self.percentage_shock
        if self.profit_and_loss != expected:
            raise ValueError("position profit and loss must equal market value multiplied by shock")
        return self


class ScenarioResult(AnalysisResult):
    methodology: Literal[AnalysisMethod.DETERMINISTIC_SCENARIO]
    shocks: tuple[ScenarioShock, ...]
    positions: tuple[ScenarioPositionResult, ...]
    portfolio_profit_and_loss: Decimal
    currency: NonEmptyString

    _portfolio_profit_and_loss = field_validator("portfolio_profit_and_loss")(decimal_value)

    @model_validator(mode="after")
    def scenario_values_are_ordered_and_reconciled(self) -> "ScenarioResult":
        shock_ids = [item.instrument_id for item in self.shocks]
        position_ids = [item.instrument_id for item in self.positions]
        if shock_ids != sorted(shock_ids) or len(shock_ids) != len(set(shock_ids)):
            raise ValueError("scenario shocks must be uniquely ordered by instrument")
        if position_ids != sorted(position_ids) or len(position_ids) != len(set(position_ids)):
            raise ValueError("scenario positions must be uniquely ordered by instrument")
        if self.observation_count != len(self.positions):
            raise ValueError("observation_count must match covered scenario positions")
        with localcontext(ANALYTICS_CONTEXT):
            expected_profit_and_loss = sum(
                (item.profit_and_loss for item in self.positions), start=Decimal("0")
            )
        if self.portfolio_profit_and_loss != expected_profit_and_loss:
            raise ValueError("portfolio profit and loss must reconcile to position profit and loss")
        return self


class ContributionItem(ImmutableDomainModel):
    instrument_id: NonEmptyString
    weight: Decimal
    instrument_return: Decimal | None = None
    contribution: Decimal | None = None

    _weight = field_validator("weight")(decimal_value)

    @field_validator("instrument_return", "contribution")
    @classmethod
    def optional_decimal_is_finite(cls, value: Decimal | None) -> Decimal | None:
        return decimal_value(value) if value is not None else None

    @model_validator(mode="after")
    def missing_values_remain_missing(self) -> "ContributionItem":
        if (self.instrument_return is None) != (self.contribution is None):
            raise ValueError("instrument return and contribution must both be present or both be missing")
        with localcontext(ANALYTICS_CONTEXT):
            expected = self.weight * self.instrument_return if self.instrument_return is not None else None
        if self.instrument_return is not None and self.contribution != expected:
            raise ValueError("contribution must equal weight multiplied by instrument return")
        return self


class ContributionSummary(AnalysisResult):
    methodology: Literal[AnalysisMethod.CONTRIBUTION_SUMMARY]
    items: tuple[ContributionItem, ...]
    contribution_sum: Decimal
    portfolio_return: Decimal | None = None
    reconciliation_difference: Decimal | None = None

    _contribution_sum = field_validator("contribution_sum")(decimal_value)

    @field_validator("portfolio_return", "reconciliation_difference")
    @classmethod
    def optional_summary_decimal_is_finite(cls, value: Decimal | None) -> Decimal | None:
        return decimal_value(value) if value is not None else None

    @model_validator(mode="after")
    def contribution_values_are_ordered_and_reconciled(self) -> "ContributionSummary":
        ids = [item.instrument_id for item in self.items]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError("contribution items must be uniquely ordered by instrument")
        present = [item.contribution for item in self.items if item.contribution is not None]
        if self.observation_count != len(present):
            raise ValueError("observation_count must match present constituent returns")
        with localcontext(ANALYTICS_CONTEXT):
            expected_sum = sum(present, start=Decimal("0"))
            expected = expected_sum - self.portfolio_return if self.portfolio_return is not None else None
        if self.contribution_sum != expected_sum:
            raise ValueError("contribution_sum must reconcile to contribution items")
        if self.reconciliation_difference != expected:
            raise ValueError("reconciliation_difference must disclose contribution sum minus portfolio return")
        return self


class RiskReport(AnalysisResult):
    methodology: Literal[AnalysisMethod.RISK_REPORT]
    title: NonEmptyString
    source_output_digest: str = Field(pattern=rf"^{SHA256_DIGEST_PATTERN}$")
    markdown: Annotated[str, Field(min_length=1)]
    html: Annotated[str, Field(min_length=1)]


ResultContract = (
    ReturnSeriesResult
    | VolatilityResult
    | DrawdownResult
    | HistoricalTailRiskResult
    | ScenarioResult
    | ContributionSummary
    | RiskReport
)
