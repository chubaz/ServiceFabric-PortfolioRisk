from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[2]
LABS_ROOT = ROOT / "apps" / "portfolio-risk-workbench" / "labs"
sys.path.insert(0, str(LABS_ROOT))

import duckdb_server  # noqa: E402
from risk_artifacts.legacy import EXPECTED_FILES  # noqa: E402


RUN_ID = "run-20260803T090000Z-1234abcd"


def _legacy_run(root: Path, *, data_mode: str = "synthetic_behavior_sample") -> None:
    directory = root / RUN_ID
    directory.mkdir(parents=True)
    payloads = {
        "activity.json": {"events": []},
        "blueprint.json": {"name": "Risk reviewer"},
        "capability-executions.json": [],
        "input-provenance.json": {"data_mode": data_mode},
        "input.json": {"portfolio_id": "test-portfolio"},
        "model-executions.json": [],
        "output.json": {"output_contract": "RiskBrief"},
        "research-plan.json": {},
        "review.json": {"checkpoint_release": {"human_approval": False}},
    }
    for name, payload in payloads.items():
        (directory / name).write_text(json.dumps(payload, indent=2) + "\n")
    (directory / "review-brief.md").write_text("# Risk review\n")
    (directory / "transcript.md").write_text("# Work record\n")
    files = [
        {
            "name": name,
            "bytes": (directory / name).stat().st_size,
            "kind": "markdown" if name.endswith(".md") else "json",
        }
        for name in EXPECTED_FILES
        if name != "manifest.json"
    ]
    manifest = {
        "run_id": RUN_ID,
        "agent_name": "Risk reviewer",
        "output_contract": "RiskBrief",
        "status": "completed",
        "data_mode": data_mode,
        "created_at": "2026-08-03T09:00:00+00:00",
        "files": files,
    }
    manifest_path = directory / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    manifest["files"] = [
        {"name": "manifest.json", "bytes": manifest_path.stat().st_size, "kind": "json"},
        *files,
    ]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


def test_explicit_admission_catalogue_detail_preview_and_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root = tmp_path / "runs"
    _legacy_run(run_root)
    monkeypatch.setattr(duckdb_server, "RUN_ROOT", run_root)
    monkeypatch.setenv("PORTFOLIO_RISK_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    preview = duckdb_server.preview_artifact_admission(RUN_ID)
    assert preview["eligible"]
    admitted = duckdb_server.admit_artifact_run(
        duckdb_server.ArtifactAdmissionRequest(
            run_id=RUN_ID,
            confirmation_token=preview["confirmation_token"],
            actor="test.reviewer",
        )
    )
    catalogue = duckdb_server.artifact_catalogue()
    assert catalogue["summary"] == {
        "retained_runs": 1,
        "artifacts": 1,
        "files": len(EXPECTED_FILES),
        "total_size_bytes": admitted["manifest"]["total_size_bytes"],
        "need_attention": 0,
    }
    assert "root" not in json.dumps(catalogue).lower()
    detail = duckdb_server.artifact_detail(admitted["manifest"]["artifact_id"])
    assert detail["verification"]["valid"]
    report = next(item for item in detail["manifest"]["files"] if item["path"] == "review-brief.md")
    shown = duckdb_server.preview_artifact_file(detail["manifest"]["artifact_id"], report["file_id"])
    assert shown["rendering"] == "escaped_text_only"
    assert "# Risk review" in shown["text"]
    archived = duckdb_server.archive_artifact(
        detail["manifest"]["artifact_id"],
        duckdb_server.ArtifactTransitionRequest(
            actor="test.reviewer",
            rationale="Retain this run outside the active view.",
            expected_revision=detail["revision"],
        ),
    )
    assert archived["state"] == "archived"


def test_real_raw_preview_is_denied_and_legacy_delete_is_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root = tmp_path / "runs"
    _legacy_run(run_root, data_mode="real_duckdb")
    monkeypatch.setattr(duckdb_server, "RUN_ROOT", run_root)
    monkeypatch.setenv("PORTFOLIO_RISK_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    preview = duckdb_server.preview_artifact_admission(RUN_ID)
    record = duckdb_server.admit_artifact_run(
        duckdb_server.ArtifactAdmissionRequest(
            run_id=RUN_ID,
            confirmation_token=preview["confirmation_token"],
            actor="test.reviewer",
        )
    )
    raw = next(item for item in record["manifest"]["files"] if item["path"] == "input.json")
    with pytest.raises(HTTPException) as denied:
        duckdb_server.preview_artifact_file(record["manifest"]["artifact_id"], raw["file_id"])
    assert denied.value.status_code == 409
    with pytest.raises(HTTPException) as legacy_delete:
        duckdb_server.remove_agent_run(RUN_ID)
    assert legacy_delete.value.status_code == 409
    assert (run_root / RUN_ID).is_dir()
