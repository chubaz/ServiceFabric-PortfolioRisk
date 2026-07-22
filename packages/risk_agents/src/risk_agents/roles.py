"""The four mandatory Day 0 review-bound role cards."""

from risk_capabilities import CAPABILITY_BY_ID, ORDER_AND_BROKER_EFFECTS

from .contracts import AgentRole


def _role(role_id: str, objective: str, capability_id: str) -> AgentRole:
    return AgentRole(
        role_id=role_id,
        objective=objective,
        allowed_capability_ids=(capability_id,),
        denied_effects=ORDER_AND_BROKER_EFFECTS,
        input_contracts=("CapabilityInvocation", "EvidenceReference[]"),
        output_contracts=("CapabilityOutcome",),
        evidence_requirements=("At least one supplied evidence reference is required.",),
        escalation_policy="Escalate missing, partial, stale, or consequential findings to a human reviewer.",
        human_review_required=True,
    )


AGENT_ROLES = (
    AgentRole(role_id="risk.agent.news_sentiment", objective="News & Sentiment Agent: retain registered synthetic-event classification as context only.", allowed_capability_ids=("news.event.classify", "risk.capability.news_sentiment"), denied_effects=ORDER_AND_BROKER_EFFECTS, input_contracts=("NewsClassificationRequest", "EvidenceReference[]"), output_contracts=("CapabilityResult",), evidence_requirements=("At least one supplied evidence reference is required.",), escalation_policy="Escalate synthetic event context to a human reviewer; never invent market observations.", human_review_required=True),
    AgentRole(role_id="risk.agent.market_data", objective="Market Data Agent: invoke registered return, volatility, drawdown, and historical tail-risk capabilities.", allowed_capability_ids=("data.synthetic.ingest", "market.anomaly.detect", "risk.returns.simple", "risk.returns.log", "risk.volatility.annualized", "risk.drawdown.maximum", "risk.var.historical", "risk.expected_shortfall.historical"), denied_effects=ORDER_AND_BROKER_EFFECTS, input_contracts=("SyntheticIngestRequest", "AnomalyDetectionRequest", "ReturnsRequest", "DerivedReturnsRequest", "VolatilityRequest", "HistoricalTailRiskRequest", "EvidenceReference[]"), output_contracts=("CapabilityResult",), evidence_requirements=("At least one supplied evidence reference is required.",), escalation_policy="Escalate missing, partial, stale, tail-sample, or consequential findings to a human reviewer.", human_review_required=True),
    AgentRole(role_id="risk.agent.portfolio_exposure", objective="Portfolio Exposure Agent: invoke registered snapshot, exposure, deterministic scenario, and contribution capabilities.", allowed_capability_ids=("portfolio.snapshot.create", "portfolio.exposure.summarize", "risk.scenario.evaluate", "risk.contribution.summarize"), denied_effects=ORDER_AND_BROKER_EFFECTS, input_contracts=("PortfolioSnapshotRequest", "ExposureSummaryRequest", "ScenarioRequest", "ContributionSummaryRequest", "EvidenceReference[]"), output_contracts=("CapabilityResult",), evidence_requirements=("At least one supplied evidence reference is required.",), escalation_policy="Escalate missing, partial, stale, unreconciled, or consequential findings to a human reviewer.", human_review_required=True),
    AgentRole(role_id="risk.agent.alert_recommendation", objective="Alert & Recommendation Agent: synthesize analytics findings and reports for explicit human review.", allowed_capability_ids=("alert.draft.synthesize", "alert.draft.review", "risk.report.render"), denied_effects=ORDER_AND_BROKER_EFFECTS, input_contracts=("ReportRequest", "AlertSynthesisRequest", "AlertReviewRequest", "EvidenceReference[]"), output_contracts=("CapabilityResult",), evidence_requirements=("At least one supplied evidence reference is required.",), escalation_policy="May recommend further analysis or monitoring; never optimize, trade, hedge, rebalance, or submit an order.", human_review_required=True),
)

ROLE_BY_ID = {role.role_id: role for role in AGENT_ROLES}
ACTIVE_AGENT_ROLE_IDS = tuple(role.role_id for role in AGENT_ROLES)


def validate_role_cards() -> None:
    """Ensure every role grant stays within the finite capability catalog."""
    if len(ROLE_BY_ID) != len(AGENT_ROLES):
        raise ValueError("agent role IDs must be unique")
    for role in AGENT_ROLES:
        unknown = set(role.allowed_capability_ids).difference(CAPABILITY_BY_ID)
        if unknown:
            raise ValueError(f"role {role.role_id} grants unknown capabilities: {sorted(unknown)}")
        if not set(ORDER_AND_BROKER_EFFECTS).issubset(role.denied_effects):
            raise ValueError(f"role {role.role_id} must deny order and broker effects")


validate_role_cards()
