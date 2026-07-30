from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(
    0,
    str(ROOT / "examples/portfolio-risk-thesis/src"),
)
from portfolio_risk_thesis.day3.contracts import (
    ArchitectureComparison,
    ArchitectureInputBundle,
    ArchitectureReviewOutput,
)


def test_day3_lane_and_control_plane_are_frozen():
    root = Path(__file__).resolve().parents[2]
    lanes = json.loads((root / "config/agent/thesis-sprint/lanes.json").read_text())
    assert lanes["lanes"]["day3"]["branch"] == "feature/thesis-day3"
    assert "packages/risk_agents" not in lanes["lanes"]["day3"]["allowed_directories"]
    assert json.loads((root / "config/agent/thesis-sprint/status.json").read_text())["day_3"] == "complete"


def test_day3_generated_schemas_match_immutable_contracts():
    root = Path(__file__).resolve().parents[2]
    schema_root = root / "data/schemas/thesis-agent-architectures"
    expected = {
        "architecture-input-v1.schema.json": ArchitectureInputBundle,
        "architecture-review-output-v1.schema.json": ArchitectureReviewOutput,
        "architecture-comparison-v1.schema.json": ArchitectureComparison,
    }
    for name, model in expected.items():
        assert json.loads((schema_root / name).read_text()) == model.model_json_schema()


def test_real_provider_has_no_fixture_fallback_and_fixture_data_is_public_only():
    root = Path(__file__).resolve().parents[2]
    provider = (
        root
        / "examples/portfolio-risk-thesis/src/portfolio_risk_thesis/day3"
        / "providers/openai_responses.py"
    ).read_text(encoding="utf-8")
    assert "FixtureStructuredModelProvider" not in provider
    fixture = json.loads(
        (
            root
            / "data/fixtures/synthetic/thesis-day3/fixture-manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert fixture["synthetic"] is True
    assert fixture["event_count"] >= 20
