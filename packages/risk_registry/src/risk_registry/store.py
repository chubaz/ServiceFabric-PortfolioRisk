"""Atomic, path-safe local persistence for registry projection documents."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import fcntl

from .models import (
    LIFECYCLE_TRANSITIONS,
    AssetKind,
    LifecycleReceipt,
    LifecycleState,
    RegistryDocument,
    RegistryIdentity,
    RegistryProjection,
)


class RegistryConflict(ValueError):
    """The requested operation conflicts with an immutable indexed record."""


class RegistryNotFound(KeyError):
    """No indexed record has the requested identity."""


class LocalRegistryStore:
    """Store bounded metadata documents outside Git; canonical sources stay put."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().absolute()
        self.records_root = self.root / "records"
        self.projections_root = self.root / "projections"
        self.events_root = self.root / "events"
        self._lock = threading.RLock()

    @staticmethod
    def _key(identity: RegistryIdentity) -> str:
        return hashlib.sha256(identity.reference.encode("utf-8")).hexdigest()

    def _path(self, identity: RegistryIdentity) -> Path:
        return self.records_root / f"{self._key(identity)}.json"

    def _projection_path(self, identity: RegistryIdentity) -> Path:
        return self.projections_root / f"{self._key(identity)}.json"

    def _events_path(self, identity: RegistryIdentity) -> Path:
        return self.events_root / self._key(identity)

    def _ensure_safe_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink():
            raise ValueError("registry root may not be a symbolic link")
        for directory in (self.records_root, self.projections_root, self.events_root):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if directory.is_symlink():
                raise ValueError("registry data directories may not be symbolic links")

    @contextmanager
    def _mutation_lock(self):  # type: ignore[no-untyped-def]
        self._ensure_safe_root()
        lock_path = self.root / ".registry.lock"
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _read_path(self, path: Path) -> RegistryDocument:
        if path.is_symlink():
            raise ValueError("registry record may not be a symbolic link")
        return RegistryDocument.model_validate_json(path.read_text(encoding="utf-8"))

    @staticmethod
    def _read_projection(path: Path) -> RegistryProjection:
        if path.is_symlink():
            raise ValueError("registry projection may not be a symbolic link")
        return RegistryProjection.model_validate_json(path.read_text(encoding="utf-8"))

    @staticmethod
    def _read_receipt(path: Path) -> LifecycleReceipt:
        if path.is_symlink():
            raise ValueError("registry lifecycle event may not be a symbolic link")
        return LifecycleReceipt.model_validate_json(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_immutable(path: Path, value: RegistryProjection | LifecycleReceipt) -> None:
        """Create one source projection or lifecycle event without overwrite semantics."""

        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path.parent.is_symlink() or path.is_symlink():
            raise ValueError("registry immutable paths may not be symbolic links")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o600)
        try:
            handle = os.fdopen(descriptor, "w", encoding="utf-8")
            descriptor = -1
            with handle:
                handle.write(value.model_dump_json(indent=2))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            directory_descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def _reconstruct(self, identity: RegistryIdentity) -> RegistryDocument | None:
        projection_path = self._projection_path(identity)
        if not projection_path.exists():
            return None
        projection = self._read_projection(projection_path)
        if projection.identity != identity:
            raise RegistryConflict("registry key collision detected")
        events_path = self._events_path(identity)
        if events_path.is_symlink():
            raise RegistryConflict("registry projection has no safe lifecycle event stream")
        if not events_path.exists():
            return None
        event_files = sorted(events_path.glob("*.json"))
        if not event_files:
            return None
        receipts = tuple(self._read_receipt(path) for path in event_files)
        return RegistryDocument(projection=projection, receipts=receipts)

    def _materialize_event_stream(self, document: RegistryDocument) -> None:
        """Upgrade a v1 aggregate-only record without changing its observations."""

        projection_path = self._projection_path(document.projection.identity)
        if not projection_path.exists():
            self._write_immutable(projection_path, document.projection)
        events_path = self._events_path(document.projection.identity)
        events_path.mkdir(mode=0o700, parents=True, exist_ok=True)
        if events_path.is_symlink():
            raise ValueError("registry events directory may not be a symbolic link")
        for receipt in document.receipts:
            event_path = events_path / f"{receipt.sequence:06d}.json"
            if not event_path.exists():
                self._write_immutable(event_path, receipt)

    def _write(self, path: Path, document: RegistryDocument) -> None:
        self._ensure_safe_root()
        if path.exists() and path.is_symlink():
            raise ValueError("registry record may not be a symbolic link")
        file_descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.stem}-", suffix=".tmp", dir=self.records_root
        )
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
                handle.write(document.model_dump_json(indent=2))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
            directory_descriptor = os.open(self.records_root, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _same_source_observation(
        existing: RegistryProjection, discovered: RegistryProjection
    ) -> bool:
        left = existing.model_dump(mode="json")
        right = discovered.model_dump(mode="json")
        # Discovery time records when each scan occurred. It does not change the
        # source observation and therefore must not defeat idempotent bootstrap.
        left["provenance"].pop("discovered_at", None)
        right["provenance"].pop("discovered_at", None)
        # A comment or unrelated sibling definition may change the raw source
        # file digest without changing this exact semantic definition. The
        # indexed observation stays immutable and the API reports source drift.
        left["source"].pop("source_digest", None)
        right["source"].pop("source_digest", None)
        return left == right

    def index(
        self,
        projection: RegistryProjection,
        *,
        actor: str,
        rationale: str = "Indexed an existing canonical definition.",
        occurred_at: datetime | None = None,
    ) -> RegistryDocument:
        path = self._path(projection.identity)
        with self._lock, self._mutation_lock():
            reconstructed = self._reconstruct(projection.identity)
            if reconstructed is not None:
                if self._same_source_observation(reconstructed.projection, projection):
                    if not path.exists():
                        self._write(path, reconstructed)
                    return reconstructed
                raise RegistryConflict(
                    f"{projection.identity.reference} already exists with a different source observation"
                )
            if path.exists():
                current = self._read_path(path)
                if self._same_source_observation(current.projection, projection):
                    self._materialize_event_stream(current)
                    return current
                raise RegistryConflict(
                    f"{projection.identity.reference} already exists with a different source observation"
                )
            receipt = LifecycleReceipt(
                sequence=1,
                from_state=None,
                to_state=LifecycleState.CANDIDATE,
                actor=actor,
                rationale=rationale,
                occurred_at=occurred_at or datetime.now(timezone.utc),
            )
            document = RegistryDocument(projection=projection, receipts=(receipt,))
            projection_path = self._projection_path(projection.identity)
            if projection_path.exists():
                observed = self._read_projection(projection_path)
                if not self._same_source_observation(observed, projection):
                    raise RegistryConflict(
                        f"{projection.identity.reference} has a conflicting partial source projection"
                    )
            else:
                self._write_immutable(projection_path, projection)
            self._write_immutable(
                self._events_path(projection.identity) / "000001.json", receipt
            )
            self._write(path, document)
            return document

    def get(self, identity: RegistryIdentity) -> RegistryDocument:
        path = self._path(identity)
        with self._lock:
            if path.exists() and path.is_symlink():
                raise ValueError("registry record may not be a symbolic link")
            reconstructed = self._reconstruct(identity)
            if reconstructed is not None:
                return reconstructed
            if not path.exists():
                raise RegistryNotFound(identity.reference)
            document = self._read_path(path)
            if document.projection.identity != identity:
                raise RegistryConflict("registry key collision detected")
            return document

    def list(
        self,
        *,
        kind: AssetKind | None = None,
        state: LifecycleState | None = None,
        query: str | None = None,
    ) -> list[RegistryDocument]:
        with self._lock:
            if not self.records_root.exists() and not self.projections_root.exists():
                return []
            keys = {
                path.stem
                for root in (self.records_root, self.projections_root)
                for path in root.glob("*.json")
            }
            documents = []
            for key in keys:
                projection_path = self.projections_root / f"{key}.json"
                if projection_path.exists():
                    projection = self._read_projection(projection_path)
                    document = self._reconstruct(projection.identity)
                    if document is None:  # pragma: no cover - guarded above
                        raise RegistryConflict("registry projection could not be reconstructed")
                    documents.append(document)
                else:
                    documents.append(self._read_path(self.records_root / f"{key}.json"))
        needle = (query or "").strip().casefold()
        selected = [
            item
            for item in documents
            if (kind is None or item.projection.identity.kind is kind)
            and (state is None or item.state is state)
            and (
                not needle
                or needle in item.projection.identity.asset_id.casefold()
                or needle in item.projection.display_name.casefold()
                or needle in item.projection.summary.casefold()
                or any(needle in tag.casefold() for tag in item.projection.tags)
            )
        ]
        return sorted(
            selected,
            key=lambda item: (
                item.projection.identity.kind.value,
                item.projection.display_name.casefold(),
                item.projection.identity.version,
            ),
        )

    def transition(
        self,
        identity: RegistryIdentity,
        to_state: LifecycleState,
        *,
        actor: str,
        rationale: str,
        replacement_reference: str | None = None,
        occurred_at: datetime | None = None,
    ) -> RegistryDocument:
        with self._lock, self._mutation_lock():
            current = self.get(identity)
            self._materialize_event_stream(current)
            if to_state not in LIFECYCLE_TRANSITIONS[current.state]:
                raise RegistryConflict(
                    f"invalid lifecycle transition: {current.state.value} -> {to_state.value}"
                )
            if to_state is LifecycleState.PUBLISHED:
                if not current.projection.source.canonical:
                    raise RegistryConflict(
                        "candidate source lacks a reusable canonical definition contract and cannot be published"
                    )
                if current.projection.compatibility.status != "compatible":
                    raise RegistryConflict(
                        "publication requires a compatible source observation"
                    )
            receipt = LifecycleReceipt(
                sequence=len(current.receipts) + 1,
                from_state=current.state,
                to_state=to_state,
                actor=actor,
                rationale=rationale,
                replacement_reference=replacement_reference,
                occurred_at=occurred_at or datetime.now(timezone.utc),
            )
            updated = RegistryDocument(
                projection=current.projection,
                receipts=(*current.receipts, receipt),
            )
            self._write_immutable(
                self._events_path(identity) / f"{receipt.sequence:06d}.json", receipt
            )
            self._write(self._path(identity), updated)
            return updated

    def index_many(
        self, projections: Iterable[RegistryProjection], *, actor: str
    ) -> tuple[list[RegistryDocument], list[str]]:
        indexed: list[RegistryDocument] = []
        conflicts: list[str] = []
        for projection in projections:
            try:
                indexed.append(self.index(projection, actor=actor))
            except RegistryConflict as error:
                conflicts.append(str(error))
        return indexed, conflicts

    def compare(self, left: RegistryIdentity, right: RegistryIdentity) -> dict[str, object]:
        left_document = self.get(left)
        right_document = self.get(right)
        left_value = left_document.projection.model_dump(mode="json")
        right_value = right_document.projection.model_dump(mode="json")
        fields = sorted(set(left_value) | set(right_value))
        differences = [
            {"field": field, "left": left_value.get(field), "right": right_value.get(field)}
            for field in fields
            if left_value.get(field) != right_value.get(field)
        ]
        return {
            "left": left_document,
            "right": right_document,
            "same_asset": left.asset_id == right.asset_id and left.kind is right.kind,
            "differences": differences,
        }
