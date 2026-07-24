from __future__ import annotations

import json
from pathlib import Path

import pytest

from risk_data.schema_generation import CONTRACTS, generate as generate_day23_schemas
from scripts.day23.check_lane_paths import (
    validate_changes,
    validate_manifest,
    validate_manifest_changes,
)

ROOT = Path(__file__).resolve().parents[2]


def read_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


PART_KEYS = ("part_1", "part_2", "part_3")


def lifecycle_errors(status: object) -> list[str]:
    if not isinstance(status, dict):
        return ["status must be an object"]
    required = {
        "current",
        *PART_KEYS,
        "soft_qa",
        "base_tag",
        "programme_version",
    }
    if (
        set(status) != required
        or status.get("base_tag") != "day1-complete"
        or status.get("programme_version") != "3-part-v1"
    ):
        return ["status schema, base tag, or programme version is invalid"]
    current = status["current"]
    if current in {f"D23-PART-{number}" for number in range(1, 4)}:
        active = int(str(current).rsplit("-", maxsplit=1)[1]) - 1
        active_state = status[PART_KEYS[active]]
        expected = tuple(
            "complete" if index < active else
            active_state if index == active else
            "queued"
            for index in range(3)
        )
        if active_state not in {"queued", "in_progress", "complete"}:
            return ["current part must be queued, in progress, or complete"]
        if tuple(status[key] for key in PART_KEYS) != expected or status["soft_qa"] != "queued":
            return ["part states are inconsistent with current"]
        return []
    if (
        current == "D23-QA"
        and tuple(status[key] for key in PART_KEYS)
        == ("complete", "complete", "queued")
        and status["soft_qa"] == "queued"
    ):
        return []
    if current == "D23-COMPLETE" and all(status[key] == "complete" for key in PART_KEYS) and status["soft_qa"] == "passed":
        return []
    return ["unsupported Day 2–3 lifecycle state"]


def test_current_lifecycle_state_is_valid_and_matches_part_manifest() -> None:
    status = read_json("config/agent/day23/status.json")
    programme = read_json("config/agent/day23/phases.json")
    assert lifecycle_errors(status) == []
    assert programme["current"] == status["current"]
    assert programme["programme_version"] == status["programme_version"]
    assert [item["status"] for item in programme["parts"]] == [
        status[key] for key in PART_KEYS
    ]


@pytest.mark.parametrize(
    "status",
    [
        {"current": "D23-PART-1", "part_1": "in_progress", "part_2": "queued", "part_3": "queued", "soft_qa": "queued", "base_tag": "day1-complete", "programme_version": "3-part-v1"},
        {"current": "D23-PART-1", "part_1": "complete", "part_2": "queued", "part_3": "queued", "soft_qa": "queued", "base_tag": "day1-complete", "programme_version": "3-part-v1"},
        {"current": "D23-PART-2", "part_1": "complete", "part_2": "queued", "part_3": "queued", "soft_qa": "queued", "base_tag": "day1-complete", "programme_version": "3-part-v1"},
        {"current": "D23-PART-2", "part_1": "complete", "part_2": "in_progress", "part_3": "queued", "soft_qa": "queued", "base_tag": "day1-complete", "programme_version": "3-part-v1"},
        {"current": "D23-PART-3", "part_1": "complete", "part_2": "complete", "part_3": "complete", "soft_qa": "queued", "base_tag": "day1-complete", "programme_version": "3-part-v1"},
        {"current": "D23-QA", "part_1": "complete", "part_2": "complete", "part_3": "queued", "soft_qa": "queued", "base_tag": "day1-complete", "programme_version": "3-part-v1"},
        {"current": "D23-COMPLETE", "part_1": "complete", "part_2": "complete", "part_3": "complete", "soft_qa": "passed", "base_tag": "day1-complete", "programme_version": "3-part-v1"},
    ],
)
def test_supported_lifecycle_states(status: dict[str, str]) -> None:
    assert lifecycle_errors(status) == []


def test_inconsistent_lifecycle_state_is_rejected() -> None:
    status = {"current": "D23-PART-2", "part_1": "in_progress", "part_2": "in_progress", "part_3": "queued", "soft_qa": "queued", "base_tag": "day1-complete", "programme_version": "3-part-v1"}
    assert lifecycle_errors(status)


def test_part_graph_and_storage_zones_are_governed() -> None:
    programme = read_json("config/agent/day23/phases.json")
    assert "phases" not in programme
    assert [item["id"] for item in programme["parts"]] == [
        "D23-PART-1", "D23-PART-2", "D23-PART-3"
    ]
    assert "superseded" in programme["prior_plan"].lower()
    assert programme["storage_zones"] == ["landing", "normalized", "curated", "manifests", "quality", "evidence"]
    assert programme["mutable_zones_external_to_git"] is True


def test_three_lanes_have_non_overlapping_explicit_ownership() -> None:
    manifest = read_json("config/agent/day23/lanes.json")
    lanes = manifest["lanes"]
    assert set(lanes) == {"integration", "monitoring-core", "experience"}
    assert manifest["integration_order"] == [
        "monitoring-core",
        "experience",
        "integration",
    ]
    assert validate_manifest(manifest) == []
    owned = []
    for lane in lanes.values():
        assert "allowed_paths" not in lane
        assert isinstance(lane["allowed_directories"], list)
        assert isinstance(lane["allowed_files"], list)
        owned.extend(lane["allowed_directories"] + lane["allowed_files"])
    assert len(owned) == len(set(owned))


