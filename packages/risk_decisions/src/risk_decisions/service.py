"""Lifecycle operations and the one registered effect-free follow-up workflow."""

from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    FINAL_STATES,
    DecisionConsequenceReceipt,
    DecisionContextRevision,
    DecisionFollowUpRun,
    DecisionLifecycleReceipt,
    DecisionOutcome,
    DecisionProposal,
    DecisionRecord,
    DecisionResolution,
    DecisionState,
    canonical_digest,
)
from .store import DecisionConflict, LocalDecisionStore


POLICY_ID = "risk.policy.human-decision-review.v1"


def _receipt(proposal_id: str, sequence: int, from_state: DecisionState | None,
             to_state: DecisionState, actor_id: str, actor_type: str, rationale: str,
             idempotency_key: str, occurred_at: datetime, prior: str | None) -> DecisionLifecycleReceipt:
    return DecisionLifecycleReceipt(
        receipt_id=f"receipt-{proposal_id}-{sequence}", proposal_id=proposal_id,
        sequence=sequence, from_state=from_state, to_state=to_state,
        actor_id=actor_id, actor_type=actor_type, rationale=rationale,
        occurred_at=occurred_at, idempotency_key=idempotency_key,
        prior_receipt_digest=prior,
    )


def admit_proposal(proposal: DecisionProposal) -> DecisionRecord:
    now = proposal.created_at
    first = _receipt(proposal.proposal_id, 1, None, DecisionState.PROPOSED,
                     "decision-review-runtime", "system", "Admit immutable proposal.",
                     f"{proposal.proposal_id}:proposed", now, None)
    second = _receipt(proposal.proposal_id, 2, DecisionState.PROPOSED, DecisionState.POLICY_VALIDATED,
                      "decision-review-runtime", "system", "Validate D1 authority, human review, standard outcomes, and empty effects.",
                      f"{proposal.proposal_id}:policy", now, first.receipt_digest)
    third = _receipt(proposal.proposal_id, 3, DecisionState.POLICY_VALIDATED, DecisionState.AWAITING_REVIEW,
                     "decision-review-runtime", "system", "Pause the workflow cycle for human review.",
                     f"{proposal.proposal_id}:awaiting", now, second.receipt_digest)
    return DecisionRecord(proposal=proposal, lifecycle=(first, second, third))


def resolve(store: LocalDecisionStore, proposal_id: str, outcome: DecisionOutcome, *,
            resolver_id: str, rationale: str, idempotency_key: str,
            expected_revision: str) -> DecisionRecord:
    current = store.get(proposal_id)
    existing = next((item for item in current.resolutions if item.idempotency_key == idempotency_key), None)
    if existing:
        if existing.outcome == outcome and existing.resolver_id == resolver_id:
            return current
        raise DecisionConflict("idempotency key was used for another review outcome")
    if current.record_revision != expected_revision:
        raise DecisionConflict("decision record changed; reload before acting")
    if current.state in FINAL_STATES:
        raise DecisionConflict("final decision proposal cannot be reviewed again")
    option = next(item for item in current.proposal.options if item.outcome == outcome)
    now = datetime.now(timezone.utc)
    decision_id = f"decision-{proposal_id}-{len(current.resolutions) + 1}"
    resolution = DecisionResolution(
        decision_id=decision_id, proposal_id=proposal_id,
        proposal_digest=current.proposal.proposal_digest, outcome=outcome,
        resolver_id=resolver_id, rationale=rationale, decided_at=now,
        policy_id=POLICY_ID, idempotency_key=idempotency_key,
    )
    consequence = DecisionConsequenceReceipt(
        receipt_id=f"consequence-{decision_id}", decision_id=decision_id,
        proposal_id=proposal_id, outcome=outcome, consequence=option.consequence,
        workflow_effect=option.workflow_effect, recorded_at=now,
    )
    target = {
        DecisionOutcome.INVESTIGATE: DecisionState.UNDER_INVESTIGATION,
        DecisionOutcome.ACCEPT_AND_MONITOR: DecisionState.RESOLVED,
        DecisionOutcome.DEFER: DecisionState.DEFERRED,
        DecisionOutcome.REJECT: DecisionState.REJECTED,
        DecisionOutcome.ESCALATE: DecisionState.ESCALATED,
    }[outcome]
    transition = _receipt(
        proposal_id, len(current.lifecycle) + 1, current.state, target,
        resolver_id, "human", rationale, idempotency_key, now,
        current.lifecycle[-1].receipt_digest,
    )
    lifecycle = (*current.lifecycle, transition)
    revisions = current.context_revisions
    runs = current.follow_up_runs
    if outcome == DecisionOutcome.INVESTIGATE:
        revision_id = f"context-{proposal_id}-{len(revisions) + 1}"
        revision = DecisionContextRevision(
            revision_id=revision_id, proposal_id=proposal_id,
            parent_context_digest=current.proposal.finding_digest,
            supplemental_findings=(
                f"Evidence coverage includes {len(current.proposal.evidence_ids)} direct item(s) and {len(current.proposal.capability_receipt_ids)} capability receipt(s).",
                "The loss-threshold observation remains synthetic intraday evidence and cannot be treated as empirical market history.",
            ),
            supplemental_evidence_ids=current.proposal.evidence_ids,
            unresolved_questions=current.proposal.missing_information or ("Confirm whether the movement remains material at the next released observation.",),
            created_at=now,
        )
        run = DecisionFollowUpRun(
            run_id=f"follow-up-{proposal_id}-{len(runs) + 1}", proposal_id=proposal_id,
            capability_receipts_reviewed=current.proposal.capability_receipt_ids,
            output_context_revision_id=revision_id, completed_at=now,
        )
        returned = _receipt(
            proposal_id, len(lifecycle) + 1, DecisionState.UNDER_INVESTIGATION,
            DecisionState.AWAITING_REVIEW, "decision.investigate.effect-free.v1",
            "workflow", "Effect-free evidence review completed; supplemental context is ready for human review.",
            f"{idempotency_key}:follow-up", now, lifecycle[-1].receipt_digest,
        )
        lifecycle = (*lifecycle, returned)
        revisions = (*revisions, revision)
        runs = (*runs, run)
    updated = DecisionRecord(
        proposal=current.proposal, lifecycle=lifecycle,
        resolutions=(*current.resolutions, resolution),
        consequences=(*current.consequences, consequence),
        context_revisions=revisions, follow_up_runs=runs,
    )
    return store.replace(updated, expected_revision=expected_revision)


def record_context_digest(record: DecisionRecord) -> str:
    return canonical_digest({"proposal": record.proposal.proposal_digest, "revisions": [item.revision_digest for item in record.context_revisions]})
