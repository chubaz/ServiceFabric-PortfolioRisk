"""Deterministic Wave 0C orchestration with registry-only calculations."""

from typing import Literal

from pydantic import Field
from risk_capabilities import AlertDraft, AlertSynthesisRequest, AnomalyDetectionRequest, CapabilityRegistry, CapabilityResult, EvidenceReference, ExposureSummaryRequest, NewsClassificationRequest, SyntheticNewsEvent
from risk_domain import PortfolioSnapshot

from .active import RegisteredCapabilityAgent
from .contracts import AgentContract


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
