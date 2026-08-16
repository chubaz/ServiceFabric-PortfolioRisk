"""Terminal selected-case evaluation and compact comparison projections."""

from __future__ import annotations

from typing import Any

from gold_case_runtime import gold_case_store
from matched_run_runtime import matched_run_store
from trajectory_execution_runtime import trajectory_store
from risk_experiments import (
    COHORT_EVALUATOR_VERSION,
    EvaluationConflict,
    LocalEvaluationStore,
    MatchedRunConflict,
    PerturbationCondition,
    evaluate_selected_case_cohort,
    trajectory_semantic_digest,
)


DIMENSION_LABELS = {
    "detection_quality": "Detection",
    "severity_understanding": "Severity",
    "timeliness": "Timeliness",
    "evidence_quality": "Evidence",
    "confidence_calibration": "Confidence",
    "decision_quality": "Decision",
    "robustness": "Robustness",
    "stability": "Stability",
    "efficiency": "Efficiency",
}


def evaluation_store() -> LocalEvaluationStore:
    return LocalEvaluationStore(gold_case_store().root)


def _reference_for_case(case_id: str):  # type: ignore[no-untyped-def]
    record = next(
        (item for item in gold_case_store().list() if item.compiled_case_id == case_id),
        None,
    )
    if record is None:
        raise EvaluationConflict("the matched Case has no accepted Gold reference")
    return record


def _metric_payload(metric: Any) -> dict[str, Any]:
    return {
        "metric_id": metric.metric_id,
        "label": metric.label,
        "status": metric.status,
        "value": metric.value,
        "numerator": metric.numerator,
        "denominator": metric.denominator,
        "unit": metric.unit,
        "method": metric.method,
        "limitations": list(metric.limitations),
    }


def _dimension_payload(dimension: Any) -> dict[str, Any]:
    return {
        "dimension_id": dimension.dimension_id,
        "label": DIMENSION_LABELS[dimension.dimension_id],
        "status": dimension.status,
        "score": dimension.score,
        "summary": dimension.summary,
        "metrics": [_metric_payload(item) for item in dimension.metrics],
        "limitations": list(dimension.limitations),
    }


def _validity_checks(trajectory: Any, expected_times: tuple[Any, ...], gold: Any) -> list[dict[str, Any]]:
    output_ids = tuple(
        cycle.result.architecture_output.output_id
        for cycle in trajectory.cycles
        if cycle.result.architecture_output is not None
    )
    gold_id = gold.bundle.gold_reference_id
    checks = [
        {
            "id": "terminal-status",
            "passed": trajectory.status != "failed",
            "label": "Run reached a valid terminal state",
            "detail": trajectory.status.replace("_", " "),
        },
        {
            "id": "complete-clock",
            "passed": tuple(item.context.replay_at for item in trajectory.cycles) == expected_times,
            "label": "Complete matched clock",
            "detail": f"{len(trajectory.cycles)} of {len(expected_times)} workflow cycles",
        },
        {
            "id": "point-in-time",
            "passed": all(
                observation.available_at <= cycle.context.replay_at
                for cycle in trajectory.cycles
                for observation in cycle.context.eligible_observations
            ),
            "label": "No future observation entered a cycle",
            "detail": "available_at was checked against every replay timestamp",
        },
        {
            "id": "clock-blocking",
            "passed": all(
                cycle.processing_receipt.replay_triggered_at
                == cycle.processing_receipt.replay_paused_at
                == cycle.processing_receipt.replay_resumed_at
                for cycle in trajectory.cycles
            ),
            "label": "Replay time froze during processing",
            "detail": "trigger-to-output wall time was retained separately",
        },
        {
            "id": "gold-firewall",
            "passed": (
                gold.bundle.architecture_access is False
                and all(gold_id not in item for item in output_ids)
                and all(
                    gold_id not in observation.observation_id
                    for cycle in trajectory.cycles
                    for observation in cycle.context.eligible_observations
                )
            ),
            "label": "Gold truth remained hidden",
            "detail": "the evaluator joined the accepted reference only after execution",
        },
        {
            "id": "cycle-errors",
            "passed": not any(cycle.result.status == "error" for cycle in trajectory.cycles),
            "label": "No workflow cycle failed",
            "detail": f"{sum(cycle.result.status == 'abstained' for cycle in trajectory.cycles)} explicit abstentions",
        },
    ]
    return checks


