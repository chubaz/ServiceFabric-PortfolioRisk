"""Deterministic Wave 0C orchestration with registry-only calculations."""

from typing import Literal

from pydantic import Field
from risk_capabilities import AlertDraft, AlertSynthesisRequest, AnomalyDetectionRequest, CapabilityRegistry, CapabilityResult, EvidenceReference, ExposureSummaryRequest, NewsClassificationRequest, SyntheticNewsEvent
from risk_domain import PortfolioSnapshot

from .active import RegisteredCapabilityAgent
from .contracts import AgentContract
from risk_domain.monitoring import ContextualMonitoringRun, PolicyEvaluationRequest
from risk_capabilities import (
    ContextualMonitoringCapabilityRequest,
    ContextualMonitoringWorkflowRequest,
    EventQueryCapabilityRequest,
    MonitoringAlertSynthesisCapabilityRequest,
    PolicyEvaluationCapabilityRequest,
    PortfolioDataContextCapabilityRequest,
    build_contextual_monitoring_request,
    event_signals_from_result,
)


class MonitoringRunRequest(AgentContract):
    portfolio_snapshot: PortfolioSnapshot
    market_request: AnomalyDetectionRequest
    news_event: SyntheticNewsEvent
    evidence_references: tuple[EvidenceReference, ...] = Field(min_length=1)


class MonitoringRun(AgentContract):
    status: Literal["succeeded", "failed", "stopped"]
    outputs: tuple[CapabilityResult[object], ...]
    alert_draft: AlertDraft | None = None
    human_review_required: Literal[True] = True
    effects: tuple[str, ...] = ()


class DeterministicMonitoringOrchestrator:
    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry
        self.market_agent = RegisteredCapabilityAgent("risk.agent.market_data", registry)
        self.exposure_agent = RegisteredCapabilityAgent("risk.agent.portfolio_exposure", registry)
        self.news_agent = RegisteredCapabilityAgent("risk.agent.news_sentiment", registry)
        self.alert_agent = RegisteredCapabilityAgent("risk.agent.alert_recommendation", registry)

    def run(self, request: MonitoringRunRequest) -> MonitoringRun:
        market = self.market_agent.invoke("market.anomaly.detect", request.market_request)
        if market.status != "succeeded":
            return MonitoringRun(status=market.status, outputs=(market,))
        exposure = self.exposure_agent.invoke("portfolio.exposure.summarize", ExposureSummaryRequest(snapshot_id="monitoring-exposure:" + request.portfolio_snapshot.snapshot_id, portfolio_snapshot=request.portfolio_snapshot, evidence_references=request.evidence_references))
        if exposure.status != "succeeded":
            return MonitoringRun(status=exposure.status, outputs=(market, exposure))
        news = self.news_agent.invoke("news.event.classify", NewsClassificationRequest(event=request.news_event, evidence_references=request.evidence_references))
        outputs = (market, exposure, news)
        if news.status != "succeeded":
            return MonitoringRun(status=news.status, outputs=outputs)
        alert = self.alert_agent.invoke("alert.draft.synthesize", AlertSynthesisRequest(market_output=market, exposure_output=exposure, news_output=news, evidence_references=request.evidence_references))
        return MonitoringRun(status=alert.status, outputs=outputs + (alert,), alert_draft=alert.data if alert.status == "succeeded" else None)


class DeterministicContextualMonitoringOrchestrator:
    """Invoke all four registered role capabilities before assembling the run."""

    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry
        self.market_agent = RegisteredCapabilityAgent(
            "risk.agent.market_data", registry
        )
        self.portfolio_agent = RegisteredCapabilityAgent(
            "risk.agent.portfolio_exposure", registry
        )
        self.news_agent = RegisteredCapabilityAgent(
            "risk.agent.news_sentiment", registry
        )
        self.alert_agent = RegisteredCapabilityAgent(
            "risk.agent.alert_recommendation", registry
        )

    def run(
        self, request: ContextualMonitoringWorkflowRequest
    ) -> ContextualMonitoringRun:
        context_request = PortfolioDataContextCapabilityRequest(
            request=request.context_request,
            evidence_references=request.evidence_references,
        )
        context_result = self.market_agent.invoke(
            "portfolio.data_context.create", context_request
        )
        if context_result.data is None:
            raise ValueError("portfolio data-context capability returned no context")
        event_request = EventQueryCapabilityRequest(
            request=request.event_query_request,
            snapshot=request.event_snapshot,
            as_of=request.context_request.as_of,
            evidence_references=request.evidence_references,
        )
        event_result = self.news_agent.invoke("events.query.as_of", event_request)
        events = event_signals_from_result(
            event_result, context=context_result.data
        )
        policy_request = PolicyEvaluationCapabilityRequest(
            request=PolicyEvaluationRequest(
                evaluation_id=request.evaluation_id,
                policy_version=request.policy_version,
                context=context_result.data,
                evaluated_at=request.run_at,
                metrics=request.metrics,
                events=events,
                evidence=request.context_request.evidence,
            ),
            evidence_references=request.evidence_references,
        )
        policy_result = self.portfolio_agent.invoke(
            "monitoring.policy.evaluate", policy_request
        )
        if policy_result.data is None:
            raise ValueError("monitoring policy capability returned no evaluation")
        alert_request = MonitoringAlertSynthesisCapabilityRequest(
            policy_evaluation=policy_result.data,
            run_at=request.run_at,
            evidence=request.context_request.evidence,
            evidence_references=request.evidence_references,
        )
        alert_result = self.alert_agent.invoke(
            "monitoring.alert.synthesize", alert_request
        )
        contextual_request = build_contextual_monitoring_request(
            request,
            context_result=context_result,
            policy_result=policy_result,
            event_result=event_result,
            alert_result=alert_result,
        )
        result = self.alert_agent.invoke(
            "monitoring.run.contextual",
            ContextualMonitoringCapabilityRequest(
                request=contextual_request,
                evidence_references=request.evidence_references,
            ),
        )
        if result.data is None:
            raise ValueError("contextual monitoring capability returned no run")
        return result.data
