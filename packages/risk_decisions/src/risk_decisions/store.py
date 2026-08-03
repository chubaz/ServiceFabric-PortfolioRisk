"""Symlink-safe, restart-safe local persistence for decision records."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

from .models import DecisionRecord


class DecisionConflict(ValueError):
    pass


class DecisionNotFound(KeyError):
    pass


class LocalDecisionStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().absolute()
        self.records = self.root / "records"
        self._thread_lock = threading.RLock()

    @staticmethod
    def _key(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _ensure_root(self) -> None:
        current = Path(self.root.anchor)
        for part in self.root.parts[1:]:
            current /= part
            if os.path.lexists(current) and current.is_symlink():
                raise DecisionConflict("decision storage path may not contain symbolic links")
        for directory in (self.root, self.records):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if directory.is_symlink() or not directory.resolve().is_relative_to(self.root.resolve()):
                raise DecisionConflict("decision storage must remain beneath its configured root")

    @contextmanager
    def _lock(self):  # type: ignore[no-untyped-def]
        with self._thread_lock:
            self._ensure_root()
            flags = os.O_RDWR | os.O_CREAT
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(self.root / ".decisions.lock", flags, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    def _path(self, proposal_id: str) -> Path:
        return self.records / f"{self._key(proposal_id)}.json"

    @staticmethod
    def _read(path: Path) -> bytes:
        if path.is_symlink():
            raise DecisionConflict("stored records may not be symbolic links")
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags)
        except FileNotFoundError as error:
            raise DecisionNotFound(path.stem) from error
        try:
            with os.fdopen(descriptor, "rb") as handle:
                descriptor = -1
                return handle.read()
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    @staticmethod
    def _write(path: Path, record: DecisionRecord, *, exclusive: bool = False) -> None:
        content = (json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode()
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
                raise DecisionConflict("stored records may not be symbolic links")
            if exclusive:
                try:
                    os.link(temporary, path, follow_symlinks=False)
                except FileExistsError as error:
                    raise DecisionConflict("decision proposal already exists") from error
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

    def create(self, record: DecisionRecord) -> DecisionRecord:
        with self._lock():
            path = self._path(record.proposal.proposal_id)
            if path.exists():
                current = DecisionRecord.model_validate_json(self._read(path))
                if current.proposal.proposal_digest == record.proposal.proposal_digest:
                    return current
                raise DecisionConflict("proposal ID already belongs to different content")
            self._write(path, record, exclusive=True)
        return record

    def get(self, proposal_id: str) -> DecisionRecord:
        return DecisionRecord.model_validate_json(self._read(self._path(proposal_id)))

    def list(self) -> tuple[DecisionRecord, ...]:
        self._ensure_root()
        values = [DecisionRecord.model_validate_json(self._read(path)) for path in self.records.glob("*.json")]
        return tuple(sorted(values, key=lambda item: item.proposal.created_at, reverse=True))

    def replace(self, record: DecisionRecord, *, expected_revision: str) -> DecisionRecord:
        with self._lock():
            path = self._path(record.proposal.proposal_id)
            current = DecisionRecord.model_validate_json(self._read(path))
            if current.record_revision != expected_revision:
                raise DecisionConflict("decision record changed; reload before acting")
            self._write(path, record)
        return record
