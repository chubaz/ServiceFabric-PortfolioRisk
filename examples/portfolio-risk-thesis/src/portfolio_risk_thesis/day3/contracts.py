"""Immutable, private-neutral contracts for the Day 3 architecture experiment."""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ArchitectureId = Literal["B0", "B1", "A1"]
ReviewStatus = Literal["NO_ISSUE", "REVIEW", "URGENT_REVIEW", "ABSTAIN", "ABSTAINED_AGENT_OUTPUT"]
ROLE_IDS = (
    "risk.agent.market_data", "risk.agent.portfolio_exposure",
    "risk.agent.news_sentiment", "risk.agent.alert_recommendation",
)
NEXT_STEPS = (
    "record_no_action", "continue_monitoring", "investigate_data_quality",
    "investigate_market_cause", "run_scenario", "review_concentration",
    "consider_unexecuted_exposure_review",
)
PRIVATE_MARKERS = ("permno", "gvkey", "api_key", "source_path", "portfolio-selection", "candidate-artifact")
TRANSACTION_MARKERS = ("buy ", "sell ", "trade", "broker", "rebalance", "order ", "optimiz")
PATH_MARKERS = ("/users/", "/home/", "\\users\\", "file://")
ALIAS_PATTERN = r"^[a-z][a-z0-9-]{2,63}$"


def canonical(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, BaseModel):
        return canonical(value.model_dump(mode="python"))
    if isinstance(value, (tuple, list)):
        return [canonical(item) for item in value]
    if isinstance(value, dict):
        return {key: canonical(item) for key, item in value.items()}
    return value


