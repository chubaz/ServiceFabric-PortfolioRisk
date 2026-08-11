"""Immutable scientific identities for thesis-ready experiment comparison."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator
from risk_registry import AssetKind, RegistryIdentity

from .models import DIGEST, IDENTIFIER, FrozenModel, canonical_digest


VERSION = r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$"


class MetricDirection(StrEnum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    CLOSER_TO_TARGET = "closer_to_target"
    DESCRIPTIVE = "descriptive"


class ScientificDefinition(FrozenModel):
    kind: str
    namespace: str = Field(pattern=IDENTIFIER)
    definition_id: str = Field(pattern=IDENTIFIER)
    version: str = Field(pattern=VERSION)
    name: str = Field(min_length=3, max_length=200)
    definition_digest: str | None = Field(default=None, pattern=DIGEST)

    @property
    def reference(self) -> str:
        return (
            f"{self.kind}:{self.namespace}:{self.definition_id}@{self.version}"
            f"#{self.definition_digest}"
        )

    @model_validator(mode="after")
    def bind_definition_digest(self) -> "ScientificDefinition":
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"definition_digest"})
        )
        if self.definition_digest is not None and self.definition_digest != expected:
            raise ValueError("definition_digest does not match canonical content")
        object.__setattr__(self, "definition_digest", expected)
        return self


class ResearchQuestionDefinition(ScientificDefinition):
    kind: Literal["research_question"] = "research_question"
    question: str = Field(min_length=10, max_length=1200)
    population: str = Field(min_length=3, max_length=500)
    unit_of_analysis: str = Field(min_length=3, max_length=300)
    intervention: str = Field(min_length=3, max_length=500)
    comparator: str = Field(min_length=3, max_length=500)
    estimand: str = Field(min_length=3, max_length=500)


class HypothesisDefinition(ScientificDefinition):
    kind: Literal["hypothesis"] = "hypothesis"
    research_question_reference: str = Field(min_length=20, max_length=1000)
    statement: str = Field(min_length=10, max_length=1200)
    expected_direction: str = Field(min_length=3, max_length=300)
    falsification_condition: str = Field(min_length=3, max_length=500)


class BaselineDefinition(ScientificDefinition):
    kind: Literal["baseline"] = "baseline"
    step_id: str = Field(pattern=IDENTIFIER)
    comparator_kind: Literal[
        "deterministic",
        "heuristic",
        "single_agent",
        "multi_agent",
        "human",
        "other",
    ]
    behaviour: str = Field(min_length=3, max_length=1000)
    resource_references: tuple[str, ...] = Field(default=(), max_length=100)

    @field_validator("resource_references")
    @classmethod
    def resources_are_unique_and_sorted(
        cls, value: tuple[str, ...]
    ) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("baseline resource references must be unique and sorted")
        return value


class InformationRegimeDefinition(ScientificDefinition):
    kind: Literal["information_regime"] = "information_regime"
    evidence_categories: tuple[str, ...] = Field(min_length=1, max_length=100)
    resource_references: tuple[str, ...] = Field(default=(), max_length=200)
    unavailable_information_rule: Literal["remain_missing"] = "remain_missing"
    disclosure_rule: Literal["disclose_reachable_and_used"] = (
        "disclose_reachable_and_used"
    )

    @field_validator("evidence_categories", "resource_references")
    @classmethod
    def values_are_unique_and_sorted(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("information-regime values must be unique and sorted")
        return value


class RiskOutcomeState(FrozenModel):
    state_id: str = Field(pattern=IDENTIFIER)
    ordinal: int = Field(ge=0, le=20)
    label: str = Field(min_length=1, max_length=120)
    criterion: str = Field(min_length=3, max_length=800)
    is_breach: bool = False


class RiskOutcomeDefinition(ScientificDefinition):
    kind: Literal["risk_outcome"] = "risk_outcome"
    unit_of_analysis: str = Field(min_length=3, max_length=300)
    observation_horizon_seconds: int = Field(ge=1, le=315_576_000)
    states: tuple[RiskOutcomeState, ...] = Field(min_length=2, max_length=21)
    mitigation_rule: str = Field(min_length=3, max_length=800)
    censoring_rule: str = Field(min_length=3, max_length=800)

    @field_validator("states")
    @classmethod
    def states_form_an_ordered_scale(
        cls, value: tuple[RiskOutcomeState, ...]
    ) -> tuple[RiskOutcomeState, ...]:
        ids = [item.state_id for item in value]
        ordinals = [item.ordinal for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("risk outcome state IDs must be unique")
        if ordinals != list(range(len(value))):
            raise ValueError("risk outcome ordinals must be contiguous from zero")
        if not any(item.is_breach for item in value):
            raise ValueError("risk outcome scale must identify at least one breach state")
        return value


class MetricDefinition(ScientificDefinition):
    kind: Literal["metric"] = "metric"
    risk_outcome_reference: str = Field(min_length=20, max_length=1000)
    estimand: str = Field(min_length=3, max_length=500)
    formula: str = Field(min_length=3, max_length=1200)
    aggregation: str = Field(min_length=3, max_length=500)
    direction: MetricDirection
    missingness_rule: str = Field(min_length=3, max_length=500)
    uncertainty_rule: str = Field(min_length=3, max_length=500)


class ScientificDesignPack(FrozenModel):
    schema_version: Literal["portfolio-risk.scientific-design-pack/v1"] = (
        "portfolio-risk.scientific-design-pack/v1"
    )
    namespace: str = Field(pattern=IDENTIFIER)
    pack_id: str = Field(pattern=IDENTIFIER)
    version: str = Field(pattern=VERSION)
    name: str = Field(min_length=3, max_length=200)
    owner: str = Field(pattern=IDENTIFIER)
    research_question: ResearchQuestionDefinition
    hypothesis: HypothesisDefinition
    baseline: BaselineDefinition
    information_regime: InformationRegimeDefinition
    risk_outcome: RiskOutcomeDefinition
    metric: MetricDefinition
    pack_digest: str | None = Field(default=None, pattern=DIGEST)

    @property
    def registry_identity(self) -> RegistryIdentity:
        return RegistryIdentity(
            kind=AssetKind.SCIENTIFIC_DESIGN,
            namespace=self.namespace,
            asset_id=self.pack_id,
            version=self.version,
        )

    @property
    def reference(self) -> str:
        return f"{self.registry_identity.reference}#{self.pack_digest}"

    def comparison_identity(self) -> dict[str, str]:
        return {
            "baseline_step": self.baseline.reference,
            "information_regime": self.information_regime.reference,
            "metric_definition": self.metric.reference,
            "research_question": self.research_question.reference,
            "risk_outcome_definition": self.risk_outcome.reference,
        }

    @model_validator(mode="after")
    def bind_pack(self) -> "ScientificDesignPack":
        if self.hypothesis.research_question_reference != self.research_question.reference:
            raise ValueError("hypothesis must reference the pack research question")
        if self.metric.risk_outcome_reference != self.risk_outcome.reference:
            raise ValueError("metric must reference the pack risk outcome")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"pack_digest"}))
        if self.pack_digest is not None and self.pack_digest != expected:
            raise ValueError("pack_digest does not match canonical content")
        object.__setattr__(self, "pack_digest", expected)
        return self
