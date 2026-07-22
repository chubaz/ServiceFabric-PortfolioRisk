"""Presentation-facing coordination for reviewed, effect-free risk capabilities."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, SerializeAsAny

from risk_agents import AnalysisPlanStep, AgentTimeline, Day1AnalysisRunRequest, DeterministicAnalysisOrchestrator
from risk_analytics import AnalysisEvidence, AnalysisHorizon, RiskReport, ScenarioShock
from risk_analytics.contracts import AnalysisResult
from risk_capabilities import (
    CapabilityRegistry,
    ContributionSummaryRequest,
    ContributionValue,
    DerivedReturnsRequest,
    EvidenceReference,
    ExposureSummaryRequest,
    HistoricalTailRiskRequest,
    NewsClassificationRequest,
    ReportRequest,
    ReturnsRequest,
    ScenarioRequest,
    SyntheticNewsEvent,
    VolatilityRequest,
)
from risk_domain import MarketObservation, PortfolioSnapshot
from risk_domain.digests import sha256_digest


REVIEWED_METHODS = (
    ("simple_returns", "Simple returns", "risk.returns.simple"),
    ("log_returns", "Log returns", "risk.returns.log"),
    ("annualized_volatility", "Annualized volatility", "risk.volatility.annualized"),
    ("maximum_drawdown", "Maximum drawdown", "risk.drawdown.maximum"),
    ("historical_var", "Historical VaR", "risk.var.historical"),
    ("historical_expected_shortfall", "Historical expected shortfall", "risk.expected_shortfall.historical"),
    ("contribution_summary", "Contribution summary", "risk.contribution.summarize"),
    ("fixed_scenario", "Fixed reviewed scenario", "risk.scenario.evaluate"),
)
METHOD_BY_ID = {method_id: (label, capability_id) for method_id, label, capability_id in REVIEWED_METHODS}
REVIEWED_CONFIDENCE_LEVELS = ("0.90", "0.95", "0.99")
DEFAULT_CONFIDENCE_LEVEL = "0.95"
DEFAULT_SCENARIO_ID = "broad_market_minus_10"
SCENARIO_CATALOGUE = (
    {
        "scenario_id": "broad_market_minus_10",
        "label": "Broad market minus 10%",
        "shocks": (("all selected positions", "-0.10"),),
        "all_snapshot_positions": True,
    },
    {
        "scenario_id": "concentrated_holding_minus_20",
        "label": "Concentrated holding minus 20%",
        "shocks": (("instrument-alpha", "-0.20"),),
        "all_snapshot_positions": False,
    },
    {
        "scenario_id": "rates_sensitive_assets_minus_5",
        "label": "Rates-sensitive assets minus 5%",
        "shocks": (("instrument-beta", "-0.05"),),
        "all_snapshot_positions": False,
    },
)
SCENARIO_BY_ID = {item["scenario_id"]: item for item in SCENARIO_CATALOGUE}


class ApiContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RiskAnalysisEnvelope(ApiContract):
    profile: Literal["research", "personal_portfolio"]
    data_state: str
    review_state: Literal["pending"] = "pending"
    human_review_required: Literal[True] = True
    capability_id: str
    effects: tuple[str, ...] = ()
    analysis: SerializeAsAny[AnalysisResult]


class RiskAnalysisCollection(ApiContract):
    analyses: tuple[RiskAnalysisEnvelope, ...]


class AgentTimelineEnvelope(ApiContract):
    profile: Literal["research", "personal_portfolio"]
    data_state: str
    review_state: Literal["pending"] = "pending"
    timeline: AgentTimeline


class AgentTimelineCollection(ApiContract):
    agent_timelines: tuple[AgentTimelineEnvelope, ...]


class ReportEnvelope(ApiContract):
    profile: Literal["research", "personal_portfolio"]
    data_state: str
    review_state: Literal["pending"] = "pending"
    publication_available: Literal[False] = False
    report: RiskReport


class ReportCollection(ApiContract):
    reports: tuple[ReportEnvelope, ...]


class ReviewedRiskAnalysisService:
    """Invoke only the finite reviewed capability set; calculations stay package-owned."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        snapshot: PortfolioSnapshot,
        observations: tuple[MarketObservation, ...],
    ) -> None:
        self.registry = registry
        self.snapshot = snapshot
        self.observations = tuple(
            item for item in observations if item.observed_at <= snapshot.as_of
        )
        self.horizon = AnalysisHorizon(label="daily", periods=1, expected_interval_seconds=86_400)
        self.evidence = (
            AnalysisEvidence(
                evidence_id=f"reviewed-synthetic-prices:{snapshot.snapshot_id}",
                reference="fixture://synthetic/day1/market-prices",
                digest=sha256_digest(self.observations),
                description=(
                    "Reviewed synthetic price observations supplied by the local data boundary "
                    "and bounded by the selected snapshot as-of timestamp."
                ),
            ),
        )

    def _prices(self, instrument_id: str | None = None) -> tuple[MarketObservation, ...]:
        selected_id = instrument_id or self.snapshot.positions[0].instrument_id
        return tuple(item for item in self.observations if item.instrument_id == selected_id)

    def _returns_request(self, method_id: str, instrument_id: str | None = None) -> ReturnsRequest:
        selected_id = instrument_id or self.snapshot.positions[0].instrument_id
        return ReturnsRequest(
            analysis_id=f"{method_id}:{self.snapshot.snapshot_id}:{selected_id}",
            snapshot_id=self.snapshot.snapshot_id,
            prices=self._prices(selected_id),
            horizon=self.horizon,
            evidence=self.evidence,
            assumptions=("The selected series is the reviewed local synthetic daily price fixture.",),
            limitations=(
                "This descriptive historical analysis is not a prediction, certainty claim, or investment advice.",
            ),
        )

    def _simple_returns(self, instrument_id: str | None = None):
        request = self._returns_request("simple_returns", instrument_id)
        result = self.registry.invoke("risk.returns.simple", request)
        if result.status != "succeeded" or result.data is None:
            raise ValueError("the reviewed simple-return capability did not produce an analysis")
        return result.data

    def _scenario_request(self, scenario_id: str) -> ScenarioRequest:
        if scenario_id not in SCENARIO_BY_ID:
            raise ValueError("scenario is not in the reviewed fixed catalogue")
        scenario = SCENARIO_BY_ID[scenario_id]
        portfolio_ids = {position.instrument_id for position in self.snapshot.positions}
        reviewed_shocks = (
            tuple((instrument_id, scenario["shocks"][0][1]) for instrument_id in sorted(portfolio_ids))
            if scenario["all_snapshot_positions"]
            else tuple(
                (instrument_id, shock)
                for instrument_id, shock in scenario["shocks"]
                if instrument_id in portfolio_ids
            )
        )
        if not reviewed_shocks:
            raise ValueError(
                f"reviewed scenario {scenario_id} is unavailable for the selected snapshot instruments"
            )
        shocks = tuple(
            ScenarioShock(instrument_id=instrument_id, percentage_shock=Decimal(shock))
            for instrument_id, shock in reviewed_shocks
        )
        return ScenarioRequest(
            analysis_id=f"fixed_scenario:{scenario['scenario_id']}:{self.snapshot.snapshot_id}",
            portfolio=self.snapshot,
            shocks=shocks,
            horizon=AnalysisHorizon(label="instantaneous", periods=1),
            evidence=self.evidence,
            assumptions=("Only the selected reviewed fixed scenario shocks are applied.",),
            limitations=(
                "The scenario is descriptive, linear, and cannot create a hedge, trade, rebalance, or order instruction.",
            ),
        )

    def analyze(
        self,
        method_id: str,
        *,
        confidence_level: str = DEFAULT_CONFIDENCE_LEVEL,
        scenario_id: str = DEFAULT_SCENARIO_ID,
    ):
        if method_id not in METHOD_BY_ID:
            raise ValueError("methodology is not a registered reviewed capability")
        if confidence_level not in REVIEWED_CONFIDENCE_LEVELS:
            raise ValueError("confidence level is not one of the reviewed values")
        if scenario_id not in SCENARIO_BY_ID:
            raise ValueError("scenario is not in the reviewed fixed catalogue")
        capability_id = METHOD_BY_ID[method_id][1]
        if method_id in {"simple_returns", "log_returns"}:
            request = self._returns_request(method_id)
        elif method_id in {"annualized_volatility", "maximum_drawdown", "historical_var", "historical_expected_shortfall"}:
            source = self._simple_returns()
            common = {
                "analysis_id": f"{method_id}:{self.snapshot.snapshot_id}",
                "returns": source,
                "evidence": self.evidence,
                "limitations": (
                    "This descriptive historical analysis is not a prediction, certainty claim, or investment advice.",
                ),
            }
            if method_id == "annualized_volatility":
                request = VolatilityRequest(**common, periods_per_year=252)
            elif method_id == "maximum_drawdown":
                request = DerivedReturnsRequest(**common)
            else:
                request = HistoricalTailRiskRequest(**common, confidence_level=Decimal(confidence_level))
        elif method_id == "fixed_scenario":
            request = self._scenario_request(scenario_id)
        else:
            exposure = self.registry.invoke(
                "portfolio.exposure.summarize",
                ExposureSummaryRequest(
                    snapshot_id=f"analysis-exposure:{self.snapshot.snapshot_id}",
                    portfolio_snapshot=self.snapshot,
                    evidence_references=tuple(
                        EvidenceReference(
                            evidence_id=item.evidence_id,
                            reference=item.reference,
                            source_type="analysis_evidence",
                            digest=item.digest,
                            description=item.description,
                        )
                        for item in self.evidence
                    ),
                ),
            )
            if exposure.status != "succeeded" or exposure.data is None:
                raise ValueError("the reviewed exposure capability did not produce contribution weights")
            values = []
            for item in exposure.data.position_exposures:
                try:
                    source = self._simple_returns(item.instrument_id)
                    instrument_return = source.observations[-1].value if source.observations else None
                except ValueError:
                    instrument_return = None
                values.append(
                    ContributionValue(
                        instrument_id=item.instrument_id,
                        weight=item.weight,
                        instrument_return=instrument_return,
                    )
                )
            source = self._simple_returns()
            request = ContributionSummaryRequest(
                analysis_id=f"contribution_summary:{self.snapshot.snapshot_id}",
                snapshot_id=self.snapshot.snapshot_id,
                values=tuple(values),
                horizon=self.horizon,
                sample_period=source.sample_period,
                evidence=self.evidence,
                limitations=(
                    "Contributions use reviewed supplied weights and returns; missing constituent returns remain missing.",
                ),
            )
        result = self.registry.invoke(capability_id, request)
        if result.status != "succeeded" or result.data is None:
            warning = "; ".join(result.warnings) or "no capability output was returned"
            raise ValueError(f"reviewed capability {capability_id} failed: {warning}")
        return result

    def report(self, method_id: str, *, confidence_level: str, scenario_id: str):
        analysis = self.analyze(method_id, confidence_level=confidence_level, scenario_id=scenario_id)
        label = METHOD_BY_ID[method_id][0]
        result = self.registry.invoke(
            "risk.report.render",
            ReportRequest(
                analysis_id=f"report:{analysis.data.analysis_id}",
                title=f"{label} review report",
                result=analysis.data,
            ),
        )
        if result.status != "succeeded" or result.data is None:
            raise ValueError("the reviewed report capability did not produce a report")
        return analysis, result

    def timeline(self) -> AgentTimeline:
        returns_request = self._returns_request("timeline_simple_returns")
        source = self.registry.invoke("risk.returns.simple", returns_request)
        if source.status != "succeeded" or source.data is None:
            raise ValueError("timeline source analysis is unavailable")
        scenario_request = self._scenario_request(DEFAULT_SCENARIO_ID)
        report_request = ReportRequest(
            analysis_id=f"timeline-report:{self.snapshot.snapshot_id}",
            title="Four-role risk analysis review report",
            result=source.data,
        )
        evidence_references = tuple(
            EvidenceReference(
                evidence_id=item.evidence_id,
                reference=item.reference,
                source_type="analysis_evidence",
                digest=item.digest,
                description=item.description,
            )
            for item in self.evidence
        )
        news_request = NewsClassificationRequest(
            event=SyntheticNewsEvent(
                event_id="wave-1c-synthetic-context",
                instrument_id=self.snapshot.positions[0].instrument_id,
                headline="Synthetic reviewed portfolio-risk context",
                sentiment="negative",
                relevance="high",
            ),
            evidence_references=evidence_references,
        )
        start = self.snapshot.as_of
        planned = (
            ("risk.agent.market_data", "risk.returns.simple", returns_request),
            ("risk.agent.portfolio_exposure", "risk.scenario.evaluate", scenario_request),
            ("risk.agent.news_sentiment", "news.event.classify", news_request),
            ("risk.agent.alert_recommendation", "risk.report.render", report_request),
        )
        request = Day1AnalysisRunRequest(
            timeline_id=f"analysis-timeline:{self.snapshot.snapshot_id}",
            steps=tuple(
                AnalysisPlanStep(
                    sequence=index,
                    role=role,
                    capability_id=capability_id,
                    started_at=start + timedelta(minutes=index),
                    observed_at=start + timedelta(minutes=index, seconds=30),
                    request=capability_request,
                )
                for index, (role, capability_id, capability_request) in enumerate(planned, start=1)
            ),
        )
        return DeterministicAnalysisOrchestrator(self.registry).run(request)
