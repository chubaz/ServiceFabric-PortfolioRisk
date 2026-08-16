"""Compile matched, non-executing B0/B1/A1 run plans from one accepted Case.

The compiler is intentionally separate from replay execution.  It proves that
every planned cell receives the same architecture-neutral Case input while
architecture, capability package, repetition, and identity treatment remain
explicit experimental factors.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .hierarchy import ArchitectureConfig, ExperimentalCapabilityConfig, ExperimentalCase, RunInput
from .models import DIGEST, IDENTIFIER, FrozenModel, canonical_digest


class MatchedRunConflict(ValueError):
    pass


class MatchedRunNotFound(KeyError):
    pass


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("matched-run timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


class IdentityCondition(str, Enum):
    NAMED_HISTORICAL = "named_historical"
    ANONYMIZED_HISTORICAL = "anonymized_historical"


class PerturbationCondition(str, Enum):
    NONE = "none"
    DELAY_ADVERSE_EVENT_ONE_CYCLE = "delay_adverse_event_one_cycle"


class RunBudget(FrozenModel):
    max_model_calls: int = Field(ge=0, le=100)
    max_input_tokens: int = Field(ge=0, le=2_000_000)
    max_output_tokens: int = Field(ge=0, le=500_000)
    max_cost_usd: float = Field(ge=0, le=1000)
    max_processing_seconds: int = Field(ge=1, le=3600)

    @model_validator(mode="after")
    def no_cost_without_calls(self) -> "RunBudget":
        if self.max_model_calls == 0 and any((self.max_input_tokens, self.max_output_tokens, self.max_cost_usd)):
            raise ValueError("a zero-model-call budget cannot reserve model tokens or cost")
        if self.max_model_calls > 0 and not all((self.max_input_tokens, self.max_output_tokens, self.max_cost_usd)):
            raise ValueError("model treatments require bounded token and monetary budgets")
        return self


class ExperimentalCapabilityPackage(FrozenModel):
    package_id: str = Field(pattern=IDENTIFIER)
    version: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=3, max_length=200)
    capabilities: tuple[ExperimentalCapabilityConfig, ...] = Field(min_length=1)
    package_digest: str | None = Field(default=None, pattern=DIGEST)

    @model_validator(mode="after")
    def package_is_reconciled(self) -> "ExperimentalCapabilityPackage":
        ids = tuple(item.capability_id for item in self.capabilities)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("capability package contents must be unique and sorted")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"package_digest"}))
        if self.package_digest is not None and self.package_digest != expected:
            raise ValueError("package_digest does not match canonical content")
        object.__setattr__(self, "package_digest", expected)
        return self


class ArchitectureTreatment(FrozenModel):
    treatment_id: Literal["B0", "B1", "A1"]
    architecture: ArchitectureConfig
    prompt_reference: str | None = Field(default=None, max_length=300)
    model_reference: str | None = Field(default=None, max_length=300)
    context_policy_reference: str = Field(min_length=3, max_length=300)
    memory_policy: Literal["cleared_each_run", "bounded_case_memory"] = "cleared_each_run"
    budget: RunBudget

    @model_validator(mode="after")
    def treatment_matches_architecture(self) -> "ArchitectureTreatment":
        expected_type = {"B0": "deterministic", "B1": "single_agent", "A1": "agent_graph"}[self.treatment_id]
        if self.architecture.architecture_type != expected_type:
            raise ValueError("architecture type does not match the declared treatment")
        if self.treatment_id == "B0":
            if self.prompt_reference is not None or self.model_reference is not None or self.budget.max_model_calls != 0:
                raise ValueError("B0 cannot carry a model, prompt, or model-call budget")
        elif not (self.prompt_reference and self.model_reference and self.budget.max_model_calls > 0):
            raise ValueError("agent treatments require exact model, prompt, and call-budget references")
        if self.architecture.model_reference != self.model_reference:
            raise ValueError("treatment and ArchitectureConfig model references must match")
        return self


class MatchedRunCell(FrozenModel):
    cell_id: str = Field(pattern=IDENTIFIER)
    case_digest: str = Field(pattern=DIGEST)
    treatment_id: Literal["B0", "B1", "A1"]
    capability_package_id: str = Field(pattern=IDENTIFIER)
    capability_package_digest: str = Field(pattern=DIGEST)
    repetition: int = Field(ge=1, le=20)
    seed: str = Field(min_length=1, max_length=200)
    identity_condition: IdentityCondition
    perturbation_condition: PerturbationCondition = PerturbationCondition.NONE
    run_input: RunInput
    architecture: ArchitectureConfig
    prompt_reference: str | None = Field(default=None, max_length=300)
    model_reference: str | None = Field(default=None, max_length=300)
    context_policy_reference: str = Field(min_length=3, max_length=300)
    memory_policy: Literal["cleared_each_run", "bounded_case_memory"]
    budget: RunBudget

    @model_validator(mode="after")
    def cell_is_bound(self) -> "MatchedRunCell":
        if self.run_input.architecture_id != self.architecture.architecture_id:
            raise ValueError("cell RunInput and architecture identity must match")
        if self.architecture.model_reference != self.model_reference:
            raise ValueError("cell model identity must match ArchitectureConfig")
        if self.treatment_id == "B0" and any(
            item.implementation_class == "generative" or item.parameterization == "adaptive"
            for item in self.run_input.capability_configurations
        ):
            raise ValueError("B0 cannot use generative or adaptively parameterized capabilities")
        return self


class MatchedRunMatrixPlan(FrozenModel):
    schema_version: Literal["portfolio-risk.matched-run-matrix/v1"] = "portfolio-risk.matched-run-matrix/v1"
    matrix_id: str = Field(pattern=IDENTIFIER)
    study_id: str = Field(pattern=IDENTIFIER)
    experiment_id: str = Field(pattern=IDENTIFIER)
    case_id: str = Field(pattern=IDENTIFIER)
    case_digest: str = Field(pattern=DIGEST)
    information_regime: str = Field(pattern=IDENTIFIER)
    identity_condition: IdentityCondition
    variable_factors: tuple[
        Literal["architecture", "capability_package", "perturbation", "repetition"], ...
    ]
    controlled_factors: tuple[str, ...] = Field(min_length=1)
    cells: tuple[MatchedRunCell, ...] = Field(min_length=3, max_length=120)
    projected_run_count: int = Field(ge=3, le=120)
    projected_model_calls: int = Field(ge=0)
    projected_input_tokens: int = Field(ge=0)
    projected_output_tokens: int = Field(ge=0)
    projected_max_cost_usd: float = Field(ge=0)
    projected_max_processing_seconds: int = Field(ge=1)
    external_model_authorized: bool
    qualification_state: Literal["ready", "requires_model_authorization"]
    architecture_access_to_gold: Literal[False] = False
    execution_status: Literal["not_started"] = "not_started"
    compiled_by: str = Field(min_length=2, max_length=120)
    compiled_at: datetime
    matrix_digest: str | None = Field(default=None, pattern=DIGEST)

    _compiled_at = field_validator("compiled_at")(_utc)

    @model_validator(mode="after")
    def matrix_is_matched(self) -> "MatchedRunMatrixPlan":
        if self.variable_factors != tuple(sorted(set(self.variable_factors))):
            raise ValueError("variable factors must be unique and sorted")
        if self.controlled_factors != tuple(sorted(set(self.controlled_factors))):
            raise ValueError("controlled factors must be unique and sorted")
        if self.projected_run_count != len(self.cells):
            raise ValueError("projected run count must match matrix cells")
        if {item.treatment_id for item in self.cells} != {"B0", "B1", "A1"}:
            raise ValueError("the initial matched matrix requires B0, B1 and A1")
        if any(item.case_digest != self.case_digest or item.run_input.case_id != self.case_id for item in self.cells):
            raise ValueError("every cell must bind to the exact same Case")
        observable_inputs = {
            canonical_digest({
                "case_id": item.run_input.case_id,
                "information_regime": item.run_input.information_regime,
                "observation_ids": item.run_input.observation_ids,
                "identity_condition": item.identity_condition.value,
            })
            for item in self.cells
        }
        if len(observable_inputs) != 1:
            raise ValueError("matched cells must receive the same observable Case input")
        expected_authorization_state = "ready" if self.external_model_authorized else "requires_model_authorization"
        if self.qualification_state != expected_authorization_state:
            raise ValueError("qualification state must reflect external-model authorization")
        totals = (
            sum(item.budget.max_model_calls for item in self.cells),
            sum(item.budget.max_input_tokens for item in self.cells),
            sum(item.budget.max_output_tokens for item in self.cells),
            round(sum(item.budget.max_cost_usd for item in self.cells), 6),
            sum(item.budget.max_processing_seconds for item in self.cells),
        )
        declared = (
            self.projected_model_calls,
            self.projected_input_tokens,
            self.projected_output_tokens,
            round(self.projected_max_cost_usd, 6),
            self.projected_max_processing_seconds,
        )
        if totals != declared:
            raise ValueError("projected resource bounds must reconcile to matrix cells")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"matrix_digest"}))
        if self.matrix_digest is not None and self.matrix_digest != expected:
            raise ValueError("matrix_digest does not match canonical content")
        object.__setattr__(self, "matrix_digest", expected)
        return self


def compile_matched_run_matrix(
    *,
    case: ExperimentalCase,
    study_id: str,
    experiment_id: str,
    treatments: tuple[ArchitectureTreatment, ...],
    capability_packages: tuple[ExperimentalCapabilityPackage, ...],
    repetitions: int,
    information_regime: str,
    identity_condition: IdentityCondition,
    seed: str,
    external_model_authorized: bool,
    compiled_by: str,
    compiled_at: datetime,
    perturbations: tuple[PerturbationCondition, ...] = (PerturbationCondition.NONE,),
) -> MatchedRunMatrixPlan:
    """Compile a reviewable plan; never invoke a capability or model."""

    if case.evaluation_state.label_state != "admitted" or not case.evaluation_state.reference_label_ids:
        raise MatchedRunConflict("the saved Case requires an admitted evaluation reference")
    if case.evaluation_state.architecture_access is not False:
        raise MatchedRunConflict("Gold evaluation state must remain unreachable by architectures")
    if case.experiment_id != experiment_id:
        raise MatchedRunConflict("the Case and planned Experiment identities must match")
    if repetitions < 1 or repetitions > 20:
        raise MatchedRunConflict("repetitions must be between 1 and 20")
    treatment_ids = tuple(item.treatment_id for item in treatments)
    if treatment_ids != ("B0", "B1", "A1"):
        raise MatchedRunConflict("treatments must be B0, B1 and A1 in that order")
    if not capability_packages:
        raise MatchedRunConflict("at least one versioned capability package is required")
    if len({item.package_id for item in capability_packages}) != len(capability_packages):
        raise MatchedRunConflict("capability package identities must be unique")
    if not perturbations or perturbations[0] is not PerturbationCondition.NONE:
        raise MatchedRunConflict("the unperturbed control must be the first perturbation condition")
    if len(set(perturbations)) != len(perturbations):
        raise MatchedRunConflict("perturbation conditions must be unique")

    cells = []
    for package in capability_packages:
        capability_ids = tuple(item.capability_id for item in package.capabilities)
        for perturbation in perturbations:
            for repetition in range(1, repetitions + 1):
                for treatment in treatments:
                    if treatment.treatment_id == "B0" and any(
                        item.implementation_class == "generative" or item.parameterization == "adaptive"
                        for item in package.capabilities
                    ):
                        raise MatchedRunConflict("B0 cannot be compiled with generative or adaptive capabilities")
                    identity = canonical_digest({
                        "case": case.context_digest,
                        "treatment": treatment.treatment_id,
                        "package": package.package_digest,
                        "perturbation": perturbation.value,
                        "repetition": repetition,
                        "seed": seed,
                        "identity_condition": identity_condition.value,
                    })
                    cells.append(MatchedRunCell(
                        cell_id=f"matched-cell-{identity[7:31]}",
                        case_digest=case.context_digest,
                        treatment_id=treatment.treatment_id,
                        capability_package_id=package.package_id,
                        capability_package_digest=package.package_digest,
                        repetition=repetition,
                        seed=f"{seed}:{perturbation.value}:{repetition}",
                        identity_condition=identity_condition,
                        perturbation_condition=perturbation,
                        run_input=RunInput(
                            case_id=case.case_id,
                            architecture_id=treatment.architecture.architecture_id,
                            information_regime=information_regime,
                            capability_references=capability_ids,
                            capability_configurations=package.capabilities,
                            repetition=repetition,
                            observation_ids=case.observable_state.observation_ids,
                        ),
                        architecture=treatment.architecture,
                        prompt_reference=treatment.prompt_reference,
                        model_reference=treatment.model_reference,
                        context_policy_reference=treatment.context_policy_reference,
                        memory_policy=treatment.memory_policy,
                        budget=treatment.budget,
                    ))
    identity = canonical_digest({
        "case": case.context_digest,
        "study": study_id,
        "experiment": experiment_id,
        "cells": [item.cell_id for item in cells],
        "information_regime": information_regime,
        "identity_condition": identity_condition.value,
        "perturbations": [item.value for item in perturbations],
        "external_model_authorized": external_model_authorized,
    })
    return MatchedRunMatrixPlan(
        matrix_id=f"matched-matrix-{identity[7:31]}",
        study_id=study_id,
        experiment_id=experiment_id,
        case_id=case.case_id,
        case_digest=case.context_digest,
        information_regime=information_regime,
        identity_condition=identity_condition,
        variable_factors=tuple(sorted((
            "architecture", "capability_package", "repetition",
            *(("perturbation",) if len(perturbations) > 1 else ()),
        ))),
        controlled_factors=tuple(sorted((
            "case_observable_state", "context_policy", "data_revisions", "evaluation_reference",
            "information_regime", "mandate_version", "portfolio_quantities", "temporal_boundary",
        ))),
        cells=tuple(cells),
        projected_run_count=len(cells),
        projected_model_calls=sum(item.budget.max_model_calls for item in cells),
        projected_input_tokens=sum(item.budget.max_input_tokens for item in cells),
        projected_output_tokens=sum(item.budget.max_output_tokens for item in cells),
        projected_max_cost_usd=round(sum(item.budget.max_cost_usd for item in cells), 6),
        projected_max_processing_seconds=sum(item.budget.max_processing_seconds for item in cells),
        external_model_authorized=external_model_authorized,
        qualification_state="ready" if external_model_authorized else "requires_model_authorization",
        compiled_by=compiled_by,
        compiled_at=compiled_at,
    )


class LocalMatchedRunPlanStore:
    """Immutable local plan repository; execution records live elsewhere."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().absolute()
        self.plans = self.root / "matched-run-plans"
        self._thread_lock = threading.RLock()

    @staticmethod
    def _key(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def _ensure_root(self) -> None:
        current = Path(self.root.anchor)
        for part in self.root.parts[1:]:
            current /= part
            if os.path.lexists(current) and current.is_symlink():
                raise MatchedRunConflict("matched-run storage path may not contain symbolic links")
        self.plans.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.plans.is_symlink() or not self.plans.resolve().is_relative_to(self.root.resolve()):
            raise MatchedRunConflict("matched-run storage must remain beneath its configured root")

    @contextmanager
    def _lock(self):  # type: ignore[no-untyped-def]
        with self._thread_lock:
            self._ensure_root()
            flags = os.O_RDWR | os.O_CREAT
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(self.root / ".matched-runs.lock", flags, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    def _path(self, matrix_id: str) -> Path:
        return self.plans / f"{self._key(matrix_id)}.json"

    def save(self, plan: MatchedRunMatrixPlan) -> MatchedRunMatrixPlan:
        with self._lock():
            path = self._path(plan.matrix_id)
            if path.exists():
                existing = MatchedRunMatrixPlan.model_validate_json(path.read_text(encoding="utf-8"))
                if existing.matrix_digest == plan.matrix_digest:
                    return existing
                existing_semantics = existing.model_dump(
                    mode="json", exclude={"compiled_at", "matrix_digest"},
                )
                candidate_semantics = plan.model_dump(
                    mode="json", exclude={"compiled_at", "matrix_digest"},
                )
                if existing_semantics == candidate_semantics:
                    return existing
                raise MatchedRunConflict("matrix identity already exists with different content")
            descriptor, temporary = tempfile.mkstemp(prefix=".matrix-", suffix=".json", dir=path.parent)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    json.dump(plan.model_dump(mode="json"), handle, sort_keys=True, separators=(",", ":"))
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(temporary, 0o600)
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            return plan

    def get(self, matrix_id: str) -> MatchedRunMatrixPlan:
        with self._lock():
            path = self._path(matrix_id)
            if not path.exists():
                raise MatchedRunNotFound(matrix_id)
            if path.is_symlink():
                raise MatchedRunConflict("matched-run plan may not be a symbolic link")
            return MatchedRunMatrixPlan.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> tuple[MatchedRunMatrixPlan, ...]:
        with self._lock():
            values = [
                MatchedRunMatrixPlan.model_validate_json(path.read_text(encoding="utf-8"))
                for path in self.plans.glob("*.json")
                if not path.is_symlink()
            ]
            return tuple(sorted(values, key=lambda item: item.compiled_at, reverse=True))
