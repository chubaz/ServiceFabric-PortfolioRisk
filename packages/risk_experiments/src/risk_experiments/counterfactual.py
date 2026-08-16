"""Counterfactual experiment catalogue and terminal batch analysis.

The evaluator consumes immutable Run results after execution. It never rewrites
an ArchitectureOutput and never upgrades descriptive contrasts into causal or
thesis claims when labels or matured outcomes are unavailable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import canonical_digest


COUNTERFACTUAL_DIMENSIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "architecture",
        "label": "Architecture",
        "kind": "system_intervention",
        "question": "What changes under deterministic, single-agent or agent-graph execution?",
        "treatments": ("B0", "B1", "A1"),
        "execution_state": "available",
    },
    {
        "id": "information_regime",
        "label": "Information regime",
        "kind": "system_intervention",
        "question": "What changes when portfolio, market, event or mandate context is added or removed?",
        "treatments": ("portfolio_only", "market", "events", "mandate_thesis_context"),
        "execution_state": "design_only",
    },
    {
        "id": "capability_pack",
        "label": "Capability pack",
        "kind": "system_intervention",
        "question": "What is the marginal value of monitoring, scenario, factor or decision capabilities?",
        "treatments": ("basic_metrics", "monitoring", "scenario_factor", "decision"),
        "execution_state": "design_only",
    },
    {
        "id": "parameterisation",
        "label": "Parameterisation",
        "kind": "system_intervention",
        "question": "What changes under fixed, mechanically derived or agent-selected parameters?",
        "treatments": ("fixed", "mechanically_derived", "agent_selected"),
        "execution_state": "design_only",
    },
    {
        "id": "event_selection",
        "label": "Event selection",
        "kind": "system_intervention",
        "question": "What changes under unfiltered, provider, ex-ante ML or oracle event selection?",
        "treatments": ("unfiltered", "provider_filter", "ex_ante_ml", "retrospective_oracle"),
        "execution_state": "design_only",
    },
    {
        "id": "model_configuration",
        "label": "Agent / model configuration",
        "kind": "system_intervention",
        "question": "What changes with another model, prompt, budget or coordinator configuration?",
        "treatments": ("registered_configuration",),
        "execution_state": "design_only",
    },
    {
        "id": "repetition",
        "label": "Repetition",
        "kind": "system_intervention",
        "question": "How stable is an identical configuration across repeated Runs?",
        "treatments": ("identical_repeat",),
        "execution_state": "available",
    },
    {
        "id": "decision_policy",
        "label": "Decision policy",
        "kind": "system_intervention",
        "question": "What changes when the method may alert, recommend or select a simulated action?",
        "treatments": ("alert_only", "recommendation", "simulated_action"),
        "execution_state": "design_only",
    },
    {
        "id": "portfolio_action",
        "label": "Portfolio action",
        "kind": "financial_counterfactual",
        "question": "What would happen under no action, a 25% reduction or a 50% reduction?",
        "treatments": ("NO_ACTION", "REDUCE_POSITION_25%", "REDUCE_POSITION_50%"),
        "execution_state": "design_only",
    },
    {
        "id": "market_scenario",
        "label": "Market scenario",
        "kind": "financial_counterfactual",
        "question": "Would the same decision remain useful under another explicit future market path?",
        "treatments": ("historical_path", "event_worsens", "sector_shock", "market_rebound", "liquidity_stress"),
        "execution_state": "design_only",
    },
    {
        "id": "regime",
        "label": "Regime",
        "kind": "conditioning_variable",
        "question": "Do paired effects differ across observed market and event regimes?",
        "treatments": (),
        "execution_state": "conditioning_only",
    },
    {
        "id": "case_characteristics",
        "label": "Case characteristics",
        "kind": "conditioning_variable",
        "question": "Do effects differ by event type, risk type, severity or portfolio concentration?",
        "treatments": (),
        "execution_state": "conditioning_only",
    },
)


EVALUATION_LABELS = {
    "detection_quality": "Detection quality",
    "severity_understanding": "Severity and risk understanding",
    "timeliness": "Timeliness",
    "evidence_quality": "Evidence quality",
    "confidence_calibration": "Confidence and calibration",
    "decision_quality": "Decision quality",
    "robustness": "Robustness",
    "stability": "Stability",
    "efficiency": "Efficiency",
}


SEQUENTIAL_EXPERIMENT_PROGRAMME: tuple[dict[str, str], ...] = (
    {"id": "architecture", "label": "Architecture", "comparison": "B0 vs B1 vs A1", "state": "executable"},
    {"id": "information", "label": "Information", "comparison": "Architecture × information regime", "state": "planned"},
    {"id": "capabilities", "label": "Capabilities", "comparison": "Architecture × capability pack", "state": "planned"},
    {"id": "parameterisation", "label": "Parameterisation", "comparison": "Fixed vs derived vs agent-selected", "state": "planned"},
    {"id": "event_selection", "label": "Event selection", "comparison": "Provider vs ML vs oracle filter", "state": "planned"},
    {"id": "decisions", "label": "Decisions", "comparison": "Policy and portfolio-action branches", "state": "planned"},
    {"id": "robustness", "label": "Robustness", "comparison": "Condition prior effects on regime and Case", "state": "planned"},
)


def dimension_catalogue() -> list[dict[str, Any]]:
    """Return a JSON-safe copy of the governed comparison taxonomy."""

    return [
        {**item, "treatments": list(item["treatments"])}
        for item in COUNTERFACTUAL_DIMENSIONS
    ]


def counterfactual_design_map() -> dict[str, Any]:
    """Return the plain-language map used to design bounded experiments."""

    return {
        "groups": (
            {
                "id": "system_intervention",
                "label": "Change the system",
                "rule": "Change one declared system feature while the Case and other controls stay fixed.",
            },
            {
                "id": "financial_counterfactual",
                "label": "Simulate financial outcomes",
                "rule": "Keep the system decision fixed and branch over permitted actions or explicit future paths.",
            },
            {
                "id": "conditioning_variable",
                "label": "Group the results",
                "rule": "Do not treat these labels as interventions; use them to explain where effects differ.",
            },
        ),
        "outcomes": tuple(
            {"id": outcome_id, "label": label}
            for outcome_id, label in EVALUATION_LABELS.items()
        ),
        "programme": SEQUENTIAL_EXPERIMENT_PROGRAMME,
        "design_rule": (
            "Run one primary comparison at a time. Add a second varying dimension only for a declared interaction; "
            "everything else is a control or a result-grouping variable."
        ),
    }


def _architecture_signature(result: dict[str, Any]) -> str:
    outputs = result.get("run_record", {}).get("architecture_outputs") or []
    normalized = []
    for output in outputs:
        normalized.append(
            {
                "assessment_state": output.get("assessment_state"),
                "severity": output.get("severity"),
                "confidence": output.get("confidence"),
                "change_since_previous": output.get("change_since_previous"),
                "findings": [
                    {
                        "risk_type": item.get("risk_type"),
                        "affected_asset": item.get("affected_asset"),
                        "severity": item.get("severity"),
                        "materiality": item.get("materiality"),
                        "metric_id": item.get("metric_id"),
                    }
                    for item in output.get("findings", [])
                ],
                "decision": {
                    "monitoring_action": output.get("decision", {}).get("monitoring_action"),
                    "portfolio_action": output.get("decision", {}).get("portfolio_action"),
                    "human_review_required": output.get("decision", {}).get("human_review_required"),
                },
            }
        )
    return canonical_digest(normalized)


def _evaluation_dimensions(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    dimensions = result.get("evaluation", {}).get("dimensions") or []
    return {item["id"]: item for item in dimensions if item.get("id")}


def _mean(values: list[float]) -> float | None:
    return None if not values else sum(values) / len(values)


def _observed_outcomes(result: dict[str, Any]) -> list[dict[str, Any]]:
    run = result.get("run_record", {})
    outputs = run.get("architecture_outputs") or []
    dimensions = _evaluation_dimensions(result)
    resource = result.get("execution_regime", {}).get("resource_usage", {})
    metric = lambda dimension_id, name, default=None: (  # noqa: E731
        dimensions.get(dimension_id, {}).get("metrics", {}).get(name, default)
    )
    common_metrics: dict[str, dict[str, Any]] = {
        "detection_quality": {
            "true_positives": metric("detection_quality", "true_positives"),
            "false_positives": metric("detection_quality", "false_positives"),
            "false_negatives": metric("detection_quality", "false_negatives"),
            "precision": metric("detection_quality", "precision"),
            "recall": metric("detection_quality", "recall"),
            "f1": metric("detection_quality", "f1"),
            "cycle_classification_accuracy": metric("detection_quality", "cycle_classification_accuracy"),
        },
        "severity_understanding": {
            "maximum_severity": max((int(item.get("severity", 0)) for item in outputs), default=0),
            "matched_findings": metric("severity_understanding", "matched_findings"),
            "severity_mae": metric("severity_understanding", "severity_mae"),
            "exact_severity_rate": metric("severity_understanding", "exact_severity_rate"),
            "risk_type_accuracy": metric("severity_understanding", "risk_type_accuracy"),
        },
        "timeliness": {
            "same_cycle_detection_rate": metric("timeliness", "same_cycle_detection_rate"),
            "mean_trigger_to_cycle_hours": metric("timeliness", "mean_trigger_to_cycle_hours"),
            "mean_processing_to_first_finding_ms": metric("timeliness", "mean_processing_to_first_finding_ms"),
        },
        "evidence_quality": {
            "finding_citation_coverage": metric("evidence_quality", "finding_citation_coverage"),
            "evidence_index_coverage": metric("evidence_quality", "evidence_index_coverage"),
            "mean_evidence_references_per_finding": metric("evidence_quality", "mean_evidence_references_per_finding"),
            "unsupported_findings": metric("evidence_quality", "unsupported_findings"),
        },
        "confidence_calibration": {
            "brier_score": metric("confidence_calibration", "brier_score"),
            "calibration_cases": metric("confidence_calibration", "calibration_cases"),
            "mean_ordinal_confidence": metric("confidence_calibration", "mean_ordinal_confidence"),
        },
        "decision_quality": {
            "monitoring_action_agreement": metric("decision_quality", "monitoring_action_agreement"),
            "portfolio_action_agreement": metric("decision_quality", "portfolio_action_agreement"),
            "mean_monitoring_action_distance": metric("decision_quality", "mean_monitoring_action_distance"),
            "regret": metric("decision_quality", "regret"),
        },
        "robustness": {
            "perturbation_cases": metric("robustness", "perturbation_cases", 0),
            "position_observation_completeness": metric("robustness", "position_observation_completeness"),
        },
        "stability": {
            "architecture_signature": _architecture_signature(result),
        },
        "efficiency": {
            "processing_wall_ms": metric("efficiency", "processing_wall_ms", resource.get("processing_wall_ms")),
            "model_calls": metric("efficiency", "model_calls", resource.get("model_calls", 0)),
            "input_tokens": metric("efficiency", "input_tokens", resource.get("input_tokens", 0)),
            "output_tokens": metric("efficiency", "output_tokens", resource.get("output_tokens", 0)),
            "estimated_cost_usd": metric("efficiency", "estimated_cost_usd", resource.get("estimated_cost_usd")),
            "schema_validation_failures": metric("efficiency", "schema_validation_failures"),
            "semantic_verification_failures": metric("efficiency", "semantic_verification_failures"),
        },
    }
    return [
        {
            "dimension_id": dimension_id,
            "label": EVALUATION_LABELS[dimension_id],
            "status": dimensions.get(dimension_id, {}).get("status", "not_measurable"),
            "score": dimensions.get(dimension_id, {}).get("score"),
            "formula": dimensions.get(dimension_id, {}).get("formula", "Not declared by the evaluator."),
            "measurement_scope": dimensions.get(dimension_id, {}).get(
                "measurement_scope", "Not declared by the evaluator."
            ),
            "summary": dimensions.get(dimension_id, {}).get(
                "summary", "The selected evaluator did not return this dimension."
            ),
            "metrics": common_metrics[dimension_id],
        }
        for dimension_id in EVALUATION_LABELS
    ]


def _control_identity(result: dict[str, Any]) -> dict[str, Any]:
    hierarchy = result.get("hierarchy", {})
    case = hierarchy.get("case", {})
    return {
        "case_id": case.get("case_id"),
        "context_digest": case.get("context_digest"),
        "portfolio_id": result.get("portfolio", {}).get("id"),
        "mandate_reference": result.get("mandate", {}).get("reference"),
        "period": result.get("period"),
        "evaluation_id": result.get("evaluation", {}).get("id"),
        "information_regime": result.get("run_record", {}).get("run_input", {}).get("information_regime"),
    }


def _metric_deltas(
    baseline: list[dict[str, Any]], treatment: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    treatment_by_id = {item["dimension_id"]: item for item in treatment}
    deltas = []
    for baseline_dimension in baseline:
        treatment_dimension = treatment_by_id[baseline_dimension["dimension_id"]]
        observations = []
        for metric, baseline_value in baseline_dimension["metrics"].items():
            treatment_value = treatment_dimension["metrics"].get(metric)
            delta = None
            if (
                isinstance(baseline_value, (int, float))
                and not isinstance(baseline_value, bool)
                and isinstance(treatment_value, (int, float))
                and not isinstance(treatment_value, bool)
            ):
                delta = treatment_value - baseline_value
            observations.append(
                {
                    "metric": metric,
                    "baseline": baseline_value,
                    "treatment": treatment_value,
                    "delta": delta,
                }
            )
        statuses = {baseline_dimension["status"], treatment_dimension["status"]}
        comparison_status = (
            "measured"
            if statuses == {"measured"}
            else "not_measurable"
            if statuses <= {"not_measurable", "not_applicable"}
            else "partial"
        )
        deltas.append(
            {
                "dimension_id": baseline_dimension["dimension_id"],
                "label": baseline_dimension["label"],
                "status": comparison_status,
                "observations": observations,
                "interpretation": (
                    "Observed paired difference only; no causal, predictive or decision-quality claim is implied."
                ),
            }
        )
    return deltas


def analyse_counterfactual_batch(
    *,
    study_id: str,
    experiment_id: str,
    research_question: str,
    hypothesis: str,
    baseline_workflow_id: str,
    planned_cells: list[dict[str, Any]],
    completed_cells: list[dict[str, Any]],
    failed_cells: list[dict[str, Any]],
    evaluation_version: str = "counterfactual-terminal-analysis/1.0.0",
) -> dict[str, Any]:
    """Produce one terminal analysis over a predeclared architecture matrix."""

    completed = []
    for cell in completed_cells:
        result = cell["result"]
        hierarchy = result.get("hierarchy", {})
        completed.append(
            {
                "cell_id": cell["cell_id"],
                "case_id": hierarchy.get("case", {}).get("case_id"),
                "run_id": result.get("run_id"),
                "artifact_id": cell.get("artifact_id"),
                "workflow_id": cell["workflow_id"],
                "repetition": cell["repetition"],
                "is_baseline": cell["workflow_id"] == baseline_workflow_id,
                "regimes": hierarchy.get("regimes", []),
                "control_identity": _control_identity(result),
                "observed_outcomes": _observed_outcomes(result),
                "architecture_signature": _architecture_signature(result),
                "diagnostics": result.get("diagnostics", {}),
            }
        )

    by_pair = {
        (item["case_id"], item["repetition"], item["workflow_id"]): item
        for item in completed
    }
    workflows = sorted({item["workflow_id"] for item in planned_cells})
    cases = sorted({item["case_id"] for item in completed if item["case_id"]})
    repetitions = sorted({int(item["repetition"]) for item in planned_cells})
    contrasts = []
    confounds: list[dict[str, Any]] = []
    for case_id in cases:
        for repetition in repetitions:
            baseline = by_pair.get((case_id, repetition, baseline_workflow_id))
            if baseline is None:
                continue
            for workflow_id in workflows:
                if workflow_id == baseline_workflow_id:
                    continue
                treatment = by_pair.get((case_id, repetition, workflow_id))
                if treatment is None:
                    continue
                changed_controls = sorted(
                    key
                    for key, value in baseline["control_identity"].items()
                    if treatment["control_identity"].get(key) != value
                )
                if changed_controls:
                    confounds.append(
                        {
                            "case_id": case_id,
                            "repetition": repetition,
                            "baseline_run_id": baseline["run_id"],
                            "treatment_run_id": treatment["run_id"],
                            "changed_controls": changed_controls,
                        }
                    )
                contrasts.append(
                    {
                        "contrast_id": f"{case_id}:r{repetition}:{baseline_workflow_id}-vs-{workflow_id}",
                        "case_id": case_id,
                        "repetition": repetition,
                        "changed_dimension": "architecture",
                        "baseline": {
                            "workflow_id": baseline_workflow_id,
                            "run_id": baseline["run_id"],
                            "artifact_id": baseline["artifact_id"],
                        },
                        "treatment": {
                            "workflow_id": workflow_id,
                            "run_id": treatment["run_id"],
                            "artifact_id": treatment["artifact_id"],
                        },
                        "pair_comparable": not changed_controls,
                        "changed_controls": changed_controls,
                        "outcomes": _metric_deltas(
                            baseline["observed_outcomes"], treatment["observed_outcomes"]
                        ),
                    }
                )

    stability = []
    for case_id in cases:
        for workflow_id in workflows:
            cells = [
                item
                for item in completed
                if item["case_id"] == case_id and item["workflow_id"] == workflow_id
            ]
            signatures = {item["architecture_signature"] for item in cells}
            stability.append(
                {
                    "case_id": case_id,
                    "workflow_id": workflow_id,
                    "completed_repetitions": len(cells),
                    "status": "measured" if len(cells) > 1 else "partial",
                    "identical_outputs": len(cells) > 1 and len(signatures) == 1,
                    "unique_output_signatures": len(signatures),
                    "run_ids": [item["run_id"] for item in cells],
                }
            )

    regimes: dict[str, set[str]] = {}
    for item in completed:
        for regime in item["regimes"]:
            regimes.setdefault(regime.get("dimension", "unknown"), set()).add(
                regime.get("value", "unknown")
            )
    planned_count = len(planned_cells)
    completed_count = len(completed)
    failed_count = len(failed_cells)
    expected_contrasts = len(cases) * len(repetitions) * max(0, len(workflows) - 1)
    status = (
        "complete"
        if planned_count > 0
        and completed_count == planned_count
        and failed_count == 0
        and len(contrasts) == expected_contrasts
        and not confounds
        else "partial"
    )
    generated_at = datetime.now(timezone.utc).isoformat()
    shortcomings = []
    seen_shortcomings: set[tuple[str, str]] = set()
    for cell in completed:
        for issue in cell.get("diagnostics", {}).get("shortcomings", []):
            identity = (cell["workflow_id"], issue.get("code", "UNKNOWN"))
            if identity in seen_shortcomings:
                continue
            seen_shortcomings.add(identity)
            shortcomings.append({
                **issue,
                "workflow_id": cell["workflow_id"],
                "run_id": cell["run_id"],
                "case_id": cell["case_id"],
            })
    for cell in failed_cells:
        workflow_id = cell.get("workflow_id") or str(cell.get("cell_id", "unknown")).rsplit(":", 1)[-1]
        case_id = cell.get("case_id") or str(cell.get("cell_id", "unknown")).split(":r", 1)[0]
        shortcomings.append({
            "code": "RUN-CELL-EXECUTION-FAILED",
            "category": "execution",
            "severity": "critical",
            "summary": f"{workflow_id} did not produce a retained ArchitectureOutput.",
            "detail": cell.get("error", "Unknown execution error."),
            "affected_dimensions": list(EVALUATION_LABELS),
            "remediation": "Inspect the failed cell, repair the runtime or architecture, and repeat the matched batch.",
            "codex_actionable": True,
            "workflow_id": workflow_id,
            "run_id": None,
            "case_id": case_id,
        })
    diagnostic_counts = {
        level: sum(item.get("severity") == level for item in shortcomings)
        for level in ("critical", "high", "medium", "low")
    }
    analysis = {
        "schema_version": "portfolio-risk.counterfactual-analysis/v1",
        "analysis_version": evaluation_version,
        "generated_at": generated_at,
        "study_id": study_id,
        "experiment_id": experiment_id,
        "research_question": research_question,
        "hypothesis": hypothesis,
        "status": status,
        "planned_variable_dimensions": ["architecture", "repetition"],
        "conditioning_variables": ["regime", "case_characteristics"],
        "matrix_coverage": {
            "planned": planned_count,
            "completed": completed_count,
            "failed": failed_count,
            "missing": max(0, planned_count - completed_count - failed_count),
            "fraction": 0.0 if planned_count == 0 else completed_count / planned_count,
        },
        "cells": completed,
        "failed_cells": failed_cells,
        "contrasts": contrasts,
        "interactions": [],
        "interaction_status": "not_applicable_single_variable_experiment",
        "stability": stability,
        "regime_conditioning": [
            {"dimension": dimension, "observed_values": sorted(values)}
            for dimension, values in sorted(regimes.items())
        ],
        "confounds": confounds,
        "diagnostics": {
            "schema_version": "portfolio-risk.batch-diagnostics/v1",
            "status": "attention_required" if diagnostic_counts["critical"] or diagnostic_counts["high"] else "review",
            "counts": diagnostic_counts,
            "shortcomings": shortcomings,
            "codex_handoff": {
                "purpose": "Compare recurring apparatus limitations and architecture-specific failures across the matched batch.",
                "priority_issue_codes": sorted({
                    item["code"] for item in shortcomings
                    if item.get("severity") in {"critical", "high"}
                }),
            },
        },
        "failed_treatment_manipulations": [],
        "run_ids": sorted(item["run_id"] for item in completed),
        "interpretation_boundary": (
            "Contrasts are descriptive paired observations over the completed matrix. "
            "Detection accuracy, calibration, decision regret, robustness and causal effects remain "
            "unavailable until their declared labels, matured outcomes or perturbation sets are admitted."
        ),
    }
    analysis["analysis_digest"] = canonical_digest(analysis)
    return analysis
