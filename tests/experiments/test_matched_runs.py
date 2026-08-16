from datetime import datetime, timezone

import pytest

from risk_experiments import (
    ArchitectureConfig, ArchitectureTreatment, CaseEvaluationState,
    ExperimentalCapabilityConfig, ExperimentalCapabilityPackage, ExperimentalCase,
    IdentityCondition, LocalMatchedRunPlanStore, MatchedRunConflict,
    ObservableCaseState, PerturbationCondition, RunBudget, compile_matched_run_matrix,
)


NOW = datetime(2016, 6, 1, tzinfo=timezone.utc)


def _case(*, admitted: bool = True, experiment_id: str = "experiment-one") -> ExperimentalCase:
    return ExperimentalCase(
        case_id="case-one", experiment_id=experiment_id,
        observable_state=ObservableCaseState(
            portfolio_reference="portfolio-version-one",
            mandate_reference="mandate-version-one-approved",
            risk_policy_reference="risk-policy-version-one-approved",
            data_references=("licensed-data-revision-one",),
            observation_ids=("observation-a", "observation-b"), as_of=NOW,
        ),
        evaluation_state=CaseEvaluationState(
            evaluation_horizon_end=datetime(2016, 7, 1, tzinfo=timezone.utc),
            label_state="admitted" if admitted else "not_admitted",
            reference_label_ids=("gold-reference-one",) if admitted else (),
            outcome_observation_ids=("outcome-one",), architecture_access=False,
        ),
    )


def _capability(*, adaptive: bool = False) -> ExperimentalCapabilityConfig:
    return ExperimentalCapabilityConfig(
        capability_id="market-metrics", version="1.0.0",
        implementation_class="statistical" if adaptive else "deterministic",
        parameterization="adaptive" if adaptive else "preconfigured",
        evaluation_roles=("architecture_input",),
        parameter_digest=None if adaptive else "sha256:" + "1" * 64,
        selector_agent_id="selector-one" if adaptive else None,
    )


def _package(*, adaptive: bool = False) -> ExperimentalCapabilityPackage:
    return ExperimentalCapabilityPackage(
        package_id="market-core", version="1.0.0", display_name="Market core",
        capabilities=(_capability(adaptive=adaptive),),
    )


def _treatments() -> tuple[ArchitectureTreatment, ...]:
    return (
        ArchitectureTreatment(
            treatment_id="B0",
            architecture=ArchitectureConfig(
                architecture_id="b0-baseline", architecture_type="deterministic",
                version="1.0.0", deterministic=True, interpretation_mode="fixed_rules",
            ), context_policy_reference="case-observable-state-v1",
            budget=RunBudget(max_model_calls=0, max_input_tokens=0, max_output_tokens=0,
                             max_cost_usd=0, max_processing_seconds=30),
        ),
        ArchitectureTreatment(
            treatment_id="B1",
            architecture=ArchitectureConfig(
                architecture_id="b1-single-agent", architecture_type="single_agent",
                version="1.0.0", deterministic=False, model_reference="model-one",
                interpretation_mode="single_agent",
            ), prompt_reference="prompt-b1-v1", model_reference="model-one",
            context_policy_reference="case-observable-state-v1",
            budget=RunBudget(max_model_calls=2, max_input_tokens=1000, max_output_tokens=200,
                             max_cost_usd=0.20, max_processing_seconds=60),
        ),
        ArchitectureTreatment(
            treatment_id="A1",
            architecture=ArchitectureConfig(
                architecture_id="a1-agent-graph", architecture_type="agent_graph",
                version="1.0.0", deterministic=False, model_reference="model-one",
                interpretation_mode="agent_graph",
            ), prompt_reference="prompt-a1-v1", model_reference="model-one",
            context_policy_reference="case-observable-state-v1",
            budget=RunBudget(max_model_calls=4, max_input_tokens=2000, max_output_tokens=400,
                             max_cost_usd=0.40, max_processing_seconds=120),
        ),
    )


def _compile(**overrides):
    values = dict(
        case=_case(), study_id="study-one", experiment_id="experiment-one",
        treatments=_treatments(), capability_packages=(_package(),), repetitions=1,
        information_regime="point-in-time", identity_condition=IdentityCondition.NAMED_HISTORICAL,
        seed="fixed-seed", external_model_authorized=False, compiled_by="test-compiler",
        compiled_at=NOW,
    )
    values.update(overrides)
    return compile_matched_run_matrix(**values)


def test_compiles_three_matched_cells_without_executing() -> None:
    plan = _compile()
    assert tuple(item.treatment_id for item in plan.cells) == ("B0", "B1", "A1")
    assert plan.projected_run_count == 3
    assert plan.projected_model_calls == 6
    assert plan.projected_max_cost_usd == pytest.approx(0.60)
    assert plan.execution_status == "not_started"
    assert plan.qualification_state == "requires_model_authorization"
    assert {item.run_input.observation_ids for item in plan.cells} == {("observation-a", "observation-b")}
    assert "gold-reference-one" not in str([item.run_input.model_dump() for item in plan.cells])


def test_repetitions_expand_only_the_declared_factor() -> None:
    plan = _compile(repetitions=2, external_model_authorized=True)
    assert plan.projected_run_count == 6
    assert plan.projected_model_calls == 12
    assert plan.qualification_state == "ready"
    assert {item.repetition for item in plan.cells} == {1, 2}


def test_predeclared_perturbation_expands_the_matrix_without_changing_case_input() -> None:
    plan = _compile(perturbations=(
        PerturbationCondition.NONE,
        PerturbationCondition.DELAY_ADVERSE_EVENT_ONE_CYCLE,
    ))
    assert plan.projected_run_count == 6
    assert "perturbation" in plan.variable_factors
    assert {item.perturbation_condition for item in plan.cells} == set(PerturbationCondition)
    assert {item.run_input.observation_ids for item in plan.cells} == {("observation-a", "observation-b")}


def test_requires_an_admitted_gold_backed_case() -> None:
    with pytest.raises(MatchedRunConflict, match="admitted"):
        _compile(case=_case(admitted=False))


def test_rejects_case_from_another_experiment() -> None:
    with pytest.raises(MatchedRunConflict, match="identities"):
        _compile(case=_case(experiment_id="experiment-other"))


def test_b0_rejects_adaptive_capability_package() -> None:
    with pytest.raises(MatchedRunConflict, match="B0"):
        _compile(capability_packages=(_package(adaptive=True),))


def test_store_is_immutable_and_idempotent(tmp_path) -> None:
    store = LocalMatchedRunPlanStore(tmp_path)
    plan = _compile()
    assert store.save(plan).matrix_digest == store.save(plan).matrix_digest
    assert store.get(plan.matrix_id).matrix_digest == plan.matrix_digest
    assert tuple(item.matrix_id for item in store.list()) == (plan.matrix_id,)


def test_recompilation_is_idempotent_despite_a_later_compile_timestamp(tmp_path) -> None:
    store = LocalMatchedRunPlanStore(tmp_path)
    original = store.save(_compile())
    later = _compile(compiled_at=datetime(2016, 6, 2, tzinfo=timezone.utc))
    retained = store.save(later)
    assert retained.matrix_id == original.matrix_id
    assert retained.compiled_at == original.compiled_at


def test_authorization_is_part_of_plan_identity() -> None:
    assert _compile().matrix_id != _compile(external_model_authorized=True).matrix_id
