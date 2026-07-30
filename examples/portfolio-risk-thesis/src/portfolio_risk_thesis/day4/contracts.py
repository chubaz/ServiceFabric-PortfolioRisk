"""Strict immutable contracts for the Day 4 historical evaluation."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from portfolio_risk_thesis.day3.contracts import (
    ArchitectureId,
    ModelCallReceipt,
    ModelConfiguration,
    ReviewStatus,
    digest,
)

WindowId = Literal["stress_a", "stress_b", "control"]
WindowKind = Literal["stress", "control"]
LabelView = Literal["event_window", "outcome", "composite"]
ObservationClass = Literal["alert", "no_alert", "abstention", "execution_failure"]
TaskState = Literal["pending", "completed", "failed"]
SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"

PRIMARY_CONTEXTS = 45
PRIMARY_OBSERVATIONS = 135
REPEATABILITY_ANCHORS = 9
REPEAT_OBSERVATIONS = 18
TOTAL_OBSERVATIONS = 153
PRIMARY_MODEL_CALLS = 225
REPEAT_MODEL_CALLS = 45
AUTHORIZED_MODEL_CALLS = 270
ARCHITECTURES: tuple[ArchitectureId, ...] = ("B0", "B1", "A1")
REPEATED_ARCHITECTURES: tuple[ArchitectureId, ...] = ("B1", "A1")
WORKED_EXAMPLE_RULES = (
    "earliest_true_positive_stress_a",
    "earliest_true_positive_stress_b",
    "highest_severity_true_positive_different_portfolio",
    "earliest_false_positive_or_failure",
    "earliest_abstention",
)


def _utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{field_name} must be explicit UTC")
    return value.astimezone(UTC)


def _unique(values: tuple[object, ...], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")


class Strict(BaseModel):
    """The common Day 4 contract boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class HistoricalWindow(Strict):
    window_id: WindowId
    kind: WindowKind
    rationale: str = Field(min_length=1)
    review_dates: tuple[datetime, ...] = Field(min_length=5, max_length=5)
    trigger_available_at: datetime | None = None
    relevant_portfolios: tuple[str, ...] = ()

    @field_validator("review_dates")
    @classmethod
    def utc_review_dates(cls, values: tuple[datetime, ...]) -> tuple[datetime, ...]:
        normalized = tuple(_utc(value, "review date") for value in values)
        _unique(normalized, "review dates")
        if normalized != tuple(sorted(normalized)):
            raise ValueError("review dates must be chronological")
        return normalized

    @field_validator("trigger_available_at")
    @classmethod
    def utc_trigger(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value, "trigger_available_at")

    @model_validator(mode="after")
    def frozen_window_shape(self) -> "HistoricalWindow":
        expected_kind = "control" if self.window_id == "control" else "stress"
        if self.kind != expected_kind:
            raise ValueError("window identifier and kind disagree")
        if self.kind == "stress" and self.trigger_available_at is None:
            raise ValueError("stress windows require trigger_available_at")
        if self.kind == "control" and self.trigger_available_at is not None:
            raise ValueError("control window cannot declare a stress trigger")
        _unique(self.relevant_portfolios, "relevant portfolios")
        return self


class PortfolioDayKey(Strict):
    portfolio_id: str = Field(min_length=1)
    window_id: WindowId
    as_of: datetime
    key_digest: str = ""

    @field_validator("as_of")
    @classmethod
    def utc_as_of(cls, value: datetime) -> datetime:
        return _utc(value, "as_of")

    @model_validator(mode="after")
    def stable_key(self) -> "PortfolioDayKey":
        actual = digest(self.model_dump(exclude={"key_digest"}, mode="python"))
        if self.key_digest and self.key_digest != actual:
            raise ValueError("key_digest does not match the portfolio-day key")
        object.__setattr__(self, "key_digest", actual)
        return self


