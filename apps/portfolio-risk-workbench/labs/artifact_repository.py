"""Application projection for the governed local artifact repository."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from agent_studio import RUN_ROOT
from risk_artifacts import (
    ArtifactRecord,
    LocalArtifactRepository,
    discover_legacy_runs,
)


def artifact_root() -> Path:
    configured = os.environ.get("PORTFOLIO_RISK_ARTIFACT_ROOT")
    if configured:
        return Path(configured).expanduser().absolute()
    state_root = os.environ.get("XDG_STATE_HOME")
    base = Path(state_root).expanduser() if state_root else Path.home() / ".servicefabric-portfolio-risk"
    return (base / "artifacts-v1").absolute()


def artifact_store() -> LocalArtifactRepository:
    return LocalArtifactRepository(artifact_root())


def record_payload(record: ArtifactRecord) -> dict[str, Any]:
    value = record.model_dump(mode="json")
    value["state"] = record.state.value
    value["revision"] = record.revision
    value["file_count"] = len(record.manifest.files)
    value["integrity"] = "not_currently_verified"
    value["references"] = "evaluated_on_deletion_preview"
    return value


def catalogue_payload(*, include_deleted: bool = False) -> dict[str, Any]:
    store = artifact_store()
    records = list(store.list(include_deleted=include_deleted))
    candidates = [candidate.payload() for candidate in discover_legacy_runs(RUN_ROOT)]
    need_attention = sum(
        record.state.value in {"tombstoned", "deleted"}
        or record.manifest.rights_policy_id == ""
        for record in records
    ) + sum(not item["eligible"] for item in candidates)
    return {
        "records": [record_payload(record) for record in records],
        "candidates": candidates,
        "summary": {
            "retained_runs": sum(record.manifest.run_id is not None for record in records),
            "artifacts": len(records),
            "files": sum(len(record.manifest.files) for record in records),
            "total_size_bytes": sum(record.manifest.total_size_bytes for record in records),
            "need_attention": need_attention,
        },
        "boundary": {
            "storage": "content-addressed local repository outside Git",
            "execution": "disabled",
            "external_effects": "disabled",
            "host_paths_exposed": False,
        },
    }
