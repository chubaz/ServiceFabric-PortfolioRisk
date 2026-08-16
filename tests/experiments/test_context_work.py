from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from risk_experiments import (
    AssociationMethod,
    CandidateReviewOutcome,
    ContextAssociationProposal,
    ContextCandidateReview,
    ContextChannel,
    ContextEvidenceCandidate,
    ContextExecutionReview,
    ContextPurpose,
    ContextReviewOutcome,
    ContextWindow,
    ContextWorkConflict,
    ContextWorkExecution,
    ControlKind,
    ControlSpecification,
    EvidencePosition,
    EvidenceRole,
    LocalContextExecutionStore,
    LocalContextWorkStore,
    compile_context_work_plan,
)


NOW = datetime(2026, 8, 14, 10, tzinfo=UTC)
READINESS = "sha256:" + "a" * 64


def build_plan(*, prior=None, blockers=(), prepared_at=NOW):  # type: ignore[no-untyped-def]
    return compile_context_work_plan(
        batch_id="label-batch-alpha", unit_id="signal-review-alpha",
        purpose=ContextPurpose.PREPARE_CASE_CONTEXT,
        channels=(ContextChannel.EVENTS, ContextChannel.FUNDAMENTALS),
        window=ContextWindow(event_days_before=30, event_days_after=10, fundamental_lookback_quarters=8),
        method=AssociationMethod(alternatives_required=True),
        controls=ControlSpecification(requested=(ControlKind.AMBIGUOUS_EVENT, ControlKind.NO_MATERIAL_EVENT)),
        source_readiness_digest=READINESS, blockers=blockers,
        warnings=("partial scope coverage",),
        prepared_by="researcher-primary", prepared_at=prepared_at, prior=prior,
    )


def test_plan_is_dormant_content_addressed_and_explicit_about_outputs() -> None:
    plan = build_plan(blockers=("availability mapping incomplete",))
    assert plan.readiness_state == "prepared_with_blockers"
    assert plan.execution_status == "not_started"
    assert plan.retrieval_count == plan.association_count == plan.controls_generated_count == 0
    assert not plan.label_modified and not plan.gold_case_created
    assert plan.required_outputs == ("supporting", "contradicting", "alternatives", "unresolved", "quality_limit")
    assert plan.method.causal_claims_allowed is False
    assert plan.warnings == ("partial scope coverage",)
    assert plan.plan_digest.startswith("sha256:")


def test_future_candidate_contract_is_proposal_only_and_temporally_safe() -> None:
    value = ContextEvidenceCandidate(
        candidate_id="context-candidate-alpha", plan_id="context-plan-alpha",
        unit_id="signal-review-alpha", channel=ContextChannel.EVENTS,
        canonical_entity_id="issuer-alpha", observed_at=NOW,
        available_at=NOW + timedelta(minutes=1), eligible_at_replay_time=True,
        proposed_role=EvidenceRole.PRECURSOR,
        proposed_position=EvidencePosition.SUPPORTING,
        relevance_score=0.8, association_score=0.7,
        evidence_ids=("evidence-alpha",),
    )
    assert value.proposal_only and value.human_review_required
    with pytest.raises(ValidationError, match="availability cannot precede"):
        value.model_copy(update={"available_at": NOW - timedelta(minutes=1)}).model_validate(
            {**value.model_dump(), "available_at": NOW - timedelta(minutes=1)}
        )


def test_local_store_appends_revisions_and_rejects_stale_writes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = LocalContextWorkStore(tmp_path / "labels")
    first = build_plan()
    record = store.save(first)
    assert record.latest.revision == 1
    second = build_plan(prior=first, prepared_at=NOW + timedelta(minutes=1))
    revised = store.save(second, expected_record_digest=record.record_digest)
    assert [item.revision for item in revised.revisions] == [1, 2]
    assert revised.latest.supersedes_plan_id == first.plan_id
    with pytest.raises(ContextWorkConflict, match="changed"):
        third = build_plan(prior=second, prepared_at=NOW + timedelta(minutes=2))
        store.save(third, expected_record_digest=record.record_digest)


