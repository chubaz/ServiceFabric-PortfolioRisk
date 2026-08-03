"""Explicit fail-closed admission of current Agent Lab run folders."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import (
    ArtifactKind,
    ArtifactManifest,
    DataTruthClass,
    PreviewMode,
    PublicationState,
    RetentionClass,
    RightsState,
    SourceRevision,
    file_manifest,
)


ADAPTER_ID = "portfolio-risk.legacy-agent-run-adapter"
ADAPTER_REVISION = "1.0.0"
RUN_ID_PATTERN = re.compile(r"run-[0-9]{8}T[0-9]{6}(?:Z|\+0000)-[a-f0-9]{8}")
EXPECTED_FILES = (
    "activity.json",
    "blueprint.json",
    "capability-executions.json",
    "input-provenance.json",
    "input.json",
    "manifest.json",
    "model-executions.json",
    "output.json",
    "research-plan.json",
    "review-brief.md",
    "review.json",
    "transcript.md",
)
ROLE_BY_NAME = {
    "activity.json": "activity_log",
    "blueprint.json": "agent_blueprint_input",
    "capability-executions.json": "capability_receipts",
    "input-provenance.json": "input_provenance",
    "input.json": "run_input",
    "manifest.json": "legacy_manifest",
    "model-executions.json": "model_receipts",
    "output.json": "structured_output",
    "research-plan.json": "research_plan",
    "review-brief.md": "rendered_report",
    "review.json": "review_receipt",
    "transcript.md": "run_transcript",
}
MAX_FILE_BYTES = 2_000_000
PREVIEWABLE_SYNTHETIC = {
    "input-provenance.json",
    "blueprint.json",
    "output.json",
    "research-plan.json",
    "review.json",
    "review-brief.md",
    "transcript.md",
}


class LegacyRunInvalid(ValueError):
    """A source folder cannot be admitted without changing its meaning."""


@dataclass(frozen=True)
class LegacyRunPreview:
    run_id: str
    status: str
    eligible: bool
    artifact_id: str | None
    title: str | None
    data_truth: str | None
    rights: str | None
    rights_policy_id: str | None
    file_count: int
    total_size_bytes: int
    source_manifest_digest: str | None
    confirmation_token: str | None
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]

    def payload(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "eligible": self.eligible,
            "artifact_id": self.artifact_id,
            "title": self.title,
            "data_truth": self.data_truth,
            "rights": self.rights,
            "rights_policy_id": self.rights_policy_id,
            "file_count": self.file_count,
            "total_size_bytes": self.total_size_bytes,
            "source_manifest_digest": self.source_manifest_digest,
            "confirmation_token": self.confirmation_token,
            "warnings": list(self.warnings),
            "blockers": list(self.blockers),
        }


def _digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _safe_directory(root: Path, run_id: str) -> Path:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise LegacyRunInvalid("invalid_run_id")
    if root.is_symlink():
        raise LegacyRunInvalid("unsafe_source_root")
    directory = root / run_id
    try:
        result = directory.lstat()
    except FileNotFoundError as error:
        raise LegacyRunInvalid("source_run_missing") from error
    if not stat.S_ISDIR(result.st_mode) or stat.S_ISLNK(result.st_mode):
        raise LegacyRunInvalid("unsafe_source_directory")
    return directory


def _read_regular(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except (FileNotFoundError, OSError) as error:
        raise LegacyRunInvalid("source_file_unavailable") from error
    try:
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode) or observed.st_size > MAX_FILE_BYTES:
            raise LegacyRunInvalid("unsafe_or_oversized_source_file")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            content = handle.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES:
            raise LegacyRunInvalid("unsafe_or_oversized_source_file")
        return content
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _observe(root: Path, run_id: str) -> tuple[dict[str, Any], dict[str, bytes], tuple[str, ...]]:
    directory = _safe_directory(root, run_id)
    names = []
    for child in directory.iterdir():
        observed = child.lstat()
        if not stat.S_ISREG(observed.st_mode) or stat.S_ISLNK(observed.st_mode):
            raise LegacyRunInvalid("source_contains_non_regular_file")
        names.append(child.name)
    if tuple(sorted(names)) != EXPECTED_FILES:
        raise LegacyRunInvalid("source_inventory_mismatch")
    contents = {name: _read_regular(directory / name) for name in EXPECTED_FILES}
    try:
        manifest = json.loads(contents["manifest.json"])
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise LegacyRunInvalid("manifest_invalid") from error
    if not isinstance(manifest, dict) or manifest.get("run_id") != run_id:
        raise LegacyRunInvalid("manifest_run_id_mismatch")
    declared = manifest.get("files")
    if not isinstance(declared, list):
        raise LegacyRunInvalid("manifest_inventory_invalid")
    declared_by_name = {
        item.get("name"): item
        for item in declared
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    if set(declared_by_name) != set(EXPECTED_FILES):
        raise LegacyRunInvalid("manifest_inventory_mismatch")
    warnings: list[str] = []
    for name, content in contents.items():
        size = declared_by_name[name].get("bytes")
        if not isinstance(size, int):
            raise LegacyRunInvalid("declared_size_invalid")
        if size != len(content):
            if name == "manifest.json":
                warnings.append(
                    "The legacy manifest self-size is stale by construction; the repository uses the observed size and digest."
                )
            else:
                raise LegacyRunInvalid("declared_size_mismatch")
    try:
        provenance = json.loads(contents["input-provenance.json"])
        blueprint = json.loads(contents["blueprint.json"])
        output = json.loads(contents["output.json"])
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise LegacyRunInvalid("cross_file_json_invalid") from error
    data_mode = manifest.get("data_mode")
    if not isinstance(provenance, dict) or provenance.get("data_mode") != data_mode:
        raise LegacyRunInvalid("data_mode_inconsistent")
    if isinstance(blueprint, dict) and manifest.get("agent_name") and blueprint.get("name") not in {
        None,
        manifest.get("agent_name"),
    }:
        raise LegacyRunInvalid("agent_name_inconsistent")
    if isinstance(output, dict) and output.get("output_contract") != manifest.get("output_contract"):
        raise LegacyRunInvalid("output_contract_inconsistent")
    return manifest, contents, tuple(warnings)


def preview_legacy_run(root: str | Path, run_id: str) -> LegacyRunPreview:
    try:
        manifest, contents, warnings = _observe(Path(root), run_id)
    except LegacyRunInvalid as error:
        return LegacyRunPreview(
            run_id=run_id,
            status="damaged",
            eligible=False,
            artifact_id=None,
            title=None,
            data_truth=None,
            rights=None,
            rights_policy_id=None,
            file_count=0,
            total_size_bytes=0,
            source_manifest_digest=None,
            confirmation_token=None,
            warnings=(),
            blockers=(str(error),),
        )
    source_digest = _digest(contents["manifest.json"])
    inventory_digest = _digest(
        json.dumps(
            [(name, len(contents[name]), _digest(contents[name])) for name in EXPECTED_FILES],
            separators=(",", ":"),
        ).encode("utf-8")
    )
    real = manifest.get("data_mode") == "real_duckdb"
    truth = DataTruthClass.LICENSED_REAL if real else DataTruthClass.SYNTHETIC_SAMPLE
    rights = RightsState.LICENSED_RESTRICTED if real else RightsState.INTERNAL
    policy = "local.licensed.research.v1" if real else "internal.synthetic.research.v1"
    artifact_id = f"retained-run-{inventory_digest[7:31]}"
    token = _digest(
        f"{ADAPTER_ID}|{ADAPTER_REVISION}|{run_id}|{inventory_digest}|{policy}".encode()
    )
    return LegacyRunPreview(
        run_id=run_id,
        status="compatible",
        eligible=True,
        artifact_id=artifact_id,
        title=f"{manifest.get('agent_name') or 'Agent'} · retained run",
        data_truth=truth.value,
        rights=rights.value,
        rights_policy_id=policy,
        file_count=len(contents),
        total_size_bytes=sum(map(len, contents.values())),
        source_manifest_digest=source_digest,
        confirmation_token=token,
        warnings=warnings,
        blockers=(),
    )


def compile_legacy_run(
    root: str | Path,
    run_id: str,
    *,
    confirmation_token: str,
) -> tuple[ArtifactManifest, dict[str, bytes]]:
    preview = preview_legacy_run(root, run_id)
    if not preview.eligible or preview.confirmation_token != confirmation_token:
        raise LegacyRunInvalid("source_changed_since_preview")
    source, contents, _warnings = _observe(Path(root), run_id)
    real = source.get("data_mode") == "real_duckdb"
    files = []
    for name in EXPECTED_FILES:
        sensitive = real and name in {
            "input.json",
            "activity.json",
            "capability-executions.json",
            "transcript.md",
        }
        files.append(
            file_manifest(
                path=name,
                content=contents[name],
                media_type="text/markdown" if name.endswith(".md") else "application/json",
                role=ROLE_BY_NAME[name],
                preview_mode=(
                    PreviewMode.ESCAPED_TEXT
                    if not sensitive and name in PREVIEWABLE_SYNTHETIC
                    else PreviewMode.NONE
                ),
                download_allowed=not real and not sensitive,
                sensitive=sensitive,
            )
        )
    created_at = datetime.fromisoformat(str(source["created_at"]).replace("Z", "+00:00"))
    adapter_digest = _digest(f"{ADAPTER_ID}@{ADAPTER_REVISION}".encode())
    manifest = ArtifactManifest(
        artifact_id=preview.artifact_id or "",
        title=preview.title or "Retained agent run",
        kind=ArtifactKind.RETAINED_RUN,
        created_at=created_at.astimezone(timezone.utc),
        created_by="agent.lab.runtime",
        creation_method=ADAPTER_ID,
        run_id=run_id,
        data_truth=DataTruthClass(preview.data_truth),
        rights=RightsState(preview.rights),
        rights_policy_id=preview.rights_policy_id or "",
        publication=PublicationState.RESTRICTED,
        retention=RetentionClass.RUN_RETAINED,
        entry_file="review-brief.md",
        files=tuple(sorted(files, key=lambda item: item.path)),
        total_size_bytes=sum(len(value) for value in contents.values()),
        source_revisions=(
            SourceRevision(
                kind="adapter",
                source_id=ADAPTER_ID,
                revision=ADAPTER_REVISION,
                digest=adapter_digest,
            ),
        ),
        restrictions=("local_development_only", "no_external_publication") if real else (),
        source_manifest_digest=preview.source_manifest_digest,
    )
    return manifest, contents


def discover_legacy_runs(root: str | Path) -> tuple[LegacyRunPreview, ...]:
    source = Path(root)
    if not source.exists() or source.is_symlink():
        return ()
    candidates = []
    for path in sorted(source.iterdir(), key=lambda item: item.name, reverse=True):
        if RUN_ID_PATTERN.fullmatch(path.name):
            candidates.append(preview_legacy_run(source, path.name))
    return tuple(candidates)
