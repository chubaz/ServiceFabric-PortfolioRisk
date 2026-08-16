from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from risk_analytics import SignalDirection, SignalScope
from risk_experiments import (
    CandidateReviewOutcome,
    ContextAssociationProposal,
    ContextCandidateReview,
    ContextChannel,
    ContextEvidenceCandidate,
    ContextExecutionRecord,
    ContextExecutionReview,
    ContextReviewOutcome,
    ContextWorkExecution,
    GoldCaseConflict,
    GoldCaseRecord,
    GoldCaseReview,
    GoldDecisionCheckpoint,
    GoldReviewOutcome,
    LabelAnnotationReview,
    LabelDirection,
    LabelOutcome,
    LabellingBatch,
    LocalGoldCaseStore,
    ManifestationInterval,
    PlannedExperimentSelection,
    RelevanceLabel,
    ReviewOutcome,
    SignalAnnotation,
    SignalReference,
    SignalReviewUnit,
    SignalScoreBand,
    SignalSelectionPlan,
    TemporalMorphology,
    compile_experimental_case,
    default_labelling_protocol,
    prepare_gold_case_bundle,
)


NOW = datetime(2015, 8, 24, 20, tzinfo=UTC)
DIGEST_A = "sha256:" + "a" * 64


def accepted_batch() -> LabellingBatch:
    signal = SignalReference(
        signal_id="signal-alpha", detector_run_id="detector-run-alpha",
        detector_output_digest=DIGEST_A, detector_id="robust-z",
        detector_version="1.0.0", series_id="instrument-alpha",
        scope_type=SignalScope.INSTRUMENT, scope_id="instrument-alpha",
        observation_time=NOW, available_at=NOW, direction=SignalDirection.DOWNSIDE,
        standardised_score=Decimal("-4"), threshold=Decimal("3"),
        evidence_ids=("market-observation-alpha",),
    )
    unit = SignalReviewUnit(
        unit_id="signal-review-alpha", scope_type=SignalScope.INSTRUMENT,
        scope_id="instrument-alpha", observation_time=NOW, available_at=NOW,
        direction=SignalDirection.DOWNSIDE, score_band=SignalScoreBand.BOUNDARY,
        signals=(signal,), evidence_ids=("market-observation-alpha",),
    )
    protocol = default_labelling_protocol()
    plan = SignalSelectionPlan(
        plan_id="signal-selection-alpha", protocol_digest=protocol.protocol_digest,
        source_run_ids=("detector-run-alpha",), source_output_digests=(DIGEST_A,),
        portfolio_id="portfolio-alpha", dataset_snapshot_id="licensed-history-alpha",
        seed="gold-case-test-seed", selection_start=NOW - timedelta(days=2),
        selection_end=NOW + timedelta(days=2), target_count=1,
        observed_signal_count=1, review_unit_count=1,
        selected_unit_ids=(unit.unit_id,), excluded_unit_ids=(),
        selection_note="One controlled review unit selected for the Gold lifecycle test.",
        created_at=NOW + timedelta(days=3),
    )
    annotation = SignalAnnotation(
        annotation_id="annotation-alpha", unit_id=unit.unit_id, revision=1,
        outcome=LabelOutcome.MATERIALISED_RISK, relevance=RelevanceLabel.RELEVANT,
        scope_type="instrument", scope_id=unit.scope_id,
        direction=LabelDirection.DOWNSIDE, morphology=TemporalMorphology.PUNCTUAL_SHOCK,
        manifestation_interval=ManifestationInterval(
            start=NOW, peak=NOW + timedelta(days=1), end=NOW + timedelta(days=2),
        ),
        severity_level=2, severity_basis_points=Decimal("650"), severity_horizon_sessions=5,
        supporting_evidence_ids=unit.evidence_ids, review_confidence=Decimal("0.85"),
        notes="The reviewed path crosses the predeclared materiality boundary.",
        annotated_by="label-researcher", annotator_role="human_researcher",
        created_at=NOW + timedelta(days=4),
    )
    review = LabelAnnotationReview(
        review_id="annotation-review-alpha", annotation_id=annotation.annotation_id,
        annotation_digest=annotation.annotation_digest,
        outcome=ReviewOutcome.ACCEPT_FOR_GOLD_PREPARATION,
        detection_fields_verified=True, severity_fields_verified=True,
        evidence_fields_verified=True, temporal_fields_verified=True,
        reviewer_confidence=Decimal("0.9"),
        rationale="The manifestation, scope, severity and timing reconcile to retained evidence.",
        reviewed_by="label-reviewer", reviewed_at=NOW + timedelta(days=5),
    )
    return LabellingBatch(
        batch_id="label-batch-alpha", protocol=protocol, plan=plan,
        selected_units=(unit,), annotations=(annotation,), reviews=(review,), revision=3,
    )


