from __future__ import annotations

import json
from pathlib import Path

from scripts.thesis.check_lane_paths import validate_manifest


ROOT = Path(__file__).resolve().parents[2]


def _json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_phase2_starts_from_the_accepted_phase1_merge() -> None:
    status = _json("config/agent/platform-development/status.json")
    assert status["current"] == "PLATFORM-P2"
    assert status["phase_0"] == "accepted"
    assert status["phase_1"] == "accepted"
    assert status["phase_2"] in {"in_progress", "accepted"}
    assert status["phase_2_baseline_commit"] == (
        "9440bbaeb3f43f04ff259dbde0eb2824b7f9c6f1"
    )
    assert status["phase_1_accepted_candidate_commit"] == (
        "a68ef6fce9d39f5341fa8675c093db2eba95aed6"
    )
    assert status["development_profile_only"] is True
    assert status["external_effects"] == "disabled"


def test_phase2_lanes_are_bounded_and_vendor_is_frozen() -> None:
    manifest = _json("config/agent/platform-development/phase2-lanes.json")
    assert manifest["namespace"] == "platform-development-phase2"
    assert manifest["base_commit"] == (
        "9440bbaeb3f43f04ff259dbde0eb2824b7f9c6f1"
    )
    assert validate_manifest(manifest) == []
    assert manifest["frozen_directories"] == ["vendor/servicefabric"]
    assert manifest["rules"]["shared_contract_owner"] == "integration"
    assert manifest["rules"]["phase_3_work_is_prohibited"] is True
    expected = {
        "artifact-contracts": "phase2-contracts-persistence.md",
        "run-migration": "phase2-run-migration.md",
        "repository-ui": "phase2-repository-ui.md",
        "independent-qa": "phase2-independent-qa.md",
    }
    for lane, filename in expected.items():
        record = manifest["lanes"][lane]
        assert record["allowed_directories"] == []
        assert record["allowed_files"] == [
            f"docs/handoffs/platform-development/{filename}"
        ]


def test_phase2_tasks_and_boundary_are_explicit() -> None:
    task_root = ROOT / "docs/workplans/platform-development/phase-2"
    for name in (
        "TASK-00-INTEGRATION-ACTIVATION.md",
        "TASK-01-CONTRACTS-PERSISTENCE.md",
        "TASK-02-RUN-MIGRATION.md",
        "TASK-03-REPOSITORY-UI.md",
        "TASK-04-INTEGRATION-IMPLEMENTATION.md",
        "TASK-05-INDEPENDENT-QA.md",
    ):
        text = (task_root / name).read_text(encoding="utf-8")
        assert "Objective" in text
    workplan = (
        ROOT / "docs/workplans/platform-development/phase-2-artifact-repository.md"
    ).read_text(encoding="utf-8")
    assert "outside Git" in workplan
    assert "content-addressed" in workplan
    assert "Ordinary deletion is denied" in workplan
    assert "no Phase 3 work" in workplan


def test_phase2_gate_is_deterministic_and_effect_free() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    gate = makefile.split(".PHONY: verify-platform-phase2", maxsplit=1)[1]
    assert "test_platform_phase2_control_plane.py" in gate
    assert "git diff --check" in gate
    for forbidden in (
        "OPENAI_API_KEY",
        "curl ",
        "submit_order",
        "execute_trade",
        "rebalance_portfolio",
    ):
        assert forbidden not in gate
