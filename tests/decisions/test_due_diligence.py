from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from risk_decisions import (
    DecisionConflict,
    DecisionOutcome,
    DecisionProposal,
    DecisionState,
    DecisionSupplementalEvidence,
    DueDiligenceCapability,
    EvidenceTruth,
    LocalDecisionStore,
    admit_proposal,
    canonical_digest,
    resolve,
    run_due_diligence,
)


def proposal(identifier: str = "proposal-due-diligence-1") -> DecisionProposal:
    now = datetime(2026, 8, 3, 10, tzinfo=timezone.utc)
    return DecisionProposal(
        proposal_id=identifier,
        finding_id="finding-due-diligence-1",
        finding_digest=canonical_digest({"return": -0.021}),
        question="How should this material synthetic loss finding be resolved?",
        why_now="The synthetic portfolio crossed its declared review threshold.",
        proposing_agent_id="risk.agent.daily-review",
        proposing_workflow_id="risk.workflow.daily-review",
        recommendation=DecisionOutcome.INVESTIGATE,
        mandate_relevance="The reviewed mandate requires a human threshold review.",
        portfolio_relevance="The finding concerns total simulated portfolio NAV.",
        risk_environment_relevance="No independent environment evidence is present.",
        evidence_ids=("evidence.nav",),
        artifact_ids=("artifact.dashboard", "artifact.report"),
        capability_receipt_ids=("receipt.nav",),
        policy_ids=("risk.policy.human-decision-review.v1",),
        uncertainties=("The path is synthetic rather than empirical intraday history.",),
        missing_information=("Confirm persistence at the next released observation.",),
        as_of=now,
        available_at=now,
        created_at=now,
        expires_at=now + timedelta(hours=4),
        downstream_workflow_preview="Human review may authorize a later manual resume only.",
    )


def run(store: LocalDecisionStore, record, *, key: str = "due-diligence-1"):
    return run_due_diligence(
        store,
        record.proposal.proposal_id,
        name="Threshold evidence review",
        investigation_question="Does the available context support the proposed investigation?",
        capability_ids=(
            DueDiligenceCapability.EVIDENCE_COVERAGE,
            DueDiligenceCapability.POLICY_ALIGNMENT,
            DueDiligenceCapability.ALTERNATIVES,
        ),
        candidate_recommendation=DecisionOutcome.INVESTIGATE,
        actor_id="reviewer.phase6",
        idempotency_key=key,
        expected_revision=record.record_revision,
    )


def test_temporary_workflow_persists_receipts_evidence_and_additive_revision(tmp_path):
    store = LocalDecisionStore(tmp_path / "decisions")
    created = store.create(admit_proposal(proposal()))
    original_digest = created.proposal.proposal_digest
    updated = run(store, created)

    assert updated.state == DecisionState.AWAITING_REVIEW
    assert updated.proposal.proposal_digest == original_digest
    assert len(updated.investigation_runs) == 1
    assert len(updated.supplemental_evidence) == 3
    assert updated.investigation_runs[0].temporary is True
    assert updated.investigation_runs[0].registry_publication is False
    assert all(step.effects == () for step in updated.investigation_runs[0].steps)
    assert all(item.effects == () for item in updated.supplemental_evidence)
    assert updated.proposal_revisions[0].revision_number == 2
    assert updated.proposal_revisions[0].recommendation == DecisionOutcome.INVESTIGATE
    assert updated.proposal_revisions[0].effects == ()
    assert updated.resolutions == ()

    restarted = LocalDecisionStore(tmp_path / "decisions").get(created.proposal.proposal_id)
    assert restarted.record_revision == updated.record_revision
    assert restarted.investigation_runs[0].run_digest == updated.investigation_runs[0].run_digest


