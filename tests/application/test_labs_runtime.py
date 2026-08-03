from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LABS_ROOT = ROOT / "apps" / "portfolio-risk-workbench" / "labs"
sys.path.insert(0, str(LABS_ROOT))

from agent_studio import GENERATED_ROOT, RunRequest  # noqa: E402
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


def test_agent_review_checkpoint_requires_explicit_test_harness_release() -> None:
    assert RunRequest.model_fields["auto_approve_review"].default is False
    source = (LABS_ROOT / "agent_studio.py").read_text(encoding="utf-8")
    assert '"actor_type": (' in source
    assert '"test_harness"' in source
    assert '"human_approval": False' in source
    assert "this is not human approval" in source


def test_labs_disclose_runtime_data_authority_and_persistence_boundaries() -> None:
    html = (LABS_ROOT / "index.html").read_text(encoding="utf-8")
    javascript = (LABS_ROOT / "labs.js").read_text(encoding="utf-8")
    server = (LABS_ROOT / "duckdb_server.py").read_text(encoding="utf-8")
    css = (LABS_ROOT / "styles.css").read_text(encoding="utf-8")

    for field_id in (
        "truth-profile",
        "truth-data",
        "truth-authority",
        "truth-persistence",
    ):
        assert f'id="{field_id}"' in html
    assert "function renderRuntimeTruth" in javascript
    assert '"development_controls": True' in server
    assert '"external_effects": "disabled"' in server
    assert '"runtime_boundary": LAB_RUNTIME_BOUNDARY' in server
    assert "Synthetic behavior fixture · not empirical evidence" in server
    assert "Temporary local run · deletable · not published" in server
    assert ".runtime-truth-strip" in css
    assert ".runtime-truth-strip { grid-template-columns: repeat(2" in css

    for ambiguous_label in (
        "Live cycle",
        "Live work record",
        "Live Agent Card",
        "AUTO_CLEARED",
        "Auto-approve the human interrupt",
    ):
        assert ambiguous_label not in html
    assert 'id="agent-auto-review" type="checkbox" checked' not in html


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
