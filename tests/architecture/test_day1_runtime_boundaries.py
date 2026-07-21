from __future__ import annotations

from pathlib import Path

from scripts.day1.check_lane_paths import validate_changes

ROOT = Path(__file__).resolve().parents[2]


def lane() -> dict[str, object]:
    return {
        "allowed_files": ["docs/handoffs/day-1/data.md"],
        "allowed_directories": ["packages/risk_data", "tests/data"],
    }


def test_forbidden_type_change_is_rejected() -> None:
    assert validate_changes([("T", ("Makefile",))], lane())


def test_descendant_under_exact_handoff_file_is_rejected() -> None:
    assert validate_changes([("A", ("docs/handoffs/day-1/data.md/extra",))], lane())


def test_rename_validates_source_and_destination() -> None:
    errors = validate_changes([("R100", ("packages/risk_data/old.py", "Makefile"))], lane())
    assert any("Makefile" in error for error in errors)


def test_exact_handoff_file_is_allowed() -> None:
    assert validate_changes([("M", ("docs/handoffs/day-1/data.md",))], lane()) == []


def test_owned_directory_descendant_is_allowed() -> None:
    assert validate_changes([("A", ("packages/risk_data/src/risk_data/reader.py",))], lane()) == []


def test_unsafe_and_empty_paths_are_rejected() -> None:
    errors = validate_changes([("A", ("",)), ("M", ("../Makefile",)), ("M", ("/Makefile",))], lane())
    assert len(errors) == 3


def test_cumulative_gates_do_not_apply_the_integration_lane_to_all_changes() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/day1-preparation.yml").read_text(encoding="utf-8")
    cumulative_check = "--lane integration --base day1-prepared --head HEAD"
    assert cumulative_check not in makefile
    assert cumulative_check not in workflow
