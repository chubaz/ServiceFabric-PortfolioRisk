from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from risk_analytics import (
    AnalysisEvidence,
    DetectorDefinition,
    DetectorKind,
    DetectorObservation,
    DetectorParameter,
    SignalScope,
    PathObservation,
    StudyDirection,
    build_label_study,
    execute_detector,
)
from risk_experiments import (
    LabelAnnotationReview,
    LabelDirection,
    LabelOutcome,
    LabelProductionConflict,
    LabellingEvent,
    LabellingBatch,
    LocalLabellingStore,
    ManifestationInterval,
    RelevanceLabel,
    ReviewOutcome,
    SignalAnnotation,
    TemporalMorphology,
    build_review_units,
    compile_signal_selection,
    default_labelling_protocol,
    canonical_digest,
)


START = datetime(2015, 1, 2, 21, tzinfo=UTC)
EVIDENCE = (
    AnalysisEvidence(
        evidence_id="synthetic-labelled-path",
        reference="fixture://synthetic/labelling-path",
        digest="sha256:" + "c" * 64,
        description="Reviewed synthetic path used only to test label-production mechanics.",
    ),
)


def detector_runs():  # type: ignore[no-untyped-def]
    values = ("-0.01", "0", "0.01", "-0.02", "0.02", "-0.10", "0.12", "-0.09")
    observations = tuple(
        DetectorObservation(
            series_id="instrument-alpha",
            scope_type=SignalScope.INSTRUMENT,
            scope_id="instrument-alpha",
            observed_at=START + timedelta(days=index),
            available_at=START + timedelta(days=index),
            value=Decimal(value),
            benchmark_value=Decimal("0"),
            evidence_ids=(f"price:alpha:{index}",),
            quality_flags=("reviewed_synthetic",),
        )
        for index, value in enumerate(values)
    )
    robust = DetectorDefinition(
        detector_id="robust-residual-z",
        version="1.0.0",
        kind=DetectorKind.ROBUST_RESIDUAL_Z_SCORE,
        lookback=5,
        threshold=Decimal("3"),
    )
    cusum = DetectorDefinition(
        detector_id="two-sided-cusum",
        version="1.0.0",
        kind=DetectorKind.TWO_SIDED_CUSUM,
        lookback=5,
        threshold=Decimal("1.5"),
        parameters=(DetectorParameter(name="drift", value=Decimal("0.25")),),
    )
    return tuple(
        execute_detector(
            definition,
            observations,
            as_of=START + timedelta(days=7),
            evidence=EVIDENCE,
        )
        for definition in (robust, cusum)
    )


def selection(runs=None):  # type: ignore[no-untyped-def]
    runs = runs or detector_runs()
    return compile_signal_selection(
        runs,
        target_count=4,
        seed="stable-labelling-seed",
        portfolio_id="portfolio-alpha",
        dataset_snapshot_id="dataset-alpha-v1",
        selection_start=START,
        selection_end=START + timedelta(days=7),
        created_at=START + timedelta(days=8),
    )


def material_annotation(unit, *, revision=1, supersedes=None, actor="annotator-a"):  # type: ignore[no-untyped-def]
    return SignalAnnotation(
        annotation_id=f"annotation-alpha-r{revision}",
        unit_id=unit.unit_id,
        revision=revision,
        supersedes_annotation_id=supersedes,
        outcome=LabelOutcome.MATERIALISED_RISK,
        relevance=RelevanceLabel.RELEVANT,
        scope_type="instrument",
        scope_id=unit.scope_id,
        direction=LabelDirection(unit.direction.value),
        morphology=TemporalMorphology.PUNCTUAL_SHOCK,
        manifestation_interval=ManifestationInterval(
            start=unit.observation_time,
            peak=unit.observation_time,
            end=unit.observation_time + timedelta(days=1),
        ),
        severity_level=2,
        severity_basis_points=Decimal("650"),
        severity_horizon_sessions=5,
        supporting_evidence_ids=unit.evidence_ids,
        review_confidence=Decimal("0.8"),
        notes="The labelled market path crosses the predeclared materiality boundary.",
        annotated_by=actor,
        annotator_role="human_researcher",
        created_at=START + timedelta(days=9 + revision),
    )