def test_store_lists_only_matching_batch_and_contains_no_evidence_rows(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = LocalContextWorkStore(tmp_path / "labels")
    record = store.save(build_plan())
    assert store.list_for_batch("label-batch-alpha") == (record,)
    assert store.list_for_batch("label-batch-other") == ()
    text = next((tmp_path / "labels" / "context-work").glob("*.json")).read_text()
    assert "event_text" not in text
    assert '"retrieval_count": 0' in text
    assert '"association_count": 0' in text


def test_execution_store_is_idempotent_and_reviews_are_append_only(tmp_path) -> None:  # type: ignore[no-untyped-def]
    plan = build_plan()
    candidate = ContextEvidenceCandidate(
        candidate_id="context-candidate-alpha", plan_id=plan.plan_id,
        unit_id=plan.unit_id, channel=ContextChannel.EVENTS,
        canonical_entity_id="permno:101", source_record_id="source-event-alpha",
        display_title="Earnings · Guidance", display_summary="A bounded event candidate.",
        observed_at=NOW, available_at=NOW + timedelta(minutes=1),
        eligible_at_replay_time=False, proposed_role=EvidenceRole.UNRESOLVED,
        proposed_position=EvidencePosition.UNRESOLVED,
        relevance_score=0.8, association_score=0.7,
        evidence_ids=("evidence-alpha",), quality_flags=("provider_lifecycle_unverified",),
    )
    proposal = ContextAssociationProposal(
        proposal_id="context-proposal-alpha", plan_id=plan.plan_id,
        plan_digest=plan.plan_digest, unit_id=plan.unit_id, candidates=(candidate,),
    )
    execution = ContextWorkExecution(
        execution_id="context-execution-alpha", batch_id=plan.batch_id,
        unit_id=plan.unit_id, plan_id=plan.plan_id, plan_digest=plan.plan_digest,
        plan_revision=plan.revision, retrospective_cutoff=NOW + timedelta(days=1),
        prepared_at=NOW, prepared_by="context-preparation-kernel", proposal=proposal,
        excluded_missing_availability=0, excluded_temporal_violations=0,
        excluded_after_cutoff=0, source_revisions=("rp-v1",),
        query_receipts=("ravenpack-selected-context-v1",),
    )
    store = LocalContextExecutionStore(tmp_path / "labels")
    record = store.save_execution(execution)
    assert store.save_execution(execution) == record
    review = ContextExecutionReview(
        review_id="context-review-alpha", execution_id=execution.execution_id,
        execution_digest=execution.execution_digest, revision=1,
        outcome=ContextReviewOutcome.ACCEPT_CONTEXT,
        candidate_reviews=(ContextCandidateReview(
            candidate_id=candidate.candidate_id, outcome=CandidateReviewOutcome.RETAIN,
            evidence_role=EvidenceRole.PRECURSOR,
            evidence_position=EvidencePosition.SUPPORTING,
            rationale="Retained after human review.",
        ),),
        limitations_acknowledged=True, reviewed_by="researcher-primary",
        reviewed_at=NOW + timedelta(minutes=2),
        summary="The candidate is useful while its provider lifecycle remains uncertain.",
    )
    revised = store.save_review(
        batch_id=plan.batch_id, unit_id=plan.unit_id, plan_id=plan.plan_id,
        review=review, expected_record_digest=record.record_digest,
    )
    assert revised.latest_review == review
    assert not revised.execution.label_modified and not revised.execution.gold_case_created
    with pytest.raises(ContextWorkConflict, match="changed"):
        store.save_review(
            batch_id=plan.batch_id, unit_id=plan.unit_id, plan_id=plan.plan_id,
            review=review, expected_record_digest=record.record_digest,
        )
    ContextWorkExecution,
