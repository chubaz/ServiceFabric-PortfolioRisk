from risk_agents import AGENT_ROLES, AgentRunContext, DeterministicAgentProvider
from risk_capabilities import CapabilityInvocation, EvidenceReference


def invocation(evidence: bool = True) -> CapabilityInvocation:
    return CapabilityInvocation(
        invocation_id="invocation-1",
        capability_id="risk.capability.news_sentiment",
        inputs={"subject": "synthetic fixture"},
        evidence_references=(EvidenceReference(evidence_id="evidence-1", reference="fixture://synthetic/news-1", source_type="synthetic_fixture"),) if evidence else (),
    )


def context() -> AgentRunContext:
    return AgentRunContext(run_id="run-1", role_id="risk.agent.news_sentiment", provider_id="risk.provider.deterministic_no_llm")


def test_role_ids_are_unique_and_capability_grants_are_bounded() -> None:
    assert len({role.role_id for role in AGENT_ROLES}) == 4
    assert all(len(role.allowed_capability_ids) == 1 for role in AGENT_ROLES)
    assert all("order_submission" in role.denied_effects for role in AGENT_ROLES)
    assert all("broker_connectivity" in role.denied_effects for role in AGENT_ROLES)


def test_provider_output_is_deterministic_and_preserves_evidence() -> None:
    provider = DeterministicAgentProvider()
    first = provider.prepare(context(), invocation())
    second = provider.prepare(context(), invocation())

    assert first == second
    assert first.status == "prepared"
    assert first.evidence_references == invocation().evidence_references
    assert "deterministic" in " ".join(first.disclosures).lower()
    assert "trade" in " ".join(first.disclosures).lower()


def test_missing_evidence_causes_a_review_blocking_draft() -> None:
    result = DeterministicAgentProvider().prepare(context(), invocation(evidence=False))
    assert result.status == "blocked"
    assert "Evidence is required" in result.warnings[0]


def test_provider_has_no_direct_execution_method() -> None:
    assert not hasattr(DeterministicAgentProvider(), "run")
