"""Effect-free, retained trace for one resolved Fixture Context.

This is deliberately a host for observation, not an agent worker: it cannot
reach an undeclared source, inspect sealed labels, calculate a metric, or make
an external portfolio change.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .fixture_context import FixtureContext
from .models import DIGEST, IDENTIFIER, FrozenModel, canonical_digest


class RunTraceCheckpoint(FrozenModel):
    checkpoint_id: str = Field(pattern=IDENTIFIER)
    stage: Literal["context_verified", "capability_selected", "finding_recorded", "human_proposal"]
    message: str = Field(min_length=3, max_length=1000)


class EffectFreeRunTrace(FrozenModel):
    schema_version: Literal["portfolio-risk.effect-free-run-trace/v1"] = "portfolio-risk.effect-free-run-trace/v1"
    trace_id: str = Field(pattern=IDENTIFIER)
    fixture_context_digest: str = Field(pattern=DIGEST)
    acceptance_reference: str = Field(min_length=20, max_length=1200)
    selected_capability_reference: str = Field(min_length=3, max_length=1000)
    accessed_dataset_references: tuple[str, ...] = Field(min_length=1)
    processing_references: tuple[str, ...] = Field(min_length=1)
    checkpoints: tuple[RunTraceCheckpoint, ...] = Field(min_length=4, max_length=4)
    finding: str = Field(min_length=10, max_length=3000)
    uncertainty: str = Field(min_length=10, max_length=3000)
    human_proposal: str = Field(min_length=10, max_length=3000)
    labels_accessed: Literal[False] = False
    metric_calculated: Literal[False] = False
    external_effects: Literal["disabled"] = "disabled"
    created_at: datetime
    trace_digest: str | None = Field(default=None, pattern=DIGEST)

    @field_validator("created_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("trace time must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("accessed_dataset_references", "processing_references")
    @classmethod
    def ordered_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("trace references must be unique")
        return value

    @model_validator(mode="after")
    def bind_digest(self) -> "EffectFreeRunTrace":
        expected = canonical_digest(self.model_dump(mode="json", exclude={"trace_digest"}))
        if self.trace_digest is not None and self.trace_digest != expected:
            raise ValueError("trace_digest does not match canonical content")
        object.__setattr__(self, "trace_digest", expected)
        return self


def build_effect_free_trace(context: FixtureContext, *, created_at: datetime, trace_id: str | None = None) -> EffectFreeRunTrace:
    """Create the calibration trace with only declared, non-outcome inputs."""
    capability = context.reachable_capability_references[0]
    datasets = context.reachable_dataset_references
    processing = (context.object_set.authority_envelope.processing.reference,)
    return EffectFreeRunTrace(
        trace_id=trace_id or "fixture-trace-" + context.fixture_context_digest.removeprefix("sha256:")[:24],
        fixture_context_digest=context.fixture_context_digest,
        acceptance_reference=context.acceptance.reference,
        selected_capability_reference=capability,
        accessed_dataset_references=datasets,
        processing_references=processing,
        checkpoints=(
            RunTraceCheckpoint(checkpoint_id="context-verified", stage="context_verified", message="The accepted Fixture Context and authority boundary were verified."),
            RunTraceCheckpoint(checkpoint_id="capability-selected", stage="capability_selected", message=f"Selected declared capability {capability}; no other capability was available."),
            RunTraceCheckpoint(checkpoint_id="finding-recorded", stage="finding_recorded", message="Recorded an effect-free concentration-review observation from declared inputs only."),
            RunTraceCheckpoint(checkpoint_id="human-proposal", stage="human_proposal", message="Prepared a human review proposal; no portfolio action was attempted."),
        ),
        finding="The declared concentration-review inputs are available for inspection within the frozen calibration context.",
        uncertainty="This trace does not access forward labels, estimate risk-position accuracy, or establish any comparative performance claim.",
        human_proposal="Human reviewer: inspect the retained trace and decide whether the calibration fixture is suitable for the next bounded treatment implementation.",
        created_at=created_at,
    )
