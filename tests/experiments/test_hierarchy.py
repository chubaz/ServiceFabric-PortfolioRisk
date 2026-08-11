from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from risk_experiments.hierarchy import (
    ArchitectureConfig,
    ArchitectureDecision,
    ArchitectureOutput,
    CaseEvaluationState,
    EvaluationDimensionRecord,
    EvaluationRecord,
    ExperimentalCapabilityConfig,
    ExperimentalCase,
    ExperimentalRun,
    ObservableCaseState,
    RegimeLabel,
    RunInput,
    RunTraceRecord,
    EVALUATION_DIMENSION_IDS,
)


NOW = datetime(2020, 1, 2, tzinfo=timezone.utc)


def _case() -> ExperimentalCase:
    return ExperimentalCase(
        case_id="case-01",
        experiment_id="experiment-01",
        observable_state=ObservableCaseState(
            portfolio_reference="portfolio:01",
            mandate_reference="mandate:portfolio-risk:01@1.0.0",
            risk_policy_reference="risk-policy:portfolio-risk:01@1.0.0",
            data_references=("dataset:market",),
            observation_ids=("observation-01",),
            as_of=NOW,
        ),
        evaluation_state=CaseEvaluationState(
            evaluation_horizon_end=NOW,
            regimes=(RegimeLabel(
                dimension="volatility",
                value="low",
                evidence_ids=("observation-01",),
            ),),
        ),
    )


def _run(case_id: str = "case-01") -> ExperimentalRun:
    output = ArchitectureOutput(
        output_id="output-01",
        run_id="run-01",
        architecture_type="deterministic",
        assessment_state="clear",
        severity=0,
        confidence=0.65,
        confidence_method="deterministic threshold distance",
        findings=(),
        supporting_evidence_ids=(),
        risk_interpretation="No mandate threshold was breached.",
        expectations="No market forecast was produced.",
        decision=ArchitectureDecision(
            monitoring_action="continue_monitoring",
            portfolio_action="none",
            alternatives_considered=("continue_monitoring",),
            human_review_required=False,
        ),
        missing_information=("reviewed outcomes",),
        assumptions=("fixed quantities",),
        architecture_id="architecture-01",
        capabilities_used=("capability-01",),
    )
    evaluation = EvaluationRecord(
        evaluation_id="evaluation-01",
        run_id="run-01",
        evaluator="deterministic_evaluator",
        evaluated_output_id=output.output_id,
        label_state="not_admitted",
        dimensions=tuple(EvaluationDimensionRecord(
            dimension_id=dimension_id,
            status="measured" if dimension_id in {"stability", "efficiency"} else "not_measurable",
            score=1.0 if dimension_id == "stability" else None,
            summary="The complete evaluation dimension is retained.",
            metric_values={"deterministic": True},
        ) for dimension_id in EVALUATION_DIMENSION_IDS),
        created_at=NOW,
    )
    return ExperimentalRun(
        run_id="run-01",
        study_id="study-01",
        experiment_id="experiment-01",
        case_id=case_id,
        regime_labels=(),
        run_input=RunInput(
            case_id="case-01",
            architecture_id="architecture-01",
            information_regime="licensed-data",
            capability_references=("capability-01",),
            repetition=1,
            observation_ids=("observation-01",),
        ),
        architecture_config=ArchitectureConfig(
            architecture_id="architecture-01",
            architecture_type="deterministic",
            version="1.0.0",
            deterministic=True,
        ),
        architecture_output=output,
        run_trace=RunTraceRecord(
            started_at=NOW,
            completed_at=NOW,
            wall_clock_ms=1.0,
            model_calls=0,
            tool_calls=1,
        ),
        runtime_observations=(),
        evaluation_record=evaluation,
    )


def test_case_separates_observable_input_from_hidden_evaluation_state() -> None:
    case = _case()

    assert case.context_digest
    assert case.evaluation_state.architecture_access is False
    assert case.evaluation_state.regimes[0].value == "low"


def test_run_binds_evaluation_to_exact_immutable_architecture_output() -> None:
    run = _run()

    assert run.evaluation_record.evaluated_output_id == run.architecture_output.output_id
    with pytest.raises(ValidationError, match="RunInput must reference the exact Case"):
        _run(case_id="case-02")


def test_architecture_type_controls_how_cycle_context_is_interpreted() -> None:
    single_agent = ArchitectureConfig(
        architecture_id="agent-01",
        architecture_type="single_agent",
        version="1.0.0",
        deterministic=False,
        interpretation_mode="single_agent",
    )
    assert single_agent.interpretation_mode == "single_agent"

    with pytest.raises(ValidationError, match="interpretation_mode must match architecture_type"):
        ArchitectureConfig(
            architecture_id="agent-01",
            architecture_type="single_agent",
            version="1.0.0",
            deterministic=False,
            interpretation_mode="fixed_rules",
        )


def test_experimental_capabilities_distinguish_frozen_and_adaptive_parameters() -> None:
    frozen = ExperimentalCapabilityConfig(
        capability_id="event-relevance-classifier",
        version="1.0.0",
        implementation_class="statistical",
        parameterization="preconfigured",
        evaluation_roles=("architecture_input", "reference_label"),
        parameter_digest="sha256:" + "1" * 64,
    )
    assert frozen.selector_agent_id is None

    adaptive = ExperimentalCapabilityConfig(
        capability_id="adaptive-event-query",
        version="1.0.0",
        implementation_class="generative",
        parameterization="adaptive",
        evaluation_roles=("architecture_input",),
        selector_agent_id="risk.agent.news_sentiment",
        comparable_across_architectures=False,
    )
    assert adaptive.parameter_digest is None

    with pytest.raises(ValidationError, match="frozen parameters"):
        ExperimentalCapabilityConfig(
            capability_id="invalid-preconfigured-capability",
            version="1.0.0",
            implementation_class="deterministic",
            parameterization="preconfigured",
            evaluation_roles=("measurement",),
        )

    deterministic_run = _run().model_dump(mode="python")
    deterministic_run["run_input"]["capability_references"] = (adaptive.capability_id,)
    deterministic_run["run_input"]["capability_configurations"] = (adaptive.model_dump(mode="python"),)
    with pytest.raises(ValidationError, match="cannot use adaptive or generative"):
        ExperimentalRun.model_validate(deterministic_run)


def test_evaluation_record_requires_the_complete_nine_dimension_framework() -> None:
    with pytest.raises(ValidationError, match="nine dimensions"):
        EvaluationRecord(
            evaluation_id="evaluation-incomplete",
            run_id="run-01",
            evaluator="deterministic_evaluator",
            evaluated_output_id="output-01",
            label_state="not_admitted",
            dimensions=(EvaluationDimensionRecord(
                dimension_id="stability", status="partial", score=None,
                summary="Only one dimension was supplied.", metric_values={},
            ),),
            created_at=NOW,
        )


def test_architecture_output_rejects_semantically_inconsistent_severity() -> None:
    payload = _run().architecture_output.model_dump(mode="python")
    payload["severity"] = 1
    with pytest.raises(ValidationError, match="highest finding severity"):
        ArchitectureOutput.model_validate(payload)