def accepted_context() -> ContextExecutionRecord:
    candidate = ContextEvidenceCandidate(
        candidate_id="context-candidate-alpha", plan_id="context-plan-alpha",
        unit_id="signal-review-alpha", channel=ContextChannel.EVENTS,
        canonical_entity_id="permno:101", source_record_id="event-alpha",
        display_title="Guidance reduced", display_summary="The issuer reduced earnings guidance.",
        observed_at=NOW - timedelta(hours=2), available_at=NOW - timedelta(hours=1),
        eligible_at_replay_time=True, proposed_role="precursor",
        proposed_position="supporting", relevance_score=0.9, association_score=0.8,
        evidence_ids=("event-evidence-alpha",), quality_flags=("provider_lifecycle_unverified",),
    )
    proposal = ContextAssociationProposal(
        proposal_id="context-proposal-alpha", plan_id="context-plan-alpha",
        plan_digest=DIGEST_A, unit_id="signal-review-alpha", candidates=(candidate,),
        unresolved_questions=("Provider amendment state is not available.",),
    )
    execution = ContextWorkExecution(
        execution_id="context-execution-alpha", batch_id="label-batch-alpha",
        unit_id="signal-review-alpha", plan_id="context-plan-alpha",
        plan_digest=DIGEST_A, plan_revision=1,
        retrospective_cutoff=NOW + timedelta(days=2), prepared_at=NOW + timedelta(days=3),
        prepared_by="context-kernel", proposal=proposal,
        excluded_missing_availability=0, excluded_temporal_violations=0,
        excluded_after_cutoff=0, source_revisions=("ravenpack-v1",),
        query_receipts=("events-selected-context-v1",),
    )
    review = ContextExecutionReview(
        review_id="context-review-alpha", execution_id=execution.execution_id,
        execution_digest=execution.execution_digest, revision=1,
        outcome=ContextReviewOutcome.ACCEPT_CONTEXT,
        candidate_reviews=(ContextCandidateReview(
            candidate_id=candidate.candidate_id, outcome=CandidateReviewOutcome.RETAIN,
            evidence_role="precursor", evidence_position="supporting",
            rationale="The event is temporally eligible and relevant to the manifestation.",
        ),),
        limitations_acknowledged=True, reviewed_by="context-reviewer",
        reviewed_at=NOW + timedelta(days=6),
        summary="The event is retained with its provider lifecycle limitation visible.",
    )
    return ContextExecutionRecord(
        record_id="context-record-alpha", execution=execution, reviews=(review,),
    )


def selection() -> PlannedExperimentSelection:
    return PlannedExperimentSelection(
        selection_id="gold-selection-alpha", study_id="study-thesis-alpha",
        experiment_id="experiment-thesis-alpha",
        research_use="Compare three architecture families under one sealed historical case.",
        selected_by="research-lead", selected_at=NOW + timedelta(days=7),
    )