def accepted_review(annotation, *, actor="reviewer-b"):  # type: ignore[no-untyped-def]
    return LabelAnnotationReview(
        review_id=f"review-{annotation.annotation_id}",
        annotation_id=annotation.annotation_id,
        annotation_digest=annotation.annotation_digest,
        outcome=ReviewOutcome.ACCEPT_FOR_GOLD_PREPARATION,
        detection_fields_verified=True,
        severity_fields_verified=True,
        evidence_fields_verified=True,
        temporal_fields_verified=True,
        reviewer_confidence=Decimal("0.85"),
        rationale="All mandatory reference fields reconcile to the retained market evidence.",
        reviewed_by=actor,
        reviewed_at=START + timedelta(days=12),
    )


def study_proposal(unit):  # type: ignore[no-untyped-def]
    price = Decimal("100")
    rows = []
    for index, value in enumerate(("0.01", "0", "-0.01", "0.01", "0", "-0.02", "-0.08", "0.01", "0.02", "0.01", "0.01", "0")):
        result = Decimal(value)
        price *= Decimal("1") + result
        rows.append(PathObservation(
            scope_id=unit.scope_id,
            observed_at=START + timedelta(days=index),
            available_at=START + timedelta(days=index, hours=1),
            total_return=result,
            valuation_price=price,
            evidence_id=f"study-path-{index}",
        ))
    return build_label_study(
        unit_id=unit.unit_id,
        scope_id=unit.scope_id,
        signal_time=unit.observation_time,
        direction=StudyDirection(unit.direction.value),
        dataset_snapshot_id="dataset-alpha-v1",
        retrospective_cutoff=START + timedelta(days=11),
        observations=tuple(rows),
        peer_observations=tuple(rows),
    )


def test_protocol_aligns_labels_to_architecture_output_without_creating_gold() -> None:
    protocol = default_labelling_protocol()

    assert len(protocol.field_rules) == 10
    assert protocol.gold_creation is False
    assert protocol.labels_reachable_by_experimental_architecture is False
    assert {dimension for rule in protocol.field_rules for dimension in rule.evaluation_dimensions} == {
        "detection_quality",
        "severity_understanding",
        "timeliness",
        "evidence_quality",
        "confidence_calibration",
    }
    assert any("assessment_state" in item for item in protocol.architecture_output_mapping)
    assert any("case_id<-assigned_only_after_gold_preparation" == item for item in protocol.architecture_output_mapping)


def test_study_proposal_is_immutable_idempotent_and_cannot_change_annotation_state(tmp_path) -> None:
    plan, units = selection()
    store = LocalLabellingStore(tmp_path / "labels")
    batch = store.create(
        protocol=default_labelling_protocol(), plan=plan, units=units,
        actor="researcher-a", idempotency_key="create-study-batch",
        occurred_at=START + timedelta(days=8),
    )
    proposal = study_proposal(units[0])
    studied = store.record_study_proposal(
        batch.batch_id, proposal, idempotency_key="study-proposal-alpha",
        expected_batch_digest=batch.batch_digest, actor="researcher-a",
        occurred_at=START + timedelta(days=12),
    )
    repeated = store.record_study_proposal(
        batch.batch_id, proposal, idempotency_key="study-proposal-alpha",
        expected_batch_digest=batch.batch_digest, actor="researcher-a",
        occurred_at=START + timedelta(days=12),
    )
    assert studied == repeated
    assert studied.study_proposal(units[0].unit_id) == proposal
    assert studied.latest_annotation(units[0].unit_id) is None
    assert studied.readiness(units[0].unit_id).state == "unlabelled"
    assert proposal.annotation_status == "proposal_only"
    assert proposal.gold_case_created is False
    revised_proposal = type(proposal).model_validate({
        **proposal.model_dump(mode="python", exclude={"study_digest"}),
        "study_id": "label-study-recalculated-alpha",
        "dataset_snapshot_id": "dataset-alpha-v2",
    })
    revised_study = store.record_study_proposal(
        batch.batch_id, revised_proposal, idempotency_key="study-proposal-alpha-v2",
        expected_batch_digest=studied.batch_digest, actor="researcher-a",
        occurred_at=START + timedelta(days=13),
    )
    assert len(revised_study.study_proposals) == 2
    assert revised_study.study_proposal(units[0].unit_id) == revised_proposal
    assert revised_study.latest_annotation(units[0].unit_id) is None


