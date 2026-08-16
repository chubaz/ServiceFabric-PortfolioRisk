"""Blocking simulated-time scheduler for event and daily-close workflows.

Replay time never advances while a processor is running. Wall-clock execution
continues and is retained in a receipt so acceleration cannot compress model or
capability latency into fictitious simulated minutes.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .models import IDENTIFIER, FrozenModel, canonical_digest


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("scheduler timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


class ReplayTrigger(FrozenModel):
    trigger_id: str = Field(pattern=IDENTIFIER)
    kind: Literal["event_available", "daily_close", "scheduled_cycle"]
    replay_at: datetime
    event_id: str | None = Field(default=None, pattern=IDENTIFIER)

    _replay_at = field_validator("replay_at")(_utc)

    @model_validator(mode="after")
    def event_trigger_has_event(self) -> "ReplayTrigger":
        if (self.kind == "event_available") != (self.event_id is not None):
            raise ValueError("only event-availability triggers identify an event")
        return self


class ReplayProcessingOutcome(FrozenModel):
    output_id: str = Field(pattern=IDENTIFIER)
    capability_calls: int = Field(default=0, ge=0)
    model_calls: int = Field(default=0, ge=0)
    capability_processing_ms: float = Field(default=0, ge=0)
    model_processing_ms: float = Field(default=0, ge=0)
    validation_processing_ms: float = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    pricing_reference: str | None = Field(default=None, max_length=512)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReplayProcessingReceipt(FrozenModel):
    receipt_id: str = Field(pattern=IDENTIFIER)
    trigger_id: str = Field(pattern=IDENTIFIER)
    trigger_kind: Literal["event_available", "daily_close", "scheduled_cycle"]
    event_id: str | None = Field(default=None, pattern=IDENTIFIER)
    replay_triggered_at: datetime
    replay_paused_at: datetime
    replay_resumed_at: datetime
    wall_started_at: datetime
    wall_completed_at: datetime
    processing_wall_ms: float = Field(ge=0)
    output_id: str = Field(pattern=IDENTIFIER)
    capability_calls: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    capability_processing_ms: float = Field(ge=0)
    model_processing_ms: float = Field(ge=0)
    validation_processing_ms: float = Field(ge=0)
    input_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    pricing_reference: str | None = Field(default=None, max_length=512)
    metadata: dict[str, Any] = Field(default_factory=dict)

    _timestamps = field_validator(
        "replay_triggered_at", "replay_paused_at", "replay_resumed_at",
        "wall_started_at", "wall_completed_at",
    )(_utc)

    @model_validator(mode="after")
    def clock_is_frozen_until_output(self) -> "ReplayProcessingReceipt":
        if not (
            self.replay_triggered_at == self.replay_paused_at == self.replay_resumed_at
        ):
            raise ValueError("replay time must remain frozen from trigger through output")
        if self.wall_completed_at < self.wall_started_at:
            raise ValueError("wall completion cannot precede wall start")
        measured = (self.wall_completed_at - self.wall_started_at).total_seconds() * 1000
        if abs(measured - self.processing_wall_ms) > 1.0:
            raise ValueError("processing_wall_ms must match wall timestamps")
        component_total = (
            self.capability_processing_ms
            + self.model_processing_ms
            + self.validation_processing_ms
        )
        if component_total > self.processing_wall_ms + 1.0:
            raise ValueError("processing components cannot exceed total blocked wall time")
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError("cached input tokens cannot exceed total input tokens")
        return self


class BlockingReplayScheduler:
    """Run chronological triggers without advancing simulated time in handlers."""

    def __init__(self) -> None:
        self.replay_at: datetime | None = None
        self.receipts: list[ReplayProcessingReceipt] = []

    def run(
        self,
        triggers: Iterable[ReplayTrigger],
        processor: Callable[[ReplayTrigger], ReplayProcessingOutcome],
    ) -> tuple[ReplayProcessingReceipt, ...]:
        ordered = sorted(triggers, key=lambda item: (item.replay_at, item.trigger_id))
        for trigger in ordered:
            if self.replay_at is not None and trigger.replay_at < self.replay_at:
                raise ValueError("replay triggers cannot move simulated time backwards")
            self.replay_at = trigger.replay_at
            wall_started = datetime.now(timezone.utc)
            outcome = processor(trigger)
            wall_completed = datetime.now(timezone.utc)
            wall_ms = (wall_completed - wall_started).total_seconds() * 1000
            component_values = (
                outcome.capability_processing_ms,
                outcome.model_processing_ms,
                outcome.validation_processing_ms,
            )
            component_total = sum(component_values)
            # Provider and graph-node timings can overlap.  Receipts retain exclusive
            # wall-time shares while preserving the reported aggregate in metadata.
            scale = min(1.0, wall_ms / component_total) if component_total else 1.0
            receipt_metadata = dict(outcome.metadata)
            if scale < 1.0:
                receipt_metadata["reported_component_ms"] = {
                    "capability": component_values[0], "model": component_values[1],
                    "validation": component_values[2], "overlap_reconciled": True,
                }
            receipt = ReplayProcessingReceipt(
                receipt_id=f"processing-{canonical_digest((trigger, outcome))[7:23]}",
                trigger_id=trigger.trigger_id,
                trigger_kind=trigger.kind,
                event_id=trigger.event_id,
                replay_triggered_at=trigger.replay_at,
                replay_paused_at=trigger.replay_at,
                replay_resumed_at=trigger.replay_at,
                wall_started_at=wall_started,
                wall_completed_at=wall_completed,
                processing_wall_ms=wall_ms,
                output_id=outcome.output_id,
                capability_calls=outcome.capability_calls,
                model_calls=outcome.model_calls,
                capability_processing_ms=component_values[0] * scale,
                model_processing_ms=component_values[1] * scale,
                validation_processing_ms=component_values[2] * scale,
                input_tokens=outcome.input_tokens,
                cached_input_tokens=outcome.cached_input_tokens,
                output_tokens=outcome.output_tokens,
                estimated_cost_usd=outcome.estimated_cost_usd,
                pricing_reference=outcome.pricing_reference,
                metadata=receipt_metadata,
            )
            self.receipts.append(receipt)
            # replay_at deliberately remains trigger.replay_at until the next trigger
        return tuple(self.receipts)
