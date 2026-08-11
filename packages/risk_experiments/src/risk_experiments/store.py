"""Restart-safe local experiment metadata store and bounded queue projection."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .models import (
    ExperimentDefinition,
    ExperimentRecord,
    ExperimentSet,
    ExperimentState,
    LifecycleReceipt,
    PresentationMode,
    QueueEntry,
    TRANSITIONS,
    canonical_digest,
)


class ExperimentConflict(ValueError):
    pass


class ExperimentNotFound(KeyError):
    pass


class LocalExperimentStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().absolute()
        self.experiments = self.root / "experiments"
        self.sets = self.root / "sets"
        self.queue = self.root / "queue"
        self._thread_lock = threading.RLock()

    @staticmethod
    def _key(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _ensure_root(self) -> None:
        current = Path(self.root.anchor)
        for part in self.root.parts[1:]:
            current /= part
            if os.path.lexists(current) and current.is_symlink():
                raise ExperimentConflict("experiment storage path may not contain symbolic links")
        for directory in (self.root, self.experiments, self.sets, self.queue):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if directory.is_symlink() or not directory.resolve().is_relative_to(self.root.resolve()):
                raise ExperimentConflict("experiment storage must remain beneath its configured root")

    @contextmanager
    def _lock(self):  # type: ignore[no-untyped-def]
        with self._thread_lock:
            self._ensure_root()
            flags = os.O_RDWR | os.O_CREAT
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(self.root / ".experiments.lock", flags, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    @staticmethod
    def _read(path: Path) -> bytes:
        if path.is_symlink():
            raise ExperimentConflict("stored records may not be symbolic links")
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags)
        except FileNotFoundError as error:
            raise ExperimentNotFound(path.stem) from error
        try:
            with os.fdopen(descriptor, "rb") as handle:
                descriptor = -1
                return handle.read()
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    @staticmethod
    def _write(path: Path, value: object, *, exclusive: bool = False) -> None:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        content = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = -1
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            if path.is_symlink():
                raise ExperimentConflict("stored records may not be symbolic links")
            if exclusive:
                try:
                    os.link(temporary, path, follow_symlinks=False)
                except FileExistsError as error:
                    raise ExperimentConflict("immutable definition already exists") from error
            else:
                os.replace(temporary, path)
            directory_descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _experiment_path(self, experiment_id: str) -> Path:
        return self.experiments / f"{self._key(experiment_id)}.json"

    def _set_path(self, set_id: str) -> Path:
        return self.sets / f"{self._key(set_id)}.json"

    def _queue_path(self, queue_id: str) -> Path:
        return self.queue / f"{self._key(queue_id)}.json"

    def create(self, definition: ExperimentDefinition, *, actor: str, idempotency_key: str) -> ExperimentRecord:
        now = datetime.now(timezone.utc)
        receipt = LifecycleReceipt(
            experiment_id=definition.experiment_id,
            sequence=1,
            from_state=None,
            to_state=ExperimentState.DRAFT,
            actor=actor,
            rationale="Create immutable experiment definition.",
            occurred_at=now,
            idempotency_key=idempotency_key,
        )
        record = ExperimentRecord(definition=definition, receipts=(receipt,))
        with self._lock():
            path = self._experiment_path(definition.experiment_id)
            if path.exists():
                current = ExperimentRecord.model_validate_json(self._read(path))
                if current.definition.definition_digest == definition.definition_digest and any(
                    item.idempotency_key == idempotency_key for item in current.receipts
                ):
                    return current
                raise ExperimentConflict("experiment ID already exists")
            self._write(path, record, exclusive=True)
        return record

    def get(self, experiment_id: str) -> ExperimentRecord:
        return ExperimentRecord.model_validate_json(self._read(self._experiment_path(experiment_id)))

    def list(self) -> tuple[ExperimentRecord, ...]:
        self._ensure_root()
        records = [ExperimentRecord.model_validate_json(self._read(path)) for path in self.experiments.glob("*.json")]
        return tuple(sorted(records, key=lambda item: item.definition.created_at, reverse=True))

    def transition(self, experiment_id: str, to_state: ExperimentState, *, actor: str,
                   rationale: str, idempotency_key: str, expected_revision: str) -> ExperimentRecord:
        with self._lock():
            path = self._experiment_path(experiment_id)
            current = ExperimentRecord.model_validate_json(self._read(path))
            existing = next((item for item in current.receipts if item.idempotency_key == idempotency_key), None)
            if existing:
                if existing.to_state == to_state:
                    return current
                raise ExperimentConflict("idempotency key was used for another transition")
            if current.revision != expected_revision:
                raise ExperimentConflict("experiment revision changed; reload before acting")
            if to_state not in TRANSITIONS[current.state]:
                raise ExperimentConflict(f"cannot transition {current.state.value} to {to_state.value}")
            receipt = LifecycleReceipt(
                experiment_id=experiment_id,
                sequence=len(current.receipts) + 1,
                from_state=current.state,
                to_state=to_state,
                actor=actor,
                rationale=rationale,
                occurred_at=datetime.now(timezone.utc),
                idempotency_key=idempotency_key,
                prior_receipt_digest=current.revision,
            )
            updated = ExperimentRecord(definition=current.definition, receipts=(*current.receipts, receipt))
            self._write(path, updated)
            return updated

    def create_set(self, definition: ExperimentSet) -> ExperimentSet:
        with self._lock():
            missing = [item for item in definition.experiment_ids if not self._experiment_path(item).exists()]
            if missing:
                raise ExperimentConflict(f"experiment set contains unknown experiments: {', '.join(missing)}")
            path = self._set_path(definition.experiment_set_id)
            if path.exists():
                current = ExperimentSet.model_validate_json(self._read(path))
                if current.definition_digest == definition.definition_digest:
                    return current
                raise ExperimentConflict("experiment set ID already exists")
            self._write(path, definition, exclusive=True)
        return definition

    def list_sets(self) -> tuple[ExperimentSet, ...]:
        self._ensure_root()
        values = [ExperimentSet.model_validate_json(self._read(path)) for path in self.sets.glob("*.json")]
        return tuple(sorted(values, key=lambda item: item.created_at, reverse=True))

    def enqueue(self, experiment_id: str, *, actor: str, idempotency_key: str,
                expected_revision: str) -> tuple[ExperimentRecord, QueueEntry]:
        with self._lock():
            current = ExperimentRecord.model_validate_json(self._read(self._experiment_path(experiment_id)))
            existing_queue = [
                QueueEntry.model_validate_json(self._read(path)) for path in self.queue.glob("*.json")
            ]
            duplicate = next((item for item in existing_queue if item.idempotency_key == idempotency_key), None)
            if duplicate:
                if duplicate.experiment_id != experiment_id:
                    raise ExperimentConflict("queue idempotency key belongs to another experiment")
                return current, duplicate
            if current.state != ExperimentState.READY:
                raise ExperimentConflict("only ready experiments can be enqueued")
            if current.revision != expected_revision:
                raise ExperimentConflict("experiment revision changed; reload before enqueueing")
            job_kind = (
                "evaluate_existing_outputs"
                if current.definition.presentation_mode == PresentationMode.EVALUATION_ONLY
                else "workflow_replay"
            )
            now = datetime.now(timezone.utc)
            queue_id = f"queue-{self._key(experiment_id + ':' + idempotency_key)[:20]}"
            entry = QueueEntry(
                queue_id=queue_id,
                experiment_id=experiment_id,
                job_kind=job_kind,
                status="queued",
                idempotency_key=idempotency_key,
                enqueued_at=now,
                updated_at=now,
                resume_token=canonical_digest({"queue_id": queue_id, "definition": current.definition.definition_digest}),
                message=(
                    "Evaluation is queued against existing outputs; agent and workflow execution are disabled."
                    if job_kind == "evaluate_existing_outputs"
                    else "Replay is queued for an explicit local worker; no worker was started by admission."
                ),
            )
            receipt = LifecycleReceipt(
                experiment_id=experiment_id,
                sequence=len(current.receipts) + 1,
                from_state=current.state,
                to_state=ExperimentState.QUEUED,
                actor=actor,
                rationale="Admit the validated experiment to the bounded local queue.",
                occurred_at=now,
                idempotency_key=f"lifecycle-{idempotency_key}",
                prior_receipt_digest=current.revision,
            )
            updated = ExperimentRecord(definition=current.definition, receipts=(*current.receipts, receipt))
            self._write(self._experiment_path(experiment_id), updated)
            self._write(self._queue_path(queue_id), entry, exclusive=True)
            return updated, entry

    def queue_entries(self) -> tuple[QueueEntry, ...]:
        self._ensure_root()
        values = [QueueEntry.model_validate_json(self._read(path)) for path in self.queue.glob("*.json")]
        return tuple(sorted(values, key=lambda item: item.enqueued_at, reverse=True))

    def update_queue(self, queue_id: str, *, action: str, resume_token: str) -> tuple[ExperimentRecord, QueueEntry]:
        allowed = {
            ("queued", "start"): ("running", ExperimentState.RUNNING),
            ("running", "pause"): ("paused", ExperimentState.PAUSED_FOR_DECISION),
            ("paused", "resume"): ("running", ExperimentState.RUNNING),
            ("queued", "cancel"): ("cancelled", ExperimentState.CANCELLED),
            ("running", "cancel"): ("cancelled", ExperimentState.CANCELLED),
            ("paused", "cancel"): ("cancelled", ExperimentState.CANCELLED),
            ("running", "complete"): ("completed", ExperimentState.COMPLETED),
            ("running", "fail"): ("failed", ExperimentState.FAILED),
        }
        with self._lock():
            queue_path = self._queue_path(queue_id)
            entry = QueueEntry.model_validate_json(self._read(queue_path))
            if entry.resume_token != resume_token:
                raise ExperimentConflict("resume token does not match the queued job")
            desired_status = {
                "start": "running",
                "resume": "running",
                "pause": "paused",
                "cancel": "cancelled",
                "complete": "completed",
                "fail": "failed",
            }.get(action)
            if desired_status is None:
                raise ExperimentConflict(f"unknown queue action: {action}")
            current = ExperimentRecord.model_validate_json(
                self._read(self._experiment_path(entry.experiment_id))
            )
            if entry.status == desired_status:
                return current, entry
            target = allowed.get((entry.status, action))
            if target is None:
                raise ExperimentConflict(f"queue action {action} is invalid from {entry.status}")
            queue_status, experiment_state = target
            if current.state == experiment_state and entry.status == queue_status:
                return current, entry
            now = datetime.now(timezone.utc)
            lifecycle_key = f"queue-{queue_id}-{action}-{entry.attempt}"
            receipt = LifecycleReceipt(
                experiment_id=entry.experiment_id,
                sequence=len(current.receipts) + 1,
                from_state=current.state,
                to_state=experiment_state,
                actor="local.queue.controller",
                rationale=f"Queue control action: {action}.",
                occurred_at=now,
                idempotency_key=lifecycle_key,
                prior_receipt_digest=current.revision,
            )
            updated_record = ExperimentRecord(definition=current.definition, receipts=(*current.receipts, receipt))
            updated_entry = entry.model_copy(update={
                "status": queue_status,
                "updated_at": now,
                "message": f"Local queue state changed to {queue_status}; no external effects are available.",
            })
            self._write(self._experiment_path(entry.experiment_id), updated_record)
            self._write(queue_path, updated_entry)
            return updated_record, updated_entry
