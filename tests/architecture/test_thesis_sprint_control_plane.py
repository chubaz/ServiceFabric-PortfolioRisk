from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.thesis.check_lane_paths import (
    changed_paths,
    is_allowed,
    safe_path,
    validate_changes,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parents[2]


def read_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_thesis_day3_is_complete_and_day4_is_honestly_deferred() -> None:
    assert read_json("config/agent/thesis-sprint/status.json") == {
        "current": "THESIS-DEFERRED",
        "day_1": "complete",
        "day_2": "complete",
        "day_2_stage": "complete",
        "day_3": "complete",
        "day_4": "deferred",
        "soft_qa": "not_run",
        "closeout": "public_fixture_verified_real_panel_not_run",
        "base_tag": "day23-complete",
        "experiment_id": "portfolio-risk-architecture-comparison-v1",
    }
    assert read_json("config/agent/day23/status.json")["current"] == "D23-COMPLETE"
    current = (ROOT / "docs/workplans/current.md").read_text(encoding="utf-8")
    assert "ID: PLATFORM-P1" in current
    assert "Status: accepted" in current
    assert "Phase 0 is accepted" in current
    assert "thesis-sprint/deferred.md" in current
    assert "Days 1–3 remain accepted" in current
    assert "paid real panel and human scientific QA\nwere not run" in current
    deferred = (ROOT / "docs/workplans/thesis-sprint/deferred.md").read_text(
        encoding="utf-8"
    )
    assert "THESIS-DEFERRED" in deferred
    assert "complete 270-call real Day 4 panel" in deferred
    assert "human scientific QA of real-panel results" in deferred


def test_lane_manifest_has_frozen_explicit_ownership() -> None:
    manifest = read_json("config/agent/thesis-sprint/lanes.json")
    assert manifest["namespace"] == "thesis-sprint"
    assert manifest["base_tag"] == "day23-complete"
    assert manifest["integration_order"] == [
        "day1",
        "day2",
        "day3",
        "day4",
        "integration",
    ]
    assert validate_manifest(manifest) == []
    assert manifest["lanes"] == {
        "integration": {
            "branch": "integration/thesis-experiment",
            "allowed_directories": [
                ".github",
                "config/agent/thesis-sprint",
                "docs/workplans/thesis-sprint",
                "docs/contracts",
                "docs/architecture/adr",
                "docs/handoffs/thesis-sprint",
                "scripts/thesis",
                "tests/architecture",
                "tests/integration",
                "tests/journeys",
            ],
            "allowed_files": [
                "AGENTS.md",
                "README.md",
                "Makefile",
                "docs/workplans/current.md",
            ],
        },
        "day3": {
            "branch": "feature/thesis-day3",
            "allowed_directories": [
                "examples/portfolio-risk-thesis",
                "data/fixtures/synthetic/thesis-day3",
                "data/schemas/thesis-agent-architectures",
                "tests/thesis",
            ],
            "allowed_files": ["docs/handoffs/thesis-sprint/day3.md"],
        },
        "day2": {
            "branch": "feature/thesis-day2",
            "allowed_directories": [
                "packages/risk_data",
                "data/schemas/thesis-real-data",
                "examples/portfolio-risk-thesis",
                "tests/data",
                "tests/thesis",
            ],
            "allowed_files": ["docs/handoffs/thesis-sprint/day2.md"],
        },
        "day1": {
            "branch": "feature/thesis-day1",
            "allowed_directories": [
                "examples/portfolio-risk-thesis",
                "data/fixtures/synthetic/thesis-day1",
                "tests/thesis",
            ],
            "allowed_files": ["docs/handoffs/thesis-sprint/day1.md"],
        },
        "day4": {
            "branch": "feature/thesis-day4",
            "allowed_directories": [
                "examples/portfolio-risk-thesis",
                "data/fixtures/synthetic/thesis-day4",
                "data/schemas/thesis-experiment-results",
                "tests/thesis",
            ],
            "allowed_files": ["docs/handoffs/thesis-sprint/day4.md"],
        },
    }


@pytest.mark.parametrize(
    "path",
    (
        "",
        "/absolute.py",
        "../escape.py",
        "tests/../escape.py",
        "tests//double.py",
        "./tests/file.py",
        "tests\\file.py",
        "tests/\nfile.py",
    ),
)
def test_lane_checker_rejects_empty_absolute_unsafe_and_traversal_paths(
    path: str,
) -> None:
    assert safe_path(path) is False


def test_lane_checker_handles_exact_files_directories_types_renames_and_copies() -> None:
    lane = {
        "allowed_files": ["README.md"],
        "allowed_directories": ["tests/thesis"],
    }
    assert is_allowed("README.md", {"README.md"}, ("tests/thesis",))
    assert not is_allowed("README.md/child", {"README.md"}, ("tests/thesis",))
    assert not is_allowed("tests/thesis", {"README.md"}, ("tests/thesis",))
    assert is_allowed("tests/thesis/test_replay.py", {"README.md"}, ("tests/thesis",))

    assert validate_changes(
        [
            ("T", ("tests/thesis/test_type.py",)),
            ("R100", ("tests/thesis/old.py", "tests/thesis/new.py")),
            ("C100", ("README.md", "tests/thesis/copied.md")),
        ],
        lane,
    ) == []
    errors = validate_changes(
        [
            ("R100", ("tests/thesis/old.py", "packages/risk_domain/new.py")),
            ("C100", ("README.md", "../README.md")),
        ],
        lane,
    )
    assert any("packages/risk_domain/new.py" in error for error in errors)
    assert any("../README.md" in error for error in errors)


def test_lane_checker_excludes_later_integration_only_changes(monkeypatch) -> None:
    def fake_run(command: list[str], **kwargs):
        assert command[-1] == "integration/thesis-experiment...feature/thesis-day2"
        assert kwargs == {"check": True, "capture_output": True}

        class Result:
            stdout = b"M\0tests/data/test_bridge.py\0"

        return Result()

    monkeypatch.setattr(
        "scripts.thesis.check_lane_paths.subprocess.run",
        fake_run,
    )

    assert changed_paths(
        "integration/thesis-experiment",
        "feature/thesis-day2",
    ) == [("M", ("tests/data/test_bridge.py",))]


def test_environment_reuses_locked_python311_dependencies_and_paths() -> None:
    bootstrap = (ROOT / "scripts/thesis/bootstrap_environment.sh").read_text(
        encoding="utf-8"
    )
    assert '.venv-thesis}"' in bootstrap
    assert "python3.11" in bootstrap
    assert "--require-hashes" in bootstrap
    assert "requirements/thesis.lock" in bootstrap
    assert "-m pip check" in bootstrap

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    for package_path in (
        "packages/risk_domain/src",
        "packages/risk_planning/src",
        "packages/risk_data/src",
        "packages/risk_capabilities/src",
        "packages/risk_agents/src",
        "packages/risk_analytics/src",
        "examples/portfolio-risk-thesis/src",
    ):
        assert package_path in makefile


def test_make_targets_preserve_baselines_and_stage_eventual_day1_gate() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    targets = (
        "thesis-env",
        "test-thesis-control",
        "test-thesis-day1",
        "test-thesis-integration",
        "test-thesis-journeys",
        "verify-thesis-current",
        "verify-thesis-day1",
        "demo-thesis-day1",
    )
    for target in targets:
        assert f".PHONY: {target}" in makefile

    completion_gate = makefile.split(
        ".PHONY: verify-thesis-day1", maxsplit=1
    )[1].split(".PHONY: verify-thesis-current", maxsplit=1)[0]
    for dependency in (
        "verify-d23-current",
        "test-thesis-control",
        "test-thesis-day1",
        "test-thesis-integration",
        "test-thesis-journeys",
        "check-thesis-day1-fixture-digests",
    ):
        assert dependency in completion_gate

    assert "git diff --check" in completion_gate
    assert "--base day23-complete" not in completion_gate
    assert '--base "$(THESIS_DAY1_LANE_BASE)"' in completion_gate
    assert '--head "$(THESIS_DAY1_LANE_HEAD)"' in completion_gate
    assert "git merge-base --is-ancestor" in completion_gate
    assert "specialist candidate must descend" in completion_gate
    assert (
        "git log --diff-filter=A --format=%H -1 -- "
        "config/agent/thesis-sprint/status.json"
    ) in makefile
    assert "validate_fixture_digests.py" in makefile
    assert "scripts/thesis/run_day1_demo.py" in makefile
    assert 'THESIS_DATA_ROOT="$(THESIS_DATA_ROOT)"' in makefile
    current_gate = makefile.split(
        ".PHONY: verify-thesis-current", maxsplit=1
    )[1].split(".PHONY: demo-thesis-day1", maxsplit=1)[0]
    assert "verify-thesis-day2" in current_gate
    assert (
        "Day 4 public fixture verified; real panel and human QA deferred"
        in current_gate
    )


def test_specialist_workflow_uses_control_plane_base_and_exact_candidate_head() -> None:
    workplan = (
        ROOT / "docs/workplans/thesis-sprint/day-1-data-portfolios-replay.md"
    ).read_text(encoding="utf-8")
    handoff = (ROOT / "docs/handoffs/thesis-sprint/day1.md").read_text(
        encoding="utf-8"
    )
    assert "Create `feature/thesis-day1` from the reviewed integration commit" in workplan
    assert "--diff-filter=A" in workplan
    assert '--base "$thesis_control_plane_base"' in workplan
    assert "THESIS_DAY1_LANE_HEAD=<specialist-candidate-head>" in workplan
    assert "Lane base: reviewed control-plane addition commit" in handoff
    assert "record the exact lane base and candidate head" in handoff


def test_contract_and_adr_freeze_runtime_and_effect_boundaries() -> None:
    text = " ".join(
        "\n".join(
            (ROOT / path).read_text(encoding="utf-8").lower()
            for path in (
                "docs/contracts/thesis-experiment-v0.1.md",
                "docs/architecture/adr/0006-thesis-experiment-runtime.md",
                "docs/workplans/thesis-sprint/day-1-data-portfolios-replay.md",
            )
        ).split()
    )
    for term in (
        "deterministic in-process replay",
        "parquet",
        "available_at <= as_of",
        "timezone-aware utc",
        "fixed",
        "outside git",
        "synthetic",
        "b0",
        "b1",
        "a1",
        "no llm",
        "kafka",
        "redis",
        "websocket",
        "scheduler",
        "network provider",
        "portfolio mutation",
    ):
        assert term in text, term


def test_ci_uses_locked_python_and_current_gate_without_process_host_smoke() -> None:
    workflow = (ROOT / ".github/workflows/thesis-sprint.yml").read_text(
        encoding="utf-8"
    )
    assert "integration/thesis-experiment" in workflow
    assert "branches: [main]" in workflow
    assert "submodules: recursive" in workflow
    assert "python-version: '3.11'" in workflow
    assert "pip install --require-hashes -r requirements/thesis.lock" in workflow
    assert "make verify-thesis-current" in workflow
    assert "make demo-thesis-day3-fixture" in workflow
    assert "make demo-thesis-day1" in workflow
    assert "never invokes private real-data or model gates" in workflow
    assert "run: make verify-thesis-day2-real" not in workflow
    assert "servicefabric" not in workflow.lower()
