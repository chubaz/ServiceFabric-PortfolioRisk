from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LABS_ROOT = ROOT / "apps" / "portfolio-risk-workbench" / "labs"
sys.path.insert(0, str(LABS_ROOT))

from agent_studio import GENERATED_ROOT  # noqa: E402
from workflow_cycle_runtime import SyntheticWorkflowSession  # noqa: E402


def _configuration() -> dict[str, object]:
    return {
        "portfolio_id": "synthetic-test",
        "portfolio_name": "Synthetic test portfolio",
        "speed": 60,
        "seed": 20260802,
        "cash": 1_000.0,
        "daily_loss_limit": 0.02,
        "quantities": {"instrument-alpha": 10.0},
        "instruments": [
            {
                "instrument_id": "instrument-alpha",
                "display_name": "Instrument Alpha",
                "ticker": "ALPHA",
                "sector": "Synthetic",
            }
        ],
        "intervals": [
            {
                "date": "2020-01-02",
                "open_prices": {"instrument-alpha": 100.0},
                "close_prices": {"instrument-alpha": 101.0},
                "daily_volatility": {"instrument-alpha": 0.02},
            },
            {
                "date": "2020-01-03",
                "open_prices": {"instrument-alpha": 101.0},
                "close_prices": {"instrument-alpha": 99.0},
                "daily_volatility": {"instrument-alpha": 0.02},
            },
        ],
    }


def test_generated_agents_default_outside_application_source() -> None:
    assert LABS_ROOT not in GENERATED_ROOT.parents
    assert GENERATED_ROOT == ROOT / ".agent-runs" / "generated-agents"


def test_synthetic_cycle_is_deterministic_and_discloses_data_truth() -> None:
    first = SyntheticWorkflowSession("cycle-first", _configuration())
    second = SyntheticWorkflowSession("cycle-second", _configuration())

    for _ in range(61):
        first._advance_second()
        second._advance_second()

    first_snapshot = first.snapshot()
    second_snapshot = second.snapshot()

    assert first_snapshot["data_truth"] == {
        "daily_anchors": "real CRSP closes",
        "intraday": "synthetic seeded Brownian bridge",
        "empirical_intraday": False,
        "look_ahead_rule": (
            "future close anchors remain sealed from agent context until released by the clock"
        ),
    }
    assert first_snapshot["market"] == second_snapshot["market"]
    candle = first_snapshot["market"]["candles"]["instrument-alpha"][0]
    assert candle["synthetic"] is True
    assert candle["updates"] == 60