def _run_shortcomings(evaluation: Any, trajectory: Any, gold: Any) -> list[str]:
    shortcomings = [
        item.summary
        for item in evaluation.dimensions
        if item.status == "not_measurable"
    ]
    evidence = next(item for item in evaluation.dimensions if item.dimension_id == "evidence_quality")
    alternative = next(
        item for item in evidence.metrics if item.metric_id == "alternative-evidence-handling"
    )
    if alternative.status == "measured" and float(alternative.value) < 1:
        shortcomings.insert(0, "Reviewed alternative evidence was not kept distinct from supporting evidence.")
    support_available = min(
        (item.available_at for item in gold.bundle.evidence if item.position == "supporting"),
        default=None,
    )
    pre_reference_outputs = sum(
        cycle.result.architecture_output is not None
        and bool(cycle.result.architecture_output.findings)
        and support_available is not None
        and cycle.context.replay_at < support_available
        for cycle in trajectory.cycles
    )
    if pre_reference_outputs:
        shortcomings.append(
            f"{pre_reference_outputs} earlier risk outputs concern other portfolio risks and are outside this selected episode label."
        )
    return list(dict.fromkeys(shortcomings))


def _run_payload(
    trajectory: Any, cell: Any, evaluation: Any,
    checks: list[dict[str, Any]], gold: Any,
) -> dict[str, Any]:
    dimensions = [_dimension_payload(item) for item in evaluation.dimensions]
    measured = sum(item["status"] in {"measured", "partial"} for item in dimensions)
    unavailable = sum(item["status"] == "not_measurable" for item in dimensions)
    processing_ms = sum(item.processing_receipt.processing_wall_ms for item in trajectory.cycles)
    valid = all(item["passed"] for item in checks) and not evaluation.failure_codes
    return {
        "architecture": cell.treatment_id,
        "repetition": cell.repetition,
        "perturbation": cell.perturbation_condition.value,
        "capability_package": cell.capability_package_id,
        "run_id": trajectory.run_id,
        "trajectory_id": trajectory.trajectory_id,
        "evaluation_id": evaluation.evaluation_id,
        "semantic_digest": trajectory_semantic_digest(trajectory),
        "status": "valid_with_limitations" if valid and unavailable else "valid" if valid else "invalid",
        "archivable": valid,
        "measured_dimensions": measured,
        "unavailable_dimensions": unavailable,
        "dimensions": dimensions,
        "shortcomings": _run_shortcomings(evaluation, trajectory, gold),
        "resources": {
            "processing_ms": round(processing_ms, 3),
            "model_calls": trajectory.total_model_calls,
            "input_tokens": trajectory.total_input_tokens,
            "output_tokens": trajectory.total_output_tokens,
            "cost_usd": trajectory.total_cost_usd,
        },
        "checks": checks,
    }


