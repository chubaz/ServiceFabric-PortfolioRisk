"""Recoverable, content-addressed bundles for completed thesis comparisons."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .models import DIGEST, IDENTIFIER, FrozenModel, canonical_digest


class ReproducibilityConflict(ValueError):
    pass


class ReproducibilityNotFound(KeyError):
    pass


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("bundle timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


class BundleFile(FrozenModel):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9._/-]{0,199}$")
    media_type: str = Field(min_length=3, max_length=100)
    sha256: str = Field(pattern=DIGEST)
    size_bytes: int = Field(ge=0)
    audience: Literal["supervisor", "developer", "system"]


class ReproducibilityBundle(FrozenModel):
    schema_version: Literal["portfolio-risk.reproducibility-bundle/v1"] = "portfolio-risk.reproducibility-bundle/v1"
    bundle_id: str = Field(pattern=IDENTIFIER)
    matrix_id: str = Field(pattern=IDENTIFIER)
    case_id: str = Field(pattern=IDENTIFIER)
    comparison_digest: str = Field(pattern=DIGEST)
    files: tuple[BundleFile, ...] = Field(min_length=1)
    exact_versions: dict[str, str]
    created_at: datetime
    bundle_digest: str | None = Field(default=None, pattern=DIGEST)

    _created = field_validator("created_at")(_utc)

    @model_validator(mode="after")
    def reconciles(self) -> "ReproducibilityBundle":
        if tuple(item.name for item in self.files) != tuple(sorted({item.name for item in self.files})):
            raise ValueError("bundle files must be unique and sorted")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"bundle_digest"}))
        if self.bundle_digest is not None and self.bundle_digest != expected:
            raise ValueError("bundle_digest does not match canonical content")
        object.__setattr__(self, "bundle_digest", expected)
        return self


class BundleProjection(FrozenModel):
    manifest: ReproducibilityBundle
    state: Literal["active", "archived", "removed"]
    verified: bool
    verification_errors: tuple[str, ...] = ()


class LocalReproducibilityStore:
    """Atomic bundle storage with archive and recoverable-removal states."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().absolute()
        self.active = self.root / "reproducibility-bundles"
        self.archived = self.root / "archived-reproducibility-bundles"
        self.removed = self.root / "removed-reproducibility-bundles"
        self._thread_lock = threading.RLock()

    @contextmanager
    def _lock(self):  # type: ignore[no-untyped-def]
        with self._thread_lock:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
            descriptor = os.open(self.root / ".reproducibility.lock", os.O_RDWR | os.O_CREAT, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    def _locate(self, bundle_id: str) -> tuple[Path, str]:
        key = hashlib.sha256(bundle_id.encode()).hexdigest()
        for parent, state in ((self.active, "active"), (self.archived, "archived"), (self.removed, "removed")):
            candidate = parent / key
            if candidate.exists():
                return candidate, state
        raise ReproducibilityNotFound(bundle_id)

    @staticmethod
    def _verify_at(path: Path, manifest: ReproducibilityBundle) -> tuple[str, ...]:
        errors = []
        for record in manifest.files:
            target = path / record.name
            if not target.exists() or target.is_symlink():
                errors.append(f"missing or unsafe file: {record.name}")
                continue
            payload = target.read_bytes()
            if f"sha256:{hashlib.sha256(payload).hexdigest()}" != record.sha256:
                errors.append(f"digest mismatch: {record.name}")
            if len(payload) != record.size_bytes:
                errors.append(f"size mismatch: {record.name}")
        return tuple(errors)

    def save(self, manifest: ReproducibilityBundle, files: dict[str, bytes]) -> BundleProjection:
        expected = {item.name for item in manifest.files}
        if set(files) != expected:
            raise ReproducibilityConflict("bundle payload names do not match the manifest")
        key = hashlib.sha256(manifest.bundle_id.encode()).hexdigest()
        with self._lock():
            try:
                existing_path, state = self._locate(manifest.bundle_id)
            except ReproducibilityNotFound:
                existing_path = None
            if existing_path is not None:
                existing = ReproducibilityBundle.model_validate_json(
                    (existing_path / "manifest.json").read_text(encoding="utf-8")
                )
                if existing != manifest:
                    raise ReproducibilityConflict("bundle identity already has different content")
                errors = self._verify_at(existing_path, existing)
                return BundleProjection(manifest=existing, state=state, verified=not errors, verification_errors=errors)
            self.active.mkdir(mode=0o700, parents=True, exist_ok=True)
            temporary = Path(tempfile.mkdtemp(prefix=".bundle-", dir=self.active))
            try:
                for name, payload in files.items():
                    target = temporary / name
                    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    target.write_bytes(payload)
                    target.chmod(0o600)
                (temporary / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
                (temporary / "manifest.json").chmod(0o600)
                errors = self._verify_at(temporary, manifest)
                if errors:
                    raise ReproducibilityConflict("; ".join(errors))
                os.replace(temporary, self.active / key)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)
            return BundleProjection(manifest=manifest, state="active", verified=True)

    def get(self, bundle_id: str) -> BundleProjection:
        with self._lock():
            path, state = self._locate(bundle_id)
            manifest = ReproducibilityBundle.model_validate_json((path / "manifest.json").read_text(encoding="utf-8"))
            errors = self._verify_at(path, manifest)
            return BundleProjection(manifest=manifest, state=state, verified=not errors, verification_errors=errors)

    def read(self, bundle_id: str, name: str) -> bytes:
        with self._lock():
            path, _ = self._locate(bundle_id)
            manifest = ReproducibilityBundle.model_validate_json((path / "manifest.json").read_text(encoding="utf-8"))
            if name not in {item.name for item in manifest.files}:
                raise ReproducibilityNotFound(name)
            target = path / name
            if target.is_symlink() or not target.resolve().is_relative_to(path.resolve()):
                raise ReproducibilityConflict("bundle file escaped its storage boundary")
            return target.read_bytes()

    def list(self) -> tuple[BundleProjection, ...]:
        values = []
        with self._lock():
            for parent, state in ((self.active, "active"), (self.archived, "archived")):
                if not parent.exists():
                    continue
                for path in parent.iterdir():
                    if not path.is_dir() or path.is_symlink():
                        continue
                    manifest = ReproducibilityBundle.model_validate_json((path / "manifest.json").read_text(encoding="utf-8"))
                    errors = self._verify_at(path, manifest)
                    values.append(BundleProjection(manifest=manifest, state=state, verified=not errors, verification_errors=errors))
        return tuple(sorted(values, key=lambda item: item.manifest.created_at, reverse=True))

    def _move(self, bundle_id: str, expected: str, destination: Path) -> BundleProjection:
        with self._lock():
            path, state = self._locate(bundle_id)
            if state != expected:
                raise ReproducibilityConflict(f"bundle must be {expected} before this transition")
            destination.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.replace(path, destination / path.name)
        return self.get(bundle_id)

    def archive(self, bundle_id: str) -> BundleProjection:
        return self._move(bundle_id, "active", self.archived)

    def restore(self, bundle_id: str) -> BundleProjection:
        return self._move(bundle_id, "archived", self.active)

    def remove(self, bundle_id: str, *, confirmation: str) -> BundleProjection:
        if confirmation != bundle_id:
            raise ReproducibilityConflict("exact bundle identity confirmation is required")
        path, state = self._locate(bundle_id)
        return self._move(bundle_id, state, self.removed)


def build_bundle_manifest(
    *, matrix_id: str, case_id: str, comparison: dict[str, Any], files: dict[str, tuple[bytes, str, str]],
    exact_versions: dict[str, str], created_at: datetime,
) -> ReproducibilityBundle:
    comparison_digest = canonical_digest(comparison)
    identity = canonical_digest({
        "matrix": matrix_id, "comparison": comparison_digest, "versions": exact_versions,
        "files": {
            name: f"sha256:{hashlib.sha256(payload).hexdigest()}"
            for name, (payload, _media_type, _audience) in sorted(files.items())
        },
    })
    records = tuple(sorted((BundleFile(
        name=name, media_type=media_type, audience=audience,
        sha256=f"sha256:{hashlib.sha256(payload).hexdigest()}", size_bytes=len(payload),
    ) for name, (payload, media_type, audience) in files.items()), key=lambda item: item.name))
    return ReproducibilityBundle(
        bundle_id=f"comparison-bundle-{identity[7:31]}", matrix_id=matrix_id, case_id=case_id,
        comparison_digest=comparison_digest, files=records, exact_versions=exact_versions,
        created_at=created_at,
    )
