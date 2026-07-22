"""Immutable evidence-rich contracts for Day 1 four-agent timelines."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from risk_capabilities import EvidenceReference
from risk_domain.common import normalize_utc

from .contracts import AgentContract


DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"


class ReviewCheckpoint(AgentContract):
    """An explicit human-review state; pending is never implicit approval."""

    state: Literal["pending", "approved", "rejected", "changes_requested"] = "pending"
    human_review_required: Literal[True] = True
    reviewer_id: str | None = Field(default=None, min_length=1, max_length=256)
    rationale: str | None = Field(default=None, min_length=1, max_length=2048)

    @model_validator(mode="after")
    def completed_review_identifies_reviewer(self) -> "ReviewCheckpoint":
        if self.state != "pending" and (self.reviewer_id is None or self.rationale is None):
            raise ValueError("completed review checkpoints require reviewer_id and rationale")
        if self.state == "pending" and (self.reviewer_id is not None or self.rationale is not None):
            raise ValueError("pending review checkpoints cannot claim a reviewer decision")
        return self


class CapabilityReceipt(AgentContract):
    capability_id: str = Field(min_length=1, max_length=256)
    status: Literal["succeeded", "failed", "stopped"]
    input_digest: str = Field(pattern=DIGEST_PATTERN)
    output_digest: str = Field(pattern=DIGEST_PATTERN)
    evidence: tuple[EvidenceReference, ...] = Field(min_length=1)
    methodology: str = Field(min_length=1, max_length=256)
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()

    @field_validator("effects")
    @classmethod
    def receipt_has_no_effects(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if values:
            raise ValueError("agent capability receipts cannot contain effects")
        return values


class AgentTimelineStep(AgentContract):
    sequence: int = Field(ge=1)
    role: str = Field(pattern=r"^risk\.agent\.[a-z_]+$")
    capability_id: str = Field(min_length=1, max_length=256)
    started_at: datetime
    observed_at: datetime
    input_digest: str = Field(pattern=DIGEST_PATTERN)
    output_digest: str = Field(pattern=DIGEST_PATTERN)
    evidence: tuple[EvidenceReference, ...] = Field(min_length=1)
    methodology: str = Field(min_length=1, max_length=256)
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    status: Literal["succeeded", "failed", "stopped"]
    effects: tuple[str, ...] = ()
    review_state: Literal["pending", "approved", "rejected", "changes_requested"] = "pending"
    review: ReviewCheckpoint = Field(default_factory=ReviewCheckpoint)
    receipt: CapabilityReceipt

    _started_at = field_validator("started_at")(normalize_utc)
    _observed_at = field_validator("observed_at")(normalize_utc)

    @field_validator("effects")
    @classmethod
    def step_has_no_effects(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if values:
            raise ValueError("agent timeline steps cannot contain effects")
        return values

    @model_validator(mode="after")
    def receipt_and_step_are_consistent(self) -> "AgentTimelineStep":
        if self.observed_at < self.started_at:
            raise ValueError("observed_at cannot precede started_at")
        compared = (
            "capability_id",
            "status",
            "input_digest",
            "output_digest",
            "evidence",
            "methodology",
            "assumptions",
            "warnings",
            "limitations",
            "effects",
        )
        if any(getattr(self, field) != getattr(self.receipt, field) for field in compared):
            raise ValueError("timeline step must preserve its capability receipt")
        if self.review_state != self.review.state:
            raise ValueError("timeline review_state must match its review checkpoint")
        return self


class AgentTimeline(AgentContract):
    timeline_id: str = Field(min_length=1, max_length=256)
    status: Literal["succeeded", "failed", "stopped"]
    steps: tuple[AgentTimelineStep, ...] = Field(min_length=1)
    human_review_required: Literal[True] = True
    effects: tuple[str, ...] = ()

    @field_validator("effects")
    @classmethod
    def timeline_has_no_effects(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if values:
            raise ValueError("agent timelines cannot contain effects")
        return values

    @model_validator(mode="after")
    def ordering_and_status_are_deterministic(self) -> "AgentTimeline":
        sequences = [step.sequence for step in self.steps]
        if sequences != list(range(1, len(self.steps) + 1)):
            raise ValueError("timeline steps must use contiguous deterministic sequence numbers")
        expected = (
            "failed"
            if any(step.status == "failed" for step in self.steps)
            else "stopped"
            if any(step.status == "stopped" for step in self.steps)
            else "succeeded"
        )
        if self.status != expected:
            raise ValueError("timeline status must preserve the most severe step status")
        return self
