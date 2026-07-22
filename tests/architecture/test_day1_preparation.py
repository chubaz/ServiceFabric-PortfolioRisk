from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from scripts.day1.check_preparation import PREPARED_STATUS, status_errors, validate, wave_1b_workbench_errors, workplan_errors
from scripts.day1.verify_current import verification_target

ROOT = Path(__file__).resolve().parents[2]


def payload(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


@pytest.mark.parametrize("from_command_line", [False, True])
def test_empty_day1_venv_uses_repository_default(from_command_line: bool) -> None:
    environment = {**os.environ, "DAY1_VENV": ""}
    command = ["make", "--no-print-directory", "-n"]
    if from_command_line:
        command.append("DAY1_VENV=")
    command.append("day1-env")

    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    expected_python = ROOT / ".venv-day1/bin/python"
    assert f'test -x "{expected_python}"' in result.stdout
    assert 'test -x "/bin/python"' not in result.stdout


def test_lifecycle_aware_checker_passes_for_day1_qa() -> None:
    assert validate() == []


def test_status_schema_and_day0_unchanged() -> None:
    assert payload("config/agent/day1/status.json") == {
        "current": "D1-QA", "preparation": "complete", "wave_1a": "complete",
        "wave_1b": "complete", "wave_1c": "complete", "soft_qa": "queued", "base_tag": "day0-complete",
    }
    assert payload("config/agent/day0/status.json")["current"] == "D0-COMPLETE"
    assert payload("config/agent/day0/status.json")["soft_qa"] == "passed"


def test_prepared_baseline_remains_strict() -> None:
    assert status_errors(PREPARED_STATUS, require_prepared=True) == []
    assert status_errors(payload("config/agent/day1/status.json"), require_prepared=True)


def test_all_supported_lifecycle_states_are_valid() -> None:
    states = [
        PREPARED_STATUS,
        {**PREPARED_STATUS, "wave_1a": "in_progress"},
        {**PREPARED_STATUS, "current": "D1-WAVE-1B", "wave_1a": "complete", "wave_1b": "in_progress"},
        {**PREPARED_STATUS, "current": "D1-WAVE-1C", "wave_1a": "complete", "wave_1b": "complete", "wave_1c": "in_progress"},
        {**PREPARED_STATUS, "current": "D1-QA", "wave_1a": "complete", "wave_1b": "complete", "wave_1c": "complete"},
        {**PREPARED_STATUS, "current": "D1-COMPLETE", "wave_1a": "complete", "wave_1b": "complete", "wave_1c": "complete", "soft_qa": "passed"},
    ]
    assert all(status_errors(state) == [] for state in states)


@pytest.mark.parametrize(
    ("status", "workplan_id", "workplan_status"),
    [
        (PREPARED_STATUS, "D1-WAVE-1A", "queued; implementation has not started"),
        ({**PREPARED_STATUS, "wave_1a": "in_progress"}, "D1-WAVE-1A", "in progress"),
        ({**PREPARED_STATUS, "current": "D1-WAVE-1B", "wave_1a": "complete", "wave_1b": "in_progress"}, "D1-WAVE-1B", "in progress"),
        ({**PREPARED_STATUS, "current": "D1-WAVE-1C", "wave_1a": "complete", "wave_1b": "complete", "wave_1c": "in_progress"}, "D1-WAVE-1C", "in progress"),
        ({**PREPARED_STATUS, "current": "D1-QA", "wave_1a": "complete", "wave_1b": "complete", "wave_1c": "complete"}, "D1-QA", "ready for soft QA"),
        ({**PREPARED_STATUS, "current": "D1-COMPLETE", "wave_1a": "complete", "wave_1b": "complete", "wave_1c": "complete", "soft_qa": "passed"}, "D1-COMPLETE", "complete"),
    ],
)
def test_workplan_validation_tracks_lifecycle(status: dict, workplan_id: str, workplan_status: str) -> None:
    text = f"# Current Workplan\n\n- ID: `{workplan_id}`\n- Status: {workplan_status}\n"
    assert workplan_errors(status, text) == []


def test_workplan_validation_rejects_stale_wave_1a_pointer() -> None:
    status = {**PREPARED_STATUS, "current": "D1-WAVE-1B", "wave_1a": "complete", "wave_1b": "in_progress"}
    text = "# Current Workplan\n\n- ID: `D1-WAVE-1A`\n- Status: in progress\n"
    assert workplan_errors(status, text)


def test_verification_target_rejects_inconsistent_later_state() -> None:
    status = {**PREPARED_STATUS, "current": "D1-WAVE-1B", "wave_1a": "complete", "wave_1b": "in_progress", "wave_1c": "complete", "soft_qa": "passed"}
    with pytest.raises(ValueError, match="valid lifecycle"):
        verification_target(status)


def test_verification_targets_only_completed_wave_gates() -> None:
    assert verification_target({**PREPARED_STATUS, "wave_1a": "in_progress"}) is None
    assert verification_target({**PREPARED_STATUS, "current": "D1-WAVE-1B", "wave_1a": "complete", "wave_1b": "in_progress"}) == "verify-wave-1a"
    assert verification_target({**PREPARED_STATUS, "current": "D1-WAVE-1C", "wave_1a": "complete", "wave_1b": "complete", "wave_1c": "in_progress"}) == "verify-wave-1b"


def test_wave_dependency_structure() -> None:
    waves = payload("config/agent/day1/waves.json")
    assert [wave["id"] for wave in waves["waves"]] == ["D1-WAVE-1A", "D1-WAVE-1B", "D1-WAVE-1C"]
    assert waves["waves"][0]["depends_on"] == []
    assert waves["waves"][1]["depends_on"] == ["D1-WAVE-1A"]
    assert set(waves["waves"][2]["depends_on"]) == {"D1-WAVE-1A", "D1-WAVE-1B"}


def test_lane_non_overlap_and_exact_handoffs() -> None:
    lanes = payload("config/agent/day1/lanes.json")["lanes"]
    assert all("allowed_paths" not in lane for lane in lanes.values())
    owned = []
    for lane_name, lane in lanes.items():
        handoffs = [item for item in lane["allowed_files"] if item.startswith("docs/handoffs/day-1/")]
        assert len(handoffs) == (2 if lane_name == "integration" else 1)
        assert handoffs[0].endswith(".md")
        owned += lane["allowed_directories"] + [item for item in lane["allowed_files"] if item not in handoffs]
    assert len(owned) == len(set(owned))


def test_profiles_and_boundaries_are_explicit() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in [
        ROOT / "docs/architecture/adr/0004-day1-operating-profiles-and-data-boundary.md",
        ROOT / "docs/contracts/day1-portfolio-input-v0.1.md",
        ROOT / "docs/rights/day1-provider-access-boundary.md",
    ]).lower()
    assert "research" in text and "personal_portfolio" in text
    assert "enabled: false" in text and "arbitrary sql" in text
    assert "notebook execution" in text
    assert "broker" in text and "order" in text and "rebalance" in text