def test_lane_manifest_rejects_ambiguous_and_overlapping_allowances() -> None:
    ambiguous = {
        "lanes": {
            "one": {
                "allowed_paths": ["tests"],
                "allowed_directories": [],
                "allowed_files": [],
            }
        }
    }
    overlapping = {
        "lanes": {
            "one": {"allowed_directories": ["tests/data"], "allowed_files": []},
            "two": {"allowed_directories": [], "allowed_files": ["tests/data"]},
        }
    }
    assert validate_manifest(ambiguous)
    assert validate_manifest(overlapping)


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


def test_completion_gates_use_all_lanes_and_ci_fetches_base_tag() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    target = makefile.split(".PHONY: verify-d23-phase1", maxsplit=1)[1].split(
        ".PHONY: demo-d23-phase1", maxsplit=1
    )[0]
    assert "--all-lanes" in target
    assert "--lane integration" not in target
    workflow = (ROOT / ".github/workflows/day23.yml").read_text(encoding="utf-8")
    assert "fetch-depth: 0" in workflow
    assert "fetch-tags: true" in workflow
    assert "make verify-d23-current" in workflow
    assert "make demo-d23-part2" in workflow
    assert "servicefabric-d23-phase1-smoke" not in workflow
    assert "servicefabric-d23-part2-smoke" not in workflow


def test_part_2_is_complete_and_part_3_is_queued_without_qa_pass() -> None:
    status = read_json("config/agent/day23/status.json")
    assert status == {
        "current": "D23-PART-3",
        "part_1": "complete",
        "part_2": "complete",
        "part_3": "queued",
        "soft_qa": "queued",
        "base_tag": "day1-complete",
        "programme_version": "3-part-v1",
    }
    current = (ROOT / "docs/workplans/current.md").read_text(encoding="utf-8").lower()
    assert "id: d23-part-3" in current
    assert "part 2 integration accepted" in current
    assert "part 1 and part 2 are complete" in current
    assert "remains queued" in current
    assert "no qa pass claim" in current


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


def test_part_2_contract_vocabulary_and_metric_conventions_are_frozen() -> None:
    text = " ".join(
        "\n".join(
            (ROOT / path).read_text(encoding="utf-8").lower()
            for path in (
                "docs/contracts/portfolio-data-context-v0.1.md",
                "docs/contracts/event-dataset-v0.1.md",
                "docs/contracts/monitoring-policy-v0.1.md",
                "docs/contracts/replay-evaluation-v0.1.md",
            )
        ).split()
    )
    for term in (
        "portfolio snapshot",
        "market dataset revision",
        "fundamental dataset revision",
        "crosswalk revision",
        "event dataset revision",
        "mapping coverage",
        "unmapped positions",
        "ambiguous mappings",
        "stale observations",
        "source_event_id",
        "local_event_id",
        "entity_id",
        "event_time",
        "relevance",
        "sentiment",
        "novelty",
        "retraction",
        "percentage-move",
        "concentration",
        "event-relevance",
        "negative-sentiment",
        "stale-data",
        "tail-risk",
        "scenario-loss",
        "one-to-one deterministic",
        "true positives",
        "false positives",
        "false negatives",
        "precision = tp / (tp + fp)",
        "recall = tp / (tp + fn)",
        "lead_time",
        "detection_delay",
        "abstentions",
        "sample-size",
        "null",
        "no look-ahead",
        "no predictive claim",
    ):
        assert term in text, term


def test_part_2_make_targets_and_current_gate_are_declared() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target in (
        "test-d23-monitoring-core",
        "test-d23-monitoring-experience",
        "test-d23-part2-integration",
        "test-d23-part2-journeys",
        "verify-d23-part2",
        "demo-d23-part2",
        "servicefabric-d23-part2-smoke",
        "verify-d23-current",
        "check-d23-application-manifest",
    ):
        assert f".PHONY: {target}" in makefile
    assert "config/agent/day23/part1-lanes.json" in makefile
    assert "--manifest config/agent/day23/lanes.json" in makefile


def test_part_2_demo_smoke_and_ci_are_complete_without_process_host_claim() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "scripts/day23/run_part2_demo.py" in makefile
    assert "scripts/day23/servicefabric_part2_smoke.sh" in makefile
    assert "unavailable until implementation is complete" not in makefile

    smoke = (ROOT / "scripts/day23/servicefabric_part2_smoke.sh").read_text(
        encoding="utf-8"
    )
    assert "apps/portfolio-risk-workbench/stage_package.py" in smoke
    assert "bootstrap_staged_servicefabric_runtime.py" in smoke
    assert smoke.index("# The pinned upstream Text Utility baseline") < smoke.index(
        '"$servicefabric" apps install "$staged_package"'
    )
    for tool_id in (
        "portfolio.data_context.create",
        "events.query.as_of",
        "monitoring.policy.evaluate",
        "monitoring.run.contextual",
        "monitoring.replay",
        "monitoring.evaluate",
        "monitoring.report.render",
    ):
        assert tool_id in smoke
    for proof in (
        "capability returned non-empty or missing effects",
        "unexpectedly executed after Workbench stop",
        "Workbench process remains alive after stop",
        "modified the pinned upstream ServiceFabric tree",
    ):
        assert proof in smoke

    workflow = (ROOT / ".github/workflows/day23.yml").read_text(encoding="utf-8")
    for command in (
        "make verify-day0",
        "make verify-day1",
        "make verify-d23-phase1",
        "make verify-d23-part2",
        "make demo-d23-part2",
        "make check-d23-application-manifest",
        "git diff --check",
    ):
        assert command in workflow
    assert "servicefabric-d23-part2-smoke" not in workflow
