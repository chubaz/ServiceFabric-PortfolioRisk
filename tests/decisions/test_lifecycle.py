from datetime import datetime, timedelta, timezone

import pytest

from risk_decisions import (
    DecisionConflict,
    DecisionOutcome,
    DecisionProposal,
    DecisionState,
    LocalDecisionStore,
    admit_proposal,
    canonical_digest,
    resolve,
)


def make_proposal(identifier="proposal-lifecycle-1"):
    now = datetime(2026, 8, 3, 10, tzinfo=timezone.utc)
    return DecisionProposal(
        proposal_id=identifier, finding_id="finding-lifecycle-1",
        finding_digest=canonical_digest({"return": -0.021}),
        question="How should the human reviewer resolve this material loss finding?",
        why_now="The synthetic loss threshold was crossed at the current workflow time.",
        proposing_agent_id="risk.agent.daily-review", proposing_workflow_id="risk.workflow.daily-review",
        recommendation=DecisionOutcome.INVESTIGATE,
        mandate_relevance="The policy declares a two percent human review threshold.",
        portfolio_relevance="The observation concerns total portfolio NAV.",
        risk_environment_relevance="No external environment evidence is included in this bounded slice.",
        evidence_ids=("evidence.nav",), capability_receipt_ids=("receipt.nav",),
        missing_information=("Confirm persistence at the next released observation.",),
        as_of=now, available_at=now, created_at=now, expires_at=now + timedelta(hours=4),
        downstream_workflow_preview="Only an effect-free evidence review or manual clock resume is eligible.",
    )


def test_investigate_runs_effect_free_follow_up_and_returns_to_review(tmp_path):
    store = LocalDecisionStore(tmp_path / "decisions")
    created = store.create(admit_proposal(make_proposal()))
    updated = resolve(
        store, created.proposal.proposal_id, DecisionOutcome.INVESTIGATE,
        resolver_id="reviewer.one", rationale="Check evidence coverage before resolving.",
        idempotency_key="review-action-1", expected_revision=created.record_revision,
    )
    assert updated.state == DecisionState.AWAITING_REVIEW
    assert updated.context_revisions[-1].effects == ()
    assert updated.follow_up_runs[-1].workflow_id == "decision.investigate.effect-free.v1"
    assert updated.consequences[-1].portfolio_effects == ()
    assert resolve(
        store, updated.proposal.proposal_id, DecisionOutcome.INVESTIGATE,
        resolver_id="reviewer.one", rationale="Duplicate request.",
        idempotency_key="review-action-1", expected_revision=created.record_revision,
    ).record_revision == updated.record_revision


@pytest.mark.parametrize(
    ("outcome", "state"),
    [
        (DecisionOutcome.ACCEPT_AND_MONITOR, DecisionState.RESOLVED),
        (DecisionOutcome.DEFER, DecisionState.DEFERRED),
        (DecisionOutcome.REJECT, DecisionState.REJECTED),
        (DecisionOutcome.ESCALATE, DecisionState.ESCALATED),
    ],
)
def test_human_outcomes_have_explicit_effect_free_consequences(tmp_path, outcome, state):
    store = LocalDecisionStore(tmp_path / outcome.value)
    created = store.create(admit_proposal(make_proposal(f"proposal-{outcome.value}")))
    updated = resolve(
        store, created.proposal.proposal_id, outcome,
        resolver_id="reviewer.one", rationale=f"Human selected {outcome.value} after review.",
        idempotency_key=f"action-{outcome.value}", expected_revision=created.record_revision,
    )
    assert updated.state == state
    assert updated.resolutions[-1].effects == ()
    assert updated.consequences[-1].portfolio_effects == ()
    assert updated.consequences[-1].external_effects == ()


def test_final_decision_cannot_be_reviewed_again(tmp_path):
    store = LocalDecisionStore(tmp_path / "decisions")
    created = store.create(admit_proposal(make_proposal()))
    resolved = resolve(
        store, created.proposal.proposal_id, DecisionOutcome.REJECT,
        resolver_id="reviewer.one", rationale="Evidence does not support the proposal.",
        idempotency_key="reject-1", expected_revision=created.record_revision,
    )
    with pytest.raises(DecisionConflict, match="final"):
        resolve(
            store, created.proposal.proposal_id, DecisionOutcome.ACCEPT_AND_MONITOR,
            resolver_id="reviewer.two", rationale="Attempt to change a final resolution.",
            idempotency_key="accept-2", expected_revision=resolved.record_revision,
        )


def test_idempotency_key_cannot_be_reused_for_another_outcome(tmp_path):
    store = LocalDecisionStore(tmp_path / "decisions")
    created = store.create(admit_proposal(make_proposal()))
    investigated = resolve(
        store, created.proposal.proposal_id, DecisionOutcome.INVESTIGATE,
        resolver_id="reviewer.one", rationale="Inspect the evidence first.",
        idempotency_key="same-action", expected_revision=created.record_revision,
    )
    with pytest.raises(DecisionConflict, match="another review outcome"):
        resolve(
            store, created.proposal.proposal_id, DecisionOutcome.ACCEPT_AND_MONITOR,
            resolver_id="reviewer.one", rationale="Attempt a conflicting retry.",
            idempotency_key="same-action", expected_revision=investigated.record_revision,
        )
