from pathlib import Path
import json


def test_day3_lane_and_control_plane_are_frozen():
    root = Path(__file__).resolve().parents[2]
    lanes = json.loads((root / "config/agent/thesis-sprint/lanes.json").read_text())
    assert lanes["lanes"]["day3"]["branch"] == "feature/thesis-day3"
    assert "packages/risk_agents" not in lanes["lanes"]["day3"]["allowed_directories"]
    assert json.loads((root / "config/agent/thesis-sprint/status.json").read_text())["day_3"] == "in_progress"
