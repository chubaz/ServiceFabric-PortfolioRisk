"""Canonical experimental hierarchy and execution-result contracts.

Study -> Experiment -> Case -> Run is the ownership hierarchy. Regime labels
classify Cases across experiments. ArchitectureOutput is immutable scientific
output; reports are downstream renderings and never evaluation inputs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .models import DIGEST, IDENTIFIER, FrozenModel, canonical_digest
from .replay_scheduler import ReplayProcessingReceipt


EVALUATION_DIMENSION_IDS = (
    "confidence_calibration",
    "decision_quality",
    "detection_quality",
    "efficiency",
    "evidence_quality",
    "robustness",
    "severity_understanding",
    "stability",
    "timeliness",
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("experimental timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


class StudyDefinition(FrozenModel):
    study_id: str = Field(pattern=IDENTIFIER)
    title: str = Field(min_length=3, max_length=300)
    research_programme: str = Field(min_length=10, max_length=2000)


class ResearchExperimentDefinition(FrozenModel):
    experiment_id: str = Field(pattern=IDENTIFIER)
    study_id: str = Field(pattern=IDENTIFIER)
    research_question: str = Field(min_length=10, max_length=2000)
    hypothesis: str = Field(min_length=10, max_length=2000)
    controlled_factors: tuple[str, ...]
    variable_factors: tuple[str, ...]
    evaluation_dimensions: tuple[str, ...] = Field(min_length=1)

    @field_validator("controlled_factors", "variable_factors")
    @classmethod
    def factors_are_unique_sorted(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("experiment factors must be unique and sorted")
        return value

    @field_validator("evaluation_dimensions")
    @classmethod
    def dimensions_are_complete(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("experiment dimensions must be unique and sorted")
        if value != EVALUATION_DIMENSION_IDS:
            raise ValueError("portfolio-risk experiments require the complete nine-dimension framework")
        return value


class RegimeLabel(FrozenModel):
    dimension: Literal["volatility", "market_direction", "liquidity", "event", "sector"]
    value: str = Field(pattern=IDENTIFIER)
    method: Literal["deterministic_market_data"] = "deterministic_market_data"
    evidence_ids: tuple[str, ...] = Field(min_length=1)


class ObservableCaseState(FrozenModel):
    portfolio_reference: str = Field(min_length=3, max_length=1000)
    mandate_reference: str = Field(min_length=20, max_length=1000)
    risk_policy_reference: str = Field(min_length=20, max_length=1000)
    data_references: tuple[str, ...] = Field(min_length=1)
    observation_ids: tuple[str, ...]
    as_of: datetime

    _as_of = field_validator("as_of")(_utc)


class CaseEvaluationState(FrozenModel):
    evaluation_horizon_end: datetime
    label_state: Literal["not_admitted", "admitted"] = "not_admitted"
    reference_label_ids: tuple[str, ...] = ()
    outcome_observation_ids: tuple[str, ...] = ()
    regimes: tuple[RegimeLabel, ...] = ()
    architecture_access: Literal[False] = False

    _horizon = field_validator("evaluation_horizon_end")(_utc)


class ExperimentalCase(FrozenModel):
    case_id: str = Field(pattern=IDENTIFIER)
    experiment_id: str = Field(pattern=IDENTIFIER)
    observable_state: ObservableCaseState
    evaluation_state: CaseEvaluationState
    context_digest: str | None = Field(default=None, pattern=DIGEST)

    @model_validator(mode="after")
    def bind_digest(self) -> "ExperimentalCase":
        expected = canonical_digest(self.model_dump(mode="json", exclude={"context_digest"}))
        if self.context_digest is not None and self.context_digest != expected:
            raise ValueError("case context_digest does not match canonical content")
        object.__setattr__(self, "context_digest", expected)
        return self


class ExperimentalCapabilityConfig(FrozenModel):
    """One capability as admitted to an experimental architecture.

    Preconfigured parameters are frozen before the Case is executed. Adaptive
    parameters are selected by an agent during execution and are therefore not
    available to the deterministic B0 architecture. Evaluation roles make the
    measurement dependency explicit instead of hiding it in evaluator code.
    """

    capability_id: str = Field(pattern=IDENTIFIER)
    version: str = Field(min_length=1, max_length=128)
    implementation_class: Literal["deterministic", "statistical", "generative"]
    parameterization: Literal["preconfigured", "adaptive"]
    evaluation_roles: tuple[Literal["architecture_input", "reference_label", "measurement"] , ...] = Field(min_length=1)
    parameter_digest: str | None = Field(default=None, pattern=DIGEST)
    selector_agent_id: str | None = Field(default=None, pattern=IDENTIFIER)
    comparable_across_architectures: bool = True
    effects: tuple[str, ...] = ()

    @model_validator(mode="after")
    def experimental_boundary_is_explicit(self) -> "ExperimentalCapabilityConfig":
        if len(self.evaluation_roles) != len(set(self.evaluation_roles)):
            raise ValueError("experimental capability evaluation roles must be unique")
        if self.effects:
            raise ValueError("thesis evaluation capabilities must be effect-free")
        if self.parameterization == "preconfigured":
            if self.parameter_digest is None or self.selector_agent_id is not None:
                raise ValueError("preconfigured capabilities require frozen parameters and no selector agent")
        elif self.selector_agent_id is None:
            raise ValueError("adaptive capabilities require the selecting agent identity")
        if "reference_label" in self.evaluation_roles and not self.comparable_across_architectures:
            raise ValueError("reference-label capabilities must be comparable across architectures")
        return self


class RunInput(FrozenModel):
    case_id: str = Field(pattern=IDENTIFIER)
    architecture_id: str = Field(pattern=IDENTIFIER)
    information_regime: str = Field(pattern=IDENTIFIER)
    capability_references: tuple[str, ...]
    capability_configurations: tuple[ExperimentalCapabilityConfig, ...] = ()
    repetition: int = Field(ge=1, le=100)
    observation_ids: tuple[str, ...]

    @model_validator(mode="after")
    def capability_references_are_bound(self) -> "RunInput":
        configured = tuple(item.capability_id for item in self.capability_configurations)
        if len(configured) != len(set(configured)):
            raise ValueError("RunInput capability configurations must be unique")
        if configured and set(configured) != set(self.capability_references):
            raise ValueError("every RunInput capability reference requires one experimental configuration")
        return self


class ArchitectureConfig(FrozenModel):
    architecture_id: str = Field(pattern=IDENTIFIER)
    architecture_type: Literal["deterministic", "single_agent", "agent_graph", "multi_agent"]
    version: str = Field(min_length=1, max_length=128)
    deterministic: bool
    model_reference: str | None = Field(default=None, max_length=300)
    interpretation_mode: Literal["fixed_rules", "single_agent", "agent_graph"] = "fixed_rules"
    context_contract_version: str = Field(default="1.0.0", min_length=1, max_length=128)

    @model_validator(mode="after")
    def execution_mode_matches_architecture(self) -> "ArchitectureConfig":
        expected = {
            "deterministic": "fixed_rules",
            "single_agent": "single_agent",
            "agent_graph": "agent_graph",
            "multi_agent": "agent_graph",
        }[self.architecture_type]
        if self.interpretation_mode != expected:
            raise ValueError("interpretation_mode must match architecture_type")
        if self.deterministic != (self.architecture_type == "deterministic"):
            raise ValueError("only the deterministic architecture type may declare deterministic execution")
        return self


class MetricSpecification(FrozenModel):
    metric_id: str = Field(pattern=IDENTIFIER)
    label: str = Field(min_length=2, max_length=200)
    formula: str = Field(min_length=3, max_length=1200)
    unit: str = Field(pattern=IDENTIFIER)
    history_policy: Literal["instrument_lifetime_to_as_of", "point_in_time"]
    adjustment_policy: str = Field(min_length=3, max_length=500)
    missing_data_policy: Literal["unavailable", "partial_with_warning", "block"]
    required_observation_kinds: tuple[str, ...] = Field(min_length=1)


class ArchitectureFinding(FrozenModel):
    finding_id: str = Field(pattern=IDENTIFIER)
    claim: str | None = Field(default=None, min_length=3, max_length=2000)
    risk_type: Literal["loss", "volatility", "liquidity", "concentration", "event", "market", "data"]
    affected_asset: str
    direction: Literal["negative", "positive", "mixed", "unknown"]
    materiality: float = Field(ge=0, le=1)
    severity: int = Field(ge=0, le=3)
    confidence: float | None = Field(default=None, ge=0, le=1)
    confidence_method: str | None = Field(default=None, min_length=3, max_length=300)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    episode_id: str | None = Field(default=None, pattern=IDENTIFIER)
    metric_id: str | None = Field(default=None, pattern=IDENTIFIER)
    observed_value: float | None = None
    threshold_value: float | None = None
    observed_at: datetime | None = None

    @field_validator("observed_at")
    @classmethod
    def observed_at_is_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value)


class FindingEpisode(FrozenModel):
    episode_id: str = Field(pattern=IDENTIFIER)
    risk_type: str = Field(pattern=IDENTIFIER)
    rule_id: str = Field(pattern=IDENTIFIER)
    first_detected_at: datetime
    last_detected_at: datetime
    observation_count: int = Field(ge=1)
    maximum_severity: int = Field(ge=0, le=3)
    maximum_threshold_distance: float = Field(ge=0)
    state: Literal["open", "resolved"]
    evidence_ids: tuple[str, ...] = Field(min_length=1)

    _first = field_validator("first_detected_at")(_utc)
    _last = field_validator("last_detected_at")(_utc)


class ArchitectureDecision(FrozenModel):
    decision_id: str | None = Field(default=None, pattern=IDENTIFIER)
    monitoring_action: Literal["no_action", "continue_monitoring", "increase_monitoring", "urgent_human_review"]
    portfolio_action: Literal["none", "review_exposure"]
    alternatives_considered: tuple[str, ...]
    human_review_required: bool
    rationale_finding_ids: tuple[str, ...] = ()
    branch_id: str | None = Field(default=None, pattern=IDENTIFIER)
    counterfactual_branch_ids: tuple[str, ...] = ()


class AgentContributionSummary(FrozenModel):
    agent_id: str = Field(pattern=IDENTIFIER)
    agent_version: str = Field(min_length=1, max_length=128)
    experimental_role: Literal["final_decision_agent", "specialist_node"]
    output_id: str = Field(pattern=IDENTIFIER)
    output_digest: str = Field(pattern=DIGEST)
    started_at: datetime
    completed_at: datetime
    first_finding_at: datetime | None = None
    elapsed_ms: float = Field(ge=0)
    finding_ids: tuple[str, ...] = ()
    confidence: float = Field(ge=0, le=1)
    proposed_monitoring_action: str | None = Field(default=None, max_length=120)
    capability_ids: tuple[str, ...] = ()
    model_calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    retries: int = Field(ge=0)
    timeouts: int = Field(ge=0)
    schema_validation_failures: int = Field(ge=0)
    semantic_verification_failures: int = Field(ge=0)
    errors: tuple[str, ...] = ()

    _started = field_validator("started_at")(_utc)
    _completed = field_validator("completed_at")(_utc)

    @field_validator("first_finding_at")
    @classmethod
    def first_finding_is_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value)

    @model_validator(mode="after")
    def contribution_is_coherent(self) -> "AgentContributionSummary":
        if self.completed_at < self.started_at:
            raise ValueError("agent contribution completion cannot precede start")
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError("cached input tokens cannot exceed input tokens")
        if self.first_finding_at is not None and not (
            self.started_at <= self.first_finding_at <= self.completed_at
        ):
            raise ValueError("first finding must fall inside the contribution interval")
        return self


class CriticCorrectionSummary(FrozenModel):
    critic_agent_id: str = Field(pattern=IDENTIFIER)
    target_output_id: str = Field(pattern=IDENTIFIER)
    revised_output_id: str = Field(pattern=IDENTIFIER)
    findings_added: tuple[str, ...] = ()
    findings_removed: tuple[str, ...] = ()
    findings_retained: tuple[str, ...] = ()
    severity_delta: int = Field(ge=-3, le=3)
    confidence_delta: float = Field(ge=-1, le=1)
    evidence_coverage_delta: float = Field(ge=-1, le=1)
    accepted: bool


class ArchitectureExecutionSummary(FrozenModel):
    started_at: datetime
    completed_at: datetime
    first_finding_at: datetime | None = None
    wall_clock_ms: float = Field(ge=0)
    critical_path_ms: float = Field(ge=0)
    model_calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    capability_calls: int = Field(ge=0)
    retries: int = Field(ge=0)
    timeouts: int = Field(ge=0)
    schema_validation_failures: int = Field(ge=0)
    semantic_verification_failures: int = Field(ge=0)
    errors: tuple[str, ...] = ()

    _started = field_validator("started_at")(_utc)
    _completed = field_validator("completed_at")(_utc)

    @field_validator("first_finding_at")
    @classmethod
    def first_finding_is_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value)

    @model_validator(mode="after")
    def execution_is_coherent(self) -> "ArchitectureExecutionSummary":
        if self.completed_at < self.started_at:
            raise ValueError("architecture completion cannot precede start")
        if self.critical_path_ms > self.wall_clock_ms + 1e-6:
            raise ValueError("critical path cannot exceed wall-clock duration")
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError("cached input tokens cannot exceed input tokens")
        if self.first_finding_at is not None and not (
            self.started_at <= self.first_finding_at <= self.completed_at
        ):
            raise ValueError("first finding must fall inside architecture execution")
        measured_wall_clock = (self.completed_at - self.started_at).total_seconds() * 1000
        if abs(self.wall_clock_ms - measured_wall_clock) > 1.0:
            raise ValueError("wall-clock milliseconds must match execution timestamps")
        return self


class ArchitectureBehaviorSummary(FrozenModel):
    architecture_type: Literal["single_agent", "agent_graph"]
    contributions: tuple[AgentContributionSummary, ...] = Field(min_length=1)
    edge_traversals: tuple[str, ...] = ()
    handoff_count: int = Field(default=0, ge=0)
    synthesis_ms: float = Field(default=0, ge=0)
    coordination_overhead_ms: float = Field(default=0, ge=0)
    finding_disagreement: float = Field(default=0, ge=0, le=1)
    severity_dispersion: float = Field(default=0, ge=0)
    confidence_dispersion: float = Field(default=0, ge=0, le=1)
    decision_disagreement: float = Field(default=0, ge=0, le=1)
    critic_corrections: tuple[CriticCorrectionSummary, ...] = ()

    @model_validator(mode="after")
    def roles_match_architecture(self) -> "ArchitectureBehaviorSummary":
        output_ids = [item.output_id for item in self.contributions]
        if len(output_ids) != len(set(output_ids)):
            raise ValueError("agent contribution output IDs must be unique")
        agent_ids = [item.agent_id for item in self.contributions]
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("agent contribution IDs must be unique")
        final_count = sum(
            item.experimental_role == "final_decision_agent"
            for item in self.contributions
        )
        if final_count != 1:
            raise ValueError("architecture behavior requires exactly one final decision contribution")
        if self.architecture_type == "single_agent" and len(self.contributions) != 1:
            raise ValueError("single-agent behavior requires one contribution")
        if self.architecture_type == "agent_graph" and len(self.contributions) < 2:
            raise ValueError("graph behavior requires at least two contributions")
        return self


class ArchitectureOutput(FrozenModel):
    output_id: str = Field(pattern=IDENTIFIER)
    run_id: str = Field(pattern=IDENTIFIER)
    architecture_type: Literal["deterministic", "single_agent", "agent_graph"]
    assessment_state: Literal["clear", "watch", "alert"]
    severity: int = Field(ge=0, le=3)
    confidence: float = Field(ge=0, le=1)
    confidence_kind: Literal["calibrated_probability", "model_score", "ordinal_judgement"] | None = None
    confidence_method: str = Field(min_length=3, max_length=300)
    findings: tuple[ArchitectureFinding, ...]
    supporting_evidence_ids: tuple[str, ...]
    conflicting_evidence_ids: tuple[str, ...] = ()
    risk_interpretation: str = Field(min_length=3, max_length=3000)
    expectations: str = Field(min_length=3, max_length=1500)
    decision: ArchitectureDecision
    missing_information: tuple[str, ...]
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    data_quality_score: float | None = Field(default=None, ge=0, le=1)
    trigger_available_at: datetime | None = None
    produced_at: datetime | None = None
    input_context_digest: str | None = Field(default=None, pattern=DIGEST)
    case_id: str | None = Field(default=None, pattern=IDENTIFIER)
    repetition: int | None = Field(default=None, ge=1, le=100)
    perturbation_id: str | None = Field(default=None, pattern=IDENTIFIER)
    execution_summary: ArchitectureExecutionSummary | None = None
    architecture_behavior: ArchitectureBehaviorSummary | None = None
    architecture_id: str = Field(pattern=IDENTIFIER)
    capabilities_used: tuple[str, ...]
    agents_used: tuple[str, ...] = ()
    cycle_id: str | None = Field(default=None, pattern=IDENTIFIER)
    as_of: datetime | None = None
    change_since_previous: Literal["initial", "unchanged", "improved", "deteriorated", "mixed"] = "initial"
    classified_context_ids: tuple[str, ...] = ()
    source_output_id: str | None = Field(default=None, pattern=IDENTIFIER)
    source_output_digest: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")
    mapper_version: str | None = Field(default=None, pattern=IDENTIFIER)

    @field_validator("as_of", "trigger_available_at", "produced_at")
    @classmethod
    def timestamps_are_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value)

    @model_validator(mode="after")
    def evaluation_semantics_are_complete(self) -> "ArchitectureOutput":
        finding_ids = [item.finding_id for item in self.findings]
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("ArchitectureOutput finding IDs must be unique")
        expected_severity = max((item.severity for item in self.findings), default=0)
        if self.severity != expected_severity:
            raise ValueError("ArchitectureOutput severity must equal its highest finding severity")
        if self.assessment_state == "clear" and self.findings:
            raise ValueError("a clear ArchitectureOutput cannot contain findings")
        if self.assessment_state == "alert" and not self.findings:
            raise ValueError("an alert ArchitectureOutput requires findings")
        if not set(self.decision.rationale_finding_ids).issubset(finding_ids):
            raise ValueError("decision rationale must reference ArchitectureOutput findings")
        indexed_evidence = set(self.supporting_evidence_ids) | set(self.conflicting_evidence_ids)
        cited_evidence = {evidence for item in self.findings for evidence in item.evidence_ids}
        if not cited_evidence.issubset(indexed_evidence):
            raise ValueError("ArchitectureOutput evidence index must include every finding citation")
        for field_name in ("supporting_evidence_ids", "conflicting_evidence_ids", "capabilities_used", "agents_used", "classified_context_ids"):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must contain unique values")
        if self.trigger_available_at is not None and self.as_of is not None and self.trigger_available_at > self.as_of:
            raise ValueError("trigger availability cannot follow ArchitectureOutput as-of")
        if self.produced_at is not None and self.as_of is not None and self.produced_at < self.as_of:
            raise ValueError("ArchitectureOutput cannot be produced before its as-of")
        if self.architecture_behavior is not None and self.architecture_behavior.architecture_type != self.architecture_type:
            raise ValueError("architecture behavior type must match ArchitectureOutput type")
        if self.architecture_type == "deterministic" and self.architecture_behavior is not None:
            raise ValueError("deterministic output cannot contain agent behavior")
        provenance = (self.source_output_id, self.source_output_digest, self.mapper_version)
        if any(provenance) and not all(provenance):
            raise ValueError("mapped source output identity and mapper version must be complete")
        if self.source_output_id is not None:
            required = (
                self.as_of, self.cycle_id, self.trigger_available_at,
                self.produced_at, self.input_context_digest, self.case_id,
                self.repetition, self.execution_summary, self.architecture_behavior,
            )
            if any(value is None for value in required):
                raise ValueError("mapped agent output lacks mandatory experimental observations")
        return self


class DecisionBranch(FrozenModel):
    branch_id: str = Field(pattern=IDENTIFIER)
    decision_id: str = Field(pattern=IDENTIFIER)
    action: Literal["continue_monitoring", "increase_monitoring", "review_exposure"]
    created_at: datetime
    outcome_horizon_end: datetime
    status: Literal["awaiting_outcome", "evaluable"] = "awaiting_outcome"

    _created = field_validator("created_at")(_utc)
    _outcome = field_validator("outcome_horizon_end")(_utc)


class RunTraceRecord(FrozenModel):
    started_at: datetime
    completed_at: datetime
    wall_clock_ms: float = Field(ge=0)
    model_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    errors: tuple[str, ...] = ()

    _started = field_validator("started_at")(_utc)
    _completed = field_validator("completed_at")(_utc)

    @model_validator(mode="after")
    def runtime_is_coherent(self) -> "RunTraceRecord":
        if self.completed_at < self.started_at:
            raise ValueError("run completion cannot precede start")
        measured = (self.completed_at - self.started_at).total_seconds() * 1000
        if self.wall_clock_ms > measured + 50.0:
            raise ValueError("run wall-clock milliseconds cannot exceed its timestamp interval")
        return self


class RuntimeObservation(FrozenModel):
    observation_id: str = Field(pattern=IDENTIFIER)
    kind: Literal["input", "derived", "event", "runtime"]
    name: str = Field(pattern=IDENTIFIER)
    value: float | int | str | bool | None
    unit: str | None = None
    observed_at: datetime
    available_at: datetime
    evidence_ids: tuple[str, ...]

    _observed = field_validator("observed_at")(_utc)
    _available = field_validator("available_at")(_utc)


class EvaluationMetricResult(FrozenModel):
    """One auditable measurement inside an evaluation dimension.

    A metric is never silently coerced to zero.  The numerator, denominator,
    unit, reference and limitations travel with the value so a human or coding
    assistant can reconstruct exactly what was—and was not—measured.
    """

    metric_id: str = Field(pattern=IDENTIFIER)
    label: str = Field(min_length=2, max_length=200)
    status: Literal["measured", "not_measurable", "not_applicable"]
    value: float | int | str | bool | None = None
    numerator: float | int | None = None
    denominator: float | int | None = None
    unit: str = Field(pattern=IDENTIFIER)
    method: str = Field(min_length=3, max_length=1200)
    reference_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def measurement_is_explicit(self) -> "EvaluationMetricResult":
        if self.status == "measured" and self.value is None:
            raise ValueError("a measured evaluation metric requires a value")
        if self.status != "measured" and any(
            value is not None for value in (self.value, self.numerator, self.denominator)
        ):
            raise ValueError("an unavailable evaluation metric cannot carry a numeric result")
        if self.denominator is not None and self.denominator <= 0:
            raise ValueError("an evaluation metric denominator must be positive")
        if self.reference_ids != tuple(sorted(set(self.reference_ids))):
            raise ValueError("evaluation metric references must be unique and sorted")
        return self


class EvaluationDimensionRecord(FrozenModel):
    dimension_id: str = Field(pattern=IDENTIFIER)
    status: Literal["measured", "partial", "not_measurable", "not_applicable"]
    score: float | None = Field(default=None, ge=0, le=1)
    summary: str = Field(min_length=3, max_length=1500)
    metric_values: dict[str, float | int | str | bool | None]
    metrics: tuple[EvaluationMetricResult, ...] = ()
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def score_is_supported(self) -> "EvaluationDimensionRecord":
        if self.status in {"not_measurable", "not_applicable"} and self.score is not None:
            raise ValueError("an unavailable evaluation dimension cannot have a score")
        metric_ids = tuple(item.metric_id for item in self.metrics)
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("evaluation dimension metrics must be unique")
        return self


class EvaluationRecord(FrozenModel):
    evaluation_id: str = Field(pattern=IDENTIFIER)
    run_id: str = Field(pattern=IDENTIFIER)
    evaluator: Literal["deterministic_evaluator", "model_evaluator", "human_evaluator"]
    evaluated_output_id: str = Field(pattern=IDENTIFIER)
    label_state: Literal["not_admitted", "admitted"]
    dimensions: tuple[EvaluationDimensionRecord, ...]
    failure_codes: tuple[str, ...] = ()
    created_at: datetime
    evaluator_version: str = Field(default="1.0.0", min_length=1, max_length=128)
    evaluated_output_ids: tuple[str, ...] = ()
    metric_specification_ids: tuple[str, ...] = ()
    label_set_digest: str | None = Field(default=None, pattern=DIGEST)

    _created = field_validator("created_at")(_utc)

    @model_validator(mode="after")
    def dimensions_are_complete(self) -> "EvaluationRecord":
        dimension_ids = tuple(sorted(item.dimension_id for item in self.dimensions))
        if dimension_ids != EVALUATION_DIMENSION_IDS:
            raise ValueError("EvaluationRecord requires each of the nine dimensions exactly once")
        if self.label_state == "not_admitted" and self.label_set_digest is not None:
            raise ValueError("an unavailable label set cannot have an admitted digest")
        if self.evaluated_output_ids and self.evaluated_output_id not in self.evaluated_output_ids:
            raise ValueError("primary evaluated output must be included in evaluated_output_ids")
        return self


class ExperimentalRun(FrozenModel):
    run_id: str = Field(pattern=IDENTIFIER)
    study_id: str = Field(pattern=IDENTIFIER)
    experiment_id: str = Field(pattern=IDENTIFIER)
    case_id: str = Field(pattern=IDENTIFIER)
    regime_labels: tuple[RegimeLabel, ...]
    run_input: RunInput
    architecture_config: ArchitectureConfig
    architecture_output: ArchitectureOutput
    run_trace: RunTraceRecord
    runtime_observations: tuple[RuntimeObservation, ...]
    evaluation_record: EvaluationRecord
    metric_specifications: tuple[MetricSpecification, ...] = ()
    architecture_outputs: tuple[ArchitectureOutput, ...] = ()
    finding_episodes: tuple[FindingEpisode, ...] = ()
    decision_branches: tuple[DecisionBranch, ...] = ()
    processing_receipts: tuple[ReplayProcessingReceipt, ...] = ()
    agent_output_ids: tuple[str, ...] = ()
    architecture_output_ids: tuple[str, ...] = ()
    # Deprecated run-record fields retained for older saved experiments.
    agent_artifact_ids: tuple[str, ...] = ()
    projection_receipt_ids: tuple[str, ...] = ()

    @field_validator("agent_output_ids", "architecture_output_ids", "agent_artifact_ids", "projection_receipt_ids")
    @classmethod
    def output_references_are_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("agent and architecture output references must be unique")
        return values

    @model_validator(mode="after")
    def identities_align(self) -> "ExperimentalRun":
        if self.run_input.case_id != self.case_id:
            raise ValueError("RunInput must reference the exact Case")
        if self.run_input.architecture_id != self.architecture_config.architecture_id:
            raise ValueError("RunInput and ArchitectureConfig must name the same architecture")
        if self.architecture_config.architecture_type == "deterministic" and any(
            item.parameterization == "adaptive" or item.implementation_class == "generative"
            for item in self.run_input.capability_configurations
        ):
            raise ValueError("deterministic architectures cannot use adaptive or generative capabilities")
        if self.architecture_output.architecture_id != self.architecture_config.architecture_id:
            raise ValueError("ArchitectureOutput must name the executed architecture")
        if self.architecture_output.run_id != self.run_id:
            raise ValueError("ArchitectureOutput must name the exact Run")
        expected_output_type = (
            "agent_graph"
            if self.architecture_config.architecture_type in {"agent_graph", "multi_agent"}
            else self.architecture_config.architecture_type
        )
        if self.architecture_output.architecture_type != expected_output_type:
            raise ValueError("ArchitectureOutput type must match ArchitectureConfig")
        if self.evaluation_record.run_id != self.run_id:
            raise ValueError("EvaluationRecord must reference the exact Run")
        if self.evaluation_record.evaluated_output_id != self.architecture_output.output_id:
            raise ValueError("EvaluationRecord must reference the immutable ArchitectureOutput")
        if any(
            item.run_id != self.run_id
            or item.architecture_id != self.architecture_config.architecture_id
            for item in self.architecture_outputs
        ):
            raise ValueError("every cycle ArchitectureOutput must belong to the exact Run and architecture")
        if self.architecture_outputs and self.architecture_output.output_id != self.architecture_outputs[-1].output_id:
            raise ValueError("the primary ArchitectureOutput must be the final cycle output")
        if self.evaluation_record.evaluated_output_ids and self.evaluation_record.evaluated_output_ids != tuple(
            item.output_id for item in self.architecture_outputs
        ):
            raise ValueError("EvaluationRecord output sequence must match retained ArchitectureOutputs")
        if self.architecture_outputs and self.architecture_outputs[-1].output_id != self.architecture_output.output_id:
            raise ValueError("architecture_output must be the final per-cycle ArchitectureOutput")
        if self.processing_receipts and tuple(item.output_id for item in self.processing_receipts) != tuple(
            item.output_id for item in self.architecture_outputs
        ):
            raise ValueError("processing receipts must match the ordered per-cycle ArchitectureOutputs")
        output_ids = tuple(item.output_id for item in self.architecture_outputs)
        if self.evaluation_record.evaluated_output_ids and self.evaluation_record.evaluated_output_ids != output_ids:
            raise ValueError("EvaluationRecord must reference the ordered per-cycle outputs")
        return self