class Day4WindowSet(Strict):
    windows: tuple[HistoricalWindow, ...] = Field(min_length=3, max_length=3)
    window_set_digest: str = ""

    @model_validator(mode="after")
    def frozen_windows(self) -> "Day4WindowSet":
        if tuple(window.window_id for window in self.windows) != (
            "stress_a",
            "stress_b",
            "control",
        ):
            raise ValueError("windows must be stress_a, stress_b and control in order")
        all_dates = tuple(date for window in self.windows for date in window.review_dates)
        _unique(all_dates, "review dates across windows")
        for index, left in enumerate(self.windows):
            for right in self.windows[index + 1 :]:
                if not (
                    max(left.review_dates) < min(right.review_dates)
                    or max(right.review_dates) < min(left.review_dates)
                ):
                    raise ValueError("historical window date ranges must not overlap")
        actual = digest(self.model_dump(exclude={"window_set_digest"}, mode="python"))
        if self.window_set_digest and self.window_set_digest != actual:
            raise ValueError("window_set_digest does not match the reviewed windows")
        object.__setattr__(self, "window_set_digest", actual)
        return self


class EventWindowLabel(Strict):
    key: PortfolioDayKey
    positive: bool
    trigger_available_at: datetime | None = None
    evidence_refs: tuple[str, ...] = ()
    rationale: str = Field(min_length=1)

    @field_validator("trigger_available_at")
    @classmethod
    def utc_trigger(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value, "trigger_available_at")

    @model_validator(mode="after")
    def positive_label_has_trigger(self) -> "EventWindowLabel":
        if self.positive and self.trigger_available_at is None:
            raise ValueError("a positive event-window label requires its reviewed trigger")
        if self.key.window_id == "control" and self.positive:
            raise ValueError("control cannot have a positive event-window label")
        return self


class OutcomeLabel(Strict):
    key: PortfolioDayKey
    positive: bool
    realized_at: datetime | None = None
    portfolio_drawdown: Decimal | None = None
    realized_volatility: Decimal | None = None
    worst_position_loss: Decimal | None = None
    material_event: bool = False
    evidence_refs: tuple[str, ...] = ()
    rationale: str = Field(min_length=1)

    @field_validator("realized_at")
    @classmethod
    def utc_realized_at(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value, "realized_at")

    @model_validator(mode="after")
    def positive_outcome_has_time(self) -> "OutcomeLabel":
        if self.positive and self.realized_at is None:
            raise ValueError("a positive outcome requires its realization time")
        if self.realized_at is not None and self.realized_at <= self.key.as_of:
            raise ValueError("outcome realization must follow the review timestamp")
        return self


class PortfolioDayLabel(Strict):
    key: PortfolioDayKey
    event_window: EventWindowLabel
    outcome: OutcomeLabel
    composite: bool | None = None
    label_digest: str = ""

    @model_validator(mode="after")
    def aligned_and_stable(self) -> "PortfolioDayLabel":
        if self.event_window.key != self.key or self.outcome.key != self.key:
            raise ValueError("label components must use the same portfolio-day key")
        expected = self.event_window.positive or self.outcome.positive
        if self.composite is not None and self.composite != expected:
            raise ValueError("composite label must be event_window OR outcome")
        object.__setattr__(self, "composite", expected)
        actual = digest(self.model_dump(exclude={"label_digest"}, mode="python"))
        if self.label_digest and self.label_digest != actual:
            raise ValueError("label_digest does not match the label")
        object.__setattr__(self, "label_digest", actual)
        return self


class Day4LabelPolicy(Strict):
    future_business_sessions: Literal[5] = 5
    future_portfolio_drawdown_threshold: Decimal
    future_realized_volatility_threshold: Decimal
    worst_position_loss_threshold: Decimal
    material_event_enabled: bool
    matching_lookback_business_days: int = Field(gt=0)
    primary_label_view: Literal["event_window"] = "event_window"
    sensitivity_label_views: tuple[Literal["outcome", "composite"], ...] = (
        "outcome",
        "composite",
    )

    @model_validator(mode="after")
    def frozen_views(self) -> "Day4LabelPolicy":
        if self.sensitivity_label_views != ("outcome", "composite"):
            raise ValueError("outcome and composite are the frozen sensitivity views")
        return self


