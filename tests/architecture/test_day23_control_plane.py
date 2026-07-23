from __future__ import annotations

import json
from pathlib import Path

import pytest

from risk_data.schema_generation import CONTRACTS, generate as generate_day23_schemas
from scripts.day23.check_lane_paths import validate_changes, validate_manifest_changes

ROOT = Path(__file__).resolve().parents[2]


def read_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


PHASE_KEYS = ("phase_1", "phase_2", "phase_3", "phase_4")


def lifecycle_errors(status: object) -> list[str]:
    if not isinstance(status, dict):
        return ["status must be an object"]
    required = {"current", *PHASE_KEYS, "soft_qa", "base_tag"}
    if set(status) != required or status.get("base_tag") != "day1-complete":
        return ["status schema or base tag is invalid"]
    current = status["current"]
    if current in {f"D23-PHASE-{number}" for number in range(1, 5)}:
        active = int(str(current).rsplit("-", maxsplit=1)[1]) - 1
        active_state = status[PHASE_KEYS[active]]
        expected = tuple(
            "complete" if index < active else
            active_state if index == active else
            "queued"
            for index in range(4)
        )
        if active_state not in {"queued", "in_progress", "complete"}:
            return ["current phase must be queued, in progress, or complete"]
        if tuple(status[key] for key in PHASE_KEYS) != expected or status["soft_qa"] != "queued":
            return ["phase states are inconsistent with current"]
        return []
    if current == "D23-QA" and all(status[key] == "complete" for key in PHASE_KEYS) and status["soft_qa"] == "queued":
        return []
    if current == "D23-COMPLETE" and all(status[key] == "complete" for key in PHASE_KEYS) and status["soft_qa"] == "passed":
        return []
    return ["unsupported Day 2–3 lifecycle state"]


def test_current_lifecycle_state_is_valid_and_matches_phase_manifest() -> None:
    status = read_json("config/agent/day23/status.json")
    phases = read_json("config/agent/day23/phases.json")
    assert lifecycle_errors(status) == []
    assert phases["current"] == status["current"]
    assert [item["status"] for item in phases["phases"]] == [status[key] for key in PHASE_KEYS]


@pytest.mark.parametrize(
    "status",
    [
        {"current": "D23-PHASE-1", "phase_1": "in_progress", "phase_2": "queued", "phase_3": "queued", "phase_4": "queued", "soft_qa": "queued", "base_tag": "day1-complete"},
        {"current": "D23-PHASE-1", "phase_1": "complete", "phase_2": "queued", "phase_3": "queued", "phase_4": "queued", "soft_qa": "queued", "base_tag": "day1-complete"},
        {"current": "D23-PHASE-2", "phase_1": "complete", "phase_2": "queued", "phase_3": "queued", "phase_4": "queued", "soft_qa": "queued", "base_tag": "day1-complete"},
        {"current": "D23-PHASE-2", "phase_1": "complete", "phase_2": "in_progress", "phase_3": "queued", "phase_4": "queued", "soft_qa": "queued", "base_tag": "day1-complete"},
        {"current": "D23-PHASE-4", "phase_1": "complete", "phase_2": "complete", "phase_3": "complete", "phase_4": "complete", "soft_qa": "queued", "base_tag": "day1-complete"},
        {"current": "D23-QA", "phase_1": "complete", "phase_2": "complete", "phase_3": "complete", "phase_4": "complete", "soft_qa": "queued", "base_tag": "day1-complete"},
        {"current": "D23-COMPLETE", "phase_1": "complete", "phase_2": "complete", "phase_3": "complete", "phase_4": "complete", "soft_qa": "passed", "base_tag": "day1-complete"},
    ],
)
def test_supported_lifecycle_states(status: dict[str, str]) -> None:
    assert lifecycle_errors(status) == []


def test_inconsistent_lifecycle_state_is_rejected() -> None:
    status = {"current": "D23-PHASE-2", "phase_1": "in_progress", "phase_2": "in_progress", "phase_3": "queued", "phase_4": "queued", "soft_qa": "queued", "base_tag": "day1-complete"}
    assert lifecycle_errors(status)


def test_phase_graph_and_storage_zones_are_governed() -> None:
    phases = read_json("config/agent/day23/phases.json")
    assert [item["id"] for item in phases["phases"]] == [
        "D23-PHASE-1", "D23-PHASE-2", "D23-PHASE-3", "D23-PHASE-4"
    ]
    assert phases["storage_zones"] == ["landing", "normalized", "curated", "manifests", "quality", "evidence"]
    assert phases["mutable_zones_external_to_git"] is True


def test_three_lanes_have_non_overlapping_explicit_ownership() -> None:
    lanes = read_json("config/agent/day23/lanes.json")["lanes"]
    assert set(lanes) == {"integration", "data-platform", "experience"}
    owned = []
    for lane in lanes.values():
        assert "allowed_paths" not in lane
        assert isinstance(lane["allowed_directories"], list)
        assert isinstance(lane["allowed_files"], list)
        owned.extend(lane["allowed_directories"] + lane["allowed_files"])
    assert len(owned) == len(set(owned))


