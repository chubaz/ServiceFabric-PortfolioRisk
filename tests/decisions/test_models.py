from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from risk_decisions import DecisionOutcome, DecisionProposal, canonical_digest


def proposal(**changes):
    now = datetime(2026, 8, 3, 10, tzinfo=timezone.utc)
    values = {
        "proposal_id": "proposal-test-1",
        "finding_id": "finding-test-1",
        "finding_digest": canonical_digest({"finding": 1}),
        "question": "Should the synthetic threshold finding be accepted for monitoring?",
        "why_now": "The workflow crossed its declared intraday review threshold.",
        "proposing_agent_id": "risk.agent.daily-review",
        "proposing_workflow_id": "risk.workflow.daily-review",
        "recommendation": DecisionOutcome.INVESTIGATE,
        "mandate_relevance": "The mandate requires human review at the threshold.",
        "portfolio_relevance": "The movement affects the complete synthetic portfolio NAV.",
        "risk_environment_relevance": "No independent environment mechanism is established by this fixture.",
        "evidence_ids": ("evidence.nav",),
        "capability_receipt_ids": ("receipt.exposure",),
        "as_of": now,
        "available_at": now,
        "created_at": now,
        "expires_at": now + timedelta(hours=4),
        "downstream_workflow_preview": "Human review may authorize manual clock resume only.",
    }
    values.update(changes)
    return DecisionProposal(**values)


def test_proposal_has_five_canonical_effect_free_outcomes_and_bound_digest():
    value = proposal()
    assert tuple(item.outcome for item in value.options) == tuple(DecisionOutcome)
    assert all(not item.portfolio_effects and not item.external_effects for item in value.options)
    assert value.effects == ()
    assert value.proposal_digest.startswith("sha256:")


def test_proposal_rejects_look_ahead_and_naive_time():
    now = datetime(2026, 8, 3, 10, tzinfo=timezone.utc)
    with pytest.raises(ValidationError, match="available after"):
        proposal(available_at=now + timedelta(minutes=1))
    with pytest.raises(ValidationError, match="timezone-aware"):
        proposal(as_of=datetime(2026, 8, 3, 10))


def test_proposal_digest_is_tamper_evident():
    value = proposal()
    with pytest.raises(ValidationError, match="proposal_digest"):
        proposal(proposal_digest=value.proposal_digest, question="A different question that invalidates the supplied digest?")