def prepared_bundle():  # type: ignore[no-untyped-def]
    return prepare_gold_case_bundle(
        batch=accepted_batch(), unit_id="signal-review-alpha",
        context_record=accepted_context(), selection=selection(),
        checkpoints=(GoldDecisionCheckpoint(
            checkpoint_id="checkpoint-early-warning", label="Early warning",
            information_cutoff=NOW - timedelta(hours=1),
            acceptable_actions=("investigate", "monitor"),
            required_evidence_ids=("event-evidence-alpha",),
        ),),
        data_truth="licensed_historical", prepared_by="gold-preparer",
        prepared_at=NOW + timedelta(days=8),
    )


def accepted_record() -> GoldCaseRecord:
    bundle = prepared_bundle()
    review = GoldCaseReview(
        review_id="gold-review-alpha", gold_reference_id=bundle.gold_reference_id,
        bundle_digest=bundle.bundle_digest, revision=1, outcome=GoldReviewOutcome.ACCEPT,
        label_reconciled=True, evidence_reconciled=True,
        temporal_firewall_verified=True, limitations_acceptable=True,
        rationale="The reference reconciles and its retrospective content is isolated from replay.",
        reviewed_by="gold-reviewer", reviewed_at=NOW + timedelta(days=9),
    )
    return GoldCaseRecord(record_id="gold-record-alpha", bundle=bundle, reviews=(review,))


def test_gold_preparation_reuses_accepted_label_and_context_without_inference() -> None:
    bundle = prepared_bundle()

    assert bundle.state == "awaiting_independent_review"
    assert bundle.architecture_access is False
    assert bundle.evidence[0].source_record_id == "event-alpha"
    assert bundle.evidence[0].replay_visibility == "ex_ante_eligible"
    assert bundle.unresolved_limits == ("Provider amendment state is not available.",)
    assert bundle.selection.experiment_id == "experiment-thesis-alpha"


def test_gold_preparation_refuses_unreviewed_label_or_context() -> None:
    batch = accepted_batch().model_copy(update={"reviews": ()})
    with pytest.raises(GoldCaseConflict, match="label requires accepted independent review"):
        prepare_gold_case_bundle(
            batch=batch, unit_id="signal-review-alpha", context_record=accepted_context(),
            selection=selection(), checkpoints=(), data_truth="licensed_historical",
            prepared_by="gold-preparer", prepared_at=NOW + timedelta(days=8),
        )

    context = accepted_context().model_copy(update={"reviews": ()})
    with pytest.raises(GoldCaseConflict, match="evidence context requires accepted human review"):
        prepare_gold_case_bundle(
            batch=accepted_batch(), unit_id="signal-review-alpha", context_record=context,
            selection=selection(), checkpoints=(), data_truth="licensed_historical",
            prepared_by="gold-preparer", prepared_at=NOW + timedelta(days=8),
        )


def test_independent_gold_review_is_mandatory_and_self_review_is_rejected() -> None:
    bundle = prepared_bundle()
    incomplete = GoldCaseReview(
        review_id="gold-review-incomplete", gold_reference_id=bundle.gold_reference_id,
        bundle_digest=bundle.bundle_digest, revision=1,
        outcome=GoldReviewOutcome.REQUEST_CHANGES, label_reconciled=True,
        evidence_reconciled=False, temporal_firewall_verified=False,
        limitations_acceptable=False,
        rationale="The temporal isolation and evidence reconciliation need further work.",
        reviewed_by="gold-reviewer", reviewed_at=NOW + timedelta(days=9),
    )
    assert GoldCaseRecord(record_id="gold-record-incomplete", bundle=bundle, reviews=(incomplete,)).state == "changes_requested"

    self_review = GoldCaseReview.model_validate({
        **incomplete.model_dump(mode="python", exclude={"review_digest"}),
        "reviewed_by": bundle.prepared_by,
    })
    with pytest.raises(ValueError, match="preparer cannot independently approve"):
        GoldCaseRecord(record_id="gold-record-self", bundle=bundle, reviews=(self_review,))