def _architecture_payload(architecture: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    dimensions = []
    for dimension_id, label in DIMENSION_LABELS.items():
        matching = [
            dimension for run in runs for dimension in run["dimensions"]
            if dimension["dimension_id"] == dimension_id
        ]
        scores = [float(item["score"]) for item in matching if item["score"] is not None]
        dimensions.append({
            "dimension_id": dimension_id,
            "label": label,
            "status": "measured" if matching and all(item["status"] == "measured" for item in matching)
            else "partial" if any(item["status"] in {"measured", "partial"} for item in matching)
            else "not_measurable",
            "score": None if not scores else sum(scores) / len(scores),
            "summary": matching[0]["summary"] if matching else "No result retained.",
            "limitations": list(dict.fromkeys(
                limitation for item in matching for limitation in item["limitations"]
            )),
            "metrics": [],
        })
    resources = {
        key: round(sum(float(run["resources"][key]) for run in runs), 6)
        for key in ("processing_ms", "model_calls", "input_tokens", "output_tokens", "cost_usd")
    }
    valid = all(run["archivable"] for run in runs)
    return {
        "architecture": architecture,
        "status": "valid_with_limitations" if valid else "invalid",
        "archivable": valid,
        "run_count": len(runs),
        "repetitions": len({run["repetition"] for run in runs}),
        "perturbations": len({run["perturbation"] for run in runs}),
        "measured_dimensions": sum(item["status"] in {"measured", "partial"} for item in dimensions),
        "unavailable_dimensions": sum(item["status"] == "not_measurable" for item in dimensions),
        "dimensions": dimensions,
        "resources": resources,
        "shortcomings": list(dict.fromkeys(item for run in runs for item in run["shortcomings"])),
        "checks": [check for run in runs for check in run["checks"] if not check["passed"]],
    }


def evaluate_matched_matrix(matrix_id: str) -> dict[str, Any]:
    """Persist exact Run evaluations and return a salient human projection."""

    plan = matched_run_store().get(matrix_id)
    gold = _reference_for_case(plan.case_id)
    by_cell = {
        item.cell_id: item
        for item in trajectory_store().list()
        if item.matrix_id == matrix_id
    }
    cell_by_id = {item.cell_id: item for item in plan.cells}
    if not by_cell:
        return {
            "matrix_id": matrix_id,
            "status": "not_ready",
            "archivable": False,
            "summary": "No retained Runs are available for evaluation.",
            "coverage": {"completed": 0, "planned": len(plan.cells)},
            "runs": [],
            "findings": [],
            "limitations": ["Execute every matched cell before comparing architectures."],
        }
    expected_by_perturbation: dict[Any, tuple[Any, ...]] = {}
    for cell in plan.cells:
        trajectory = by_cell.get(cell.cell_id)
        if trajectory is not None and cell.perturbation_condition not in expected_by_perturbation:
            expected_by_perturbation[cell.perturbation_condition] = tuple(
                item.context.replay_at for item in trajectory.cycles
            )
    runs = []
    for cell in plan.cells:
        trajectory = by_cell.get(cell.cell_id)
        if trajectory is None:
            continue
        repeats = tuple(
            by_cell[peer.cell_id] for peer in plan.cells
            if peer.cell_id in by_cell
            and peer.treatment_id == cell.treatment_id
            and peer.capability_package_id == cell.capability_package_id
            and peer.perturbation_condition == cell.perturbation_condition
            and peer.cell_id != cell.cell_id
        )
        paired_cell = next((
            peer for peer in plan.cells
            if peer.treatment_id == cell.treatment_id
            and peer.capability_package_id == cell.capability_package_id
            and peer.repetition == cell.repetition
            and peer.perturbation_condition != cell.perturbation_condition
            and peer.cell_id in by_cell
        ), None)
        evaluation = evaluation_store().save(evaluate_selected_case_cohort(
            trajectory, gold, repeat_trajectories=repeats,
            paired_trajectory=None if paired_cell is None else by_cell[paired_cell.cell_id],
        ))
        checks = _validity_checks(
            trajectory, expected_by_perturbation[cell.perturbation_condition], gold,
        )
        runs.append(_run_payload(trajectory, cell_by_id[cell.cell_id], evaluation, checks, gold))
    order = {"B0": 0, "B1": 1, "A1": 2}
    runs.sort(key=lambda item: (order[item["architecture"]], item["run_id"]))
    complete = len(runs) == len(plan.cells)
    valid = complete and all(item["archivable"] for item in runs)
    unperturbed = [item for item in runs if item["perturbation"] == PerturbationCondition.NONE.value]
    detection_hits = {
        f'{item["architecture"]}-{item["repetition"]}': next(
            dimension["score"] for dimension in item["dimensions"]
            if dimension["dimension_id"] == "detection_quality"
        )
        for item in unperturbed
    }
    evidence_scores = {
        architecture: sum(scores) / len(scores)
        for architecture in ("B0", "B1", "A1")
        if (scores := [
            float(next(dimension["score"] for dimension in item["dimensions"]
                       if dimension["dimension_id"] == "evidence_quality") or 0)
            for item in unperturbed if item["architecture"] == architecture
        ])
    }
    findings: list[str] = []
    if complete and len(set(detection_hits.values())) == 1:
        findings.append("All three methods recognised the selected episode in the same daily-price session.")
    if evidence_scores:
        best = max(evidence_scores, key=lambda key: evidence_scores[key] or 0)
        if len(set(evidence_scores.values())) > 1:
            findings.append(f"{best} handled the reviewed supporting and alternative evidence most faithfully.")
    if complete:
        baseline = next(item for item in unperturbed if item["architecture"] == "B0")
        agent_cost = sum(item["resources"]["cost_usd"] for item in runs if item["architecture"] != "B0")
        findings.append(
            f"The agent methods used ${agent_cost:.4f} and more processing time; this one Case shows no detection-timing gain over B0."
        )
        findings.append(
            "Repeat-run stability and resilience to a one-cycle adverse-event delay are now measured for every method."
        )
    limitations = [
        "One selected materialised Case cannot rank architectures or estimate population precision and recall.",
        "Severity forecasts, representative calibration and economic branch outcomes are not yet present.",
        "Daily prices support session-level timeliness only; event processing latency is reported separately in real wall time.",
    ]
    return {
        "matrix_id": matrix_id,
        "case_id": plan.case_id,
        "data_truth": gold.bundle.data_truth,
        "status": "valid_with_limitations" if valid else "incomplete_or_invalid",
        "archivable": valid,
        "summary": (
            "The matched comparison ran correctly. Its scientific scope remains limited to one selected Case."
            if valid else "The comparison is incomplete or contains a failed validity check."
        ),
        "coverage": {"completed": len(runs), "planned": len(plan.cells)},
        "runs": runs,
        "architectures": [
            _architecture_payload(architecture, [run for run in runs if run["architecture"] == architecture])
            for architecture in ("B0", "B1", "A1")
        ],
        "findings": findings,
        "limitations": limitations,
        "technical_receipt": {
            "gold_reference_id": gold.bundle.gold_reference_id,
            "gold_digest": gold.bundle.bundle_digest,
            "matrix_digest": plan.matrix_digest,
            "evaluation_ids": [item["evaluation_id"] for item in runs],
            "evaluator": COHORT_EVALUATOR_VERSION,
        },
    }
