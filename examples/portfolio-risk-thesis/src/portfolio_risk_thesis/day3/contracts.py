"""Strict, immutable Day 3 architecture contracts."""
from __future__ import annotations

import hashlib, json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ArchitectureId = Literal["B0", "B1", "A1"]
ReviewStatus = Literal["NO_ISSUE", "REVIEW", "URGENT_REVIEW", "ABSTAIN", "ABSTAINED_AGENT_OUTPUT"]
NEXT_STEPS = ("record_no_action", "continue_monitoring", "investigate_data_quality", "investigate_market_cause", "run_scenario", "review_concentration", "consider_unexecuted_exposure_review")
FORBIDDEN = ("chain_of_thought", "reasoning_trace", "hidden_reasoning", "proposed_trade", "order", "broker", "rebalance", "optimization", "executable_effect")

def canonical(value: object) -> object:
    if isinstance(value, Decimal): return format(value, "f")
    if isinstance(value, datetime): return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, BaseModel): return canonical(value.model_dump(mode="python"))
    if isinstance(value, tuple): return [canonical(x) for x in value]
    if isinstance(value, dict): return {k: canonical(v) for k,v in value.items()}
    return value

def digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(canonical(value), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

class PositionExposure(Strict):
    position_alias: str = Field(min_length=1)
    weight: Decimal
    evidence_refs: tuple[str, ...] = Field(min_length=1)

class EligibleAgentEvent(Strict):
    event_id: str; event_time: datetime; available_at: datetime; entity_alias: str
    instrument_aliases: tuple[str, ...]; title: str; short_summary: str
    sentiment: Literal["positive", "negative", "neutral"]; relevance: Decimal
    source_reference: str; evidence_digest: str; profile: Literal["synthetic_curated", "public_curated", "private_curated"]
    publication_state: Literal["reviewed"]; limitations: tuple[str, ...]
    @field_validator("event_time", "available_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value): raise ValueError("timestamp must be UTC")
        return value

class StructuredClaim(Strict):
    claim_id: str; statement: str; claim_type: Literal["metric", "event", "portfolio", "interpretation"]
    metric_ref: str | None = None; reported_metric_value: Decimal | None = None; event_ref: str | None = None
    affected_positions: tuple[str, ...] = (); evidence_refs: tuple[str, ...] = ()
    @model_validator(mode="after")
    def supported(self):
        if self.claim_type in ("metric", "event", "portfolio") and not self.evidence_refs: raise ValueError("factual claims need evidence")
        if self.claim_type == "metric" and (not self.metric_ref or self.reported_metric_value is None): raise ValueError("metric claim needs exact ref and value")
        if self.claim_type == "event" and not self.event_ref: raise ValueError("event claim needs event ref")
        return self

class ArchitectureReviewOutput(Strict):
    architecture_id: ArchitectureId; status: ReviewStatus; severity: int = Field(ge=0, le=3)
    summary: str; affected_positions: tuple[str, ...] = (); metric_refs: tuple[str, ...] = (); event_refs: tuple[str, ...] = (); evidence_refs: tuple[str, ...] = ()
    supporting_claims: tuple[StructuredClaim, ...] = (); contradictory_claims: tuple[StructuredClaim, ...] = (); uncertainties: tuple[str, ...] = ()
    recommended_next_steps: tuple[str, ...] = (); human_review_required: Literal[True] = True; effects: tuple[()] = (); output_digest: str = ""
    @field_validator("recommended_next_steps")
    @classmethod
    def permitted(cls, values):
        if set(values).difference(NEXT_STEPS): raise ValueError("unpermitted next step")
        return values
    @model_validator(mode="after")
    def identity(self):
        actual = digest(self.model_dump(exclude={"output_digest"}, mode="python"))
        if self.output_digest and self.output_digest != actual: raise ValueError("output digest mismatch")
        object.__setattr__(self, "output_digest", actual); return self

class ArchitectureInputBundle(Strict):
    portfolio_id: str; as_of: datetime; metrics: dict[str, Decimal]; deterministic_finding: str; review_item: str; decision_point: str
    exposures: tuple[PositionExposure, ...]; events: tuple[EligibleAgentEvent, ...]; evidence_refs: tuple[str, ...]; warnings: tuple[str, ...] = (); limitations: tuple[str, ...] = (); context_digest: str = ""
    @model_validator(mode="after")
    def identity(self):
        actual = digest(self.model_dump(exclude={"context_digest"}, mode="python"))
        if self.context_digest and self.context_digest != actual: raise ValueError("context digest mismatch")
        object.__setattr__(self, "context_digest", actual); return self
    def model_safe(self) -> dict:
        payload = canonical(self); encoded = json.dumps(payload).lower()
        if any(word in encoded for word in ("permno", "gvkey", "api_key", "source_path", "portfolio-selection")): raise ValueError("private model payload")
        return payload

class CriticViolation(Strict): code: str; message: str
class CriticReport(Strict): passed: bool; violations: tuple[CriticViolation, ...] = ()
class ModelConfiguration(Strict): provider_id: str; model_id: str; model_snapshot: str; prompt_manifest_digest: str; maximum_output_tokens: int; timeout_seconds: int; retry_count: int = 0; store: Literal[False] = False; tools: tuple[()] = (); response_schema_version: str = "v1"
class PromptReference(Strict): prompt_id: str; version: str; digest: str; role: str
class ModelRequest(Strict): architecture_id: ArchitectureId; role_id: str; prompt: PromptReference; context_digest: str; payload: dict
class ModelCallReceipt(Strict): provider_id: str; model_id: str; request_digest: str; parsed_output_digest: str; input_tokens: int = 0; output_tokens: int = 0; elapsed_ms: int = 0; response_id: str | None = None; warnings: tuple[str,...] = (); limitations: tuple[str,...] = ()
class SpecialistAgentOutput(Strict): role_id: str; output: ArchitectureReviewOutput
class ArchitectureTreatmentDefinition(Strict): architecture_id: ArchitectureId; role_ids: tuple[str,...]; model_calls: int
class ArchitectureRun(Strict): architecture_id: ArchitectureId; context_digest: str; output: ArchitectureReviewOutput; critic: CriticReport; receipts: tuple[ModelCallReceipt,...]
class ArchitectureComparison(Strict): context_digest: str; runs: tuple[ArchitectureRun,...]
class Day3ExperimentManifest(Strict): experiment_id: str; context_digest: str; model: ModelConfiguration
class Day3RunManifest(Strict): run_id: str; context_digest: str; artifacts: dict[str,str]