def test_empty_session_three_batch_is_upgraded_without_changing_retained_content(tmp_path) -> None:
    plan, units = selection()
    batch = LocalLabellingStore(tmp_path / "labels").create(
        protocol=default_labelling_protocol(), plan=plan, units=units,
        actor="researcher-a", idempotency_key="legacy-study-batch",
        occurred_at=START + timedelta(days=8),
    )
    legacy_payload = batch.model_dump(mode="json", exclude={"batch_digest", "study_proposals"})
    restored = LabellingBatch.model_validate({**legacy_payload, "batch_digest": canonical_digest(legacy_payload)})
    assert restored.selected_units == batch.selected_units
    assert restored.study_proposals == ()
    assert restored.batch_digest == batch.batch_digest


def test_detector_agreement_is_reviewed_once_and_sampling_is_reproducible() -> None:
    runs = detector_runs()
    all_units = build_review_units(runs)
    first_plan, first = selection(runs)
    second_plan, second = compile_signal_selection(
        tuple(reversed(runs)),
        target_count=4,
        seed="stable-labelling-seed",
        portfolio_id="portfolio-alpha",
        dataset_snapshot_id="dataset-alpha-v1",
        selection_start=START,
        selection_end=START + timedelta(days=7),
        created_at=START + timedelta(days=8),
    )

    assert len(all_units) < sum(len(run.signals) for run in runs)
    assert first == second
    assert first_plan == second_plan
    assert first_plan.selected_unit_ids == tuple(item.unit_id for item in first)
    assert first_plan.observed_signal_count == sum(len(run.signals) for run in runs)
    assert first_plan.review_unit_count == len(all_units)
    assert set(first_plan.selected_unit_ids).isdisjoint(first_plan.excluded_unit_ids)


def test_sampling_window_excludes_lookback_signals_and_accounts_for_every_unit() -> None:
    runs = detector_runs()
    plan, units = compile_signal_selection(
        runs,
        target_count=10,
        seed="narrow-window",
        portfolio_id="portfolio-alpha",
        dataset_snapshot_id="dataset-alpha-v1",
        selection_start=START + timedelta(days=7),
        selection_end=START + timedelta(days=7),
        created_at=START + timedelta(days=8),
    )

    assert units
    assert all(item.observation_time == START + timedelta(days=7) for item in units)
    assert len(plan.selected_unit_ids) + len(plan.excluded_unit_ids) == plan.review_unit_count


def test_annotation_contract_distinguishes_material_nonmaterial_ambiguous_and_data_error() -> None:
    _plan, units = selection()
    unit = units[0]
    assert material_annotation(unit).severity_level == 2

    nonmaterial = material_annotation(unit).model_dump(mode="python", exclude={"annotation_digest"})
    nonmaterial.update(
        annotation_id="annotation-nonmaterial",
        outcome=LabelOutcome.NON_MATERIAL_MOVE,
        manifestation_interval=None,
        severity_level=0,
        severity_basis_points=None,
        severity_horizon_sessions=None,
    )
    assert SignalAnnotation.model_validate(nonmaterial).outcome is LabelOutcome.NON_MATERIAL_MOVE

    invalid = material_annotation(unit).model_dump(mode="python", exclude={"annotation_digest"})
    invalid["manifestation_interval"] = None
    with pytest.raises(ValidationError, match="requires an interval"):
        SignalAnnotation.model_validate(invalid)

    data_error = material_annotation(unit).model_dump(mode="python", exclude={"annotation_digest"})
    data_error.update(
        annotation_id="annotation-data-error",
        outcome=LabelOutcome.DATA_QUALITY_ERROR,
        morphology=TemporalMorphology.DATA_ARTIFACT,
        manifestation_interval=None,
        severity_level=0,
        severity_basis_points=None,
        severity_horizon_sessions=None,
        data_quality_flags=("invalid_price",),
    )
    assert SignalAnnotation.model_validate(data_error).outcome is LabelOutcome.DATA_QUALITY_ERROR


