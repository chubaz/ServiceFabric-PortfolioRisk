from __future__ import annotations

import json

import pytest

from risk_artifacts import (
    ArtifactConflict,
    DataTruthClass,
    LegacyRunInvalid,
    LocalArtifactRepository,
    PreviewMode,
    RightsState,
    compile_legacy_run,
    discover_legacy_runs,
    preview_legacy_run,
)
from risk_artifacts.legacy import EXPECTED_FILES


RUN_ID = "run-20260803T090000Z-deadbeef"


def write_run(root, *, data_mode="synthetic_behavior_sample"):
    directory = root / RUN_ID
    directory.mkdir(parents=True)
    values = {
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
    for name, value in values.items():
        (directory / name).write_text(json.dumps(value, indent=2) + "\n")
    (directory / "review-brief.md").write_text("# Risk review\n")
    (directory / "transcript.md").write_text("# Work record\n")
    source_files = []
    for name in EXPECTED_FILES:
        if name == "manifest.json":
            continue
        path = directory / name
        source_files.append(
            {"name": name, "bytes": path.stat().st_size, "kind": "markdown" if name.endswith(".md") else "json"}
        )
    manifest = {
        "run_id": RUN_ID,
        "agent_name": "Risk reviewer",
        "output_contract": "RiskBrief",
        "status": "completed",
        "data_mode": data_mode,
        "created_at": "2026-08-03T09:00:00+00:00",
        "files": source_files,
    }
    path = directory / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    manifest["files"] = [
        {"name": "manifest.json", "bytes": path.stat().st_size, "kind": "json"},
        *source_files,
    ]
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return directory


def test_preview_is_zero_write_and_known_self_size_is_a_warning(tmp_path):
    root = tmp_path / "runs"
    directory = write_run(root)
    before = {path.name: path.read_bytes() for path in directory.iterdir()}
    preview = preview_legacy_run(root, RUN_ID)
    after = {path.name: path.read_bytes() for path in directory.iterdir()}
    assert preview.eligible
    assert preview.file_count == 12
    assert preview.warnings and "self-size" in preview.warnings[0]
    assert before == after


def test_compile_and_admit_rechecks_exact_source(tmp_path):
    root = tmp_path / "runs"
    write_run(root)
    preview = preview_legacy_run(root, RUN_ID)
    manifest, files = compile_legacy_run(
        root, RUN_ID, confirmation_token=preview.confirmation_token or ""
    )
    repository = LocalArtifactRepository(tmp_path / "repository")
    record = repository.admit(manifest, files, actor="local.developer")
    assert record.manifest.run_id == RUN_ID
    assert record.manifest.data_truth == DataTruthClass.SYNTHETIC_SAMPLE
    assert repository.verify(record.manifest.artifact_id).valid
    (root / RUN_ID / "output.json").write_text("{}\n")
    with pytest.raises(LegacyRunInvalid, match="source_changed_since_preview"):
        compile_legacy_run(
            root, RUN_ID, confirmation_token=preview.confirmation_token or ""
        )


def test_real_data_is_licensed_restricted_and_raw_files_are_not_previewable(tmp_path):
    root = tmp_path / "runs"
    write_run(root, data_mode="real_duckdb")
    preview = preview_legacy_run(root, RUN_ID)
    assert preview.rights == RightsState.LICENSED_RESTRICTED.value
    manifest, _files = compile_legacy_run(
        root, RUN_ID, confirmation_token=preview.confirmation_token or ""
    )
    assert manifest.data_truth == DataTruthClass.LICENSED_REAL
    assert manifest.rights == RightsState.LICENSED_RESTRICTED
    raw = next(item for item in manifest.files if item.path == "input.json")
    assert raw.sensitive and raw.preview_mode == PreviewMode.NONE
    assert not raw.download_allowed


def test_extra_missing_symlink_and_non_manifest_size_damage_fail_closed(tmp_path):
    root = tmp_path / "runs"
    directory = write_run(root)
    (directory / "extra.txt").write_text("not declared")
    assert not preview_legacy_run(root, RUN_ID).eligible
    (directory / "extra.txt").unlink()
    (directory / "output.json").unlink()
    assert not preview_legacy_run(root, RUN_ID).eligible
    (directory / "output.json").symlink_to(directory / "input.json")
    assert not preview_legacy_run(root, RUN_ID).eligible


def test_discovery_surfaces_damaged_candidate(tmp_path):
    root = tmp_path / "runs"
    directory = root / RUN_ID
    directory.mkdir(parents=True)
    candidates = discover_legacy_runs(root)
    assert len(candidates) == 1
    assert candidates[0].status == "damaged"
    assert candidates[0].blockers
