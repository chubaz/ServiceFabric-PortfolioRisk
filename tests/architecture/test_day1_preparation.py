from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.day1.check_preparation import validate

ROOT = Path(__file__).resolve().parents[2]


def payload(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_preparation_checker_passes() -> None:
    assert validate() == []


def test_status_schema_and_day0_unchanged() -> None:
    assert payload("config/agent/day1/status.json") == {
        "current": "D1-WAVE-1A", "preparation": "complete", "wave_1a": "queued",
        "wave_1b": "queued", "wave_1c": "queued", "soft_qa": "queued", "base_tag": "day0-complete",
    }
    assert payload("config/agent/day0/status.json")["current"] == "D0-COMPLETE"
    assert payload("config/agent/day0/status.json")["soft_qa"] == "passed"


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