def digest(value: object) -> str:
    payload = json.dumps(canonical(value), sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def bytes_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def contains_private_material(value: object) -> bool:
    encoded = json.dumps(canonical(value), sort_keys=True).casefold()
    username = os.environ.get("USER", "").strip().casefold()
    return any(marker in encoded for marker in PRIVATE_MARKERS + PATH_MARKERS) or (
        len(username) >= 3 and username in encoded
    )


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class PositionExposure(Strict):
    position_alias: str = Field(pattern=ALIAS_PATTERN)
    weight: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    evidence_refs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def private_neutral(self) -> "PositionExposure":
        if contains_private_material(self):
            raise ValueError("position exposure contains a private identifier or path")
        return self


class EligibleAgentEvent(Strict):
    event_id: str = Field(min_length=1)
    event_time: datetime
    available_at: datetime
    entity_alias: str = Field(pattern=ALIAS_PATTERN)
    instrument_aliases: tuple[str, ...] = Field(min_length=1)
    title: str = Field(min_length=1)
    short_summary: str = Field(min_length=1)
    sentiment: Literal["positive", "negative", "neutral"]
    relevance: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    source_reference: str = Field(min_length=1)
    evidence_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    profile: Literal["synthetic_curated", "public_curated", "private_curated"]
    publication_state: Literal["reviewed"]
    limitations: tuple[str, ...] = ()

    @field_validator("event_time", "available_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("timestamps must be explicit UTC")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def availability_follows_event_time(self) -> "EligibleAgentEvent":
        if self.available_at < self.event_time:
            raise ValueError("available_at cannot precede event_time")
        if len(self.instrument_aliases) != len(set(self.instrument_aliases)):
            raise ValueError("event instrument aliases must be unique")
        if any(
            not re.fullmatch(ALIAS_PATTERN, alias)
            for alias in self.instrument_aliases
        ):
            raise ValueError("event instrument aliases must be private-neutral")
        if contains_private_material(self):
            raise ValueError("event contains a private identifier or path")
        return self


class StructuredClaim(Strict):
    claim_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    claim_type: Literal["metric", "event", "portfolio", "interpretation"]
    metric_ref: str | None = None
    reported_metric_value: Decimal | None = None
    event_ref: str | None = None
    affected_positions: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def claim_shape(self) -> "StructuredClaim":
        if self.claim_type in {"metric", "event", "portfolio"} and not self.evidence_refs:
            raise ValueError("factual claims require evidence")
        if self.claim_type == "metric" and (not self.metric_ref or self.reported_metric_value is None):
            raise ValueError("metric claims require exact metric value")
        if self.claim_type == "event" and not self.event_ref:
            raise ValueError("event claims require an event reference")
        return self


class ArchitectureReviewOutput(Strict):
    architecture_id: ArchitectureId
    status: ReviewStatus
    severity: int = Field(ge=0, le=3)
    summary: str = Field(min_length=1)
    affected_positions: tuple[str, ...] = ()
    metric_refs: tuple[str, ...] = ()
    event_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    supporting_claims: tuple[StructuredClaim, ...] = ()
    contradictory_claims: tuple[StructuredClaim, ...] = ()
    uncertainties: tuple[str, ...] = ()
    recommended_next_steps: tuple[str, ...] = ()
    human_review_required: Literal[True] = True
    effects: tuple[str, ...] = ()
    output_digest: str = ""

    @field_validator("recommended_next_steps")
    @classmethod
    def allowed_next_steps(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if set(values).difference(NEXT_STEPS):
            raise ValueError("next step is not in the frozen catalogue")
        return values

    @field_validator("effects")
    @classmethod
    def effect_free(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if values:
            raise ValueError("Day 3 review outputs are effect-free")
        return values

    @model_validator(mode="after")
    def stable_identity(self) -> "ArchitectureReviewOutput":
        actual = digest(self.model_dump(exclude={"output_digest"}, mode="python"))
        if self.output_digest and self.output_digest != actual:
            raise ValueError("output_digest does not match semantic output")
        object.__setattr__(self, "output_digest", actual)
        return self


class ArchitectureInputBundle(Strict):
    portfolio_id: str = Field(min_length=1)
    as_of: datetime
    metrics: dict[str, Decimal] = Field(min_length=1)
    deterministic_finding: str = Field(min_length=1)
    review_item: str = Field(min_length=1)
    decision_point: str = Field(min_length=1)
    exposures: tuple[PositionExposure, ...] = Field(min_length=1)
    events: tuple[EligibleAgentEvent, ...] = ()
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    context_digest: str = ""

    @field_validator("as_of")
    @classmethod
    def utc_as_of(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("as_of must be explicit UTC")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def stable_identity_and_events(self) -> "ArchitectureInputBundle":
        if any(event.available_at > self.as_of for event in self.events):
            raise ValueError("future event is in the architecture context")
        aliases = [exposure.position_alias for exposure in self.exposures]
        if len(aliases) != len(set(aliases)):
            raise ValueError("position exposure aliases must be unique")
        known_aliases = set(aliases)
        if any(
            set(event.instrument_aliases).difference(known_aliases)
            for event in self.events
        ):
            raise ValueError("eligible event references a non-portfolio position")
        if not Decimal("0") < sum(
            (exposure.weight for exposure in self.exposures), Decimal("0")
        ) <= Decimal("1"):
            raise ValueError("position exposure weights must total more than zero and at most one")
        actual = digest(self.model_dump(exclude={"context_digest"}, mode="python"))
        if self.context_digest and self.context_digest != actual:
            raise ValueError("context_digest does not match authoritative context")
        object.__setattr__(self, "context_digest", actual)
        return self

    def model_safe(self) -> dict[str, object]:
        value = canonical(self)
        if contains_private_material(value):
            raise ValueError("private identifier or local path in model payload")
        return value


class CriticViolation(Strict):
    code: str
    message: str


class CriticReport(Strict):
    passed: bool
    violations: tuple[CriticViolation, ...] = ()
    original_output_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ModelConfiguration(Strict):
    provider_id: Literal["fixture", "openai_responses"]
    model_id: str = Field(min_length=1)
    model_snapshot: str = Field(min_length=1)
    prompt_manifest_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    temperature: Decimal | None = None
    temperature_supported: bool = False
    maximum_output_tokens: int = Field(gt=0)
    timeout_seconds: int = Field(gt=0, le=120)
    retry_count: int = Field(ge=0, le=1)
    store: Literal[False] = False
    tools: tuple[str, ...] = ()
    response_schema_version: Literal["v1"] = "v1"

    @field_validator("tools")
    @classmethod
    def tools_are_disabled(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if values:
            raise ValueError("model tools are prohibited")
        return values

    @model_validator(mode="after")
    def explicit_sampling_state(self) -> "ModelConfiguration":
        if self.model_id != self.model_snapshot:
            raise ValueError("model_id and explicit model_snapshot must match")
        if self.temperature_supported != (self.temperature is not None):
            raise ValueError("temperature value and support state disagree")
        return self


class PromptReference(Strict):
    prompt_id: str
    version: str
    digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    role: str


class ModelRequest(Strict):
    architecture_id: ArchitectureId
    role_id: str
    prompt: PromptReference
    system_prompt: PromptReference
    context_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    payload: dict[str, object]

    @model_validator(mode="after")
    def private_neutral_payload(self) -> "ModelRequest":
        if contains_private_material(self.payload):
            raise ValueError("model request payload contains private material")
        return self


class ModelCallReceipt(Strict):
    provider_id: str
    model_id: str
    architecture_id: ArchitectureId
    role_id: str
    prompt_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    request_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    raw_response_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    parsed_output_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    input_tokens: int = Field(ge=0, default=0)
    output_tokens: int = Field(ge=0, default=0)
    elapsed_ms: int = Field(ge=0, default=0)
    response_id: str | None = None
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class SpecialistAgentOutput(Strict):
    role_id: str
    output: ArchitectureReviewOutput


class ArchitectureTreatmentDefinition(Strict):
    architecture_id: ArchitectureId
    role_ids: tuple[str, ...]
    model_calls: int = Field(ge=0)


class ArchitectureRun(Strict):
    architecture_id: ArchitectureId
    context_digest: str
    output: ArchitectureReviewOutput
    critic: CriticReport
    receipts: tuple[ModelCallReceipt, ...]
    specialist_outputs: tuple[SpecialistAgentOutput, ...] = ()

    @model_validator(mode="after")
    def frozen_call_shape(self) -> "ArchitectureRun":
        expected = {"B0": 0, "B1": 1, "A1": 4}[self.architecture_id]
        if len(self.receipts) != expected:
            raise ValueError("architecture model-call count differs from the frozen treatment")
        if self.output.architecture_id != self.architecture_id:
            raise ValueError("architecture output identity mismatch")
        if any(receipt.architecture_id != self.architecture_id for receipt in self.receipts):
            raise ValueError("receipt architecture identity mismatch")
        if self.architecture_id == "A1":
            if tuple(receipt.role_id for receipt in self.receipts) != ROLE_IDS:
                raise ValueError("A1 role order differs from the frozen treatment")
            if tuple(item.role_id for item in self.specialist_outputs) != ROLE_IDS[:-1]:
                raise ValueError("A1 specialist outputs are incomplete or out of order")
        elif self.specialist_outputs:
            raise ValueError("only A1 may retain specialist outputs")
        return self


class ArchitectureComparison(Strict):
    context_digest: str
    runs: tuple[ArchitectureRun, ...]

    @model_validator(mode="after")
    def common_context(self) -> "ArchitectureComparison":
        if tuple(run.architecture_id for run in self.runs) != ("B0", "B1", "A1"):
            raise ValueError("comparison must contain B0, B1 and A1 in order")
        if any(run.context_digest != self.context_digest for run in self.runs):
            raise ValueError("architectures do not share one authoritative context digest")
        return self


class Day3ExperimentManifest(Strict):
    experiment_id: str
    context_digest: str
    model: ModelConfiguration


class Day3RunManifest(Strict):
    run_id: str
    context_digest: str
    artifacts: dict[str, str]