def test_completed_wave_1b_requires_human_readable_workbench_bindings() -> None:
    status = payload("config/agent/day1/status.json")
    application = (ROOT / "apps/portfolio-risk-workbench/app.py").read_text(encoding="utf-8")
    portfolio = (ROOT / "apps/portfolio-risk-workbench/templates/portfolio.html").read_text(encoding="utf-8")
    providers = (ROOT / "apps/portfolio-risk-workbench/templates/providers.html").read_text(encoding="utf-8")

    assert wave_1b_workbench_errors(status, application, portfolio, providers) == []
    completed = {**status, "wave_1b": "complete", "wave_1c": "in_progress", "current": "D1-WAVE-1C"}
    assert wave_1b_workbench_errors(completed, application, portfolio, providers) == []

    errors = wave_1b_workbench_errors(completed, "", "", "")
    assert any("bindings are missing" in error for error in errors)
    assert any("portfolio" in error.lower() for error in errors)
    assert any("provider catalogue" in error.lower() for error in errors)


def test_primary_interface_and_analytics_metadata() -> None:
    ia = (ROOT / "docs/design/day1-information-architecture.md").read_text(encoding="utf-8").lower()
    risk = (ROOT / "docs/contracts/day1-risk-analysis-v0.1.md").read_text(encoding="utf-8").lower()
    assert "server-rendered semantic html" in ia
    assert "json endpoints remain" in ia
    for method in ("simple returns", "log returns", "annualized volatility", "maximum drawdown", "historical var", "historical expected shortfall", "deterministic scenario shocks", "portfolio contribution summaries"):
        assert method in risk
    for metadata in ("confidence_level", "horizon", "sample_period", "observation_count", "methodology", "assumptions", "warnings", "limitations", "evidence"):
        assert metadata in risk


def test_no_effect_paths_are_tracked() -> None:
    tracked = __import__("subprocess").run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    forbidden = re.compile(r"(^|/)(broker|brokers|orders?|order_execution|trading|rebalance)(/|$)", re.I)
    assert not [path for path in tracked if forbidden.search(path)]
