from __future__ import annotations

import json
from pathlib import Path

from scripts.thesis.check_lane_paths import (
    changed_paths,
    validate_changes,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parents[2]


def read_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_phase0_acceptance_is_preserved_under_the_phase1_pointer() -> None:
    status = read_json("config/agent/platform-development/status.json")
    assert status["current"] == "PLATFORM-P1"
    assert status["phase_0"] == "accepted"
    assert status["phase_1"] in {"in_progress", "accepted"}
    assert status["phase_0_accepted_candidate_commit"] == (
        "76651ea8a580832698e99e594581db9c12969dd4"
    )
    assert status["prior_thesis_state"] == "deferred"
    assert status["development_profile_only"] is True
    assert status["external_effects"] == "disabled"
    current = (ROOT / "docs/workplans/current.md").read_text(encoding="utf-8")
    assert "ID: PLATFORM-P1" in current
    assert "Namespace: platform-development" in current
    assert "integration/platform-registry-kernel" in current
    assert "make verify-platform-phase1" in current
    assert "does not reopen or reinterpret" in current
    assert "Phase 0 is accepted" in current


def test_phase0_lane_manifest_freezes_non_overlapping_ownership() -> None:
    manifest = read_json("config/agent/platform-development/lanes.json")
    assert manifest["namespace"] == "platform-development"
    assert manifest["base_commit"] == (
        "81660bd3d4be9c8fb6725e5836e7821f9947eb17"
    )
    assert manifest["waves"] == {
        "activation": ["integration"],
        "parallel-audit": [
            "canonical-decisions",
            "storage-runtime",
            "ui-policy",
        ],
        "synthesis": ["integration"],
        "acceptance": ["independent-qa", "integration"],
    }
    assert validate_manifest(manifest) == []
    assert manifest["frozen_directories"] == ["vendor/servicefabric"]
    assert manifest["rules"]["specialist_may_merge"] is False
    assert manifest["rules"]["shared_contract_owner"] == "integration"

    expected_handoffs = {
        "canonical-decisions": (
            "docs/handoffs/platform-development/phase0-canonical-decisions.md"
        ),
        "storage-runtime": (
            "docs/handoffs/platform-development/phase0-storage-runtime.md"
        ),
        "ui-policy": "docs/handoffs/platform-development/phase0-ui-policy.md",
        "independent-qa": (
            "docs/handoffs/platform-development/phase0-independent-qa.md"
        ),
    }
    for lane_name, handoff in expected_handoffs.items():
        lane = manifest["lanes"][lane_name]
        assert lane["allowed_directories"] == []
        assert lane["allowed_files"] == [handoff]


def test_visible_synthesis_commit_is_within_integration_lane_grant() -> None:
    manifest = read_json("config/agent/platform-development/lanes.json")
    integration = manifest["lanes"]["integration"]
    assert "apps/portfolio-risk-workbench" in integration["allowed_directories"]
    assert "tests/application" in integration["allowed_directories"]
    changes = changed_paths(
        "81660bd3d4be9c8fb6725e5836e7821f9947eb17",
        "21339db19357277ca9a9a1ca50107f1a884d7aeb",
    )
    assert validate_changes(changes, integration) == []


def test_every_phase0_task_has_a_bounded_instruction() -> None:
    task_root = ROOT / "docs/workplans/platform-development/phase-0"
    tasks = {
        "TASK-00-INTEGRATION-ACTIVATION.md": "integration activation",
        "TASK-01-CANONICAL-DECISIONS.md": "Only writable path",
        "TASK-02-STORAGE-RUNTIME.md": "Only writable path",
        "TASK-03-UI-PROFILES-POLICY.md": "Only writable path",
        "TASK-04-INTEGRATION-SYNTHESIS.md": "Integration work",
        "TASK-05-INDEPENDENT-QA.md": "Only writable path",
    }
    for filename, marker in tasks.items():
        text = (task_root / filename).read_text(encoding="utf-8")
        assert marker in text
        assert "Objective" in text


def test_active_agent_instructions_preserve_profile_and_effect_boundaries() -> None:
    instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Active platform development programme" in instructions
    assert "PLATFORM-P1" in instructions
    assert "Real, synthetic, fixture, simulated, missing, and" in instructions
    assert "Studio–Codex controls remain\ndevelopment-only" in instructions
    assert "external effects remain disabled" in instructions


def test_phase0_verification_target_is_deterministic_and_network_free() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    gate = makefile.split(".PHONY: verify-platform-phase0", maxsplit=1)[1]
    assert "verify-platform-phase0: preflight day0-env" in gate
    assert "test_platform_development_control_plane.py" in gate
    assert "test_thesis_sprint_control_plane.py" in gate
    assert "git diff --check" in gate
    for forbidden in ("OPENAI_API_KEY", "curl ", "submit_order", "execute_trade"):
        assert forbidden not in gate


def test_historical_day1_gate_is_lifecycle_neutral() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    day1_gate = makefile.split(".PHONY: verify-day1", maxsplit=1)[1].split(
        ".PHONY: demo-day1-headless", maxsplit=1
    )[0]
    workflow = (ROOT / ".github/workflows/day1-preparation.yml").read_text(
        encoding="utf-8"
    )
    assert 'grep -q "^- ID: D1-"' in day1_gate
    assert 'grep -q "^- ID: D1-"' in workflow
    assert "a later programme owns the active pointer" in day1_gate
    assert "a later programme owns the active pointer" in workflow
    assert "THESIS-" not in day1_gate


def test_historical_thesis_lane_gate_is_lifecycle_neutral() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    thesis_day1_gate = makefile.split(
        ".PHONY: verify-thesis-day1", maxsplit=1
    )[1].split(".PHONY: test-thesis-day3", maxsplit=1)[0]
    assert 'grep -q "^- ID: THESIS-"' in thesis_day1_gate
    assert "Thesis Day 1 lane ownership is historical" in thesis_day1_gate
    assert "a later programme owns the active pointer" in thesis_day1_gate
    assert "git merge-base --is-ancestor" in thesis_day1_gate
    assert "scripts/thesis/check_lane_paths.py" in thesis_day1_gate