def test_lane_checker_handles_exact_files_types_and_both_rename_copy_paths() -> None:
    lane = {"allowed_files": ["README.md"], "allowed_directories": ["tests/data"]}
    assert validate_changes([("M", ("README.md",)), ("T", ("tests/data/a.py",))], lane) == []
    errors = validate_changes([
        ("R100", ("tests/data/old.py", "README.md")),
        ("C100", ("README.md", "../Makefile")),
        ("T", ("/Makefile",)),
        ("A", ("README.md/child",)),
    ], lane)
    assert any("../Makefile" in error for error in errors)
    assert any("/Makefile" in error for error in errors)
    assert any("README.md/child" in error for error in errors)


def test_cumulative_checker_accepts_paths_from_each_owning_lane() -> None:
    lanes = read_json("config/agent/day23/lanes.json")["lanes"]
    changes = [
        ("M", ("Makefile",)),
        ("A", ("packages/risk_data/src/risk_data/local_import.py",)),
        ("A", ("apps/portfolio-risk-workbench/templates/datasets.html",)),
        ("R100", ("tests/data/old.py", "tests/application/new.py")),
    ]
    assert validate_manifest_changes(changes, lanes) == []
    assert validate_manifest_changes([("T", ("vendor/servicefabric/README.md",))], lanes)


def test_completion_gate_uses_all_lanes_and_ci_fetches_base_tag() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    target = makefile.split(".PHONY: verify-d23-phase1", maxsplit=1)[1].split(
        ".PHONY: demo-d23-phase1", maxsplit=1
    )[0]
    assert "--all-lanes" in target
    assert "--lane integration" not in target
    workflow = (ROOT / ".github/workflows/day23.yml").read_text(encoding="utf-8")
    assert "fetch-depth: 0" in workflow
    assert "fetch-tags: true" in workflow
    assert "make demo-d23-phase1" in workflow
    assert "servicefabric-d23-phase1-smoke" not in workflow


def test_phase_1_closure_is_complete_and_phase_2_is_only_queued() -> None:
    status = read_json("config/agent/day23/status.json")
    assert status == {
        "current": "D23-PHASE-2",
        "phase_1": "complete",
        "phase_2": "queued",
        "phase_3": "queued",
        "phase_4": "queued",
        "soft_qa": "queued",
        "base_tag": "day1-complete",
    }
    current = (ROOT / "docs/workplans/current.md").read_text(encoding="utf-8").lower()
    assert "status: queued; not started" in current
    assert "phase 2 is queued and has not started" in current


def test_phase_1_demo_and_local_servicefabric_smoke_are_real_gates() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "scripts/day23/run_phase1_demo.py" in makefile
    assert "scripts/day23/servicefabric_phase1_smoke.sh" in makefile
    assert "control-plane only; process-host smoke is not run" not in makefile

    smoke = (ROOT / "scripts/day23/servicefabric_phase1_smoke.sh").read_text(
        encoding="utf-8"
    )
    for tool_id in (
        "data.provider.catalog",
        "data.import.preview",
        "data.dataset.list",
        "data.query.fixed",
    ):
        assert tool_id in smoke
    assert "capability returned non-empty or missing effects" in smoke
    assert "unexpectedly executed after Workbench stop" in smoke
    assert "Workbench process remains alive after stop" in smoke


def test_phase_1_contract_schema_snapshots_are_complete_and_reproducible(
    tmp_path: Path,
) -> None:
    committed = ROOT / "data" / "schemas" / "day23"
    generated = tmp_path / "day23"
    generate_day23_schemas(generated)

    committed_schemas = {
        path.name: path.read_bytes() for path in committed.glob("*.schema.json")
    }
    generated_schemas = {
        path.name: path.read_bytes() for path in generated.glob("*.schema.json")
    }
    assert len(committed_schemas) == len(CONTRACTS)
    assert committed_schemas == generated_schemas


def test_phase_1_contract_vocabulary_and_boundaries_are_present() -> None:
    text = "\n".join(
        (ROOT / path).read_text(encoding="utf-8").lower()
        for path in (
            "docs/contracts/provider-dataset-v0.1.md",
            "docs/contracts/point-in-time-data-v0.1.md",
            "docs/rights/day23-provider-register.md",
            "docs/workplans/day-2-3/phase-1-local-research-data-plane.md",
        )
    )
    for term in ("provider", "dataset_revision", "rights_state", "access_state", "local_source_digest",
                 "source_schema", "field_mapping", "source_units", "transformations", "observed_at",
                 "available_at", "retrieved_at", "as_of", "quality_report", "immutable", "crosswalk",
                 "fixed", "publication", "landing", "normalized", "curated", "manifests", "quality",
                 "evidence", "arbitrary sql", "look-ahead", "no external api call"):
        assert term in text, term
