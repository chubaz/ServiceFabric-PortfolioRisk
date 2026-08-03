from __future__ import annotations

import json
from pathlib import Path

from scripts.thesis.check_lane_paths import validate_manifest


ROOT = Path(__file__).resolve().parents[2]


def _json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_phase1_is_active_from_the_accepted_phase0_merge() -> None:
    status = _json("config/agent/platform-development/status.json")
    assert status["current"] == "PLATFORM-P1"
    assert status["phase_0"] == "accepted"
    assert status["phase_1"] in {"in_progress", "accepted"}
    assert status["baseline_commit"] == (
        "21339db19357277ca9a9a1ca50107f1a884d7aeb"
    )
    assert status["development_profile_only"] is True
    assert status["external_effects"] == "disabled"


def test_phase1_lanes_are_bounded_and_non_overlapping() -> None:
    manifest = _json("config/agent/platform-development/phase1-lanes.json")
    assert manifest["namespace"] == "platform-development-phase1"
    assert manifest["base_commit"] == (
        "21339db19357277ca9a9a1ca50107f1a884d7aeb"
    )
    assert validate_manifest(manifest) == []
    assert manifest["rules"]["canonical_definitions_are_indexed_not_duplicated"]
    assert manifest["rules"]["shared_contract_owner"] == "integration"
    assert manifest["frozen_directories"] == ["vendor/servicefabric"]

    expected = {
        "registry-contracts": "phase1-contracts-persistence.md",
        "registry-ui": "phase1-catalogue-ui.md",
        "registry-sources": "phase1-source-migration.md",
        "independent-qa": "phase1-independent-qa.md",
    }
    for lane, filename in expected.items():
        record = manifest["lanes"][lane]
        assert record["allowed_directories"] == []
        assert record["allowed_files"] == [
            f"docs/handoffs/platform-development/{filename}"
        ]


def test_every_phase1_task_has_a_bounded_instruction() -> None:
    task_root = ROOT / "docs/workplans/platform-development/phase-1"
    expected = {
        "TASK-00-INTEGRATION-ACTIVATION.md": "integration activation",
        "TASK-01-CONTRACTS-PERSISTENCE.md": "Only writable path",
        "TASK-02-CATALOGUE-UI.md": "Only writable path",
        "TASK-03-SOURCE-MIGRATION.md": "Only writable path",
        "TASK-04-INTEGRATION-IMPLEMENTATION.md": "Integration work",
        "TASK-05-INDEPENDENT-QA.md": "Only writable path",
    }
    for name, marker in expected.items():
        text = (task_root / name).read_text(encoding="utf-8")
        assert "Objective" in text
        assert marker in text


def test_phase1_workplan_draws_the_projection_and_effect_boundaries() -> None:
    workplan = (
        ROOT / "docs/workplans/platform-development/phase-1-registry-kernel.md"
    ).read_text(encoding="utf-8")
    assert "not another copy" in workplan
    assert "outside Git" in workplan
    assert "no financial effects" in workplan
    assert "No Phase 2 work" in workplan


def test_phase1_gate_is_deterministic_and_network_free() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    gate = makefile.split(".PHONY: verify-platform-phase1", maxsplit=1)[1]
    assert "tests/registry" in gate
    assert "tests/application/test_registry_api.py" in gate
    assert "git diff --check" in gate
    for forbidden in ("OPENAI_API_KEY", "curl ", "submit_order", "execute_trade"):
        assert forbidden not in gate
