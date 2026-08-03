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
        self.anchors_root = self.root / "anchors"
        self.pending_root = self.root / "pending"
        self.catalog_path = self.root / "catalog.json"
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

    def _anchors_path(self, identity: RegistryIdentity) -> Path:
        return self.anchors_root / self._key(identity)

    def _ensure_safe_root(self) -> None:
        current = Path(self.root.anchor)
        for part in self.root.parts[1:]:
            current /= part
            if os.path.lexists(current) and current.is_symlink():
                raise ValueError("registry path components may not be symbolic links")
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink():
            raise ValueError("registry root may not be a symbolic link")
        for directory in (
            self.records_root,
            self.projections_root,
            self.events_root,
            self.anchors_root,
            self.pending_root,
        ):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if directory.is_symlink():
                raise ValueError("registry data directories may not be symbolic links")
            if not directory.resolve().is_relative_to(self.root.resolve()):
                raise ValueError("registry data path escapes the configured registry root")

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
    def _write_exclusive_bytes(path: Path, value: bytes) -> None:
        """Durably stage bytes, then atomically link them to an unused final path."""

        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path.parent.is_symlink() or path.is_symlink():
            raise ValueError("registry immutable paths may not be symbolic links")
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}-", suffix=".tmp", dir=path.parent
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = -1
                handle.write(value)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o400)
            os.link(temporary, path, follow_symlinks=False)
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

    @staticmethod
    def _write_immutable(path: Path, value: RegistryProjection | LifecycleReceipt) -> None:
        """Create one source projection or lifecycle event without overwrite semantics."""

        LocalRegistryStore._write_exclusive_bytes(
            path, (value.model_dump_json(indent=2) + "\n").encode("utf-8")
        )

    @staticmethod
    def _write_immutable_text(path: Path, value: str) -> None:
        """Create an immutable plain-text integrity anchor."""

        LocalRegistryStore._write_exclusive_bytes(path, value.encode("utf-8"))

    @staticmethod
    def _catalog_digest(entries: dict[str, dict[str, str]]) -> str:
        payload = json.dumps(
            {"schema_version": "risk-registry-catalog/v1", "entries": entries},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _projection_digest(projection: RegistryProjection) -> str:
        return hashlib.sha256(
            projection.model_dump_json().encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _source_observation_digest(projection: RegistryProjection) -> str:
        value = projection.model_dump(mode="json")
        value["provenance"].pop("discovered_at", None)
        value["provenance"].pop("repository_commit", None)
        value["source"].pop("source_digest", None)
        payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(payload).hexdigest()

    def _read_catalog(self) -> dict[str, dict[str, str]]:
        if not self.catalog_path.exists():
            return {}
        if self.catalog_path.is_symlink():
            raise ValueError("registry catalogue may not be a symbolic link")
        try:
            value = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as error:
            raise RegistryConflict("registry catalogue is not readable") from error
        entries = value.get("entries") if isinstance(value, dict) else None
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != "risk-registry-catalog/v1"
            or not isinstance(entries, dict)
            or value.get("digest") != self._catalog_digest(entries)
        ):
            raise RegistryConflict("registry catalogue integrity verification failed")
        for reference, entry in entries.items():
            if (
                not isinstance(reference, str)
                or not isinstance(entry, dict)
                or set(entry) != {
                    "key",
                    "head_receipt_digest",
                    "projection_digest",
                }
                or not isinstance(entry["key"], str)
                or not isinstance(entry["head_receipt_digest"], str)
                or not isinstance(entry["projection_digest"], str)
                or len(entry["key"]) != 64
                or any(character not in "0123456789abcdef" for character in entry["key"])
                or len(entry["head_receipt_digest"]) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in entry["head_receipt_digest"]
                )
                or len(entry["projection_digest"]) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in entry["projection_digest"]
                )
            ):
                raise RegistryConflict("registry catalogue entry is invalid")
        return entries

    def _write_catalog(self, entries: dict[str, dict[str, str]]) -> None:
        self._ensure_safe_root()
        if self.catalog_path.exists() and self.catalog_path.is_symlink():
            raise ValueError("registry catalogue may not be a symbolic link")
        value = {
            "schema_version": "risk-registry-catalog/v1",
            "entries": entries,
            "digest": self._catalog_digest(entries),
        }
        descriptor, temporary = tempfile.mkstemp(
            prefix=".catalog-", suffix=".tmp", dir=self.root
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(value, indent=2, sort_keys=True))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.catalog_path)
            directory_descriptor = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _commit_catalog(self, documents: Iterable[RegistryDocument]) -> None:
        entries = self._read_catalog()
        updated = dict(entries)
        for document in documents:
            identity = document.projection.identity
            updated[identity.reference] = {
                "key": self._key(identity),
                "head_receipt_digest": document.receipts[-1].receipt_digest,
                "projection_digest": self._projection_digest(document.projection),
            }
        self._write_catalog(updated)

    @staticmethod
    def _pending_intent_digest(value: dict[str, object]) -> str:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _read_pending_intents(self) -> list[dict[str, object]]:
        if not self.pending_root.exists():
            return []
        if self.pending_root.is_symlink():
            raise ValueError("registry pending-intent directory may not be a symbolic link")
        intents: list[dict[str, object]] = []
        for path in sorted(self.pending_root.glob("*.json")):
            if path.is_symlink():
                raise ValueError("registry pending intent may not be a symbolic link")
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as error:
                raise RegistryConflict("registry pending intent is not readable") from error
            if not isinstance(value, dict):
                raise RegistryConflict("registry pending intent is invalid")
            digest = value.get("digest")
            intent = {key: item for key, item in value.items() if key != "digest"}
            references = intent.get("references")
            if (
                set(intent)
                != {
                    "schema_version",
                    "mode",
                    "references",
                    "observation_digests",
                    "actor",
                    "rationale",
                    "occurred_at",
                }
                or intent.get("schema_version") != "risk-registry-index-intent/v1"
                or intent.get("mode") not in {"single", "batch"}
                or not isinstance(references, list)
                or not references
                or any(not isinstance(reference, str) for reference in references)
                or references != sorted(set(references))
                or not isinstance(intent.get("observation_digests"), dict)
                or set(intent["observation_digests"]) != set(references)  # type: ignore[arg-type]
                or any(
                    not isinstance(digest_value, str)
                    or len(digest_value) != 64
                    or any(
                        character not in "0123456789abcdef"
                        for character in digest_value
                    )
                    for digest_value in intent["observation_digests"].values()  # type: ignore[union-attr]
                )
                or not isinstance(intent.get("actor"), str)
                or not isinstance(intent.get("rationale"), str)
                or (
                    intent.get("occurred_at") is not None
                    and not isinstance(intent.get("occurred_at"), str)
                )
                or not isinstance(digest, str)
                or digest != self._pending_intent_digest(intent)
                or path.name != f"{digest}.json"
            ):
                raise RegistryConflict("registry pending intent integrity verification failed")
            intents.append(value)
        return intents

    def _prepare_index_intent(
        self,
        projections: tuple[RegistryProjection, ...],
        *,
        mode: str,
        actor: str,
        rationale: str,
        occurred_at: datetime | None,
    ) -> None:
        if not actor or len(actor) > 128:
            raise ValueError("registry index actor must contain 1 to 128 characters")
        if len(rationale) < 3 or len(rationale) > 1200:
            raise ValueError("registry index rationale must contain 3 to 1200 characters")
        if occurred_at is not None and occurred_at.tzinfo is None:
            raise ValueError("registry index occurred_at must be timezone-aware")
        references = sorted(item.identity.reference for item in projections)
        catalog = self._read_catalog()
        timestamp = (
            occurred_at.astimezone(timezone.utc).isoformat()
            if occurred_at is not None
            else None
        )
        intent: dict[str, object] = {
            "schema_version": "risk-registry-index-intent/v1",
            "mode": mode,
            "references": references,
            "observation_digests": {
                item.identity.reference: self._source_observation_digest(item)
                for item in sorted(
                    projections, key=lambda projection: projection.identity.reference
                )
            },
            "actor": actor,
            "rationale": rationale,
            "occurred_at": timestamp,
        }
        requested = set(references)
        active: list[dict[str, object]] = []
        for candidate in self._read_pending_intents():
            candidate_references = set(candidate["references"])  # type: ignore[arg-type]
            if all(reference in catalog for reference in candidate_references):
                continue
            if requested & candidate_references:
                active.append(candidate)
        if active:
            expected = {**intent, "digest": self._pending_intent_digest(intent)}
            if len(active) != 1 or active[0] != expected:
                raise RegistryConflict(
                    "an interrupted index operation must be retried with its exact source set and intent"
                )
            return
        if all(reference in catalog for reference in references):
            return
        for projection in projections:
            events_path = self._events_path(projection.identity)
            if events_path.is_symlink():
                raise ValueError("registry events directory is not a safe contained path")
            if (
                projection.identity.reference not in catalog
                and (
                    self._projection_path(projection.identity).exists()
                    or events_path.exists()
                )
            ):
                raise RegistryConflict(
                    "uncommitted registry data has no matching pending operation intent"
                )
        digest = self._pending_intent_digest(intent)
        value = {**intent, "digest": digest}
        self._write_exclusive_bytes(
            self.pending_root / f"{digest}.json",
            (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )

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
        for sequence, event_path in enumerate(event_files, start=1):
            if event_path.name != f"{sequence:06d}.json":
                raise RegistryConflict(
                    "registry lifecycle event filenames must form a contiguous sequence"
                )
        receipts = tuple(self._read_receipt(path) for path in event_files)
        anchors_path = self._anchors_path(identity)
        if anchors_path.is_symlink() or not anchors_path.exists():
            raise RegistryConflict("registry lifecycle event stream has no safe integrity anchors")
        anchor_files = sorted(anchors_path.glob("*.sha256"))
        for anchor_path in anchor_files:
            try:
                sequence = int(anchor_path.stem)
                receipt = receipts[sequence - 1]
            except (ValueError, IndexError) as error:
                raise RegistryConflict(
                    "registry lifecycle integrity anchor has no matching event"
                ) from error
            if sequence < 1 or anchor_path.name != f"{sequence:06d}.sha256":
                raise RegistryConflict(
                    "registry lifecycle anchor filename is invalid"
                )
            if anchor_path.is_symlink():
                raise RegistryConflict("registry lifecycle integrity anchor is not safe")
            if anchor_path.read_text(encoding="utf-8").strip() != receipt.receipt_digest:
                raise RegistryConflict("registry lifecycle integrity anchor mismatch")
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
        anchors_path = self._anchors_path(document.projection.identity)
        anchors_path.mkdir(mode=0o700, parents=True, exist_ok=True)
        if anchors_path.is_symlink():
            raise ValueError("registry anchors directory may not be a symbolic link")
        for receipt in document.receipts:
            event_path = events_path / f"{receipt.sequence:06d}.json"
            if not event_path.exists():
                self._write_immutable(event_path, receipt)
            anchor_path = anchors_path / f"{receipt.sequence:06d}.sha256"
            if not anchor_path.exists():
                self._write_immutable_text(anchor_path, f"{receipt.receipt_digest}\n")

    def _committed_document(
        self,
        reconstructed: RegistryDocument,
        entry: dict[str, str],
    ) -> RegistryDocument:
        """Select the catalogue-committed prefix from a durable event stream."""

        if self._projection_digest(reconstructed.projection) != entry["projection_digest"]:
            raise RegistryConflict(
                "registry projection does not match its catalogue anchor"
            )
        committed_index = next(
            (
                index
                for index, receipt in enumerate(reconstructed.receipts)
                if receipt.receipt_digest == entry["head_receipt_digest"]
            ),
            None,
        )
        if committed_index is None:
            raise RegistryConflict(
                "registry lifecycle stream does not contain its committed catalogue head"
            )
        committed = RegistryDocument(
            projection=reconstructed.projection,
            receipts=reconstructed.receipts[: committed_index + 1],
        )
        anchors_path = self._anchors_path(reconstructed.projection.identity)
        for receipt in committed.receipts:
            anchor_path = anchors_path / f"{receipt.sequence:06d}.sha256"
            if not anchor_path.exists() or anchor_path.is_symlink():
                raise RegistryConflict(
                    "committed registry lifecycle receipt has no safe integrity anchor"
                )
            if anchor_path.read_text(encoding="utf-8").strip() != receipt.receipt_digest:
                raise RegistryConflict("registry lifecycle integrity anchor mismatch")
        snapshot_path = self._path(reconstructed.projection.identity)
        if snapshot_path.exists():
            snapshot = self._read_path(snapshot_path)
            if snapshot not in (committed, reconstructed):
                raise RegistryConflict(
                    "registry snapshot does not match its lifecycle event stream"
                )
        return committed

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
        # Scan time, repository checkout, and unrelated raw-file changes do not
        # alter the semantic definition selected by the adapter.
        return LocalRegistryStore._source_observation_digest(
            existing
        ) == LocalRegistryStore._source_observation_digest(discovered)

    def index(
        self,
        projection: RegistryProjection,
        *,
        actor: str,
        rationale: str = "Indexed an existing canonical definition.",
        occurred_at: datetime | None = None,
    ) -> RegistryDocument:
        with self._lock, self._mutation_lock():
            self._prepare_index_intent(
                (projection,),
                mode="single",
                actor=actor,
                rationale=rationale,
                occurred_at=occurred_at,
            )
            document = self._index_locked(
                projection,
                actor=actor,
                rationale=rationale,
                occurred_at=occurred_at,
            )
            self._commit_catalog((document,))
            return document

    def _index_locked(
        self,
        projection: RegistryProjection,
        *,
        actor: str,
        rationale: str,
        occurred_at: datetime | None,
    ) -> RegistryDocument:
        path = self._path(projection.identity)
        reconstructed = self._reconstruct(projection.identity)
        catalog_entry = self._read_catalog().get(projection.identity.reference)
        if reconstructed is not None and catalog_entry is not None:
            committed = self._committed_document(reconstructed, catalog_entry)
            if self._same_source_observation(committed.projection, projection):
                if not path.exists():
                    self._write(path, committed)
                return committed
            raise RegistryConflict(
                f"{projection.identity.reference} already exists with a different source observation"
            )
        if reconstructed is not None:
            receipt = reconstructed.receipts[-1]
            same_pending_request = (
                len(reconstructed.receipts) == 1
                and receipt.actor == actor
                and receipt.rationale == rationale
                and (
                    occurred_at is None
                    or receipt.occurred_at
                    == occurred_at.astimezone(timezone.utc)
                )
            )
            if not same_pending_request:
                raise RegistryConflict(
                    "an interrupted initial index must be retried exactly"
                )
            self._materialize_event_stream(reconstructed)
            if path.exists() and self._read_path(path) != reconstructed:
                raise RegistryConflict("registry snapshot does not match its lifecycle event stream")
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
        receipt = LifecycleReceipt.create(
            registry_reference=projection.identity.reference,
            sequence=1,
            from_state=None,
            to_state=LifecycleState.CANDIDATE,
            actor=actor,
            rationale=rationale,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            prior_receipt_digest=None,
        )
        document = RegistryDocument(projection=projection, receipts=(receipt,))
        events_path = self._events_path(projection.identity)
        events_path.mkdir(mode=0o700, parents=True, exist_ok=True)
        if events_path.is_symlink() or not events_path.resolve().is_relative_to(
            self.root.resolve()
        ):
            raise ValueError("registry events directory is not a safe contained path")
        anchors_path = self._anchors_path(projection.identity)
        anchors_path.mkdir(mode=0o700, parents=True, exist_ok=True)
        if anchors_path.is_symlink() or not anchors_path.resolve().is_relative_to(
            self.root.resolve()
        ):
            raise ValueError("registry anchors directory is not a safe contained path")
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
            events_path / "000001.json", receipt
        )
        self._write_immutable_text(
            anchors_path / "000001.sha256", f"{receipt.receipt_digest}\n"
        )
        self._write(path, document)
        return document

    def get(self, identity: RegistryIdentity) -> RegistryDocument:
        path = self._path(identity)
        with self._lock:
            entry = self._read_catalog().get(identity.reference)
            if entry is None:
                raise RegistryNotFound(identity.reference)
            if entry["key"] != self._key(identity):
                raise RegistryConflict("registry catalogue key does not match its identity")
            if path.exists() and path.is_symlink():
                raise ValueError("registry record may not be a symbolic link")
            reconstructed = self._reconstruct(identity)
            if reconstructed is not None:
                return self._committed_document(reconstructed, entry)
            raise RegistryConflict("committed registry lifecycle event stream is missing")

    def list(
        self,
        *,
        kind: AssetKind | None = None,
        state: LifecycleState | None = None,
        query: str | None = None,
    ) -> list[RegistryDocument]:
        with self._lock:
            entries = self._read_catalog()
            documents = []
            for reference, entry in entries.items():
                projection_path = self.projections_root / f"{entry['key']}.json"
                if not projection_path.exists():
                    raise RegistryConflict("committed registry projection is missing")
                projection = self._read_projection(projection_path)
                if projection.identity.reference != reference:
                    raise RegistryConflict("registry catalogue identity does not match projection")
                document = self._reconstruct(projection.identity)
                if document is None:
                    raise RegistryConflict("registry projection could not be reconstructed")
                documents.append(self._committed_document(document, entry))
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
        expected_revision: str | None = None,
        occurred_at: datetime | None = None,
    ) -> RegistryDocument:
        with self._lock, self._mutation_lock():
            current = self.get(identity)
            self._materialize_event_stream(current)
            if current.state is to_state:
                receipt = current.receipts[-1]
                same_completed_request = (
                    receipt.actor == actor
                    and receipt.rationale == rationale
                    and receipt.replacement_reference == replacement_reference
                    and (
                        occurred_at is None
                        or receipt.occurred_at
                        == occurred_at.astimezone(timezone.utc)
                    )
                )
                if same_completed_request:
                    return current
            if expected_revision is not None and expected_revision != current.receipts[-1].receipt_digest:
                raise RegistryConflict("registry item changed after it was reviewed")
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
            durable = self._reconstruct(identity)
            if durable is None:  # pragma: no cover - get() already proved it exists
                raise RegistryConflict("committed registry lifecycle event stream is missing")
            trailing = durable.receipts[len(current.receipts) :]
            if trailing:
                if len(trailing) != 1:
                    raise RegistryConflict(
                        "registry contains more than one uncommitted lifecycle receipt"
                    )
                receipt = trailing[0]
                same_request = (
                    receipt.from_state is current.state
                    and receipt.to_state is to_state
                    and receipt.actor == actor
                    and receipt.rationale == rationale
                    and receipt.replacement_reference == replacement_reference
                    and (
                        occurred_at is None
                        or receipt.occurred_at
                        == occurred_at.astimezone(timezone.utc)
                    )
                )
                if not same_request:
                    raise RegistryConflict(
                        "an interrupted lifecycle transition must be retried exactly"
                    )
                anchor_path = (
                    self._anchors_path(identity) / f"{receipt.sequence:06d}.sha256"
                )
                if not anchor_path.exists():
                    self._write_immutable_text(
                        anchor_path, f"{receipt.receipt_digest}\n"
                    )
                updated = durable
            else:
                receipt = LifecycleReceipt.create(
                    registry_reference=identity.reference,
                    sequence=len(current.receipts) + 1,
                    from_state=current.state,
                    to_state=to_state,
                    actor=actor,
                    rationale=rationale,
                    replacement_reference=replacement_reference,
                    occurred_at=occurred_at or datetime.now(timezone.utc),
                    prior_receipt_digest=current.receipts[-1].receipt_digest,
                )
                updated = RegistryDocument(
                    projection=current.projection,
                    receipts=(*current.receipts, receipt),
                )
                self._write_immutable(
                    self._events_path(identity) / f"{receipt.sequence:06d}.json",
                    receipt,
                )
                self._write_immutable_text(
                    self._anchors_path(identity) / f"{receipt.sequence:06d}.sha256",
                    f"{receipt.receipt_digest}\n",
                )
            self._write(self._path(identity), updated)
            self._commit_catalog((updated,))
            return updated

    def index_many(
        self, projections: Iterable[RegistryProjection], *, actor: str
    ) -> tuple[list[RegistryDocument], list[str]]:
        requested = tuple(projections)
        rationale = "Indexed as part of one prevalidated source bootstrap."
        if len({item.identity.reference for item in requested}) != len(requested):
            return [], ["bootstrap request contains duplicate identities"]
        with self._lock, self._mutation_lock():
            conflicts: list[str] = []
            for projection in requested:
                projection_path = self._projection_path(projection.identity)
                if projection_path.exists():
                    observed = self._read_projection(projection_path)
                    if not self._same_source_observation(observed, projection):
                        conflicts.append(
                            f"{projection.identity.reference} has a conflicting partial source projection"
                        )
                        continue
                try:
                    current = self.get(projection.identity)
                except RegistryNotFound:
                    continue
                if not self._same_source_observation(current.projection, projection):
                    conflicts.append(
                        f"{projection.identity.reference} already exists with a different source observation"
                    )
            if conflicts:
                return [], conflicts
            self._prepare_index_intent(
                requested,
                mode="batch",
                actor=actor,
                rationale=rationale,
                occurred_at=None,
            )
            indexed = [
                self._index_locked(
                    projection,
                    actor=actor,
                    rationale=rationale,
                    occurred_at=None,
                )
                for projection in requested
            ]
            self._commit_catalog(indexed)
            return indexed, []

    def preview_many(
        self, projections: Iterable[RegistryProjection]
    ) -> dict[str, object]:
        requested = tuple(projections)
        conflicts: list[str] = []
        existing = 0
        would_index = 0
        with self._lock:
            for projection in requested:
                try:
                    current = self.get(projection.identity)
                except RegistryNotFound:
                    would_index += 1
                    continue
                if self._same_source_observation(current.projection, projection):
                    existing += 1
                else:
                    conflicts.append(
                        f"{projection.identity.reference} already exists with a different source observation"
                    )
        return {
            "discovered": len(requested),
            "would_index": would_index,
            "already_indexed": existing,
            "conflicts": conflicts,
        }

    def compare(self, left: RegistryIdentity, right: RegistryIdentity) -> dict[str, object]:
        if (
            left.kind is not right.kind
            or left.namespace != right.namespace
            or left.asset_id != right.asset_id
        ):
            raise RegistryConflict("version comparison requires the same stable registry identity")
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