def test_case_compilation_uses_existing_case_and_keeps_gold_out_of_run_input() -> None:
    record = accepted_record()
    case = compile_experimental_case(
        record, portfolio_reference="portfolio:alpha",
        mandate_reference="mandate:portfolio-risk:alpha@1.0.0",
        risk_policy_reference="risk-policy:portfolio-risk:alpha@1.0.0",
        data_references=("dataset:crsp-alpha", "dataset:ravenpack-alpha"),
        evaluation_horizon_end=NOW + timedelta(days=20),
    )

    assert case.experiment_id == record.bundle.selection.experiment_id
    assert case.evaluation_state.reference_label_ids == (record.bundle.gold_reference_id,)
    assert case.evaluation_state.architecture_access is False
    assert case.observable_state.observation_ids == ("event-evidence-alpha",)
    observable = case.observable_state.model_dump_json()
    assert "gold" not in observable and "manifestation" not in observable and "severity" not in observable


def test_case_compilation_accepts_full_ex_ante_stream_without_leaking_gold_selection() -> None:
    record = accepted_record()
    case = compile_experimental_case(
        record, portfolio_reference="portfolio:alpha",
        mandate_reference="mandate:portfolio-risk:alpha@1.0.0",
        risk_policy_reference="risk-policy:portfolio-risk:alpha@1.0.0",
        data_references=("dataset:licensed-history",),
        evaluation_horizon_end=NOW + timedelta(days=20),
        observable_observation_ids=("event-negative-control", "event-evidence-alpha"),
        observable_as_of=NOW - timedelta(days=2),
    )

    assert case.observable_state.observation_ids == (
        "event-evidence-alpha", "event-negative-control",
    )
    assert case.observable_state.as_of == NOW - timedelta(days=2)
    assert case.evaluation_state.reference_label_ids == (record.bundle.gold_reference_id,)


def test_store_is_idempotent_append_only_and_binds_one_compiled_case(tmp_path) -> None:  # type: ignore[no-untyped-def]
    bundle = prepared_bundle()
    store = LocalGoldCaseStore(tmp_path / "labels")
    initial = store.create(bundle)
    assert store.create(bundle) == initial
    review = accepted_record().reviews[0]
    reviewed = store.review(bundle.gold_reference_id, review, expected_revision=0)
    assert reviewed.state == "accepted"
    with pytest.raises(GoldCaseConflict, match="changed"):
        store.review(bundle.gold_reference_id, review, expected_revision=0)
    case = compile_experimental_case(
        reviewed, portfolio_reference="portfolio:alpha",
        mandate_reference="mandate:portfolio-risk:alpha@1.0.0",
        risk_policy_reference="risk-policy:portfolio-risk:alpha@1.0.0",
        data_references=("dataset:licensed-history",),
        evaluation_horizon_end=NOW + timedelta(days=20),
    )
    bound = store.bind_case(bundle.gold_reference_id, case)
    assert bound.state == "experimental_case_compiled"
    assert store.get(bundle.gold_reference_id).compiled_case_id == case.case_id
    assert store.get_case(case.case_id) == case
    assert store.bind_case(bundle.gold_reference_id, case) == bound
    with pytest.raises(GoldCaseConflict, match="cannot receive another review"):
        store.review(bundle.gold_reference_id, review, expected_revision=1)


def test_revised_gold_bundle_names_the_reference_it_supersedes() -> None:
    first = prepared_bundle()
    revised = prepare_gold_case_bundle(
        batch=accepted_batch(), unit_id="signal-review-alpha",
        context_record=accepted_context(), selection=selection(),
        checkpoints=first.checkpoints, data_truth="licensed_historical",
        prepared_by="gold-preparer", prepared_at=NOW + timedelta(days=10),
        supersedes_gold_reference_id=first.gold_reference_id,
    )
    assert revised.supersedes_gold_reference_id == first.gold_reference_id
    assert revised.gold_reference_id != first.gold_reference_id