def test_store_is_restart_safe_revisioned_idempotent_and_independently_reviewed(tmp_path) -> None:
    plan, units = selection()
    store = LocalLabellingStore(tmp_path / "labels")
    protocol = default_labelling_protocol()
    batch = store.create(
        protocol=protocol,
        plan=plan,
        units=units,
        actor="researcher-a",
        idempotency_key="create-label-batch-alpha",
        occurred_at=START + timedelta(days=8),
    )
    repeated = LocalLabellingStore(tmp_path / "labels").create(
        protocol=protocol,
        plan=plan,
        units=units,
        actor="researcher-a",
        idempotency_key="create-label-batch-alpha",
        occurred_at=START + timedelta(days=8),
    )
    assert repeated == batch
    assert batch.readiness(units[0].unit_id).state == "unlabelled"

    annotation = material_annotation(units[0])
    annotated = store.record_annotation(
        batch.batch_id,
        annotation,
        idempotency_key="record-annotation-alpha",
        expected_batch_digest=batch.batch_digest,
    )
    assert annotated.readiness(units[0].unit_id).state == "awaiting_independent_review"
    assert store.record_annotation(
        batch.batch_id,
        annotation,
        idempotency_key="record-annotation-alpha",
        expected_batch_digest=batch.batch_digest,
    ) == annotated
    with pytest.raises(LabelProductionConflict, match="changed"):
        store.record_annotation(
            batch.batch_id,
            material_annotation(units[1]),
            idempotency_key="stale-write",
            expected_batch_digest=batch.batch_digest,
        )

    review = accepted_review(annotation)
    reviewed = store.record_review(
        batch.batch_id,
        review,
        idempotency_key="review-annotation-alpha",
        expected_batch_digest=annotated.batch_digest,
    )
    readiness = reviewed.readiness(units[0].unit_id)
    assert readiness.state == "ready"
    assert readiness.gold_case_created is False
    assert LocalLabellingStore(tmp_path / "labels").get(batch.batch_id) == reviewed


def test_self_review_and_incomplete_acceptance_are_rejected() -> None:
    _plan, units = selection()
    annotation = material_annotation(units[0], actor="same-person")
    incomplete = accepted_review(annotation).model_dump(mode="python", exclude={"review_digest"})
    incomplete["evidence_fields_verified"] = False
    with pytest.raises(ValidationError, match="every field family"):
        LabelAnnotationReview.model_validate(incomplete)

    plan, selected = selection()
    event = LabellingEvent(
        event_id="label-event-initial",
        event_type="batch_created",
        actor="same-person",
        idempotency_key="initial-event-key",
        occurred_at=START,
        record_digest=plan.plan_digest,
    )
    from risk_experiments import LabellingBatch

    with pytest.raises(ValidationError, match="cannot independently review"):
        LabellingBatch(
            batch_id="label-batch-self-review",
            protocol=default_labelling_protocol(),
            plan=plan,
            selected_units=selected,
            annotations=(annotation,),
            reviews=(accepted_review(annotation, actor="same-person"),),
            events=(event,),
        )


def test_changes_requested_requires_an_immutable_next_revision(tmp_path) -> None:
    plan, units = selection()
    store = LocalLabellingStore(tmp_path / "labels")
    batch = store.create(
        protocol=default_labelling_protocol(),
        plan=plan,
        units=units,
        actor="researcher-a",
        idempotency_key="create-label-batch-revise",
        occurred_at=START,
    )
    first = material_annotation(units[0])
    batch = store.record_annotation(
        batch.batch_id,
        first,
        idempotency_key="annotation-first",
        expected_batch_digest=batch.batch_digest,
    )
    review = accepted_review(first).model_copy(
        update={
            "review_id": "review-request-changes",
            "outcome": ReviewOutcome.CHANGES_REQUESTED,
            "evidence_fields_verified": False,
            "reviewer_confidence": Decimal("0.4"),
            "review_digest": None,
        }
    )
    review = LabelAnnotationReview.model_validate(review.model_dump(mode="python", exclude={"review_digest"}))
    batch = store.record_review(
        batch.batch_id,
        review,
        idempotency_key="review-request-changes",
        expected_batch_digest=batch.batch_digest,
    )
    assert batch.readiness(units[0].unit_id).state == "changes_requested"
    second = material_annotation(
        units[0], revision=2, supersedes=first.annotation_id, actor="annotator-a"
    ).model_copy(update={"annotation_id": "annotation-alpha-r2", "notes": "Revised after independent evidence review.", "annotation_digest": None})
    second = SignalAnnotation.model_validate(second.model_dump(mode="python", exclude={"annotation_digest"}))
    batch = store.record_annotation(
        batch.batch_id,
        second,
        idempotency_key="annotation-second",
        expected_batch_digest=batch.batch_digest,
    )
    assert batch.latest_annotation(units[0].unit_id).revision == 2
    assert batch.readiness(units[0].unit_id).state == "awaiting_independent_review"
