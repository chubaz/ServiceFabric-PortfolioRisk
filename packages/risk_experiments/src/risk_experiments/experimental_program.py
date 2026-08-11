"""P9-P11 contracts for arms, label admission, and repeatable run matrices."""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import product
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .fixture_context import FixtureContext
from .models import DIGEST, IDENTIFIER, FrozenModel, canonical_digest


class ExperimentCase(FrozenModel):
    case_id: str = Field(pattern=IDENTIFIER)
    portfolio_reference: str = Field(min_length=20, max_length=1000)
    window_id: str = Field(pattern=IDENTIFIER)
    as_of: datetime
    context_digest: str = Field(pattern=DIGEST)

    @field_validator("as_of")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("case as_of must be timezone-aware")
        return value.astimezone(timezone.utc)


class ExperimentalArm(FrozenModel):
    arm_id: Literal["b0", "a1"]
    role: Literal["baseline", "treatment"]
    name: str
    processing_reference: str
    information_regime_reference: str
    deterministic: bool


class QualificationIssue(FrozenModel):
    issue_id: str = Field(pattern=IDENTIFIER)
    area: Literal["fixture", "processing", "labels", "evaluation"]
    message: str = Field(min_length=10, max_length=1200)
    resolution: str = Field(min_length=10, max_length=1200)


class ArmRunPlan(FrozenModel):
    schema_version: Literal["portfolio-risk.arm-run-plan/v1"] = "portfolio-risk.arm-run-plan/v1"
    fixture_context_digest: str = Field(pattern=DIGEST)
    cases: tuple[ExperimentCase, ...] = Field(min_length=1)
    arms: tuple[ExperimentalArm, ...] = Field(min_length=2, max_length=2)
    expected_outputs: int = Field(ge=1)
    executable: bool
    blockers: tuple[QualificationIssue, ...] = ()
    plan_digest: str | None = Field(default=None, pattern=DIGEST)

    @model_validator(mode="after")
    def validate_plan(self) -> "ArmRunPlan":
        if self.expected_outputs != len(self.cases) * len(self.arms):
            raise ValueError("expected_outputs must equal cases multiplied by arms")
        if self.executable == bool(self.blockers):
            raise ValueError("executable plans have no blockers; blocked plans require blockers")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"plan_digest"}))
        if self.plan_digest is not None and self.plan_digest != expected:
            raise ValueError("plan_digest does not match canonical content")
        object.__setattr__(self, "plan_digest", expected)
        return self


class LabelReviewGate(FrozenModel):
    schema_version: Literal["portfolio-risk.label-review-gate/v1"] = "portfolio-risk.label-review-gate/v1"
    outcome_reference: str
    expected_case_ids: tuple[str, ...] = Field(min_length=1)
    required_states: tuple[Literal["optimal", "good", "bad", "very_bad"], ...]
    status: Literal["awaiting_independent_review", "admitted"]
    admitted_label_set_digest: str | None = Field(default=None, pattern=DIGEST)
    reviewer: str | None = None
    labels_reachable_by_processing: Literal[False] = False

    @model_validator(mode="after")
    def admitted_requires_review(self) -> "LabelReviewGate":
        if self.status == "admitted" and not (self.admitted_label_set_digest and self.reviewer):
            raise ValueError("admitted labels require an exact digest and reviewer")
        if self.status != "admitted" and (self.admitted_label_set_digest or self.reviewer):
            raise ValueError("unreviewed labels cannot carry admission fields")
        return self


class MatrixCell(FrozenModel):
    cell_id: str = Field(pattern=IDENTIFIER)
    arm_id: Literal["b0", "a1"]
    information_regime_reference: str
    repetition: int = Field(ge=0, le=100)
    case_count: int = Field(ge=1)