def test_due_diligence_retry_is_idempotent_and_conflicting_key_fails(tmp_path):
    store = LocalDecisionStore(tmp_path / "decisions")
    created = store.create(admit_proposal(proposal()))
    first = run(store, created)
    repeated = run_due_diligence(
        store,
        created.proposal.proposal_id,
        name="Threshold evidence review",
        investigation_question="Does the available context support the proposed investigation?",
        capability_ids=(
            DueDiligenceCapability.EVIDENCE_COVERAGE,
            DueDiligenceCapability.POLICY_ALIGNMENT,
            DueDiligenceCapability.ALTERNATIVES,
        ),
        candidate_recommendation=DecisionOutcome.INVESTIGATE,
        actor_id="reviewer.phase6",
        idempotency_key="due-diligence-1",
        expected_revision=created.record_revision,
    )
    assert repeated.record_revision == first.record_revision
    with pytest.raises(DecisionConflict, match="another due-diligence"):
        run_due_diligence(
            store,
            created.proposal.proposal_id,
            name="Different workflow",
            investigation_question="Does another question change the interpretation?",
            capability_ids=(DueDiligenceCapability.ARTIFACT_LINEAGE,),
            candidate_recommendation=DecisionOutcome.DEFER,
            actor_id="reviewer.phase6",
            idempotency_key="due-diligence-1",
            expected_revision=first.record_revision,
        )


def test_stale_and_final_proposals_reject_new_due_diligence(tmp_path):
    store = LocalDecisionStore(tmp_path / "decisions")
    created = store.create(admit_proposal(proposal()))
    with pytest.raises(DecisionConflict, match="reload"):
        run_due_diligence(
            store,
            created.proposal.proposal_id,
            name="Stale workflow",
            investigation_question="Should this stale request execute?",
            capability_ids=(DueDiligenceCapability.EVIDENCE_COVERAGE,),
            candidate_recommendation=DecisionOutcome.INVESTIGATE,
            actor_id="reviewer.phase6",
            idempotency_key="stale-workflow",
            expected_revision="sha256:" + "0" * 64,
        )
    final = resolve(
        store,
        created.proposal.proposal_id,
        DecisionOutcome.REJECT,
        resolver_id="reviewer.phase6",
        rationale="The reference-only evidence is insufficient.",
        idempotency_key="reject-final",
        expected_revision=created.record_revision,
    )
    with pytest.raises(DecisionConflict, match="inspectable"):
        run_due_diligence(
            store,
            created.proposal.proposal_id,
            name="Final workflow",
            investigation_question="Should a final proposal be re-opened?",
            capability_ids=(DueDiligenceCapability.EVIDENCE_COVERAGE,),
            candidate_recommendation=DecisionOutcome.INVESTIGATE,
            actor_id="reviewer.phase6",
            idempotency_key="final-workflow",
            expected_revision=final.record_revision,
        )


def test_later_human_resolution_preserves_due_diligence_lineage(tmp_path):
    store = LocalDecisionStore(tmp_path / "decisions")
    created = store.create(admit_proposal(proposal()))
    investigated = run(store, created)
    resolved = resolve(
        store,
        created.proposal.proposal_id,
        DecisionOutcome.DEFER,
        resolver_id="reviewer.phase6",
        rationale="The due-diligence revision identifies a material unresolved question.",
        idempotency_key="defer-after-due-diligence",
        expected_revision=investigated.record_revision,
    )
    assert resolved.state == DecisionState.DEFERRED
    assert resolved.proposal.proposal_digest == created.proposal.proposal_digest
    assert resolved.investigation_runs == investigated.investigation_runs
    assert resolved.supplemental_evidence == investigated.supplemental_evidence
    assert resolved.proposal_revisions == investigated.proposal_revisions


def test_supplemental_evidence_rejects_lookahead():
    now = datetime(2026, 8, 3, 10, tzinfo=timezone.utc)
    with pytest.raises(ValidationError, match="available after"):
        DecisionSupplementalEvidence(
            evidence_id="evidence-invalid-time",
            proposal_id="proposal-invalid-time",
            source_type="coverage_analysis",
            title="Invalid temporal evidence",
            finding="This item uses evidence that was not yet eligible.",
            data_truth=EvidenceTruth.REFERENCE_ONLY,
            as_of=now,
            available_at=now + timedelta(minutes=1),
            created_at=now,
            created_by="reviewer.phase6",
        )
