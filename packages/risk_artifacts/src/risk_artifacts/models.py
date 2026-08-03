"""Strict repository projections around canonical artifact references."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
IDENTIFIER_PATTERN = r"^[a-z0-9][a-z0-9._:-]{2,159}$"
RUN_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,159}$"
FILE_ID_PATTERN = r"^file-[0-9a-f]{16}$"


def _canonical_digest(value: dict[str, object]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _optional_aware(value: datetime | None) -> datetime | None:
    return None if value is None else _aware(value)


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ArtifactKind(StrEnum):
    RETAINED_RUN = "retained_run"
    REPORT = "report"
    TABLE = "table"
    CHART = "chart"
    DASHBOARD = "dashboard"
    DATASET = "dataset"
    EVIDENCE_BUNDLE = "evidence_bundle"
    FILE_BUNDLE = "file_bundle"


class DataTruthClass(StrEnum):
    LICENSED_REAL = "licensed_real"
    PUBLIC_REAL = "public_real"
    REVIEWED_SYNTHETIC = "reviewed_synthetic"
    SYNTHETIC_SAMPLE = "synthetic_sample"
    SIMULATED = "simulated"
    MIXED = "mixed"
    NO_DATA = "no_data"


class RightsState(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    LICENSED_RESTRICTED = "licensed_restricted"


class PublicationState(StrEnum):
    RESTRICTED = "restricted"
    CANDIDATE = "candidate"
    PUBLISHED = "published"


class RetentionClass(StrEnum):
    EPHEMERAL = "ephemeral"
    RUN_RETAINED = "run_retained"
    EXPERIMENT_EVIDENCE = "experiment_evidence"
    PUBLISHED = "published"
    EVIDENCE_LOCKED = "evidence_locked"


class ArtifactLifecycleState(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    TOMBSTONED = "tombstoned"
    DELETED = "deleted"


class PreviewMode(StrEnum):
    ESCAPED_TEXT = "escaped_text"
    NONE = "none"


class ArtifactFile(FrozenModel):
    file_id: str = Field(pattern=FILE_ID_PATTERN)
    path: str = Field(min_length=1, max_length=240)
    content_digest: str = Field(pattern=SHA256_PATTERN)
    media_type: str = Field(min_length=3, max_length=128)
    size_bytes: int = Field(ge=0, le=100_000_000)
    role: str = Field(pattern=IDENTIFIER_PATTERN)
    preview_mode: PreviewMode = PreviewMode.NONE
    download_allowed: bool = False
    sensitive: bool = False

    @field_validator("path")
    @classmethod
    def safe_relative_path(cls, value: str) -> str:
        if value.startswith(("/", "\\")) or "\\" in value:
            raise ValueError("artifact paths must be relative POSIX paths")
        parts = value.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("artifact path contains an unsafe segment")
        return value

    @model_validator(mode="after")
    def identity_matches_digest(self) -> "ArtifactFile":
        expected = f"file-{self.content_digest[7:23]}"
        if self.file_id != expected:
            raise ValueError("file_id must derive from the content digest")
        if self.sensitive and self.preview_mode != PreviewMode.NONE:
            raise ValueError("sensitive files cannot be previewed")
        return self


class SourceRevision(FrozenModel):
    kind: str = Field(pattern=IDENTIFIER_PATTERN)
    source_id: str = Field(pattern=IDENTIFIER_PATTERN)
    revision: str = Field(min_length=1, max_length=160)
    digest: str = Field(pattern=SHA256_PATTERN)


class ArtifactManifest(FrozenModel):
    schema_version: Literal["portfolio-risk.artifact-manifest/v1"] = (
        "portfolio-risk.artifact-manifest/v1"
    )
    artifact_id: str = Field(pattern=IDENTIFIER_PATTERN)
    artifact_digest: str | None = Field(default=None, pattern=SHA256_PATTERN)
    title: str = Field(min_length=1, max_length=200)
    kind: ArtifactKind
    created_at: datetime
    created_by: str = Field(pattern=IDENTIFIER_PATTERN)
    creation_method: str = Field(pattern=IDENTIFIER_PATTERN)
    operating_profile: Literal["development"] = "development"
    run_id: str | None = Field(default=None, pattern=RUN_IDENTIFIER_PATTERN)
    experiment_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    data_truth: DataTruthClass
    rights: RightsState
    rights_policy_id: str = Field(pattern=IDENTIFIER_PATTERN)
    publication: PublicationState
    retention: RetentionClass
    entry_file: str
    files: tuple[ArtifactFile, ...] = Field(min_length=1, max_length=128)
    total_size_bytes: int = Field(ge=0, le=250_000_000)
    source_revisions: tuple[SourceRevision, ...] = ()
    parent_artifact_ids: tuple[str, ...] = ()
    supersedes_artifact_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    approvals: tuple[str, ...] = ()
    restrictions: tuple[str, ...] = ()
    source_manifest_digest: str | None = Field(default=None, pattern=SHA256_PATTERN)

    _created = field_validator("created_at")(_aware)

    @field_validator("parent_artifact_ids", "approvals", "restrictions")
    @classmethod
    def sorted_unique_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("values must be unique and sorted")
        return value

    @field_validator("source_revisions")
    @classmethod
    def sorted_sources(cls, value: tuple[SourceRevision, ...]) -> tuple[SourceRevision, ...]:
        keys = [(item.kind, item.source_id, item.revision, item.digest) for item in value]
        if keys != sorted(set(keys)):
            raise ValueError("source revisions must be unique and sorted")
        return value

    @model_validator(mode="after")
    def validate_manifest(self) -> "ArtifactManifest":
        paths = [item.path for item in self.files]
        if paths != sorted(paths) or len(paths) != len(set(paths)):
            raise ValueError("artifact files must have unique deterministic path ordering")
        if self.entry_file not in paths:
            raise ValueError("entry_file must be declared")
        if sum(item.size_bytes for item in self.files) != self.total_size_bytes:
            raise ValueError("total_size_bytes must equal declared file sizes")
        if self.kind == ArtifactKind.RETAINED_RUN and self.run_id is None:
            raise ValueError("retained runs require run_id")
        if self.publication == PublicationState.PUBLISHED and self.retention != RetentionClass.PUBLISHED:
            raise ValueError("published artifacts require published retention")
        if self.retention == RetentionClass.PUBLISHED and self.publication != PublicationState.PUBLISHED:
            raise ValueError("published retention requires published state")
        if self.rights == RightsState.LICENSED_RESTRICTED and self.publication != PublicationState.RESTRICTED:
            raise ValueError("licensed artifacts must remain publication restricted")
        if self.artifact_id in self.parent_artifact_ids:
            raise ValueError("an artifact cannot reference itself as a parent")
        payload = self.model_dump(mode="json", exclude={"artifact_digest"})
        expected = _canonical_digest(payload)
        if self.artifact_digest is not None and self.artifact_digest != expected:
            raise ValueError("artifact_digest must equal the canonical manifest digest")
        object.__setattr__(self, "artifact_digest", expected)
        return self


class LifecycleReceipt(FrozenModel):
    schema_version: Literal["portfolio-risk.artifact-receipt/v1"] = (
        "portfolio-risk.artifact-receipt/v1"
    )
    artifact_id: str = Field(pattern=IDENTIFIER_PATTERN)
    sequence: int = Field(ge=1)
    operation: Literal["admit", "archive", "restore", "tombstone", "finalize_delete"]
    from_state: ArtifactLifecycleState | None = None
    to_state: ArtifactLifecycleState
    actor: str = Field(pattern=IDENTIFIER_PATTERN)
    rationale: str = Field(min_length=3, max_length=1000)
    occurred_at: datetime
    recovery_until: datetime | None = None
    previous_receipt_digest: str | None = Field(default=None, pattern=SHA256_PATTERN)
    receipt_digest: str | None = Field(default=None, pattern=SHA256_PATTERN)

    _occurred = field_validator("occurred_at")(_aware)
    _recovery = field_validator("recovery_until")(_optional_aware)

    @model_validator(mode="after")
    def validate_receipt(self) -> "LifecycleReceipt":
        if self.sequence == 1:
            if self.operation != "admit" or self.from_state is not None or self.to_state != ArtifactLifecycleState.ACTIVE:
                raise ValueError("the first receipt must admit an active artifact")
            if self.previous_receipt_digest is not None:
                raise ValueError("the first receipt has no predecessor")
        elif self.previous_receipt_digest is None:
            raise ValueError("later receipts require a predecessor digest")
        if self.operation == "tombstone" and self.recovery_until is None:
            raise ValueError("tombstone receipts require a recovery deadline")
        if self.operation != "tombstone" and self.recovery_until is not None:
            raise ValueError("only tombstone receipts carry a recovery deadline")
        expected = _canonical_digest(self.model_dump(mode="json", exclude={"receipt_digest"}))
        if self.receipt_digest is not None and self.receipt_digest != expected:
            raise ValueError("receipt_digest must equal canonical receipt content")
        object.__setattr__(self, "receipt_digest", expected)
        return self


class ArtifactRecord(FrozenModel):
    manifest: ArtifactManifest
    receipts: tuple[LifecycleReceipt, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_chain(self) -> "ArtifactRecord":
        state: ArtifactLifecycleState | None = None
        previous: str | None = None
        for index, receipt in enumerate(self.receipts, start=1):
            if receipt.artifact_id != self.manifest.artifact_id or receipt.sequence != index:
                raise ValueError("receipt identity or sequence does not match the artifact")
            if receipt.from_state != state or receipt.previous_receipt_digest != previous:
                raise ValueError("artifact receipt chain is inconsistent")
            state = receipt.to_state
            previous = receipt.receipt_digest
        return self

    @property
    def state(self) -> ArtifactLifecycleState:
        return self.receipts[-1].to_state

    @property
    def revision(self) -> str:
        return self.receipts[-1].receipt_digest or ""


class IntegrityVerification(FrozenModel):
    valid: bool
    artifact_id: str
    state: ArtifactLifecycleState
    verified_files: tuple[str, ...] = ()
    missing_files: tuple[str, ...] = ()
    digest_mismatches: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


class DeletionPreview(FrozenModel):
    artifact_id: str
    operation: Literal["tombstone", "finalize_delete"]
    eligible: bool
    blockers: tuple[str, ...] = ()
    confirmation_token: str = Field(pattern=SHA256_PATTERN)
    expected_revision: str = Field(pattern=SHA256_PATTERN)
    consequence: str
    recovery_days: int = Field(default=7, ge=7, le=7)


def file_manifest(*, path: str, content: bytes, media_type: str, role: str,
                  preview_mode: PreviewMode = PreviewMode.NONE,
                  download_allowed: bool = False, sensitive: bool = False) -> ArtifactFile:
    digest = "sha256:" + hashlib.sha256(content).hexdigest()
    return ArtifactFile(
        file_id=f"file-{digest[7:23]}",
        path=path,
        content_digest=digest,
        media_type=media_type,
        size_bytes=len(content),
        role=role,
        preview_mode=preview_mode,
        download_allowed=download_allowed,
        sensitive=sensitive,
    )
