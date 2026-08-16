"""Compile matched B0/B1/A1 plans from saved Gold-backed Cases; never execute them."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from agent_treatment_runtime import MODEL_ID
from gold_case_runtime import RequestModel, gold_case_store
from historical_replay_runtime import PRECONFIGURED_CAPABILITIES
from risk_experiments import (
    ArchitectureConfig, ArchitectureTreatment, ExperimentalCapabilityPackage,
    IdentityCondition, LocalMatchedRunPlanStore, MatchedRunConflict, RunBudget,
    PerturbationCondition, compile_matched_run_matrix,
)


CONTEXT_POLICY = "observable-case-state-point-in-time-v1"


class MatchedRunCompileRequest(RequestModel):
    case_id: str = Field(min_length=3, max_length=160)
    capability_package_ids: tuple[str, ...] = Field(min_length=1, max_length=2)
    repetitions: int = Field(default=1, ge=1, le=3)
    identity_condition: IdentityCondition = IdentityCondition.NAMED_HISTORICAL
    authorize_external_model_calls: bool = False
    include_delayed_event_perturbation: bool = False


def matched_run_store() -> LocalMatchedRunPlanStore:
    return LocalMatchedRunPlanStore(gold_case_store().root)


def _packages() -> dict[str, ExperimentalCapabilityPackage]:
    by_id = {item.capability_id: item for item in PRECONFIGURED_CAPABILITIES}
    core_ids = (
        "event-relevance-classifier", "historical-replay-context",
        "portfolio-risk-metric-pack",
    )
    full = tuple(sorted(PRECONFIGURED_CAPABILITIES, key=lambda item: item.capability_id))
    core = tuple(by_id[item] for item in core_ids if item in by_id)
    return {
        "market-event-core": ExperimentalCapabilityPackage(
            package_id="market-event-core", version="1.0.0",
            display_name="Market and event context", capabilities=core,
        ),
        "full-selected": ExperimentalCapabilityPackage(
            package_id="full-selected", version="1.0.0",
            display_name="Full selected evidence", capabilities=full,
        ),
    }


def _treatments() -> tuple[ArchitectureTreatment, ...]:
    return (
        ArchitectureTreatment(
            treatment_id="B0",
            architecture=ArchitectureConfig(
                architecture_id="b0-deterministic-reference", architecture_type="deterministic",
                version="1.0.0", deterministic=True, interpretation_mode="fixed_rules",
            ), context_policy_reference=CONTEXT_POLICY,
            budget=RunBudget(max_model_calls=0, max_input_tokens=0, max_output_tokens=0,
                             max_cost_usd=0, max_processing_seconds=30),
        ),
        ArchitectureTreatment(
            treatment_id="B1",
            architecture=ArchitectureConfig(
                architecture_id="b1-single-synthesizer", architecture_type="single_agent",
                version="1.0.0", deterministic=False, model_reference=MODEL_ID,
                interpretation_mode="single_agent",
            ), prompt_reference="day3/b1-synthesizer-v1", model_reference=MODEL_ID,
            context_policy_reference=CONTEXT_POLICY,
            budget=RunBudget(max_model_calls=10, max_input_tokens=100_000,
                             max_output_tokens=20_000, max_cost_usd=2, max_processing_seconds=120),
        ),
        ArchitectureTreatment(
            treatment_id="A1",
            architecture=ArchitectureConfig(
                architecture_id="a1-specialist-graph", architecture_type="agent_graph",
                version="1.0.0", deterministic=False, model_reference=MODEL_ID,
                interpretation_mode="agent_graph",
            ), prompt_reference="day3/a1-four-role-graph-v1", model_reference=MODEL_ID,
            context_policy_reference=CONTEXT_POLICY,
            budget=RunBudget(max_model_calls=20, max_input_tokens=200_000,
                             max_output_tokens=40_000, max_cost_usd=4, max_processing_seconds=240),
        ),
    )


def _case_catalogue() -> list[dict[str, Any]]:
    references = {item.compiled_case_id: item for item in gold_case_store().list() if item.compiled_case_id}
    values = []
    for case in gold_case_store().list_cases():
        reference = references.get(case.case_id)
        values.append({
            "case_id": case.case_id,
            "experiment_id": case.experiment_id,
            "study_id": None if reference is None else reference.bundle.selection.study_id,
            "name": case.observable_state.portfolio_reference,
            "as_of": case.observable_state.as_of.date().isoformat(),
            "observations": len(case.observable_state.observation_ids),
            "data_truth": None if reference is None else reference.bundle.data_truth,
        })
    return values


def _plan_payload(plan: Any) -> dict[str, Any]:
    return {
        "matrix_id": plan.matrix_id,
        "case_id": plan.case_id,
        "experiment_id": plan.experiment_id,
        "identity_condition": plan.identity_condition.value,
        "status": plan.qualification_state,
        "execution_status": plan.execution_status,
        "projected": {
            "runs": plan.projected_run_count, "model_calls": plan.projected_model_calls,
            "input_tokens": plan.projected_input_tokens, "output_tokens": plan.projected_output_tokens,
            "max_cost_usd": plan.projected_max_cost_usd,
            "max_processing_seconds": plan.projected_max_processing_seconds,
        },
        "cells": [{
            "cell_id": item.cell_id, "architecture": item.treatment_id,
            "package": item.capability_package_id, "repetition": item.repetition,
            "perturbation": item.perturbation_condition.value,
            "model_calls": item.budget.max_model_calls,
            "max_cost_usd": item.budget.max_cost_usd,
        } for item in plan.cells],
        "boundary": "Compiled and saved only. No capability or model was invoked.",
    }


def matched_run_setup() -> dict[str, Any]:
    cases = _case_catalogue()
    packages = _packages()
    return {
        "ready": bool(cases),
        "blocker": None if cases else "Accept a Gold reference and compile its Case before planning Runs.",
        "cases": cases,
        "packages": [{
            "package_id": item.package_id, "name": item.display_name,
            "capability_count": len(item.capabilities),
        } for item in packages.values()],
        "architectures": [
            {"id": "B0", "name": "Deterministic baseline", "model_calls_per_run": 0},
            {"id": "B1", "name": "Single agent", "model_calls_per_run": 10},
            {"id": "A1", "name": "Agent graph", "model_calls_per_run": 20},
        ],
        "saved_plans": [_plan_payload(item) for item in matched_run_store().list()],
    }


def compile_matched_plan(request: MatchedRunCompileRequest) -> dict[str, Any]:
    case = gold_case_store().get_case(request.case_id)
    reference = next(
        (item for item in gold_case_store().list() if item.compiled_case_id == case.case_id), None,
    )
    if reference is None:
        raise MatchedRunConflict("the Case has no governed Gold-reference binding")
    registry = _packages()
    unknown = set(request.capability_package_ids) - set(registry)
    if unknown:
        raise MatchedRunConflict("unknown capability package: " + ", ".join(sorted(unknown)))
    package_ids = tuple(sorted(set(request.capability_package_ids)))
    if package_ids != request.capability_package_ids:
        raise MatchedRunConflict("capability packages must be unique and sorted")
    plan = compile_matched_run_matrix(
        case=case, study_id=reference.bundle.selection.study_id,
        experiment_id=case.experiment_id, treatments=_treatments(),
        capability_packages=tuple(registry[item] for item in package_ids),
        repetitions=request.repetitions, information_regime="point-in-time",
        identity_condition=request.identity_condition, seed="matched-run-seed-v1",
        external_model_authorized=request.authorize_external_model_calls,
        compiled_by="matched-run-compiler-v1", compiled_at=datetime.now(timezone.utc),
        perturbations=(
            PerturbationCondition.NONE,
            PerturbationCondition.DELAY_ADVERSE_EVENT_ONE_CYCLE,
        ) if request.include_delayed_event_perturbation else (PerturbationCondition.NONE,),
    )
    return {"saved": True, "plan": _plan_payload(matched_run_store().save(plan))}


def get_matched_plan(matrix_id: str) -> dict[str, Any]:
    return _plan_payload(matched_run_store().get(matrix_id))
