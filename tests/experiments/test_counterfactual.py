from risk_experiments import (
    analyse_counterfactual_batch, counterfactual_design_map, dimension_catalogue,
)


def result(workflow_id: str, *, repetition: int = 1, context_digest: str = "sha256:case") -> dict:
    is_baseline = workflow_id == "B0"
    severity = 1 if is_baseline else 2
    model_calls = 0 if is_baseline else 1
    return {
        "run_id": f"run-{workflow_id.lower()}-{repetition}",
        "workflow": {"id": workflow_id},
        "hierarchy": {
            "case": {"case_id": "case-01", "context_digest": context_digest},
            "regimes": [
                {"dimension": "volatility", "value": "high"},
                {"dimension": "event", "value": "material-events"},
            ],
        },
        "portfolio": {"id": "portfolio-01"},
        "mandate": {"reference": "mandate:01"},
        "period": {"start": "2020-01-01", "end": "2020-01-03"},
        "execution_regime": {
            "resource_usage": {
                "processing_wall_ms": 10 + model_calls,
                "model_calls": model_calls,
                "input_tokens": model_calls * 100,
                "output_tokens": model_calls * 20,
                "estimated_cost_usd": model_calls * 0.01,
            }
        },
        "evaluation": {
            "id": "evaluation-v1",
            "dimensions": [
                {
                    "id": dimension_id,
                    "status": "measured" if dimension_id == "efficiency" else "partial",
                    "summary": "Retained observation only.",
                    "metrics": {
                        "structural_evidence_coverage": 1.0,
                        "unsupported_findings": 0,
                        "perturbation_cases": 0,
                    },
                }
                for dimension_id in (
                    "detection_quality",
                    "severity_understanding",
                    "timeliness",
                    "evidence_quality",
                    "confidence_calibration",
                    "decision_quality",
                    "robustness",
                    "stability",
                    "efficiency",
                )
            ],
        },
        "run_record": {
            "run_input": {"information_regime": "market-events", "repetition": repetition},
            "run_trace": {"wall_clock_ms": 10 + model_calls},
            "finding_episodes": [{"episode_id": "episode-01"}],
            "architecture_outputs": [
                {
                    "assessment_state": "warning",
                    "severity": severity,
                    "confidence": 0.7,
                    "change_since_previous": "initial",
                    "findings": [
                        {
                            "risk_type": "loss",
                            "affected_asset": "portfolio-01",
                            "severity": severity,
                            "materiality": 0.5,
                            "metric_id": "drawdown",
                        }
                    ],
                    "decision": {
                        "monitoring_action": "increase_monitoring",
                        "portfolio_action": "none",
                        "human_review_required": True,
                    },
                }
            ],
        },
    }


def cell(workflow_id: str, repetition: int = 1, **overrides) -> dict:
    value = {
        "cell_id": f"case-01:r{repetition}:{workflow_id}",
        "case_id": "case-01",
        "workflow_id": workflow_id,
        "repetition": repetition,
    }
    value.update(overrides)
    return value


def test_catalogue_separates_interventions_counterfactuals_and_conditioning() -> None:
    catalogue = {item["id"]: item for item in dimension_catalogue()}

    assert catalogue["architecture"]["execution_state"] == "available"
    assert catalogue["portfolio_action"]["kind"] == "financial_counterfactual"
    assert catalogue["regime"]["kind"] == "conditioning_variable"
    assert catalogue["regime"]["treatments"] == []
    assert catalogue["case_characteristics"]["kind"] == "conditioning_variable"
    assert catalogue["market_scenario"]["kind"] == "financial_counterfactual"

    design_map = counterfactual_design_map()
    assert [item["id"] for item in design_map["groups"]] == [
        "system_intervention", "financial_counterfactual", "conditioning_variable",
    ]
    assert design_map["programme"][0]["state"] == "executable"
    assert len(design_map["outcomes"]) == 9


def test_terminal_analysis_pairs_runs_within_the_same_case() -> None:
    planned = [cell("B0"), cell("B1"), cell("A1")]
    completed = [
        cell(workflow, result=result(workflow), artifact_id=f"historical-replay:run-{workflow.lower()}-1")
        for workflow in ("B0", "B1", "A1")
    ]

    analysis = analyse_counterfactual_batch(
        study_id="study-01",
        experiment_id="experiment-01",
        research_question="Does architecture change the same Case output?",
        hypothesis="Agent treatments produce different retained observations.",
        baseline_workflow_id="B0",
        planned_cells=planned,
        completed_cells=completed,
        failed_cells=[],
    )

    assert analysis["status"] == "complete"
    assert analysis["matrix_coverage"] == {
        "planned": 3,
        "completed": 3,
        "failed": 0,
        "missing": 0,
        "fraction": 1.0,
    }
    assert len(analysis["contrasts"]) == 2
    assert all(item["pair_comparable"] for item in analysis["contrasts"])
    assert analysis["interaction_status"] == "not_applicable_single_variable_experiment"
    assert analysis["analysis_digest"].startswith("sha256:")
    severity = next(
        item
        for item in analysis["contrasts"][0]["outcomes"]
        if item["dimension_id"] == "severity_understanding"
    )
    maximum = next(item for item in severity["observations"] if item["metric"] == "maximum_severity")
    assert maximum["delta"] == 1


def test_terminal_analysis_reports_failed_cells_and_control_confounds() -> None:
    planned = [cell("B0"), cell("B1"), cell("A1")]
    completed = [
        cell("B0", result=result("B0"), artifact_id="historical-replay:run-b0-1"),
        cell(
            "B1",
            result=result("B1", context_digest="sha256:different-case"),
            artifact_id="historical-replay:run-b1-1",
        ),
    ]
    analysis = analyse_counterfactual_batch(
        study_id="study-01",
        experiment_id="experiment-01",
        research_question="Does architecture change the same Case output?",
        hypothesis="Agent treatments produce different retained observations.",
        baseline_workflow_id="B0",
        planned_cells=planned,
        completed_cells=completed,
        failed_cells=[{"cell_id": "case-01:r1:A1", "error": "model unavailable"}],
    )

    assert analysis["status"] == "partial"
    assert analysis["matrix_coverage"]["failed"] == 1
    assert analysis["contrasts"][0]["pair_comparable"] is False
    assert analysis["confounds"][0]["changed_controls"] == ["context_digest"]
