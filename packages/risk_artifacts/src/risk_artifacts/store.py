"""Path-safe immutable artifact bytes with governed metadata lifecycle."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat as stat_module
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping

from .models import (
    ArtifactLifecycleState,
    ArtifactManifest,
    ArtifactRecord,
    DeletionPreview,
    IntegrityVerification,
    LifecycleReceipt,
    PublicationState,
    RetentionClass,
)


class ArtifactConflict(ValueError):
    """Requested mutation conflicts with immutable repository state."""


class ArtifactNotFound(KeyError):
    """Artifact or declared file is unavailable."""


def _sha256(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _json_bytes(value: object) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


class LocalArtifactRepository:
    """Local development repository; canonical business meaning stays at source."""

    RECOVERY_DAYS = 7

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().absolute()
        self.blobs_root = self.root / "blobs" / "sha256"
        self.manifests_root = self.root / "manifests"
        self.events_root = self.root / "events"
        self.anchors_root = self.root / "anchors"
        self.intents_root = self.root / "intents"
        self.catalog_path = self.root / "catalog.json"
        self._lock = threading.RLock()

    @staticmethod
    def _key(artifact_id: str) -> str:
        return hashlib.sha256(artifact_id.encode("utf-8")).hexdigest()

    def _manifest_path(self, artifact_id: str) -> Path:
        return self.manifests_root / f"{self._key(artifact_id)}.json"

    def _event_dir(self, artifact_id: str) -> Path:
        return self.events_root / self._key(artifact_id)

    def _anchor_dir(self, artifact_id: str) -> Path:
        return self.anchors_root / self._key(artifact_id)

    def _intent_path(self, artifact_id: str, sequence: int = 1) -> Path:
        return self.intents_root / f"{self._key(artifact_id)}-{sequence:08d}.json"

    def _blob_path(self, digest: str) -> Path:
        if not digest.startswith("sha256:") or len(digest) != 71:
            raise ValueError("invalid content digest")
        value = digest[7:]
        if any(character not in "0123456789abcdef" for character in value):
            raise ValueError("invalid content digest")
        return self.blobs_root / value[:2] / value

    def _ensure_safe_root(self) -> None:
        current = Path(self.root.anchor)
        for part in self.root.parts[1:]:
            current /= part
            if os.path.lexists(current) and current.is_symlink():
                raise ValueError("artifact repository path components may not be symbolic links")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        for directory in (
            self.blobs_root,
            self.manifests_root,
            self.events_root,
            self.anchors_root,
            self.intents_root,
        ):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if directory.is_symlink() or not directory.resolve().is_relative_to(self.root.resolve()):
                raise ValueError("artifact repository directories must remain beneath the configured root")

    @contextmanager
    def _mutation_lock(self):  # type: ignore[no-untyped-def]
        with self._lock:
            self._ensure_safe_root()
            lock_path = self.root / ".artifacts.lock"
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

    @staticmethod
    def _write_exclusive(path: Path, content: bytes) -> None:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path.parent.is_symlink() or path.is_symlink():
            raise ValueError("immutable artifact paths may not be symbolic links")
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = -1
                handle.write(content)
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
    def _safe_read(path: Path, *, label: str) -> bytes:
        if path.is_symlink():
            raise ArtifactConflict(f"{label} may not be a symbolic link")
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags)
        except FileNotFoundError as error:
            raise ArtifactNotFound(str(path.name)) from error
        try:
            stat_result = os.fstat(descriptor)
            if not stat_module.S_ISREG(stat_result.st_mode) or stat_result.st_nlink < 1:
                raise ArtifactConflict(f"{label} is not a regular file")
            with os.fdopen(descriptor, "rb") as handle:
                descriptor = -1
                return handle.read()
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    @staticmethod
    def _catalog_digest(entries: dict[str, dict[str, str]]) -> str:
        content = json.dumps(
            {"schema_version": "portfolio-risk.artifact-catalog/v1", "entries": entries},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return _sha256(content)

    def _read_catalog(self) -> dict[str, dict[str, str]]:
        self._ensure_safe_root()
        if not self.catalog_path.exists():
            return {}
        raw = self._safe_read(self.catalog_path, label="artifact catalog")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ArtifactConflict("artifact catalog is not valid JSON") from error
        entries = value.get("entries") if isinstance(value, dict) else None
        if (
            not isinstance(entries, dict)
            or value.get("schema_version") != "portfolio-risk.artifact-catalog/v1"
            or value.get("digest") != self._catalog_digest(entries)
        ):
            raise ArtifactConflict("artifact catalog integrity verification failed")
        required = {"key", "manifest_digest", "head_receipt_digest", "state"}
        for artifact_id, entry in entries.items():
            if not isinstance(artifact_id, str) or not isinstance(entry, dict) or set(entry) != required:
                raise ArtifactConflict("artifact catalog entry is invalid")
            if entry["key"] != self._key(artifact_id):
                raise ArtifactConflict("artifact catalog identity is inconsistent")
            if entry["state"] not in {item.value for item in ArtifactLifecycleState}:
                raise ArtifactConflict("artifact catalog lifecycle state is invalid")
            for field in ("manifest_digest", "head_receipt_digest"):
                value_digest = entry[field]
                if not isinstance(value_digest, str) or not value_digest.startswith("sha256:") or len(value_digest) != 71:
                    raise ArtifactConflict("artifact catalog digest is invalid")
        return entries

    def _write_catalog(self, entries: dict[str, dict[str, str]]) -> None:
        value = {
            "schema_version": "portfolio-risk.artifact-catalog/v1",
            "entries": entries,
            "digest": self._catalog_digest(entries),
        }
        descriptor, temporary = tempfile.mkstemp(prefix=".catalog-", suffix=".tmp", dir=self.root)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = -1
                handle.write(_json_bytes(value))
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            if self.catalog_path.is_symlink():
                raise ValueError("artifact catalog may not be a symbolic link")
            os.replace(temporary, self.catalog_path)
            directory_descriptor = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _read_manifest(self, artifact_id: str) -> ArtifactManifest:
        return ArtifactManifest.model_validate_json(
            self._safe_read(self._manifest_path(artifact_id), label="artifact manifest")
        )

    def _read_receipts(self, artifact_id: str, head: str) -> tuple[LifecycleReceipt, ...]:
        event_dir = self._event_dir(artifact_id)
        anchor_dir = self._anchor_dir(artifact_id)
        if event_dir.is_symlink() or anchor_dir.is_symlink():
            raise ArtifactConflict("artifact receipt directories may not be symbolic links")
        receipts: list[LifecycleReceipt] = []
        previous: str | None = None
        sequence = 1
        while True:
            event_path = event_dir / f"{sequence:08d}.json"
            anchor_path = anchor_dir / f"{sequence:08d}.sha256"
            if not event_path.exists() and not anchor_path.exists():
                break
            if not event_path.exists() or not anchor_path.exists():
                raise ArtifactConflict("artifact receipt event and anchor are incomplete")
            receipt = LifecycleReceipt.model_validate_json(self._safe_read(event_path, label="artifact receipt"))
            anchored = self._safe_read(anchor_path, label="artifact receipt anchor").decode("ascii").strip()
            if receipt.sequence != sequence or receipt.previous_receipt_digest != previous:
                raise ArtifactConflict("artifact receipt chain is inconsistent")
            if receipt.receipt_digest != anchored:
                raise ArtifactConflict("artifact receipt anchor mismatch")
            receipts.append(receipt)
            previous = receipt.receipt_digest
            if previous == head:
                break
            sequence += 1
        if not receipts or receipts[-1].receipt_digest != head:
            raise ArtifactConflict("artifact receipt head is unavailable")
        return tuple(receipts)

    def get(self, artifact_id: str) -> ArtifactRecord:
        entries = self._read_catalog()
        entry = entries.get(artifact_id)
        if entry is None:
            raise ArtifactNotFound(artifact_id)
        manifest = self._read_manifest(artifact_id)
        if manifest.artifact_id != artifact_id or _sha256(_json_bytes(manifest)) != entry["manifest_digest"]:
            raise ArtifactConflict("artifact manifest does not match the committed catalog")
        receipts = self._read_receipts(artifact_id, entry["head_receipt_digest"])
        record = ArtifactRecord(manifest=manifest, receipts=receipts)
        if record.state.value != entry["state"]:
            raise ArtifactConflict("artifact lifecycle state does not match the catalog")
        return record

    def list(self, *, include_deleted: bool = False) -> tuple[ArtifactRecord, ...]:
        records = []
        for artifact_id, entry in sorted(self._read_catalog().items()):
            if not include_deleted and entry["state"] == ArtifactLifecycleState.DELETED.value:
                continue
            records.append(self.get(artifact_id))
        return tuple(records)

    def _intent_value(
        self,
        manifest: ArtifactManifest,
        actor: str,
        rationale: str,
        occurred_at: datetime,
    ) -> dict[str, str]:
        return {
            "schema_version": "portfolio-risk.artifact-admission-intent/v1",
            "artifact_id": manifest.artifact_id,
            "manifest_digest": _sha256(_json_bytes(manifest)),
            "actor": actor,
            "rationale": rationale,
            "occurred_at": occurred_at.isoformat(),
        }

    def admit(
        self,
        manifest: ArtifactManifest,
        files: Mapping[str, bytes],
        *,
        actor: str,
        rationale: str = "Admitted after explicit repository validation.",
        occurred_at: datetime | None = None,
    ) -> ArtifactRecord:
        if set(files) != {item.path for item in manifest.files}:
            raise ArtifactConflict("admission bytes must exactly match the declared file inventory")
        for item in manifest.files:
            content = files[item.path]
            if len(content) != item.size_bytes or _sha256(content) != item.content_digest:
                raise ArtifactConflict(f"declared digest or size mismatch for {item.path}")
        with self._mutation_lock():
            entries = self._read_catalog()
            existing = entries.get(manifest.artifact_id)
            if existing is not None:
                record = self.get(manifest.artifact_id)
                if existing["manifest_digest"] == _sha256(_json_bytes(manifest)):
                    return record
                raise ArtifactConflict("artifact identity already has different immutable content")
            intent_path = self._intent_path(manifest.artifact_id)
            if intent_path.exists():
                observed = json.loads(self._safe_read(intent_path, label="admission intent"))
                if occurred_at is None:
                    occurred_at = datetime.fromisoformat(observed["occurred_at"])
                occurred_at = occurred_at.astimezone(timezone.utc)
                intent = self._intent_value(manifest, actor, rationale, occurred_at)
                if observed != intent:
                    raise ArtifactConflict("an interrupted admission has different source or actor")
            else:
                occurred_at = (occurred_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
                intent = self._intent_value(manifest, actor, rationale, occurred_at)
                self._write_exclusive(intent_path, _json_bytes(intent))
            for item in manifest.files:
                blob = self._blob_path(item.content_digest)
                if blob.exists():
                    existing_bytes = self._safe_read(blob, label="artifact blob")
                    if len(existing_bytes) != item.size_bytes or _sha256(existing_bytes) != item.content_digest:
                        raise ArtifactConflict("existing content-addressed blob is inconsistent")
                else:
                    self._write_exclusive(blob, files[item.path])
            manifest_path = self._manifest_path(manifest.artifact_id)
            if manifest_path.exists():
                existing_manifest = self._safe_read(manifest_path, label="artifact manifest")
                if _sha256(existing_manifest) != intent["manifest_digest"]:
                    raise ArtifactConflict("interrupted artifact manifest differs from retry")
            else:
                self._write_exclusive(manifest_path, _json_bytes(manifest))
            receipt = LifecycleReceipt(
                artifact_id=manifest.artifact_id,
                sequence=1,
                operation="admit",
                from_state=None,
                to_state=ArtifactLifecycleState.ACTIVE,
                actor=actor,
                rationale=rationale,
                occurred_at=occurred_at,
            )
            event_path = self._event_dir(manifest.artifact_id) / "00000001.json"
            anchor_path = self._anchor_dir(manifest.artifact_id) / "00000001.sha256"
            event_bytes = _json_bytes(receipt)
            anchor_bytes = ((receipt.receipt_digest or "") + "\n").encode("ascii")
            if event_path.exists():
                if self._safe_read(event_path, label="artifact receipt") != event_bytes:
                    raise ArtifactConflict("interrupted admission receipt differs from retry")
            else:
                self._write_exclusive(event_path, event_bytes)
            if anchor_path.exists():
                if self._safe_read(anchor_path, label="artifact receipt anchor") != anchor_bytes:
                    raise ArtifactConflict("interrupted admission anchor differs from retry")
            else:
                self._write_exclusive(anchor_path, anchor_bytes)
            updated = dict(entries)
            updated[manifest.artifact_id] = {
                "key": self._key(manifest.artifact_id),
                "manifest_digest": intent["manifest_digest"],
                "head_receipt_digest": receipt.receipt_digest or "",
                "state": ArtifactLifecycleState.ACTIVE.value,
            }
            self._write_catalog(updated)
            return self.get(manifest.artifact_id)

    def _append_receipt(
        self,
        record: ArtifactRecord,
        *,
        operation: str,
        to_state: ArtifactLifecycleState,
        actor: str,
        rationale: str,
        expected_revision: str,
        occurred_at: datetime,
        recovery_until: datetime | None = None,
    ) -> ArtifactRecord:
        if record.revision != expected_revision:
            raise ArtifactConflict("artifact changed after it was reviewed")
        sequence = len(record.receipts) + 1
        intent_path = self._intent_path(record.manifest.artifact_id, sequence)
        if intent_path.exists():
            intent = json.loads(self._safe_read(intent_path, label="lifecycle intent"))
            requested = {
                "schema_version": "portfolio-risk.artifact-lifecycle-intent/v1",
                "artifact_id": record.manifest.artifact_id,
                "sequence": sequence,
                "operation": operation,
                "from_state": record.state.value,
                "to_state": to_state.value,
                "actor": actor,
                "rationale": rationale,
                "expected_revision": expected_revision,
            }
            if any(intent.get(key) != value for key, value in requested.items()):
                raise ArtifactConflict("an interrupted lifecycle operation must be retried exactly")
            occurred_at = datetime.fromisoformat(intent["occurred_at"])
            recovery_until = (
                datetime.fromisoformat(intent["recovery_until"])
                if intent.get("recovery_until")
                else None
            )
        else:
            intent = {
                "schema_version": "portfolio-risk.artifact-lifecycle-intent/v1",
                "artifact_id": record.manifest.artifact_id,
                "sequence": sequence,
                "operation": operation,
                "from_state": record.state.value,
                "to_state": to_state.value,
                "actor": actor,
                "rationale": rationale,
                "expected_revision": expected_revision,
                "occurred_at": occurred_at.isoformat(),
                "recovery_until": recovery_until.isoformat() if recovery_until else None,
            }
            self._write_exclusive(intent_path, _json_bytes(intent))
        receipt = LifecycleReceipt(
            artifact_id=record.manifest.artifact_id,
            sequence=sequence,
            operation=operation,
            from_state=record.state,
            to_state=to_state,
            actor=actor,
            rationale=rationale,
            occurred_at=occurred_at,
            recovery_until=recovery_until,
            previous_receipt_digest=record.revision,
        )
        name = f"{receipt.sequence:08d}"
        event_path = self._event_dir(record.manifest.artifact_id) / f"{name}.json"
        anchor_path = self._anchor_dir(record.manifest.artifact_id) / f"{name}.sha256"
        event_bytes = _json_bytes(receipt)
        anchor_bytes = ((receipt.receipt_digest or "") + "\n").encode("ascii")
        if event_path.exists():
            if self._safe_read(event_path, label="artifact receipt") != event_bytes:
                raise ArtifactConflict("interrupted lifecycle receipt differs from retry")
        else:
            self._write_exclusive(event_path, event_bytes)
        if anchor_path.exists():
            if self._safe_read(anchor_path, label="artifact receipt anchor") != anchor_bytes:
                raise ArtifactConflict("interrupted lifecycle anchor differs from retry")
        else:
            self._write_exclusive(anchor_path, anchor_bytes)
        entries = self._read_catalog()
        entry = dict(entries[record.manifest.artifact_id])
        entry["head_receipt_digest"] = receipt.receipt_digest or ""
        entry["state"] = to_state.value
        updated = dict(entries)
        updated[record.manifest.artifact_id] = entry
        self._write_catalog(updated)
        return self.get(record.manifest.artifact_id)

    def transition(
        self,
        artifact_id: str,
        *,
        to_state: ArtifactLifecycleState,
        actor: str,
        rationale: str,
        expected_revision: str,
        occurred_at: datetime | None = None,
    ) -> ArtifactRecord:
        occurred_at = (occurred_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        allowed = {
            (ArtifactLifecycleState.ACTIVE, ArtifactLifecycleState.ARCHIVED): "archive",
            (ArtifactLifecycleState.ARCHIVED, ArtifactLifecycleState.ACTIVE): "restore",
        }
        with self._mutation_lock():
            record = self.get(artifact_id)
            operation = allowed.get((record.state, to_state))
            if operation is None:
                raise ArtifactConflict("requested artifact lifecycle transition is not allowed")
            return self._append_receipt(
                record,
                operation=operation,
                to_state=to_state,
                actor=actor,
                rationale=rationale,
                expected_revision=expected_revision,
                occurred_at=occurred_at,
            )

    def verify(self, artifact_id: str) -> IntegrityVerification:
        record = self.get(artifact_id)
        if record.state == ArtifactLifecycleState.DELETED:
            return IntegrityVerification(
                valid=True,
                artifact_id=artifact_id,
                state=record.state,
                errors=("content was removed by a governed finalization receipt",),
            )
        verified: list[str] = []
        missing: list[str] = []
        mismatches: list[str] = []
        errors: list[str] = []
        for item in record.manifest.files:
            path = self._blob_path(item.content_digest)
            try:
                content = self._safe_read(path, label="artifact blob")
            except (ArtifactNotFound, ArtifactConflict) as error:
                missing.append(item.path)
                errors.append(str(error))
                continue
            if len(content) != item.size_bytes or _sha256(content) != item.content_digest:
                mismatches.append(item.path)
            else:
                verified.append(item.path)
        return IntegrityVerification(
            valid=not (missing or mismatches or errors),
            artifact_id=artifact_id,
            state=record.state,
            verified_files=tuple(verified),
            missing_files=tuple(missing),
            digest_mismatches=tuple(mismatches),
            errors=tuple(errors),
        )

    def _reverse_references(self, artifact_id: str) -> tuple[str, ...]:
        references = []
        for record in self.list(include_deleted=False):
            if record.manifest.artifact_id == artifact_id:
                continue
            if (
                artifact_id in record.manifest.parent_artifact_ids
                or record.manifest.supersedes_artifact_id == artifact_id
            ) and record.state != ArtifactLifecycleState.TOMBSTONED:
                references.append(record.manifest.artifact_id)
        return tuple(sorted(references))

    @staticmethod
    def _confirmation_token(operation: str, record: ArtifactRecord, references: tuple[str, ...]) -> str:
        value = "|".join(
            (operation, record.manifest.artifact_id, record.manifest.artifact_digest or "", record.revision, *references)
        ).encode("utf-8")
        return _sha256(value)

    def deletion_preview(
        self,
        artifact_id: str,
        *,
        finalize: bool = False,
        now: datetime | None = None,
    ) -> DeletionPreview:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        record = self.get(artifact_id)
        references = self._reverse_references(artifact_id)
        blockers: list[str] = []
        operation = "finalize_delete" if finalize else "tombstone"
        if finalize:
            if record.state != ArtifactLifecycleState.TOMBSTONED:
                blockers.append("artifact is not recoverably tombstoned")
            else:
                receipt = record.receipts[-1]
                if receipt.recovery_until is None or now < receipt.recovery_until:
                    blockers.append("seven-day recovery window has not expired")
        elif record.state not in {ArtifactLifecycleState.ACTIVE, ArtifactLifecycleState.ARCHIVED}:
            blockers.append("only active or archived artifacts can be tombstoned")
        if record.manifest.publication == PublicationState.PUBLISHED:
            blockers.append("published artifacts deny ordinary deletion")
        if record.manifest.retention == RetentionClass.EVIDENCE_LOCKED:
            blockers.append("evidence-locked artifacts deny ordinary deletion")
        if references:
            blockers.append("active artifact references must be removed or superseded")
        verification = self.verify(artifact_id)
        if not verification.valid:
            blockers.append("integrity verification must pass before deletion")
        consequence = (
            "Finalization permanently removes unshared content bytes and preserves the manifest, tombstone and receipts."
            if finalize
            else "Tombstoning hides the artifact from active use but preserves every byte for seven days and can be restored."
        )
        return DeletionPreview(
            artifact_id=artifact_id,
            operation=operation,
            eligible=not blockers,
            blockers=tuple(blockers),
            confirmation_token=self._confirmation_token(operation, record, references),
            expected_revision=record.revision,
            consequence=consequence,
        )

    def tombstone(
        self,
        artifact_id: str,
        *,
        confirmation_token: str,
        expected_revision: str,
        actor: str,
        rationale: str,
        occurred_at: datetime | None = None,
    ) -> ArtifactRecord:
        occurred_at = (occurred_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        with self._mutation_lock():
            preview = self.deletion_preview(artifact_id)
            if not preview.eligible:
                raise ArtifactConflict("; ".join(preview.blockers))
            if preview.confirmation_token != confirmation_token or preview.expected_revision != expected_revision:
                raise ArtifactConflict("deletion preview is stale or does not match the reviewed consequence")
            record = self.get(artifact_id)
            return self._append_receipt(
                record,
                operation="tombstone",
                to_state=ArtifactLifecycleState.TOMBSTONED,
                actor=actor,
                rationale=rationale,
                expected_revision=expected_revision,
                occurred_at=occurred_at,
                recovery_until=occurred_at + timedelta(days=self.RECOVERY_DAYS),
            )

    def restore_tombstone(
        self,
        artifact_id: str,
        *,
        actor: str,
        rationale: str,
        expected_revision: str,
        occurred_at: datetime | None = None,
    ) -> ArtifactRecord:
        occurred_at = (occurred_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        with self._mutation_lock():
            record = self.get(artifact_id)
            if record.state != ArtifactLifecycleState.TOMBSTONED:
                raise ArtifactConflict("only a tombstoned artifact can be restored")
            recovery_until = record.receipts[-1].recovery_until
            if recovery_until is None or occurred_at > recovery_until:
                raise ArtifactConflict("artifact recovery window has expired")
            return self._append_receipt(
                record,
                operation="restore",
                to_state=ArtifactLifecycleState.ACTIVE,
                actor=actor,
                rationale=rationale,
                expected_revision=expected_revision,
                occurred_at=occurred_at,
            )

    def finalize_delete(
        self,
        artifact_id: str,
        *,
        confirmation_token: str,
        expected_revision: str,
        actor: str,
        rationale: str,
        occurred_at: datetime | None = None,
    ) -> ArtifactRecord:
        occurred_at = (occurred_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        with self._mutation_lock():
            record = self.get(artifact_id)
            references = self._reverse_references(artifact_id)
            if record.state != ArtifactLifecycleState.TOMBSTONED:
                raise ArtifactConflict("only a tombstoned artifact can be finalized")
            deadline = record.receipts[-1].recovery_until
            blockers = []
            if deadline is None or occurred_at < deadline:
                blockers.append("seven-day recovery window has not expired")
            if references:
                blockers.append("active artifact references must be removed or superseded")
            if record.manifest.publication == PublicationState.PUBLISHED:
                blockers.append("published artifacts deny ordinary deletion")
            if record.manifest.retention == RetentionClass.EVIDENCE_LOCKED:
                blockers.append("evidence-locked artifacts deny ordinary deletion")
            token = self._confirmation_token("finalize_delete", record, references)
            if token != confirmation_token or record.revision != expected_revision:
                blockers.append("finalization preview is stale")
            if blockers:
                raise ArtifactConflict("; ".join(blockers))
            other_digests = {
                item.content_digest
                for other in self.list(include_deleted=True)
                if other.manifest.artifact_id != artifact_id
                and other.state != ArtifactLifecycleState.DELETED
                for item in other.manifest.files
            }
            deleted = self._append_receipt(
                record,
                operation="finalize_delete",
                to_state=ArtifactLifecycleState.DELETED,
                actor=actor,
                rationale=rationale,
                expected_revision=expected_revision,
                occurred_at=occurred_at,
            )
            # The committed terminal receipt makes residual bytes unreachable. A
            # crash during cleanup can therefore be retried safely without ever
            # exposing a catalogue entry whose declared bytes have disappeared.
            for item in record.manifest.files:
                if item.content_digest in other_digests:
                    continue
                blob = self._blob_path(item.content_digest)
                if blob.is_symlink():
                    raise ArtifactConflict("artifact blob may not be a symbolic link")
                if blob.exists():
                    blob.unlink()
            return deleted

    def open_file(self, artifact_id: str, path: str, *, download: bool = False) -> tuple[bytes, str]:
        record = self.get(artifact_id)
        if record.state in {ArtifactLifecycleState.TOMBSTONED, ArtifactLifecycleState.DELETED}:
            raise ArtifactConflict("tombstoned or deleted artifacts cannot be opened")
        item = next((candidate for candidate in record.manifest.files if candidate.path == path), None)
        if item is None:
            raise ArtifactNotFound(path)
        if download and not item.download_allowed:
            raise ArtifactConflict("download is blocked by the artifact rights policy")
        if not download and item.preview_mode.value == "none":
            raise ArtifactConflict("preview is blocked by the artifact rights or media policy")
        content = self._safe_read(self._blob_path(item.content_digest), label="artifact blob")
        if len(content) != item.size_bytes or _sha256(content) != item.content_digest:
            raise ArtifactConflict("artifact file failed integrity verification")
        return content, item.media_type