class ProviderPricingSnapshot(Strict):
    reviewed: Literal[True] = True
    provider_id: str = Field(min_length=1)
    model_snapshot: str = Field(min_length=1)
    currency: str = Field(min_length=3, max_length=3)
    input_price_per_million_tokens: Decimal = Field(ge=0)
    output_price_per_million_tokens: Decimal = Field(ge=0)
    effective_at: datetime
    source_reference: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    pricing_digest: str = ""

    @field_validator("effective_at")
    @classmethod
    def utc_effective_at(cls, value: datetime) -> datetime:
        return _utc(value, "effective_at")

    @field_validator("currency")
    @classmethod
    def canonical_currency(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("currency must be a three-letter alphabetic code")
        return value.upper()

    @model_validator(mode="after")
    def stable_pricing(self) -> "ProviderPricingSnapshot":
        actual = digest(self.model_dump(exclude={"pricing_digest"}, mode="python"))
        if self.pricing_digest and self.pricing_digest != actual:
            raise ValueError("pricing_digest does not match the reviewed snapshot")
        object.__setattr__(self, "pricing_digest", actual)
        return self


class ExternalArtifactBinding(Strict):
    """An immutable local input reference; never part of a provider payload."""

    path: str = Field(min_length=1)
    digest: str = Field(pattern=SHA256_PATTERN)
    kind: Literal["file", "tree"] = "file"
    scope: Literal["external", "repository_fixture"] = "external"

    @field_validator("path")
    @classmethod
    def absolute_local_path(cls, value: str) -> str:
        return value

    @model_validator(mode="after")
    def safe_location(self) -> "ExternalArtifactBinding":
        path = Path(self.path)
        if self.scope == "external" and not path.is_absolute():
            raise ValueError("external artifact paths must be absolute")
        if self.scope == "repository_fixture" and (
            path.is_absolute() or ".." in path.parts
        ):
            raise ValueError("repository fixture paths must be safe relative paths")
        return self


class Day4InputBindings(Strict):
    coverage_profile: ExternalArtifactBinding
    day2_experiment_manifest: ExternalArtifactBinding
    day3_event_manifest: ExternalArtifactBinding
    day3_event_dataset: ExternalArtifactBinding
    day3_model_config: ExternalArtifactBinding
    day3_acceptance_run: ExternalArtifactBinding
    pricing_manifest: ExternalArtifactBinding

    @model_validator(mode="after")
    def expected_kinds(self) -> "Day4InputBindings":
        if self.day3_acceptance_run.kind != "tree":
            raise ValueError("the accepted Day 3 run binding must be a tree digest")
        if any(
            binding.kind != "file"
            for name, binding in self
            if name != "day3_acceptance_run"
        ):
            raise ValueError("all other Day 4 external bindings must be files")
        return self


class Day4RepeatabilityPolicy(Strict):
    anchors: tuple[PortfolioDayKey, ...] = Field(
        min_length=REPEATABILITY_ANCHORS,
        max_length=REPEATABILITY_ANCHORS,
    )
    architectures: tuple[ArchitectureId, ...] = REPEATED_ARCHITECTURES
    additional_repetitions: Literal[1] = 1
    expected_additional_observations: Literal[18] = REPEAT_OBSERVATIONS
    expected_additional_model_calls: Literal[45] = REPEAT_MODEL_CALLS

    @model_validator(mode="after")
    def one_anchor_per_portfolio_window(self) -> "Day4RepeatabilityPolicy":
        if self.architectures != REPEATED_ARCHITECTURES:
            raise ValueError("only B1 and A1 are repeated")
        pairs = tuple((anchor.portfolio_id, anchor.window_id) for anchor in self.anchors)
        _unique(pairs, "repeatability portfolio-window anchors")
        if len({anchor.portfolio_id for anchor in self.anchors}) != 3:
            raise ValueError("repeatability anchors must cover exactly three portfolios")
        if {anchor.window_id for anchor in self.anchors} != {
            "stress_a",
            "stress_b",
            "control",
        }:
            raise ValueError("repeatability anchors must cover every window")
        return self


class Day4ExperimentManifest(Strict):
    version: Literal["1"] = "1"
    profile: Literal["synthetic_fixture", "real"]
    experiment_id: str = Field(min_length=1)
    reviewed: Literal[True] = True
    reviewer: str = Field(min_length=1)
    portfolios: tuple[str, ...] = Field(min_length=3, max_length=3)
    window_set: Day4WindowSet
    architectures: tuple[ArchitectureId, ...] = ARCHITECTURES
    inputs: Day4InputBindings
    label_policy: Day4LabelPolicy
    repeatability: Day4RepeatabilityPolicy
    model: ModelConfiguration
    pricing: ProviderPricingSnapshot | None = None
    maximum_authorized_model_calls: int
    worked_example_rules: tuple[str, ...] = WORKED_EXAMPLE_RULES
    human_review_required: Literal[True] = True
    effects: tuple[str, ...] = Field(default=(), max_length=0)
    limitations: tuple[str, ...] = ()
    manifest_digest: str = ""

    @field_validator("effects")
    @classmethod
    def effect_free(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if values:
            raise ValueError("Day 4 is effect-free")
        return values

    @model_validator(mode="after")
    def frozen_experiment(self) -> "Day4ExperimentManifest":
        _unique(self.portfolios, "portfolios")
        if self.architectures != ARCHITECTURES:
            raise ValueError("architectures must be B0, B1 and A1 in order")
        if self.maximum_authorized_model_calls != AUTHORIZED_MODEL_CALLS:
            raise ValueError("maximum authorized provider-call budget must equal 270")
        if self.worked_example_rules != WORKED_EXAMPLE_RULES:
            raise ValueError("worked-example rules differ from the reviewed rules")
        expected_scope = "repository_fixture" if self.profile == "synthetic_fixture" else "external"
        if any(binding.scope != expected_scope for _, binding in self.inputs):
            raise ValueError("input binding scope differs from the experiment profile")
        portfolio_set = set(self.portfolios)
        for window in self.window_set.windows:
            if set(window.relevant_portfolios).difference(portfolio_set):
                raise ValueError("window relevance references an undeclared portfolio")
        expected_pairs = {
            (portfolio, window.window_id)
            for portfolio in self.portfolios
            for window in self.window_set.windows
        }
        actual_pairs = {
            (anchor.portfolio_id, anchor.window_id)
            for anchor in self.repeatability.anchors
        }
        if actual_pairs != expected_pairs:
            raise ValueError("anchors must contain one entry per portfolio-window pair")
        review_dates = {
            (portfolio, window.window_id): set(window.review_dates)
            for portfolio in self.portfolios
            for window in self.window_set.windows
        }
        if any(
            anchor.as_of not in review_dates[(anchor.portfolio_id, anchor.window_id)]
            for anchor in self.repeatability.anchors
        ):
            raise ValueError("repeatability anchor is not a reviewed window date")
        actual = digest(self.model_dump(exclude={"manifest_digest"}, mode="python"))
        if self.manifest_digest and self.manifest_digest != actual:
            raise ValueError("manifest_digest does not match the experiment")
        object.__setattr__(self, "manifest_digest", actual)
        return self

    def portfolio_day_keys(self) -> tuple[PortfolioDayKey, ...]:
        return tuple(
            PortfolioDayKey(
                portfolio_id=portfolio,
                window_id=window.window_id,
                as_of=as_of,
            )
            for window in self.window_set.windows
            for portfolio in self.portfolios
            for as_of in window.review_dates
        )


class Day4Task(Strict):
    experiment_digest: str = Field(pattern=SHA256_PATTERN)
    key: PortfolioDayKey
    architecture_id: ArchitectureId
    repetition: int = Field(ge=0, le=1)
    context_digest: str = Field(pattern=SHA256_PATTERN)
    model_snapshot: str = Field(min_length=1)
    prompt_manifest_digest: str = Field(pattern=SHA256_PATTERN)
    expected_model_calls: int = Field(ge=0, le=4)
    task_id: str = ""

    @model_validator(mode="after")
    def stable_task_identity(self) -> "Day4Task":
        expected_calls = {"B0": 0, "B1": 1, "A1": 4}[self.architecture_id]
        if self.expected_model_calls != expected_calls:
            raise ValueError("task model-call count differs from the frozen architecture")
        if self.repetition and self.architecture_id == "B0":
            raise ValueError("deterministic B0 is not recalled")
        identity = self.model_dump(
            include={
                "experiment_digest",
                "key",
                "architecture_id",
                "repetition",
                "context_digest",
                "model_snapshot",
                "prompt_manifest_digest",
            },
            mode="python",
        )
        actual = digest(identity)
        if self.task_id and self.task_id != actual:
            raise ValueError("task_id does not match semantic task identity")
        object.__setattr__(self, "task_id", actual)
        return self


class Day4ExecutionPlan(Strict):
    experiment_digest: str = Field(pattern=SHA256_PATTERN)
    contexts: tuple[PortfolioDayKey, ...] = Field(
        min_length=PRIMARY_CONTEXTS,
        max_length=PRIMARY_CONTEXTS,
    )
    tasks: tuple[Day4Task, ...] = Field(
        min_length=TOTAL_OBSERVATIONS,
        max_length=TOTAL_OBSERVATIONS,
    )
    primary_context_count: Literal[45] = PRIMARY_CONTEXTS
    primary_observation_count: Literal[135] = PRIMARY_OBSERVATIONS
    repeatability_anchor_count: Literal[9] = REPEATABILITY_ANCHORS
    repeat_observation_count: Literal[18] = REPEAT_OBSERVATIONS
    total_observation_count: Literal[153] = TOTAL_OBSERVATIONS
    expected_model_calls: Literal[270] = AUTHORIZED_MODEL_CALLS
    plan_digest: str = ""

    @model_validator(mode="after")
    def exact_plan(self) -> "Day4ExecutionPlan":
        _unique(tuple(context.key_digest for context in self.contexts), "plan contexts")
        _unique(tuple(task.task_id for task in self.tasks), "plan tasks")
        if any(task.experiment_digest != self.experiment_digest for task in self.tasks):
            raise ValueError("task experiment digest differs from its plan")
        primary = tuple(task for task in self.tasks if task.repetition == 0)
        repeats = tuple(task for task in self.tasks if task.repetition == 1)
        if len(primary) != PRIMARY_OBSERVATIONS or len(repeats) != REPEAT_OBSERVATIONS:
            raise ValueError("plan must contain exactly 135 primary and 18 repeat tasks")
        primary_by_key: dict[str, list[ArchitectureId]] = {}
        for task in primary:
            primary_by_key.setdefault(task.key.key_digest, []).append(task.architecture_id)
        if set(primary_by_key) != {context.key_digest for context in self.contexts}:
            raise ValueError("primary tasks do not cover all authoritative contexts")
        if any(tuple(values) != ARCHITECTURES for values in primary_by_key.values()):
            raise ValueError("each context must execute B0, B1 and A1 in order")
        if any(task.architecture_id not in REPEATED_ARCHITECTURES for task in repeats):
            raise ValueError("repeat panel may contain only B1 and A1")
        repeated_by_key: dict[str, list[ArchitectureId]] = {}
        for task in repeats:
            repeated_by_key.setdefault(task.key.key_digest, []).append(task.architecture_id)
        if len(repeated_by_key) != REPEATABILITY_ANCHORS or any(
            tuple(values) != REPEATED_ARCHITECTURES
            for values in repeated_by_key.values()
        ):
            raise ValueError("repeat panel must contain B1 and A1 on exactly nine anchors")
        task_contexts: dict[str, set[str]] = {}
        for task in self.tasks:
            task_contexts.setdefault(task.key.key_digest, set()).add(task.context_digest)
        if any(len(values) != 1 for values in task_contexts.values()):
            raise ValueError("architectures do not share one authoritative context digest")
        if len({task.model_snapshot for task in self.tasks}) != 1:
            raise ValueError("plan tasks do not share one model snapshot")
        if len({task.prompt_manifest_digest for task in self.tasks}) != 1:
            raise ValueError("plan tasks do not share one prompt manifest")
        if sum(task.expected_model_calls for task in self.tasks) != AUTHORIZED_MODEL_CALLS:
            raise ValueError("plan must contain exactly 270 provider calls")
        actual = digest(self.model_dump(exclude={"plan_digest"}, mode="python"))
        if self.plan_digest and self.plan_digest != actual:
            raise ValueError("plan_digest does not match the immutable task plan")
        object.__setattr__(self, "plan_digest", actual)
        return self


class Day4TaskReceipt(Strict):
    task_id: str = Field(pattern=SHA256_PATTERN)
    state: TaskState
    attempted_at: datetime
    completed_at: datetime | None = None
    model_call_receipts: tuple[ModelCallReceipt, ...] = ()
    provider_error: str | None = None
    receipt_digest: str = ""

    @field_validator("attempted_at", "completed_at")
    @classmethod
    def utc_receipt_time(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value, "task receipt timestamp")

    @model_validator(mode="after")
    def terminal_shape_and_digest(self) -> "Day4TaskReceipt":
        if self.state == "pending" and (self.completed_at or self.provider_error):
            raise ValueError("a pending receipt cannot be terminal")
        if self.state == "completed" and (self.completed_at is None or self.provider_error):
            raise ValueError("completed receipt requires a completion time and no provider error")
        if self.state == "failed" and (self.completed_at is None or not self.provider_error):
            raise ValueError("failed receipt requires a completion time and provider error")
        if self.completed_at is not None and self.completed_at < self.attempted_at:
            raise ValueError("receipt completion cannot precede its attempt")
        actual = digest(self.model_dump(exclude={"receipt_digest"}, mode="python"))
        if self.receipt_digest and self.receipt_digest != actual:
            raise ValueError("receipt_digest does not match the receipt")
        object.__setattr__(self, "receipt_digest", actual)
        return self


class ArchitectureObservation(Strict):
    task_id: str = Field(pattern=SHA256_PATTERN)
    key: PortfolioDayKey
    architecture_id: ArchitectureId
    repetition: int = Field(ge=0, le=1)
    context_digest: str = Field(pattern=SHA256_PATTERN)
    semantic_output_digest: str = Field(pattern=SHA256_PATTERN)
    status: ReviewStatus
    severity: int = Field(ge=0, le=3)
    critic_passed: bool
    critic_violations: tuple[str, ...] = ()
    claim_count: int = Field(ge=0, default=0)
    unsupported_claim_count: int = Field(ge=0, default=0)
    evidence_refs: tuple[str, ...] = ()
    affected_positions: tuple[str, ...] = ()
    provider_receipts: tuple[ModelCallReceipt, ...] = ()
    latency_ms: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    execution_failure: bool = False
    provider_error: str | None = None
    effects: tuple[str, ...] = Field(default=(), max_length=0)

    @model_validator(mode="after")
    def execution_and_effect_boundary(self) -> "ArchitectureObservation":
        if self.effects:
            raise ValueError("architecture observations are effect-free")
        expected_receipts = {"B0": 0, "B1": 1, "A1": 4}[self.architecture_id]
        if not self.execution_failure and len(self.provider_receipts) != expected_receipts:
            raise ValueError("successful observation has the wrong provider receipt count")
        if self.execution_failure != (self.provider_error is not None):
            raise ValueError("provider error and execution-failure state disagree")
        if self.unsupported_claim_count > self.claim_count:
            raise ValueError("unsupported claims cannot exceed total claims")
        if self.critic_passed and self.critic_violations:
            raise ValueError("a passing critic cannot retain violations")
        if self.repetition and self.architecture_id == "B0":
            raise ValueError("B0 has no repeated observation")
        return self

    @property
    def observation_class(self) -> ObservationClass:
        if self.execution_failure:
            return "execution_failure"
        if self.status in {"REVIEW", "URGENT_REVIEW"}:
            return "alert"
        if self.status == "NO_ISSUE":
            return "no_alert"
        return "abstention"


class PortfolioDayResult(Strict):
    key: PortfolioDayKey
    context_digest: str = Field(pattern=SHA256_PATTERN)
    observations: tuple[ArchitectureObservation, ...]
    label: PortfolioDayLabel

    @model_validator(mode="after")
    def aligned_context(self) -> "PortfolioDayResult":
        if self.label.key != self.key:
            raise ValueError("portfolio-day result label key mismatch")
        if any(
            observation.key != self.key or observation.context_digest != self.context_digest
            for observation in self.observations
        ):
            raise ValueError("portfolio-day observations do not share one context")
        return self


class AlertOutcomeMatch(Strict):
    match_id: str = ""
    architecture_id: ArchitectureId
    portfolio_id: str = Field(min_length=1)
    alert_task_id: str = Field(pattern=SHA256_PATTERN)
    outcome_label_digest: str = Field(pattern=SHA256_PATTERN)
    alert_at: datetime
    outcome_at: datetime
    lead_time_seconds: int = Field(ge=0)
    matching_lookback_business_days: int = Field(gt=0)
    rule: Literal["closest_eligible_prior_unmatched_alert"] = (
        "closest_eligible_prior_unmatched_alert"
    )
    evidence_refs: tuple[str, ...] = ()

    @field_validator("alert_at", "outcome_at")
    @classmethod
    def utc_match_time(cls, value: datetime) -> datetime:
        return _utc(value, "match timestamp")

    @model_validator(mode="after")
    def stable_match(self) -> "AlertOutcomeMatch":
        if self.alert_at > self.outcome_at:
            raise ValueError("alert must be no later than its matched outcome")
        expected_seconds = int((self.outcome_at - self.alert_at).total_seconds())
        if self.lead_time_seconds != expected_seconds:
            raise ValueError("lead_time_seconds does not match the preserved timestamps")
        actual = digest(self.model_dump(exclude={"match_id"}, mode="python"))
        if self.match_id and self.match_id != actual:
            raise ValueError("match_id does not match the alert-outcome evidence")
        object.__setattr__(self, "match_id", actual)
        return self


class ArchitectureEvaluation(Strict):
    architecture_id: ArchitectureId
    label_view: LabelView
    portfolio_id: str | None = None
    window_id: WindowId | None = None
    total_portfolio_days: int = Field(ge=0)
    alerts: int = Field(ge=0)
    abstentions: int = Field(ge=0)
    execution_failures: int = Field(ge=0)
    true_positives: int = Field(ge=0)
    false_positives: int = Field(ge=0)
    true_negatives: int = Field(ge=0)
    false_negatives: int = Field(ge=0)
    precision: Decimal | None
    recall: Decimal | None
    alerts_per_100_portfolio_days: Decimal
    abstention_rate: Decimal
    evaluated_coverage: Decimal
    evidence_reference_coverage: Decimal
    unsupported_claim_rate: Decimal
    critic_pass_rate: Decimal
    median_event_detection_delay_seconds: Decimal | None
    median_outcome_lead_time_seconds: Decimal | None
    median_latency_ms: Decimal | None
    p95_latency_ms: int | None
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    provider_cost: Decimal | None
    currency: str | None = None
    warnings: tuple[str, ...] = ()


class RepeatabilityEvaluation(Strict):
    architecture_id: ArchitectureId
    anchor_count: int = Field(ge=0)
    semantic_status_agreement: Decimal
    severity_agreement: Decimal
    exact_output_digest_agreement: Decimal
    affected_position_jaccard_agreement: Decimal
    evidence_reference_jaccard_agreement: Decimal
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class WorkedExample(Strict):
    example_id: str
    rule: Literal[
        "earliest_true_positive_stress_a",
        "earliest_true_positive_stress_b",
        "highest_severity_true_positive_different_portfolio",
        "earliest_false_positive_or_failure",
        "earliest_abstention",
    ]
    task_id: str = Field(pattern=SHA256_PATTERN)
    label_digest: str = Field(pattern=SHA256_PATTERN)
    evidence_refs: tuple[str, ...] = ()
    artifact: str = Field(min_length=1)


class Day4RunManifest(Strict):
    run_id: str = Field(min_length=1)
    experiment_digest: str = Field(pattern=SHA256_PATTERN)
    execution_plan_digest: str = Field(pattern=SHA256_PATTERN)
    created_at: datetime
    architecture_execution_sealed_at: datetime
    artifact_digests: dict[str, str]
    primary_context_count: Literal[45] = PRIMARY_CONTEXTS
    primary_observation_count: Literal[135] = PRIMARY_OBSERVATIONS
    repeat_observation_count: Literal[18] = REPEAT_OBSERVATIONS
    total_observation_count: Literal[153] = TOTAL_OBSERVATIONS
    label_count: Literal[45] = PRIMARY_CONTEXTS
    model_call_count: Literal[270] = AUTHORIZED_MODEL_CALLS
    provider_error_count: int = Field(ge=0)
    human_review_required: Literal[True] = True
    effects: tuple[str, ...] = Field(default=(), max_length=0)
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    run_manifest_digest: str = ""

    @field_validator("created_at", "architecture_execution_sealed_at")
    @classmethod
    def utc_run_time(cls, value: datetime) -> datetime:
        return _utc(value, "run manifest timestamp")

    @model_validator(mode="after")
    def sealed_effect_free_run(self) -> "Day4RunManifest":
        if self.architecture_execution_sealed_at < self.created_at:
            raise ValueError("architecture seal cannot precede run creation")
        if self.effects:
            raise ValueError("Day 4 run manifests are effect-free")
        if any(not value.startswith("sha256:") for value in self.artifact_digests.values()):
            raise ValueError("every artifact must have a SHA-256 digest")
        actual = digest(self.model_dump(exclude={"run_manifest_digest"}, mode="python"))
        if self.run_manifest_digest and self.run_manifest_digest != actual:
            raise ValueError("run_manifest_digest does not match the run manifest")
        object.__setattr__(self, "run_manifest_digest", actual)
        return self
