"""Point-in-time trajectory execution over one previously compiled matrix cell."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
import threading
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .hierarchy import ArchitectureOutput
from .matched_runs import MatchedRunCell
from .models import DIGEST, IDENTIFIER, FrozenModel, canonical_digest
from .replay_scheduler import (
    BlockingReplayScheduler, ReplayProcessingOutcome, ReplayProcessingReceipt,
    ReplayTrigger,
)


class TrajectoryConflict(ValueError):
    pass


class TrajectoryNotFound(KeyError):
    pass


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("trajectory timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


class ReplayObservation(FrozenModel):
    # Provider-neutral evidence coordinates may legitimately contain colons
    # (for example CRSP snapshot:security:date identities). They are retained
    # verbatim and never used as filesystem paths.
    observation_id: str = Field(min_length=1, max_length=1000)
    kind: Literal["market", "fundamental", "event", "portfolio", "mandate", "derived"]
    observed_at: datetime
    available_at: datetime
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    content_reference: str = Field(min_length=3, max_length=1000)
    content_digest: str = Field(pattern=DIGEST)

    _observed = field_validator("observed_at")(_utc)
    _available = field_validator("available_at")(_utc)


class CycleContext(FrozenModel):
    run_id: str = Field(pattern=IDENTIFIER)
    cycle_id: str = Field(pattern=IDENTIFIER)
    case_id: str = Field(pattern=IDENTIFIER)
    architecture_id: str = Field(pattern=IDENTIFIER)
    replay_at: datetime
    trigger: ReplayTrigger
    eligible_observations: tuple[ReplayObservation, ...]
    previous_output_ids: tuple[str, ...]
    input_context_digest: str | None = Field(default=None, pattern=DIGEST)

    _replay = field_validator("replay_at")(_utc)

    @model_validator(mode="after")
    def context_is_point_in_time(self) -> "CycleContext":
        if self.trigger.replay_at != self.replay_at:
            raise ValueError("cycle time must equal trigger time")
        if any(item.available_at > self.replay_at for item in self.eligible_observations):
            raise ValueError("cycle context cannot contain future observations")
        ids = tuple(item.observation_id for item in self.eligible_observations)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("eligible observations must be unique and sorted")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"input_context_digest"}))
        if self.input_context_digest is not None and self.input_context_digest != expected:
            raise ValueError("cycle input digest does not match content")
        object.__setattr__(self, "input_context_digest", expected)
        return self


class CycleExecutionResult(FrozenModel):
    cycle_id: str = Field(pattern=IDENTIFIER)
    status: Literal["output", "abstained", "error"]
    architecture_output: ArchitectureOutput | None = None
    reason: str | None = Field(default=None, min_length=3, max_length=1500)
    capability_calls: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    capability_processing_ms: float = Field(ge=0)
    model_processing_ms: float = Field(ge=0)
    validation_processing_ms: float = Field(ge=0)
    input_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    pricing_reference: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def result_is_explicit(self) -> "CycleExecutionResult":
        if (self.status == "output") != (self.architecture_output is not None):
            raise ValueError("only a successful cycle may contain ArchitectureOutput")
        if self.status != "output" and not self.reason:
            raise ValueError("abstention and error cycles require a reason")
        if self.architecture_output is not None and self.architecture_output.cycle_id != self.cycle_id:
            raise ValueError("ArchitectureOutput must name the exact cycle")
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError("cached tokens cannot exceed input tokens")
        return self


class TrajectoryCycle(FrozenModel):
    context: CycleContext
    result: CycleExecutionResult
    processing_receipt: ReplayProcessingReceipt

    @model_validator(mode="after")
    def cycle_reconciles(self) -> "TrajectoryCycle":
        if self.context.cycle_id != self.result.cycle_id:
            raise ValueError("context and result must identify one cycle")
        output_id = (
            self.result.architecture_output.output_id
            if self.result.architecture_output is not None
            else f"{self.result.status}-{self.context.cycle_id}"
        )
        if self.processing_receipt.output_id != output_id:
            raise ValueError("processing receipt must reference the cycle outcome")
        if self.processing_receipt.replay_triggered_at != self.context.replay_at:
            raise ValueError("processing receipt must retain the frozen cycle time")
        return self


class RunTrajectory(FrozenModel):
    schema_version: Literal["portfolio-risk.run-trajectory/v1"] = "portfolio-risk.run-trajectory/v1"
    trajectory_id: str = Field(pattern=IDENTIFIER)
    matrix_id: str = Field(pattern=IDENTIFIER)
    cell_id: str = Field(pattern=IDENTIFIER)
    run_id: str = Field(pattern=IDENTIFIER)
    case_id: str = Field(pattern=IDENTIFIER)
    architecture_id: str = Field(pattern=IDENTIFIER)
    cycles: tuple[TrajectoryCycle, ...] = Field(min_length=1)
    started_at: datetime
    completed_at: datetime
    status: Literal["completed", "completed_with_abstentions", "failed"]
    total_model_calls: int = Field(ge=0)
    total_capability_calls: int = Field(ge=0)
    total_input_tokens: int = Field(ge=0)
    total_output_tokens: int = Field(ge=0)
    total_cost_usd: float = Field(ge=0)
    trajectory_digest: str | None = Field(default=None, pattern=DIGEST)

    _started = field_validator("started_at")(_utc)
    _completed = field_validator("completed_at")(_utc)

    @model_validator(mode="after")
    def trajectory_reconciles(self) -> "RunTrajectory":
        if self.completed_at < self.started_at:
            raise ValueError("trajectory completion cannot precede start")
        times = tuple(item.context.replay_at for item in self.cycles)
        if times != tuple(sorted(times)):
            raise ValueError("trajectory cycles must remain chronological")
        results = tuple(item.result for item in self.cycles)
        expected_status = (
            "failed" if any(item.status == "error" for item in results)
            else "completed_with_abstentions" if any(item.status == "abstained" for item in results)
            else "completed"
        )
        if self.status != expected_status:
            raise ValueError("trajectory status must reflect cycle results")
        totals = (
            sum(item.model_calls for item in results),
            sum(item.capability_calls for item in results),
            sum(item.input_tokens for item in results),
            sum(item.output_tokens for item in results),
            round(sum(item.estimated_cost_usd for item in results), 6),
        )
        declared = (
            self.total_model_calls, self.total_capability_calls, self.total_input_tokens,
            self.total_output_tokens, round(self.total_cost_usd, 6),
        )
        if totals != declared:
            raise ValueError("trajectory resource totals must reconcile to cycles")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"trajectory_digest"}))
        if self.trajectory_digest is not None and self.trajectory_digest != expected:
            raise ValueError("trajectory digest does not match content")
        object.__setattr__(self, "trajectory_digest", expected)
        return self


def execute_point_in_time_trajectory(
    *, matrix_id: str, cell: MatchedRunCell, triggers: tuple[ReplayTrigger, ...],
    observations: tuple[ReplayObservation, ...],
    processor: Callable[[CycleContext], CycleExecutionResult],
) -> RunTrajectory:
    """Execute one cell while the scheduler freezes replay time in each processor."""
    if not triggers:
        raise TrajectoryConflict("at least one workflow-cycle trigger is required")
    run_id = f"run-{canonical_digest({'matrix': matrix_id, 'cell': cell.cell_id})[7:31]}"
    cycles: list[TrajectoryCycle] = []
    previous_output_ids: list[str] = []
    scheduler = BlockingReplayScheduler()
    started_at = datetime.now(timezone.utc)

    def process(trigger: ReplayTrigger) -> ReplayProcessingOutcome:
        eligible = tuple(sorted(
            (item for item in observations if item.available_at <= trigger.replay_at),
            key=lambda item: item.observation_id,
        ))
        cycle_id = f"cycle-{canonical_digest({'run': run_id, 'trigger': trigger.trigger_id})[7:31]}"
        context = CycleContext(
            run_id=run_id, cycle_id=cycle_id, case_id=cell.run_input.case_id,
            architecture_id=cell.architecture.architecture_id, replay_at=trigger.replay_at,
            trigger=trigger, eligible_observations=eligible,
            previous_output_ids=tuple(previous_output_ids),
        )
        result = processor(context)
        if result.cycle_id != cycle_id:
            raise TrajectoryConflict("processor returned a result for a different cycle")
        output_id = (
            result.architecture_output.output_id
            if result.architecture_output is not None else f"{result.status}-{cycle_id}"
        )
        if result.architecture_output is not None:
            output = result.architecture_output
            if output.run_id != run_id or output.case_id != cell.run_input.case_id:
                raise TrajectoryConflict("ArchitectureOutput must bind to the exact Run and Case")
            if output.architecture_id != cell.architecture.architecture_id:
                raise TrajectoryConflict("ArchitectureOutput must bind to the planned architecture")
            if output.as_of != trigger.replay_at or output.input_context_digest != context.input_context_digest:
                raise TrajectoryConflict("ArchitectureOutput must bind to the exact point-in-time context")
            previous_output_ids.append(output.output_id)
        process.pending = (context, result)  # type: ignore[attr-defined]
        return ReplayProcessingOutcome(
            output_id=output_id, capability_calls=result.capability_calls,
            model_calls=result.model_calls,
            capability_processing_ms=result.capability_processing_ms,
            model_processing_ms=result.model_processing_ms,
            validation_processing_ms=result.validation_processing_ms,
            input_tokens=result.input_tokens, cached_input_tokens=result.cached_input_tokens,
            output_tokens=result.output_tokens, estimated_cost_usd=result.estimated_cost_usd,
            pricing_reference=result.pricing_reference,
            metadata={"cycle_id": cycle_id, "status": result.status},
        )

    for trigger in sorted(triggers, key=lambda item: (item.replay_at, item.trigger_id)):
        receipt = scheduler.run((trigger,), process)[-1]
        context, result = process.pending  # type: ignore[attr-defined]
        cycles.append(TrajectoryCycle(context=context, result=result, processing_receipt=receipt))
        if result.status == "error":
            break
    completed_at = datetime.now(timezone.utc)
    results = tuple(item.result for item in cycles)
    status = (
        "failed" if any(item.status == "error" for item in results)
        else "completed_with_abstentions" if any(item.status == "abstained" for item in results)
        else "completed"
    )
    identity = canonical_digest({"matrix": matrix_id, "cell": cell.cell_id, "run": run_id})
    return RunTrajectory(
        trajectory_id=f"trajectory-{identity[7:31]}", matrix_id=matrix_id,
        cell_id=cell.cell_id, run_id=run_id, case_id=cell.run_input.case_id,
        architecture_id=cell.architecture.architecture_id, cycles=tuple(cycles),
        started_at=started_at, completed_at=completed_at, status=status,
        total_model_calls=sum(item.model_calls for item in results),
        total_capability_calls=sum(item.capability_calls for item in results),
        total_input_tokens=sum(item.input_tokens for item in results),
        total_output_tokens=sum(item.output_tokens for item in results),
        total_cost_usd=round(sum(item.estimated_cost_usd for item in results), 6),
    )


class LocalTrajectoryStore:
    """Immutable retained trajectories; presentation artifacts remain elsewhere."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().absolute()
        self.trajectories = self.root / "run-trajectories"
        self._thread_lock = threading.RLock()

    @contextmanager
    def _lock(self):  # type: ignore[no-untyped-def]
        with self._thread_lock:
            self.trajectories.mkdir(mode=0o700, parents=True, exist_ok=True)
            if self.trajectories.is_symlink() or not self.trajectories.resolve().is_relative_to(self.root.resolve()):
                raise TrajectoryConflict("trajectory storage must remain beneath its root")
            flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(self.root / ".trajectories.lock", flags, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    def _path(self, trajectory_id: str) -> Path:
        key = hashlib.sha256(trajectory_id.encode()).hexdigest()
        return self.trajectories / f"{key}.json"

    def save(self, trajectory: RunTrajectory) -> RunTrajectory:
        with self._lock():
            path = self._path(trajectory.trajectory_id)
            if path.exists():
                existing = RunTrajectory.model_validate_json(path.read_text(encoding="utf-8"))
                if existing.trajectory_digest == trajectory.trajectory_digest:
                    return existing
                raise TrajectoryConflict("trajectory identity already exists with different content")
            descriptor, temporary = tempfile.mkstemp(prefix=".trajectory-", suffix=".json", dir=path.parent)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    json.dump(trajectory.model_dump(mode="json"), handle, sort_keys=True, separators=(",", ":"))
                    handle.flush(); os.fsync(handle.fileno())
                os.chmod(temporary, 0o600); os.replace(temporary, path)
            finally:
                if os.path.exists(temporary): os.unlink(temporary)
            return trajectory

    def get(self, trajectory_id: str) -> RunTrajectory:
        with self._lock():
            path = self._path(trajectory_id)
            if not path.exists(): raise TrajectoryNotFound(trajectory_id)
            if path.is_symlink(): raise TrajectoryConflict("trajectory may not be a symbolic link")
            return RunTrajectory.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> tuple[RunTrajectory, ...]:
        """Return retained trajectories without exposing storage filenames."""
        with self._lock():
            values: list[RunTrajectory] = []
            for path in sorted(self.trajectories.glob("*.json")):
                if path.is_symlink():
                    raise TrajectoryConflict("trajectory may not be a symbolic link")
                values.append(RunTrajectory.model_validate_json(path.read_text(encoding="utf-8")))
            return tuple(sorted(values, key=lambda item: (item.started_at, item.trajectory_id)))
