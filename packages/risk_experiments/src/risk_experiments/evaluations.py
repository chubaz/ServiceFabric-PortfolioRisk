"""Truthful selected-case evaluation for retained architecture trajectories.

The evaluator joins an immutable RunTrajectory to an independently accepted
GoldCaseRecord only after execution.  It never feeds Gold material back into a
Run and never manufactures a score when the required reference is absent.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from itertools import combinations
from typing import Any, Iterable

from .gold_cases import GoldCaseRecord, GoldReviewOutcome
from .hierarchy import (
    EVALUATION_DIMENSION_IDS,
    EvaluationDimensionRecord,
    EvaluationMetricResult,
    EvaluationRecord,
)
from .models import canonical_digest
from .trajectories import RunTrajectory, TrajectoryCycle


EVALUATOR_VERSION = "selected-case-evaluator-v1"
COHORT_EVALUATOR_VERSION = "selected-case-cohort-evaluator-v1"


class EvaluationConflict(ValueError):
    pass


class EvaluationNotFound(KeyError):
    pass


def _metric(
    metric_id: str,
    label: str,
    *,
    value: float | int | str | bool,
    numerator: float | int | None,
    denominator: float | int | None,
    unit: str,
    method: str,
    references: Iterable[str],
    limitations: tuple[str, ...] = (),
) -> EvaluationMetricResult:
    return EvaluationMetricResult(
        metric_id=metric_id,
        label=label,
        status="measured",
        value=value,
        numerator=numerator,
        denominator=denominator,
        unit=unit,
        method=method,
        reference_ids=tuple(sorted(set(references))),
        limitations=limitations,
    )


def _unavailable(
    metric_id: str,
    label: str,
    *,
    unit: str,
    method: str,
    references: Iterable[str] = (),
    limitations: tuple[str, ...],
) -> EvaluationMetricResult:
    return EvaluationMetricResult(
        metric_id=metric_id,
        label=label,
        status="not_measurable",
        unit=unit,
        method=method,
        reference_ids=tuple(sorted(set(references))),
        limitations=limitations,
    )


def _outputs(trajectory: RunTrajectory) -> tuple[tuple[TrajectoryCycle, object], ...]:
    return tuple(
        (cycle, cycle.result.architecture_output)
        for cycle in trajectory.cycles
        if cycle.result.architecture_output is not None
    )


def _source_citations(cycle: TrajectoryCycle) -> tuple[set[str], set[str]]:
    output = cycle.result.architecture_output
    if output is None:
        return set(), set()
    eligible = {item.observation_id for item in cycle.context.eligible_observations}
    cited = {
        value
        for value in output.supporting_evidence_ids + output.conflicting_evidence_ids
        if value.startswith("context-source-") or value.startswith("crsp:")
    }
    return cited, eligible


def evaluate_selected_case_trajectory(
    trajectory: RunTrajectory,
    gold: GoldCaseRecord,
) -> EvaluationRecord:
    """Evaluate exactly one selected Case without claiming population validity."""

    if gold.compiled_case_id != trajectory.case_id:
        raise EvaluationConflict("Gold reference and trajectory must bind to the same Case")
    review = gold.latest_review
    if review is None or review.outcome is not GoldReviewOutcome.ACCEPT:
        raise EvaluationConflict("evaluation requires an independently accepted Gold reference")
    bundle = gold.bundle
    if bundle.architecture_access:
        raise EvaluationConflict("Gold reference cannot be architecture-visible")

    output_pairs = _outputs(trajectory)
    output_ids = tuple(output.output_id for _, output in output_pairs)
    primary_output_id = output_ids[-1] if output_ids else f"abstained-{trajectory.run_id}"
    support_ids = {
        evidence_id
        for item in bundle.evidence
        if item.position == "supporting"
        for evidence_id in item.evidence_ids
    }
    alternative_ids = {
        evidence_id
        for item in bundle.evidence
        if item.position in {"alternative", "contradicting"}
        for evidence_id in item.evidence_ids
    }
    reference_ids = (bundle.gold_reference_id,)

    qualifying = tuple(
        (cycle, output)
        for cycle, output in output_pairs
        if support_ids.intersection(output.supporting_evidence_ids)
        and output.assessment_state in {"watch", "alert"}
    )
    first_cycle, first_output = qualifying[0] if qualifying else (None, None)
    detected = first_output is not None
    direction_correct = bool(
        first_output is not None
        and any(item.direction == "negative" for item in first_output.findings)
        == (bundle.direction == "downside")
    )
    detection_numerator = int(detected) + int(direction_correct)
    detection_metrics = (
        _metric(
            "selected-case-hit", "Selected episode detected",
            value=bool(detected), numerator=int(detected), denominator=1,
            unit="case", method="A hit requires watch/alert output citing a reviewed supporting Gold evidence ID.",
            references=reference_ids,
            limitations=("This selected Case does not establish population recall or false-alert rate.",),
        ),
        _metric(
            "selected-case-direction", "Direction recognised",
            value=bool(direction_correct), numerator=int(direction_correct), denominator=1,
            unit="case", method="Compare the first qualifying output direction with the reviewed Gold direction.",
            references=reference_ids,
            limitations=("Exact scope accuracy requires an admitted identifier-alias reference and is not inferred here.",),
        ),
        _unavailable(
            "population-precision-recall", "Population precision and recall",
            unit="ratio", method="Requires an exhaustive or representative labelled opportunity set.",
            references=reference_ids,
            limitations=("The Case Lab selected this episode; unlabelled cycles cannot be treated as true negatives.",),
        ),
    )
    dimensions: dict[str, EvaluationDimensionRecord] = {
        "detection_quality": EvaluationDimensionRecord(
            dimension_id="detection_quality", status="partial",
            score=detection_numerator / 2,
            summary=(
                "The selected episode was recognised from eligible evidence."
                if detected else "No output recognised the selected episode from its reviewed supporting evidence."
            ),
            metric_values={"selected_case_hit": detected, "direction_correct": direction_correct},
            metrics=detection_metrics,
            limitations=("No population precision, recall or false-alert score is claimed.",),
        )
    }

    severity_references = [bundle.gold_reference_id]
    severity_metrics = (
        _unavailable(
            "five-session-impact-error", "Five-session adverse-impact error",
            unit="basis_points", method="Absolute error between architecture forecast and realised five-session adverse portfolio impact.",
            references=severity_references,
            limitations=("ArchitectureOutput contains an ordinal urgency tier, not a five-session economic-impact forecast.",),
        ),
        _unavailable(
            "one-session-diagnostic", "One-session impact diagnostic",
            unit="basis_points", method="Compare a declared one-session forecast with the sealed realised outcome.",
            references=severity_references,
            limitations=("No one-session economic-impact forecast was emitted.",),
        ),
        _unavailable(
            "twenty-session-diagnostic", "Twenty-session impact diagnostic",
            unit="basis_points", method="Compare a declared twenty-session forecast with the reviewed Gold outcome.",
            references=severity_references,
            limitations=("Gold contains a twenty-session outcome but the architecture emitted no comparable forecast.",),
        ),
    )
    dimensions["severity_understanding"] = EvaluationDimensionRecord(
        dimension_id="severity_understanding", status="not_measurable", score=None,
        summary="Economic severity cannot be scored from ordinal urgency labels.",
        metric_values={"gold_horizon_sessions": bundle.severity_horizon_sessions},
        metrics=severity_metrics,
        limitations=("A future ArchitectureOutput must declare adverse-impact forecasts in basis points and horizons before replay.",),
    )

    manifestation_start = bundle.manifestation_start
    first_at = None if first_cycle is None else first_cycle.context.replay_at
    support_available_at = min(
        (item.available_at for item in bundle.evidence if item.position == "supporting"),
        default=None,
    )
    timeliness_metrics: list[EvaluationMetricResult] = []
    if first_at is not None and manifestation_start is not None:
        same_session = first_at.date() <= manifestation_start.date()
        absolute_delay_hours = (first_at - manifestation_start).total_seconds() / 3600
        timeliness_metrics.extend((
            _metric(
                "manifestation-session-recognition", "Recognised by manifestation session",
                value=same_session, numerator=int(same_session), denominator=1,
                unit="case", method="Compare first qualifying output date with the reviewed manifestation-start date.",
                references=reference_ids,
                limitations=("Daily prices make sub-day market-impact timing uninterpretable.",),
            ),
            _metric(
                "manifestation-delay-hours", "Delay from manifestation boundary",
                value=round(absolute_delay_hours, 6), numerator=None, denominator=None,
                unit="hours", method="First qualifying replay timestamp minus manifestation interval start.",
                references=reference_ids,
                limitations=("The manifestation boundary is daily while event availability is intraday.",),
            ),
            _metric(
                "first-detection-processing", "Real processing time at first detection",
                value=round(first_cycle.processing_receipt.processing_wall_ms, 6),
                numerator=None, denominator=None, unit="milliseconds",
                method="Measured wall time while simulated replay time remained frozen from trigger to output.",
                references=(first_cycle.processing_receipt.receipt_id,),
            ),
        ))
        if support_available_at is not None:
            timeliness_metrics.append(_metric(
                "observable-evidence-delay", "Delay after supporting evidence became available",
                value=round((first_at - support_available_at).total_seconds(), 6),
                numerator=None, denominator=None, unit="seconds",
                method="First qualifying output time minus first reviewed supporting evidence availability time.",
                references=reference_ids,
            ))
        timeliness_score = float(same_session)
        timeliness_status = "partial"
        timeliness_summary = "Recognition occurred in the manifestation session; processing latency is reported separately."
    else:
        timeliness_metrics.append(_unavailable(
            "manifestation-session-recognition", "Recognised by manifestation session",
            unit="case", method="Requires both a manifestation interval and a qualifying architecture output.",
            references=reference_ids,
            limitations=("A missing reference or detection prevents timeliness measurement.",),
        ))
        timeliness_score = None
        timeliness_status = "not_measurable"
        timeliness_summary = "No qualifying detection can be compared with the manifestation interval."
    dimensions["timeliness"] = EvaluationDimensionRecord(
        dimension_id="timeliness", status=timeliness_status, score=timeliness_score,
        summary=timeliness_summary,
        metric_values={"first_detection_at": None if first_at is None else first_at.isoformat()},
        metrics=tuple(timeliness_metrics),
        limitations=("Daily price outcomes prevent claims about intraday economic lead time.",),
    )

    support_union = set().union(*(set(output.supporting_evidence_ids) for _, output in qualifying)) if qualifying else set()
    conflict_union = set().union(*(set(output.conflicting_evidence_ids) for _, output in qualifying)) if qualifying else set()
    cited_source = set()
    eligible_source = set()
    for cycle, _ in output_pairs:
        cited, eligible = _source_citations(cycle)
        cited_source.update(cited)
        eligible_source.update(cited.intersection(eligible))
    support_hit = len(support_ids.intersection(support_union))
    alternative_hit = len(alternative_ids.intersection(conflict_union))
    eligible_hit = len(eligible_source)
    source_total = len(cited_source)
    evidence_parts = [
        support_hit / len(support_ids) if support_ids else None,
        alternative_hit / len(alternative_ids) if alternative_ids else None,
        eligible_hit / source_total if source_total else None,
    ]
    measured_parts = [item for item in evidence_parts if item is not None]
    evidence_metrics = (
        _metric(
            "supporting-evidence-coverage", "Reviewed supporting evidence used",
            value=support_hit / len(support_ids) if support_ids else 0,
            numerator=support_hit, denominator=max(len(support_ids), 1), unit="ratio",
            method="Reviewed supporting Gold evidence IDs found in qualifying output support indexes.",
            references=reference_ids,
        ),
        _metric(
            "alternative-evidence-handling", "Reviewed alternative evidence kept distinct",
            value=alternative_hit / len(alternative_ids) if alternative_ids else 0,
            numerator=alternative_hit, denominator=max(len(alternative_ids), 1), unit="ratio",
            method="Reviewed alternative/contradicting Gold evidence IDs found in qualifying conflicting-evidence indexes.",
            references=reference_ids,
        ) if alternative_ids else _unavailable(
            "alternative-evidence-handling", "Reviewed alternative evidence kept distinct",
            unit="ratio", method="Requires at least one reviewed alternative or contradicting evidence item.",
            references=reference_ids, limitations=("The Gold case contains no contrary reference.",),
        ),
        _metric(
            "source-temporal-eligibility", "Cited source records were eligible",
            value=eligible_hit / source_total if source_total else 1,
            numerator=eligible_hit, denominator=max(source_total, 1), unit="ratio",
            method="Source-record citations must occur in the same cycle's point-in-time eligible observations.",
            references=tuple(cited_source),
            limitations=("Derived capability evidence is schema-validated but not rescored by this source-record check.",),
        ),
    )
    dimensions["evidence_quality"] = EvaluationDimensionRecord(
        dimension_id="evidence_quality", status="partial",
        score=sum(measured_parts) / len(measured_parts) if measured_parts else None,
        summary=(
            "Supporting, alternative and point-in-time source use are scored separately."
            if measured_parts else "No evidence-bearing output was available."
        ),
        metric_values={
            "supporting_reference_hits": support_hit,
            "alternative_reference_hits": alternative_hit,
            "eligible_source_citations": eligible_hit,
            "source_citations": source_total,
        },
        metrics=evidence_metrics,
        limitations=("This selected Gold packet is curated and does not represent exhaustive evidence recall.",),
    )

    confidence_value = None if first_output is None else first_output.confidence
    dimensions["confidence_calibration"] = EvaluationDimensionRecord(
        dimension_id="confidence_calibration", status="not_measurable", score=None,
        summary="One selected positive Case cannot establish calibration.",
        metric_values={"first_detection_confidence": confidence_value, "case_count": 1},
        metrics=(_unavailable(
            "brier-score", "Brier score", unit="score",
            method="Mean squared error between declared probabilities and binary outcomes over a representative sample.",
            references=reference_ids,
            limitations=("Only one selected positive Case is present and outputs are model scores or ordinal judgements, not calibrated probabilities.",),
        ),),
        limitations=("Use a representative labelled sample with negative controls before calculating calibration.",),
    )

    action_map = {
        "no_action": "no_action",
        "continue_monitoring": "monitor",
        "increase_monitoring": "investigate",
        "urgent_human_review": "escalate",
    }
    checkpoint = next(
        (item for item in bundle.checkpoints if first_at is not None and first_at <= item.information_cutoff),
        None,
    )
    mapped_action = None if first_output is None else action_map[first_output.decision.monitoring_action]
    appropriate = bool(checkpoint and mapped_action in checkpoint.acceptable_actions)
    if checkpoint is not None and first_output is not None:
        decision_status = "partial"
        decision_score = float(appropriate)
        decision_metrics = (
            _metric(
                "checkpoint-action-appropriateness", "Action acceptable at checkpoint",
                value=appropriate, numerator=int(appropriate), denominator=1, unit="checkpoint",
                method="Map the monitoring action to the sealed Gold checkpoint vocabulary and test membership in its acceptable set.",
                references=(checkpoint.checkpoint_id, bundle.gold_reference_id),
            ),
            _unavailable(
                "branch-regret", "Counterfactual branch regret", unit="basis_points",
                method="Difference between the selected branch outcome and best predeclared allowed branch.",
                references=(checkpoint.checkpoint_id,),
                limitations=("No sealed counterfactual branch outcomes are attached to this Case.",),
            ),
        )
        decision_summary = "The first episode-linked monitoring action is checked against one sealed decision checkpoint."
    else:
        decision_status = "not_measurable"
        decision_score = None
        decision_metrics = (_unavailable(
            "checkpoint-action-appropriateness", "Action acceptable at checkpoint",
            unit="checkpoint", method="Requires a qualifying output and sealed Gold decision checkpoint.",
            references=reference_ids,
            limitations=("No comparable checkpoint/output pair is available.",),
        ),)
        decision_summary = "Decision appropriateness cannot be matched to a sealed checkpoint."
    dimensions["decision_quality"] = EvaluationDimensionRecord(
        dimension_id="decision_quality", status=decision_status, score=decision_score,
        summary=decision_summary,
        metric_values={"mapped_action": mapped_action, "acceptable": appropriate if checkpoint else None},
        metrics=decision_metrics,
        limitations=("Ex-ante appropriateness is separate from unavailable economic branch outcome and regret.",),
    )

    dimensions["robustness"] = EvaluationDimensionRecord(
        dimension_id="robustness", status="not_measurable", score=None,
        summary="No bounded perturbation Run has been executed for this cell.",
        metric_values={"perturbation_runs": 0},
        metrics=(_unavailable(
            "perturbation-degradation", "Performance degradation under perturbation",
            unit="ratio", method="Compare the same cell under a predeclared missing/delayed/conflicting-evidence perturbation.",
            references=(trajectory.trajectory_id,),
            limitations=("No perturbation trajectory is retained.",),
        ),),
        limitations=("Robustness requires at least one matched perturbation.",),
    )
    dimensions["stability"] = EvaluationDimensionRecord(
        dimension_id="stability", status="not_measurable", score=None,
        summary="One repetition cannot measure repeat-run agreement.",
        metric_values={"repetitions": 1},
        metrics=(_unavailable(
            "repeat-output-agreement", "Repeat-output agreement", unit="ratio",
            method="Compare structured alert, finding, evidence and decision overlap across identical repeated Runs.",
            references=(trajectory.trajectory_id,),
            limitations=("At least two identical repetitions are required.",),
        ),),
        limitations=("No stability claim is made from a single Run.",),
    )

    total_processing = sum(item.processing_receipt.processing_wall_ms for item in trajectory.cycles)
    abstentions = sum(item.result.status == "abstained" for item in trajectory.cycles)
    efficiency_metrics = (
        _metric(
            "total-processing-time", "Blocked real processing time",
            value=round(total_processing, 6), numerator=None, denominator=None,
            unit="milliseconds", method="Sum processing wall time across all workflow cycles while replay time is frozen.",
            references=(trajectory.trajectory_id,),
        ),
        _metric(
            "model-calls", "Model calls", value=trajectory.total_model_calls,
            numerator=None, denominator=None, unit="calls",
            method="Sum model calls reconciled from cycle processing receipts.", references=(trajectory.trajectory_id,),
        ),
        _metric(
            "input-tokens", "Input tokens", value=trajectory.total_input_tokens,
            numerator=None, denominator=None, unit="tokens",
            method="Sum provider-reported input tokens across cycle results.", references=(trajectory.trajectory_id,),
        ),
        _metric(
            "output-tokens", "Output tokens", value=trajectory.total_output_tokens,
            numerator=None, denominator=None, unit="tokens",
            method="Sum provider-reported output tokens across cycle results.", references=(trajectory.trajectory_id,),
        ),
        _metric(
            "estimated-cost", "Estimated model cost", value=trajectory.total_cost_usd,
            numerator=None, denominator=None, unit="usd",
            method="Sum cycle costs under each retained pricing reference.", references=(trajectory.trajectory_id,),
        ),
        _metric(
            "abstention-rate", "Workflow cycles intentionally skipped",
            value=abstentions / len(trajectory.cycles), numerator=abstentions,
            denominator=len(trajectory.cycles), unit="ratio",
            method="Abstained cycle results divided by all completed workflow cycles.", references=(trajectory.trajectory_id,),
        ),
    )
    dimensions["efficiency"] = EvaluationDimensionRecord(
        dimension_id="efficiency", status="measured", score=None,
        summary="Runtime, model use, token use, cost and abstention are retained without an arbitrary composite score.",
        metric_values={
            "processing_ms": round(total_processing, 6), "model_calls": trajectory.total_model_calls,
            "input_tokens": trajectory.total_input_tokens, "output_tokens": trajectory.total_output_tokens,
            "cost_usd": trajectory.total_cost_usd, "abstentions": abstentions,
        },
        metrics=efficiency_metrics,
    )

    ordered_dimensions = tuple(dimensions[item] for item in EVALUATION_DIMENSION_IDS)
    identity = canonical_digest({
        "trajectory": trajectory.trajectory_digest,
        "gold": bundle.bundle_digest,
        "evaluator": EVALUATOR_VERSION,
    })
    failure_codes = tuple(sorted(
        (["trajectory_failed"] if trajectory.status == "failed" else [])
        + (["no_architecture_output"] if not output_pairs else [])
    ))
    return EvaluationRecord(
        evaluation_id=f"evaluation-{identity[7:31]}",
        run_id=trajectory.run_id,
        evaluator="deterministic_evaluator",
        evaluated_output_id=primary_output_id,
        evaluated_output_ids=output_ids or (primary_output_id,),
        label_state="admitted",
        label_set_digest=bundle.bundle_digest,
        dimensions=ordered_dimensions,
        failure_codes=failure_codes,
        created_at=trajectory.completed_at,
        evaluator_version=EVALUATOR_VERSION,
        metric_specification_ids=tuple(
            metric.metric_id for dimension in ordered_dimensions for metric in dimension.metrics
        ),
    )


def _dimension(record: EvaluationRecord, dimension_id: str) -> EvaluationDimensionRecord:
    return next(item for item in record.dimensions if item.dimension_id == dimension_id)


def _cycle_signature(cycle: TrajectoryCycle) -> dict[str, Any]:
    output = cycle.result.architecture_output
    if output is None:
        return {"status": cycle.result.status, "reason": cycle.result.reason}
    return {
        "state": output.assessment_state,
        "severity": output.severity,
        "confidence": round(output.confidence, 6),
        "findings": [{
            "claim": item.claim,
            "risk_type": item.risk_type,
            "direction": item.direction,
            "materiality": round(item.materiality, 6),
            "severity": item.severity,
            "evidence": item.evidence_ids,
        } for item in output.findings],
        "supporting": output.supporting_evidence_ids,
        "conflicting": output.conflicting_evidence_ids,
        "interpretation": output.risk_interpretation,
        "expectations": output.expectations,
        "monitoring_action": output.decision.monitoring_action,
        "portfolio_action": output.decision.portfolio_action,
        "missing_information": output.missing_information,
        "assumptions": output.assumptions,
        "limitations": output.limitations,
    }


def trajectory_semantic_digest(trajectory: RunTrajectory) -> str:
    """Digest only comparable behavior, excluding Run IDs and wall-clock noise."""

    return canonical_digest([_cycle_signature(item) for item in trajectory.cycles])


def _stability_dimension(trajectories: tuple[RunTrajectory, ...]) -> EvaluationDimensionRecord:
    unique = tuple({item.trajectory_id: item for item in trajectories}.values())
    if len(unique) < 2:
        raise EvaluationConflict("stability requires at least two distinct trajectories")
    state_hits = action_hits = comparable = 0
    evidence_total = 0.0
    exact_hits = 0
    pair_count = 0
    confidence_deltas: list[float] = []
    for left, right in combinations(unique, 2):
        pair_count += 1
        exact_hits += int(trajectory_semantic_digest(left) == trajectory_semantic_digest(right))
        for left_cycle, right_cycle in zip(left.cycles, right.cycles, strict=True):
            left_output = left_cycle.result.architecture_output
            right_output = right_cycle.result.architecture_output
            comparable += 1
            left_state = None if left_output is None else left_output.assessment_state
            right_state = None if right_output is None else right_output.assessment_state
            state_hits += int(left_state == right_state)
            left_action = None if left_output is None else left_output.decision.monitoring_action
            right_action = None if right_output is None else right_output.decision.monitoring_action
            action_hits += int(left_action == right_action)
            left_evidence = set() if left_output is None else set(
                left_output.supporting_evidence_ids + left_output.conflicting_evidence_ids
            )
            right_evidence = set() if right_output is None else set(
                right_output.supporting_evidence_ids + right_output.conflicting_evidence_ids
            )
            union = left_evidence | right_evidence
            evidence_total += 1.0 if not union else len(left_evidence & right_evidence) / len(union)
            if left_output is not None and right_output is not None:
                confidence_deltas.append(abs(left_output.confidence - right_output.confidence))
    if comparable == 0:
        raise EvaluationConflict("repeat trajectories contain no comparable workflow cycles")
    state_agreement = state_hits / comparable
    action_agreement = action_hits / comparable
    evidence_agreement = evidence_total / comparable
    exact_agreement = exact_hits / pair_count
    mean_confidence_delta = sum(confidence_deltas) / len(confidence_deltas) if confidence_deltas else 0.0
    score = (state_agreement + action_agreement + evidence_agreement) / 3
    references = tuple(item.trajectory_id for item in unique)
    return EvaluationDimensionRecord(
        dimension_id="stability", status="measured", score=score,
        summary=(
            "Repeated identical Runs are compared across risk state, monitoring action, evidence and exact structured output."
        ),
        metric_values={
            "repetitions": len(unique), "state_agreement": state_agreement,
            "action_agreement": action_agreement, "evidence_agreement": evidence_agreement,
            "exact_output_agreement": exact_agreement,
            "mean_confidence_delta": mean_confidence_delta,
        },
        metrics=(
            _metric("risk-state-agreement", "Risk-state agreement", value=state_agreement,
                    numerator=state_hits, denominator=comparable, unit="ratio",
                    method="Equal assessment states across aligned cycles and identical repeated Runs.", references=references),
            _metric("monitoring-action-agreement", "Monitoring-action agreement", value=action_agreement,
                    numerator=action_hits, denominator=comparable, unit="ratio",
                    method="Equal monitoring actions across aligned cycles and identical repeated Runs.", references=references),
            _metric("evidence-index-agreement", "Evidence-index agreement", value=evidence_agreement,
                    numerator=None, denominator=comparable, unit="ratio",
                    method="Mean Jaccard overlap of supporting and conflicting evidence indexes across aligned cycles.", references=references),
            _metric("exact-structured-output-agreement", "Exact structured-output agreement", value=exact_agreement,
                    numerator=exact_hits, denominator=pair_count, unit="ratio",
                    method="Exact digest equality over normalized structured output content, excluding identities and runtime timestamps.", references=references),
            _metric("mean-confidence-delta", "Mean confidence difference", value=mean_confidence_delta,
                    numerator=None, denominator=len(confidence_deltas) or None, unit="score",
                    method="Mean absolute confidence difference across cycles where both repetitions emitted output.", references=references),
        ),
        limitations=("Two repetitions measure observed repeatability but do not establish population stability.",),
    )


def _robustness_dimension(
    baseline: EvaluationRecord,
    perturbed: EvaluationRecord,
    baseline_trajectory: RunTrajectory,
    perturbed_trajectory: RunTrajectory,
) -> EvaluationDimensionRecord:
    baseline_detection = _dimension(baseline, "detection_quality").score or 0.0
    perturbed_detection = _dimension(perturbed, "detection_quality").score or 0.0
    baseline_evidence = _dimension(baseline, "evidence_quality").score or 0.0
    perturbed_evidence = _dimension(perturbed, "evidence_quality").score or 0.0
    detection_degradation = max(0.0, baseline_detection - perturbed_detection)
    evidence_degradation = max(0.0, baseline_evidence - perturbed_evidence)
    retention = max(0.0, 1.0 - max(detection_degradation, evidence_degradation))
    references = (baseline_trajectory.trajectory_id, perturbed_trajectory.trajectory_id)
    return EvaluationDimensionRecord(
        dimension_id="robustness", status="measured", score=retention,
        summary="The unperturbed Run is paired with a predeclared one-cycle adverse-event delay.",
        metric_values={
            "perturbation_runs": 1, "detection_degradation": detection_degradation,
            "evidence_degradation": evidence_degradation, "retained_quality": retention,
        },
        metrics=(
            _metric("detection-degradation", "Detection degradation", value=detection_degradation,
                    numerator=None, denominator=None, unit="ratio",
                    method="Unperturbed selected-case detection score minus the delayed-event score, floored at zero.", references=references),
            _metric("evidence-degradation", "Evidence degradation", value=evidence_degradation,
                    numerator=None, denominator=None, unit="ratio",
                    method="Unperturbed evidence score minus the delayed-event score, floored at zero.", references=references),
            _metric("perturbation-quality-retention", "Quality retained under perturbation", value=retention,
                    numerator=None, denominator=1, unit="ratio",
                    method="One minus the larger observed detection or evidence degradation.", references=references),
        ),
        limitations=("One delayed-event condition is a bounded robustness test, not broad stress coverage.",),
    )


def evaluate_selected_case_cohort(
    trajectory: RunTrajectory,
    gold: GoldCaseRecord,
    *,
    repeat_trajectories: tuple[RunTrajectory, ...] = (),
    paired_trajectory: RunTrajectory | None = None,
) -> EvaluationRecord:
    """Extend one selected-case evaluation with retained repeat/perturbation evidence."""

    base = evaluate_selected_case_trajectory(trajectory, gold)
    repeats = tuple({item.trajectory_id: item for item in (trajectory, *repeat_trajectories)}.values())
    dimensions = {item.dimension_id: item for item in base.dimensions}
    if len(repeats) >= 2:
        dimensions["stability"] = _stability_dimension(repeats)
    peer_base: EvaluationRecord | None = None
    if paired_trajectory is not None:
        peer_base = evaluate_selected_case_trajectory(paired_trajectory, gold)
        if trajectory.cycles[0].result.architecture_output is not None:
            current_is_perturbed = trajectory.cycles[0].result.architecture_output.perturbation_id is not None
        else:
            current_is_perturbed = any(
                cycle.result.architecture_output is not None
                and cycle.result.architecture_output.perturbation_id is not None
                for cycle in trajectory.cycles
            )
        if current_is_perturbed:
            dimensions["robustness"] = _robustness_dimension(peer_base, base, paired_trajectory, trajectory)
        else:
            dimensions["robustness"] = _robustness_dimension(base, peer_base, trajectory, paired_trajectory)
    ordered = tuple(dimensions[item] for item in EVALUATION_DIMENSION_IDS)
    identity = canonical_digest({
        "trajectory": trajectory.trajectory_digest,
        "gold": gold.bundle.bundle_digest,
        "repeat_trajectories": sorted(item.trajectory_digest for item in repeats),
        "paired_trajectory": None if paired_trajectory is None else paired_trajectory.trajectory_digest,
        "evaluator": COHORT_EVALUATOR_VERSION,
    })
    return base.model_copy(update={
        "evaluation_id": f"evaluation-{identity[7:31]}",
        "dimensions": ordered,
        "evaluator_version": COHORT_EVALUATOR_VERSION,
        "metric_specification_ids": tuple(
            metric.metric_id for dimension in ordered for metric in dimension.metrics
        ),
    })


class LocalEvaluationStore:
    """Immutable local evaluation records indexed by deterministic identity."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().absolute()
        self.evaluations = self.root / "run-evaluations"
        self._thread_lock = threading.RLock()

    @contextmanager
    def _lock(self):  # type: ignore[no-untyped-def]
        with self._thread_lock:
            self.evaluations.mkdir(mode=0o700, parents=True, exist_ok=True)
            if self.evaluations.is_symlink() or not self.evaluations.resolve().is_relative_to(self.root.resolve()):
                raise EvaluationConflict("evaluation storage must remain beneath its root")
            flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(self.root / ".evaluations.lock", flags, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    def _path(self, evaluation_id: str) -> Path:
        return self.evaluations / f"{hashlib.sha256(evaluation_id.encode()).hexdigest()}.json"

    def save(self, evaluation: EvaluationRecord) -> EvaluationRecord:
        with self._lock():
            path = self._path(evaluation.evaluation_id)
            if path.exists():
                existing = EvaluationRecord.model_validate_json(path.read_text(encoding="utf-8"))
                if existing == evaluation:
                    return existing
                raise EvaluationConflict("evaluation identity already exists with different content")
            descriptor, temporary = tempfile.mkstemp(prefix=".evaluation-", suffix=".json", dir=path.parent)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    json.dump(evaluation.model_dump(mode="json"), handle, sort_keys=True, separators=(",", ":"))
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(temporary, 0o600)
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            return evaluation

    def get(self, evaluation_id: str) -> EvaluationRecord:
        with self._lock():
            path = self._path(evaluation_id)
            if not path.exists():
                raise EvaluationNotFound(evaluation_id)
            if path.is_symlink():
                raise EvaluationConflict("evaluation record may not be a symbolic link")
            return EvaluationRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> tuple[EvaluationRecord, ...]:
        with self._lock():
            values = []
            for path in self.evaluations.glob("*.json"):
                if path.is_symlink():
                    raise EvaluationConflict("evaluation record may not be a symbolic link")
                values.append(EvaluationRecord.model_validate_json(path.read_text(encoding="utf-8")))
            return tuple(sorted(values, key=lambda item: (item.created_at, item.evaluation_id)))
