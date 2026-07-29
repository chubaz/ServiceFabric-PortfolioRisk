"""Architecture guardrails for Thesis Sprint real-data admission."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_active_stage_and_day2_lane_are_frozen() -> None:
    status = json.loads((ROOT / "config/agent/thesis-sprint/status.json").read_text())
    lanes = json.loads((ROOT / "config/agent/thesis-sprint/lanes.json").read_text())
    assert status["current"] == "THESIS-D2-DATA"
    assert status["day_2_stage"] == "real_data_admission"
    assert lanes["integration_order"] == ["day1", "day2", "integration"]
    assert lanes["lanes"]["day2"]["branch"] == "feature/thesis-day2"
    assert lanes["lanes"]["day2"]["allowed_directories"] == [
        "packages/risk_data", "data/schemas/thesis-real-data",
        "examples/portfolio-risk-thesis", "tests/data", "tests/thesis"
    ]


def test_contract_forbids_private_data_and_unsafe_paths() -> None:
    text = (ROOT / "docs/contracts/thesis-real-data-v0.1.md").read_text()
    for term in ("source-inventory", "No network connector", "arbitrary SQL",
                 "ticker-based", "CI uses only tiny schema-compatible synthetic fixtures",
                 "dsf.parquet"):
        assert term in text


def test_makefile_has_explicit_real_data_gate_targets() -> None:
    text = (ROOT / "Makefile").read_text()
    for target in ("test-thesis-real-data", "profile-thesis-real-data",
                   "build-thesis-real-data", "verify-thesis-real-data",
                   "verify-thesis-real-data-daily", "test-thesis-day2",
                   "verify-thesis-day2", "verify-thesis-day2-real",
                   "demo-thesis-day2-real"):
        assert f".PHONY: {target}" in text
    assert "THESIS_REAL_DATA_ROOT" in text
    assert "dsf.parquet" in text


def run_profile(data_root: str, schema_file: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "make", "-s", "profile-thesis-real-data",
            f"THESIS_REAL_DATA_ROOT={data_root}",
            f"THESIS_REAL_SOURCE_SCHEMAS={schema_file}",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_profile_rejects_relative_and_repository_paths(tmp_path: Path) -> None:
    schema_file = tmp_path / "source-schemas.json"
    schema_file.write_text("{}\n")

    relative = run_profile(".", str(schema_file))
    assert relative.returncode != 0
    assert "must be absolute" in relative.stderr

    in_repository = run_profile(str(ROOT), str(schema_file))
    assert in_repository.returncode != 0
    assert "must remain outside Git" in in_repository.stderr


def test_profile_accepts_existing_absolute_external_paths(tmp_path: Path) -> None:
    schema_file = tmp_path / "source-schemas.json"
    schema_file.write_text("{}\n")

    result = run_profile(str(tmp_path), str(schema_file))
    assert result.returncode == 0
    assert "control-plane check PASS" in result.stdout
    assert str(tmp_path) not in result.stdout + result.stderr
