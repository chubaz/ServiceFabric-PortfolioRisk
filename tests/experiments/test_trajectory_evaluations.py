from datetime import UTC, datetime, timedelta

import pytest

from risk_experiments import (
    ArchitectureConfig,
    ArchitectureDecision,
    ArchitectureFinding,
    ArchitectureOutput,
    CycleExecutionResult,
    EvaluationConflict,
    EvaluationDimensionRecord,
    EvaluationMetricResult,
    ExperimentalCapabilityConfig,
    GoldCaseBundle,
    GoldCaseRecord,
    GoldCaseReview,
    GoldDecisionCheckpoint,
    GoldEvidenceItem,
    GoldReviewOutcome,
    IdentityCondition,
    LocalEvaluationStore,
    MatchedRunCell,
    PlannedExperimentSelection,
    ReplayObservation,
    ReplayTrigger,
    RunBudget,
    RunInput,
    evaluate_selected_case_trajectory,
    execute_point_in_time_trajectory,
)


NOW = datetime(2015, 8, 20, 19, tzinfo=UTC)
DIGEST = "sha256:" + "a" * 64


def _gold(case_id: str = "case-one") -> GoldCaseRecord:
    selection = PlannedExperimentSelection(
        selection_id="selection-one", study_id="study-one", experiment_id="experiment-one",
        research_use="Compare bounded architectures on one reviewed historical manifestation.",
        selected_by="research-lead", selected_at=NOW + timedelta(days=30),
    )
    evidence = (
        GoldEvidenceItem(
            evidence_item_id="gold-evidence-support", source_record_id="event-support",
            source_kind="event", title="Adverse event", summary="A reviewed adverse event.",
            observed_at=NOW, available_at=NOW, replay_visibility="ex_ante_eligible",
            role="precursor", position="supporting", reviewer_rationale="Relevant warning anchor.",
            evidence_ids=("context-source-support",),
        ),
        GoldEvidenceItem(
            evidence_item_id="gold-evidence-alternative", source_record_id="event-alternative",
            source_kind="event", title="Positive event", summary="A reviewed alternative event.",
            observed_at=NOW - timedelta(hours=1), available_at=NOW - timedelta(hours=1),
            replay_visibility="ex_ante_eligible", role="precursor", position="alternative",
            reviewer_rationale="Competing positive evidence.", evidence_ids=("context-source-alternative",),
        ),
    )
    bundle = GoldCaseBundle(
        gold_reference_id="gold-reference-one", batch_id="batch-one", unit_id="unit-one",
        selection=selection, annotation_id="annotation-one", annotation_digest=DIGEST,
        annotation_review_id="annotation-review-one", annotation_review_digest=DIGEST,
        context_execution_id="context-execution-one", context_execution_digest=DIGEST,
        context_review_id="context-review-one", context_review_digest=DIGEST,
        scope_type="instrument", scope_id="instrument-one", outcome="materialised_risk",
        direction="downside", morphology="punctual_shock",
        manifestation_start=NOW, manifestation_peak=NOW + timedelta(days=1),
        manifestation_end=NOW + timedelta(days=2), severity_level=2,
        severity_basis_points=500, severity_horizon_sessions=20,
        evidence=evidence, checkpoints=(GoldDecisionCheckpoint(
            checkpoint_id="checkpoint-one", label="Observable warning",
            information_cutoff=NOW + timedelta(hours=1),
            acceptable_actions=("investigate", "monitor"),
            required_evidence_ids=("context-source-support",),
        ),), data_truth="licensed_historical", prepared_by="gold-preparer",
        prepared_at=NOW + timedelta(days=31),
    )
    review = GoldCaseReview(
        review_id="gold-review-one", gold_reference_id=bundle.gold_reference_id,
        bundle_digest=bundle.bundle_digest, revision=1, outcome=GoldReviewOutcome.ACCEPT,
        label_reconciled=True, evidence_reconciled=True, temporal_firewall_verified=True,
        limitations_acceptable=True,
        rationale="The selected reference is independently reconciled and isolated from execution.",
        reviewed_by="independent-reviewer", reviewed_at=NOW + timedelta(days=32),
    )
    return GoldCaseRecord(
        record_id="gold-record-one", bundle=bundle, reviews=(review,),
        compiled_case_id=case_id, compiled_case_digest=DIGEST,
    )


def _cell() -> MatchedRunCell:
    capability = ExperimentalCapabilityConfig(
        capability_id="event-query", version="1.0.0", implementation_class="deterministic",
        parameterization="preconfigured", evaluation_roles=("architecture_input",),
        parameter_digest=DIGEST,
    )
    architecture = ArchitectureConfig(
        architecture_id="b0-baseline", architecture_type="deterministic",
        version="1.0.0", deterministic=True, interpretation_mode="fixed_rules",
    )
    return MatchedRunCell(
        cell_id="cell-b0", case_digest=DIGEST, treatment_id="B0",
        capability_package_id="case-core", capability_package_digest=DIGEST,
        repetition=1, seed="seed-one", identity_condition=IdentityCondition.NAMED_HISTORICAL,
        run_input=RunInput(
            case_id="case-one", architecture_id=architecture.architecture_id,
            information_regime="point-in-time", capability_references=("event-query",),
            capability_configurations=(capability,), repetition=1,
            observation_ids=("context-source-alternative", "context-source-support"),
        ), architecture=architecture, context_policy_reference="point-in-time-v1",
        memory_policy="cleared_each_run",
        budget=RunBudget(
            max_model_calls=0, max_input_tokens=0, max_output_tokens=0,
            max_cost_usd=0, max_processing_seconds=30,
        ),
    )