class ExperimentMatrixPlan(FrozenModel):
    schema_version: Literal["portfolio-risk.experiment-matrix/v1"] = "portfolio-risk.experiment-matrix/v1"
    fixture_context_digest: str = Field(pattern=DIGEST)
    cells: tuple[MatrixCell, ...] = Field(min_length=1)
    planned_observations: int = Field(ge=1)
    execution_status: Literal["blocked", "ready"]
    blockers: tuple[QualificationIssue, ...] = ()
    matrix_digest: str | None = Field(default=None, pattern=DIGEST)

    @model_validator(mode="after")
    def bind_matrix(self) -> "ExperimentMatrixPlan":
        if self.planned_observations != sum(item.case_count for item in self.cells):
            raise ValueError("planned_observations must equal the cell case counts")
        if (self.execution_status == "ready") == bool(self.blockers):
            raise ValueError("ready matrices have no blockers; blocked matrices require blockers")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"matrix_digest"}))
        if self.matrix_digest is not None and self.matrix_digest != expected:
            raise ValueError("matrix_digest does not match canonical content")
        object.__setattr__(self, "matrix_digest", expected)
        return self


def compile_arm_plan(context: FixtureContext, review_dates: tuple[datetime, ...]) -> ArmRunPlan:
    portfolio = context.object_set.portfolio_governance.portfolio
    scenario = context.object_set.world_context.scenario
    regime = context.object_set.scientific_design.information_regime.reference
    cases = tuple(
        ExperimentCase(
            case_id=f"diversified-{value.strftime('%Y%m%d')}",
            portfolio_reference=portfolio.reference,
            window_id=("stress-a" if value.month == 4 else "stress-b" if value.month == 5 else "control"),
            as_of=value,
            context_digest=canonical_digest({"fixture": context.fixture_context_digest, "portfolio": portfolio.reference, "as_of": value.isoformat(), "scenario": scenario.reference}),
        )
        for value in review_dates
    )
    issues = (
        QualificationIssue(
            issue_id="point-in-time-prices-unbound",
            area="fixture",
            message="The accepted pricing binding resolves to provider-pricing metadata, not case-level point-in-time market observations.",
            resolution="Create and review a new Fixture version that binds the exact synthetic market dataset bytes and availability rule.",
        ),
        QualificationIssue(
            issue_id="processing-identities-unqualified",
            area="processing",
            message="The agent, graph and workflow identities are declared but have not been qualified together as this treatment executor.",
            resolution="Register and fixture-test the exact A1 processing chain before enabling treatment output generation.",
        ),
    )
    arms = (
        ExperimentalArm(arm_id="b0", role="baseline", name=context.object_set.scientific_design.baseline.name, processing_reference=context.object_set.scientific_design.baseline.reference, information_regime_reference=regime, deterministic=True),
        ExperimentalArm(arm_id="a1", role="treatment", name="Structured single-agent treatment", processing_reference=context.object_set.authority_envelope.processing.reference, information_regime_reference=regime, deterministic=True),
    )
    return ArmRunPlan(fixture_context_digest=context.fixture_context_digest, cases=cases, arms=arms, expected_outputs=len(cases) * len(arms), executable=False, blockers=issues)


def compile_label_gate(context: FixtureContext, plan: ArmRunPlan) -> LabelReviewGate:
    return LabelReviewGate(
        outcome_reference=context.object_set.scientific_design.risk_outcome.reference,
        expected_case_ids=tuple(item.case_id for item in plan.cases),
        required_states=("optimal", "good", "bad", "very_bad"),
        status="awaiting_independent_review",
    )


def compile_matrix(context: FixtureContext, plan: ArmRunPlan, *, repeats: int = 2) -> ExperimentMatrixPlan:
    regimes = (context.object_set.scientific_design.information_regime.reference,)
    cells = tuple(
        MatrixCell(cell_id=f"{arm.arm_id}-ir1-r{repetition}", arm_id=arm.arm_id, information_regime_reference=regime, repetition=repetition, case_count=len(plan.cases))
        for arm, regime, repetition in product(plan.arms, regimes, range(repeats))
    )
    return ExperimentMatrixPlan(
        fixture_context_digest=context.fixture_context_digest,
        cells=cells,
        planned_observations=sum(item.case_count for item in cells),
        execution_status="blocked" if plan.blockers else "ready",
        blockers=plan.blockers,
    )
