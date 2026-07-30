import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _make_recipe(makefile: str, target: str) -> str:
    match = re.search(
        rf"^{re.escape(target)}:[^\n]*\n(?P<recipe>(?:\t[^\n]*\n)+)",
        makefile,
        flags=re.MULTILINE,
    )
    assert match is not None, target
    return match.group("recipe")


def test_day4_activation_state_and_specialist_lane_are_explicit() -> None:
    status = json.loads(
        (ROOT / "config/agent/thesis-sprint/status.json").read_text(
            encoding="utf-8"
        )
    )
    assert status["current"] == "THESIS-D4"
    assert status["day_3"] == "complete"
    assert status["day_4"] == "in_progress"
    assert status["soft_qa"] == "queued"

    lanes = json.loads(
        (ROOT / "config/agent/thesis-sprint/lanes.json").read_text(
            encoding="utf-8"
        )
    )
    assert lanes["integration_order"] == [
        "day1",
        "day2",
        "day3",
        "day4",
        "integration",
    ]
    assert lanes["lanes"]["day4"] == {
        "branch": "feature/thesis-day4",
        "allowed_directories": [
            "examples/portfolio-risk-thesis",
            "data/fixtures/synthetic/thesis-day4",
            "data/schemas/thesis-experiment-results",
            "tests/thesis",
        ],
        "allowed_files": ["docs/handoffs/thesis-sprint/day4.md"],
    }


def test_make_exposes_integrated_day4_gates_without_release_claim() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert ".RECIPEPREFIX" not in makefile

    targets = (
        "test-thesis-day4-boundaries",
        "test-thesis-day4",
        "demo-thesis-day4-fixture",
        "verify-thesis-day4",
        "verify-thesis-day4-real",
        "run-thesis-day4-direct",
        "serve-thesis-day4-dashboard",
        "verify-thesis-current",
    )
    for target in targets:
        assert f".PHONY: {target}" in makefile

    boundary_recipe = _make_recipe(makefile, "test-thesis-day4-boundaries")
    assert "tests/architecture/test_thesis_day4_boundaries.py" in boundary_recipe

    expected_recipe_markers = {
        "test-thesis-day4": "test_day4_runner.py",
        "demo-thesis-day4-fixture": "run-day4",
        "verify-thesis-day4": "fixture verification: PASS",
        "verify-thesis-day4-real": "--require-exit-criteria",
        "run-thesis-day4-direct": "--provider openai_responses",
        "serve-thesis-day4-dashboard": "http.server 8765",
    }
    for target, marker in expected_recipe_markers.items():
        recipe = _make_recipe(makefile, target)
        assert marker in recipe
        assert "not integrated" not in recipe

    assert "verify-thesis-current: verify-thesis-day4" in makefile
    current_recipe = _make_recipe(makefile, "verify-thesis-current")
    assert "Day 4 in progress; human QA queued" in current_recipe
    assert "release approved" not in current_recipe.casefold()


def test_ci_runs_only_the_current_public_fixture_gate() -> None:
    workflow = (
        ROOT / ".github/workflows/thesis-sprint.yml"
    ).read_text(encoding="utf-8")
    lowered = workflow.lower()

    assert "make verify-thesis-current" in workflow
    assert "OPENAI_API_KEY: ''" in workflow
    assert "make demo-thesis-day3-fixture" in workflow
    assert "make demo-thesis-day1" in workflow
    for boundary in (
        "fixture-only",
        "no api key",
        "network-blocked fixture provider",
        "public synthetic data only",
        "never invokes private real-data or model gates",
    ):
        assert boundary in lowered

    assert "run: make verify-thesis-day4-real" not in workflow
    assert "run: make run-thesis-day4-direct" not in workflow


def test_day4_contract_freezes_counts_firewall_and_descriptive_boundary() -> None:
    documents = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "docs/workplans/thesis-sprint/day-4-experiment-results.md",
            "docs/contracts/thesis-day4-evaluation-v0.1.md",
            "docs/architecture/adr/0008-thesis-day4-evaluation.md",
            "docs/handoffs/thesis-sprint/day4.md",
        )
    )
    normalized = " ".join(documents.lower().split())

    for frozen in (
        "45 contexts",
        "135 primary",
        "18 additional",
        "153 total",
        "45 labels",
        "270",
        "two stress",
        "quiet control",
        "five-business-day future outcome",
        "event_window or outcome",
        "positive-label abstention counts as a false negative",
        "provider error is an execution failure",
        "closest eligible prior unmatched alert",
        "affected-position jaccard",
        "evidence-reference jaccard",
        "pricing_unavailable",
        "explicit human qa",
    ):
        assert frozen in normalized, frozen

    for contract_name in (
        "HistoricalWindow",
        "PortfolioDayKey",
        "Day4ExperimentManifest",
        "Day4ExecutionPlan",
        "Day4TaskReceipt",
        "ArchitectureObservation",
        "ArchitectureEvaluation",
        "RepeatabilityEvaluation",
        "Day4RunManifest",
    ):
        assert f"`{contract_name}`" in documents

    assert "No label\nfile path" in documents
    assert "no significance test" in normalized
    assert "no architecture recommendation" in normalized
    assert "investment-performance claim" in normalized
    assert ".RECIPEPREFIX" not in (ROOT / "Makefile").read_text(encoding="utf-8")
