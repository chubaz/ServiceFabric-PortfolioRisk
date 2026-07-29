"""Architecture guardrails for Thesis Sprint real-data admission."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_day2_is_complete_and_lane_ownership_remains_frozen() -> None:
    status = json.loads((ROOT / "config/agent/thesis-sprint/status.json").read_text())
    lanes = json.loads((ROOT / "config/agent/thesis-sprint/lanes.json").read_text())
    assert status["current"] == "THESIS-D3"
    assert status["day_2"] == "complete"
    assert status["day_2_stage"] == "complete"
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
    verify = text.split(".PHONY: verify-thesis-real-data", 1)[1].split(
        ".PHONY: verify-thesis-real-data-daily", 1
    )[0]
    assert "verify-thesis-real-data: test-thesis-real-data build-thesis-real-data" in verify
    daily = text.split(".PHONY: verify-thesis-real-data-daily", 1)[1].split(
        ".PHONY: test-thesis-real-portfolios", 1
    )[0]
    assert "$(MAKE) verify-thesis-real-data" in daily
    assert "$(MAKE) build-thesis-real-data" not in daily


def test_portfolio_gates_invoke_real_commands_and_fail_closed() -> None:
    text = (ROOT / "Makefile").read_text()
    assert "tests/thesis/test_day2_real_portfolios.py" in text
    assert "-m portfolio_risk_thesis.cli init-real-portfolios" in text
    assert "-m portfolio_risk_thesis.cli validate-real-portfolios" in text
    for target in ("materialize-thesis-real-portfolios", "verify-thesis-real-portfolios"):
        result = subprocess.run(
            ["make", "-s", target],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode != 0
        assert "ERROR: set THESIS_REAL_" in result.stderr


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
    assert "THESIS_REAL_MANIFEST" in in_repository.stderr


def test_profile_accepts_existing_absolute_external_paths(tmp_path: Path) -> None:
    schema_file = tmp_path / "source-schemas.json"
    schema_file.write_text("{}\n")

    result = run_profile(str(tmp_path), str(schema_file))
    assert result.returncode != 0
    assert "THESIS_REAL_MANIFEST" in result.stderr
    assert str(tmp_path) not in result.stdout + result.stderr
