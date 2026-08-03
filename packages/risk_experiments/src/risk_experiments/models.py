"""Strict experiment contracts over canonical, versioned system assets."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from risk_registry import RegistryIdentity


IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$"
DIGEST = r"^sha256:[a-f0-9]{64}$"


def canonical_digest(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PresentationMode(str, Enum):
    INTERACTIVE_FOREGROUND = "interactive_foreground"
    BACKGROUND_HEADLESS = "background_headless"
    EVALUATION_ONLY = "evaluation_only"


class DataTruth(str, Enum):
    LICENSED_REAL = "licensed_real"
    PUBLIC_REAL = "public_real"
    REVIEWED_SYNTHETIC = "reviewed_synthetic"
    SIMULATED_INTRADAY = "simulated_intraday"
    MIXED = "mixed"


class ExperimentState(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    READY = "ready"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED_FOR_DECISION = "paused_for_decision"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REVIEWED = "reviewed"
    ARCHIVED = "archived"


TRANSITIONS: dict[ExperimentState, tuple[ExperimentState, ...]] = {
    ExperimentState.DRAFT: (ExperimentState.VALIDATED,),
    ExperimentState.VALIDATED: (ExperimentState.READY,),
    ExperimentState.READY: (ExperimentState.QUEUED, ExperimentState.CANCELLED),
    ExperimentState.QUEUED: (ExperimentState.RUNNING, ExperimentState.CANCELLED),
    ExperimentState.RUNNING: (
        ExperimentState.PAUSED_FOR_DECISION,
        ExperimentState.COMPLETED,
        ExperimentState.FAILED,
        ExperimentState.CANCELLED,
    ),
    ExperimentState.PAUSED_FOR_DECISION: (
        ExperimentState.RUNNING,
        ExperimentState.CANCELLED,
    ),
    ExperimentState.COMPLETED: (ExperimentState.REVIEWED,),
    ExperimentState.FAILED: (ExperimentState.REVIEWED,),
    ExperimentState.CANCELLED: (ExperimentState.REVIEWED,),
    ExperimentState.REVIEWED: (ExperimentState.ARCHIVED,),
    ExperimentState.ARCHIVED: (),
}


class TemporalWindow(FrozenModel):
    start_date: date
    end_date: date
    replay_schedule: Literal["daily_close", "business_daily", "manual_anchors"] = "daily_close"
    as_of_policy: Literal["available_at", "assignment_as_of"] = "available_at"

    @model_validator(mode="after")
    def ordered(self) -> "TemporalWindow":
        if self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date")
        if (self.end_date - self.start_date).days > 3_660:
            raise ValueError("experiment windows are bounded to ten years")
        return self


class SourceBinding(FrozenModel):
    """Immutable digest of a canonical source-binding declaration; never its replacement."""

    role: Literal[
        "portfolio",
        "snapshot_policy",
        "mandate",
        "data_revision",
        "eligibility_boundary",
        "model_policy",
        "pricing_policy",
        "decision_policy",
    ]
    reference: str = Field(min_length=1, max_length=768)
    revision: str = Field(min_length=1, max_length=160)
    digest: str = Field(pattern=DIGEST)


class ExperimentOverlay(FrozenModel):
    overlay_id: str = Field(pattern=IDENTIFIER)
    base_reference: str = Field(min_length=1, max_length=768)
    patch_reference: str = Field(min_length=1, max_length=768)
    patch_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=3, max_length=500)


class ExperimentBudget(FrozenModel):
    max_model_calls: int = Field(default=25, ge=0, le=10_000)
    max_cost_usd: Decimal = Field(default=Decimal("5.00"), ge=0, le=100_000, decimal_places=4)
    max_storage_mb: int = Field(default=512, ge=1, le=1_000_000)
    max_concurrent_tasks: int = Field(default=1, ge=1, le=32)


class ExperimentDefinition(FrozenModel):
    schema_version: Literal["portfolio-risk.experiment-definition/v1"] = (
        "portfolio-risk.experiment-definition/v1"
    )
    experiment_id: str = Field(pattern=IDENTIFIER)
    version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
    name: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=3, max_length=1200)
    hypothesis: str = Field(min_length=3, max_length=1200)
    owner: str = Field(pattern=IDENTIFIER)
    created_at: datetime
    temporal: TemporalWindow
    presentation_mode: PresentationMode = PresentationMode.INTERACTIVE_FOREGROUND
    data_truth: DataTruth
    source_bindings: tuple[SourceBinding, ...] = Field(min_length=4, max_length=32)
    system_assets: tuple[RegistryIdentity, ...] = ()
    overlays: tuple[ExperimentOverlay, ...] = ()
    budget: ExperimentBudget = ExperimentBudget()
    retention_policy: str = Field(default="experiment_evidence", pattern=IDENTIFIER)
    publication_policy: Literal["local_only", "review_required"] = "local_only"
    external_effects: Literal["disabled"] = "disabled"
    definition_digest: str | None = Field(default=None, pattern=DIGEST)

    _created = field_validator("created_at")(_aware)

    @model_validator(mode="after")
    def validate_definition(self) -> "ExperimentDefinition":
        roles = [item.role for item in self.source_bindings]
        required = {"portfolio", "snapshot_policy", "mandate", "data_revision"}
        if not required.issubset(roles):
            raise ValueError("portfolio, snapshot_policy, mandate, and data_revision bindings are required")
        binding_keys = [(item.role, item.reference, item.revision) for item in self.source_bindings]
        if binding_keys != sorted(set(binding_keys)):
            raise ValueError("source bindings must be uniquely and deterministically ordered")
        asset_refs = [item.reference for item in self.system_assets]
        if asset_refs != sorted(set(asset_refs)):
            raise ValueError("system assets must be uniquely and deterministically ordered")
        asset_kinds = {item.kind.value for item in self.system_assets}
        required_asset = (
            "evaluation"
            if self.presentation_mode == PresentationMode.EVALUATION_ONLY
            else "workflow"
        )
        if required_asset not in asset_kinds:
            raise ValueError(f"{self.presentation_mode.value} requires a registered {required_asset} asset")
        overlay_ids = [item.overlay_id for item in self.overlays]
        if overlay_ids != sorted(set(overlay_ids)):
            raise ValueError("overlays must be uniquely and deterministically ordered")
        payload = self.model_dump(mode="json", exclude={"definition_digest"})
        expected = canonical_digest(payload)
        if self.definition_digest is not None and self.definition_digest != expected:
            raise ValueError("definition_digest does not match canonical content")
        object.__setattr__(self, "definition_digest", expected)
        return self


class LifecycleReceipt(FrozenModel):
    schema_version: Literal["portfolio-risk.experiment-lifecycle-receipt/v1"] = (
        "portfolio-risk.experiment-lifecycle-receipt/v1"
    )
    experiment_id: str = Field(pattern=IDENTIFIER)
    sequence: int = Field(ge=1)
    from_state: ExperimentState | None
    to_state: ExperimentState
    actor: str = Field(pattern=IDENTIFIER)
    rationale: str = Field(min_length=3, max_length=1000)
    occurred_at: datetime
    idempotency_key: str = Field(pattern=IDENTIFIER)
    prior_receipt_digest: str | None = Field(default=None, pattern=DIGEST)
    receipt_digest: str | None = Field(default=None, pattern=DIGEST)

    _occurred = field_validator("occurred_at")(_aware)

    @model_validator(mode="after")
    def bind_digest(self) -> "LifecycleReceipt":
        if self.sequence == 1:
            if self.from_state is not None or self.to_state != ExperimentState.DRAFT:
                raise ValueError("first receipt must create a draft")
            if self.prior_receipt_digest is not None:
                raise ValueError("first receipt cannot name a predecessor")
        elif self.prior_receipt_digest is None:
            raise ValueError("later receipts require a predecessor")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"receipt_digest"}))
        if self.receipt_digest is not None and self.receipt_digest != expected:
            raise ValueError("receipt_digest does not match canonical content")
        object.__setattr__(self, "receipt_digest", expected)
        return self


class ExperimentRecord(FrozenModel):
    definition: ExperimentDefinition
    receipts: tuple[LifecycleReceipt, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_chain(self) -> "ExperimentRecord":
        state: ExperimentState | None = None
        previous: str | None = None
        keys: set[str] = set()
        for sequence, receipt in enumerate(self.receipts, start=1):
            if receipt.experiment_id != self.definition.experiment_id or receipt.sequence != sequence:
                raise ValueError("lifecycle identity or sequence is invalid")
            if receipt.from_state != state or receipt.prior_receipt_digest != previous:
                raise ValueError("lifecycle receipt chain is invalid")
            if receipt.idempotency_key in keys:
                raise ValueError("idempotency keys must be unique")
            keys.add(receipt.idempotency_key)
            state, previous = receipt.to_state, receipt.receipt_digest
        return self

    @property
    def state(self) -> ExperimentState:
        return self.receipts[-1].to_state

    @property
    def revision(self) -> str:
        return self.receipts[-1].receipt_digest or ""


class FactorDimension(FrozenModel):
    name: str = Field(pattern=IDENTIFIER)
    values: tuple[str, ...] = Field(min_length=1, max_length=100)

    @field_validator("values")
    @classmethod
    def unique_values(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("factor values must be unique")
        return values


class ExperimentSet(FrozenModel):
    schema_version: Literal["portfolio-risk.experiment-set/v1"] = (
        "portfolio-risk.experiment-set/v1"
    )
    experiment_set_id: str = Field(pattern=IDENTIFIER)
    name: str = Field(min_length=1, max_length=200)
    research_question: str = Field(min_length=3, max_length=1200)
    owner: str = Field(pattern=IDENTIFIER)
    experiment_ids: tuple[str, ...] = Field(min_length=1, max_length=500)
    controlled_factors: tuple[str, ...] = ()
    variable_factors: tuple[FactorDimension, ...] = ()
    seeds: tuple[int, ...] = Field(default=(1,), min_length=1, max_length=100)
    repeat_count: int = Field(default=1, ge=1, le=100)
    max_concurrency: int = Field(default=2, ge=1, le=32)
    max_total_cost_usd: Decimal = Field(default=Decimal("25.00"), ge=0, le=1_000_000)
    evaluation_suite: RegistryIdentity | None = None
    aggregation_rule: Literal["per_experiment_then_set_summary"] = (
        "per_experiment_then_set_summary"
    )
    created_at: datetime
    definition_digest: str | None = Field(default=None, pattern=DIGEST)

    _created = field_validator("created_at")(_aware)

    @model_validator(mode="after")
    def validate_set(self) -> "ExperimentSet":
        if self.experiment_ids != tuple(sorted(set(self.experiment_ids))):
            raise ValueError("experiment IDs must be unique and sorted")
        if self.controlled_factors != tuple(sorted(set(self.controlled_factors))):
            raise ValueError("controlled factors must be unique and sorted")
        if self.seeds != tuple(sorted(set(self.seeds))):
            raise ValueError("seeds must be unique and sorted")
        if len(self.experiment_ids) * len(self.seeds) * self.repeat_count > 10_000:
            raise ValueError("experiment set exceeds the 10,000-run planning boundary")
        names = [item.name for item in self.variable_factors]
        if names != sorted(set(names)):
            raise ValueError("variable factors must be unique and sorted")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"definition_digest"}))
        if self.definition_digest is not None and self.definition_digest != expected:
            raise ValueError("definition_digest does not match canonical content")
        object.__setattr__(self, "definition_digest", expected)
        return self


class QueueEntry(FrozenModel):
    schema_version: Literal["portfolio-risk.experiment-queue-entry/v1"] = (
        "portfolio-risk.experiment-queue-entry/v1"
    )
    queue_id: str = Field(pattern=IDENTIFIER)
    experiment_id: str = Field(pattern=IDENTIFIER)
    job_kind: Literal["workflow_replay", "evaluate_existing_outputs"]
    status: Literal["queued", "running", "paused", "completed", "failed", "cancelled"]
    idempotency_key: str = Field(pattern=IDENTIFIER)
    attempt: int = Field(default=1, ge=1, le=20)
    enqueued_at: datetime
    updated_at: datetime
    resume_token: str = Field(pattern=DIGEST)
    checkpoint_reference: str | None = Field(default=None, max_length=768)
    message: str = Field(min_length=1, max_length=500)

    _enqueued = field_validator("enqueued_at")(_aware)
    _updated = field_validator("updated_at")(_aware)

    @model_validator(mode="after")
    def compatible_job(self) -> "QueueEntry":
        if self.updated_at < self.enqueued_at:
            raise ValueError("queue update cannot precede enqueue time")
        return self