def _trajectory(*, preserve_alternative: bool = True):  # type: ignore[no-untyped-def]
    cell = _cell()
    observations = (
        ReplayObservation(
            observation_id="context-source-alternative", kind="event",
            observed_at=NOW - timedelta(hours=1), available_at=NOW - timedelta(hours=1),
            evidence_ids=("context-source-alternative",), content_reference="event:alternative",
            content_digest=DIGEST,
        ),
        ReplayObservation(
            observation_id="context-source-support", kind="event", observed_at=NOW,
            available_at=NOW, evidence_ids=("context-source-support",),
            content_reference="event:support", content_digest=DIGEST,
        ),
    )

    def processor(context):  # type: ignore[no-untyped-def]
        output = ArchitectureOutput(
            output_id=f"output-{context.cycle_id[6:]}", run_id=context.run_id,
            architecture_type="deterministic", assessment_state="watch", severity=1,
            confidence=.65, confidence_kind="model_score",
            confidence_method="fixed threshold score, not calibrated probability",
            findings=(ArchitectureFinding(
                finding_id=f"finding-{context.cycle_id[6:]}", claim="Eligible adverse event detected.",
                risk_type="event", affected_asset="instrument-one", direction="negative",
                materiality=.5, severity=1, confidence=.65,
                confidence_method="fixed event rule", evidence_ids=("context-source-support",),
                observed_at=NOW,
            ),),
            supporting_evidence_ids=("context-source-support",),
            conflicting_evidence_ids=("context-source-alternative",) if preserve_alternative else (),
            risk_interpretation="An eligible adverse event warrants investigation.",
            expectations="Continue observing the manifestation interval.",
            decision=ArchitectureDecision(
                monitoring_action="increase_monitoring", portfolio_action="none",
                alternatives_considered=("continue_monitoring",), human_review_required=True,
                rationale_finding_ids=(f"finding-{context.cycle_id[6:]}",),
            ), missing_information=(), assumptions=(), limitations=("Selected-case test.",),
            architecture_id=cell.architecture.architecture_id, capabilities_used=("event-query",),
            cycle_id=context.cycle_id, as_of=context.replay_at, case_id=context.case_id,
            input_context_digest=context.input_context_digest,
        )
        return CycleExecutionResult(
            cycle_id=context.cycle_id, status="output", architecture_output=output,
            capability_calls=1, model_calls=0, capability_processing_ms=0,
            model_processing_ms=0, validation_processing_ms=0,
            input_tokens=0, cached_input_tokens=0, output_tokens=0,
            estimated_cost_usd=0,
        )

    return execute_point_in_time_trajectory(
        matrix_id="matrix-one", cell=cell,
        triggers=(ReplayTrigger(
            trigger_id="trigger-one", kind="event_available", event_id="event-one", replay_at=NOW,
        ),), observations=observations, processor=processor,
    )


def test_selected_case_evaluation_measures_only_supported_dimensions() -> None:
    evaluation = evaluate_selected_case_trajectory(_trajectory(), _gold())
    by_id = {item.dimension_id: item for item in evaluation.dimensions}

    assert by_id["detection_quality"].status == "partial"
    assert by_id["detection_quality"].score == 1
    assert by_id["evidence_quality"].score == 1
    assert by_id["timeliness"].score == 1
    assert by_id["decision_quality"].score == 1
    assert by_id["efficiency"].status == "measured"
    assert by_id["efficiency"].score is None
    assert {
        item.dimension_id for item in evaluation.dimensions if item.status == "not_measurable"
    } == {"confidence_calibration", "robustness", "severity_understanding", "stability"}
    severity = by_id["severity_understanding"]
    assert all(item.value is None for item in severity.metrics)
    assert "ordinal urgency" in severity.summary


def test_alternative_evidence_role_changes_evidence_score_without_changing_detection() -> None:
    evaluation = evaluate_selected_case_trajectory(
        _trajectory(preserve_alternative=False), _gold(),
    )
    by_id = {item.dimension_id: item for item in evaluation.dimensions}
    assert by_id["detection_quality"].score == 1
    assert by_id["evidence_quality"].score == pytest.approx(2 / 3)


def test_evaluation_rejects_another_case_and_store_is_idempotent(tmp_path) -> None:
    trajectory = _trajectory()
    with pytest.raises(EvaluationConflict, match="same Case"):
        evaluate_selected_case_trajectory(trajectory, _gold("case-other"))

    evaluation = evaluate_selected_case_trajectory(trajectory, _gold())
    store = LocalEvaluationStore(tmp_path)
    assert store.save(evaluation) == store.save(evaluation)
    assert store.get(evaluation.evaluation_id) == evaluation


def test_unavailable_metrics_and_dimensions_cannot_carry_scores() -> None:
    with pytest.raises(ValueError, match="unavailable evaluation metric"):
        EvaluationMetricResult(
            metric_id="missing-one", label="Missing metric", status="not_measurable",
            value=0, unit="ratio", method="No valid reference is available.",
        )
    with pytest.raises(ValueError, match="unavailable evaluation dimension"):
        EvaluationDimensionRecord(
            dimension_id="missing-dimension", status="not_measurable", score=1,
            summary="No valid reference is available.", metric_values={},
        )
