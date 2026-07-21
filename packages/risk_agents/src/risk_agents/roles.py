"""The four mandatory Day 0 review-bound role cards."""

from risk_capabilities import CAPABILITY_BY_ID, ORDER_AND_BROKER_EFFECTS

from .contracts import AgentRole


def _role(role_id: str, objective: str, capability_id: str) -> AgentRole:
    return AgentRole(
        role_id=role_id,
        objective=objective,
        allowed_capability_ids=(capability_id,),
        denied_effects=ORDER_AND_BROKER_EFFECTS + ("trade_execution", "automatic_rebalancing"),
        input_contracts=("CapabilityInvocation", "EvidenceReference[]"),
        output_contracts=("CapabilityOutcome",),
        evidence_requirements=("At least one supplied evidence reference is required.",),
        escalation_policy="Escalate missing, partial, stale, or consequential findings to a human reviewer.",
        human_review_required=True,
    )


AGENT_ROLES = (
    _role("risk.agent.news_sentiment", "News & Sentiment Agent: summarize supplied news evidence.", "risk.capability.news_sentiment"),
    AgentRole(role_id="risk.agent.market_data", objective="Market Data Agent: invoke registered synthetic-data and anomaly capabilities.", allowed_capability_ids=("data.synthetic.ingest", "market.anomaly.detect"), denied_effects=ORDER_AND_BROKER_EFFECTS + ("trade_execution", "automatic_rebalancing"), input_contracts=("SyntheticIngestRequest", "AnomalyDetectionRequest", "EvidenceReference[]"), output_contracts=("CapabilityResult",), evidence_requirements=("At least one supplied evidence reference is required.",), escalation_policy="Escalate missing, partial, stale, or consequential findings to a human reviewer.", human_review_required=True),
    AgentRole(role_id="risk.agent.portfolio_exposure", objective="Portfolio Exposure Agent: invoke registered snapshot and exposure capabilities.", allowed_capability_ids=("portfolio.snapshot.create", "portfolio.exposure.summarize"), denied_effects=ORDER_AND_BROKER_EFFECTS + ("trade_execution", "automatic_rebalancing"), input_contracts=("PortfolioSnapshotRequest", "ExposureSummaryRequest", "EvidenceReference[]"), output_contracts=("CapabilityResult",), evidence_requirements=("At least one supplied evidence reference is required.",), escalation_policy="Escalate missing, partial, stale, or consequential findings to a human reviewer.", human_review_required=True),
    _role("risk.agent.alert_recommendation", "Alert & Recommendation Agent: draft a review-required, non-advisory alert.", "risk.capability.alert_recommendation"),
)

ROLE_BY_ID = {role.role_id: role for role in AGENT_ROLES}
ACTIVE_AGENT_ROLE_IDS = ("risk.agent.market_data", "risk.agent.portfolio_exposure")


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
