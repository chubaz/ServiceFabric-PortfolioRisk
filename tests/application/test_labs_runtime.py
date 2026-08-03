from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
LABS_ROOT = ROOT / "apps" / "portfolio-risk-workbench" / "labs"
sys.path.insert(0, str(LABS_ROOT))

import agent_studio  # noqa: E402
from agent_studio import (  # noqa: E402
    GENERATED_ROOT,
    RunRequest,
    _persist_run,
    _scenario_context,
    synthetic_behavior_provenance,
)
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


def test_generated_agent_sample_and_saved_manifest_are_not_reviewed_fixtures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provenance = synthetic_behavior_provenance("concentration")
    context = _scenario_context("concentration")
    assert provenance == {
        "data_mode": "synthetic_behavior_sample",
        "label": "SYNTHETIC BEHAVIOR SAMPLE · concentration",
        "scenario": "concentration",
        "licensed_data_used": False,
        "point_in_time": False,
        "reviewed_fixture": False,
        "warning": (
            "Values are generated in code for behavior testing and must not be "
            "interpreted as a reviewed fixture or historical observation."
        ),
    }
    source = context["portfolio_capability_input"]
    assert source["source_type"] == "synthetic_behavior_sample"
    assert source["source_reference"].startswith("synthetic://")
    assert "not a reviewed fixture" in source["source_detail"]

    monkeypatch.setattr(agent_studio, "RUN_ROOT", tmp_path)
    result = {
        "run_id": "run-synthetic-behavior-test",
        "agent_name": "Test reviewer",
        "output_contract": "RiskReviewDraft",
        "status": "completed",
        "data_mode": provenance["data_mode"],
        "data_label": provenance["label"],
        "scenario": provenance["scenario"],
        "execution_mode": "deterministic",
        "execution_model": None,
        "input_context": context,
        "input_provenance": provenance,
        "blueprint": {},
        "activity": [],
        "final_state": {},
        "presentation": {
            "status_label": "Review ready",
            "title": "Synthetic behavior review",
            "premise": "A code-generated behavior sample was reviewed.",
            "portfolio": context["portfolio_name"],
            "as_of": "2008-09-15",
            "data_basis": "Code-generated synthetic behavior sample",
            "executive_conclusion": "No empirical conclusion is available.",
            "observations": [],
            "findings": ["Behavior path completed."],
            "limitations": ["Not a reviewed fixture or empirical observation."],
            "next_steps": ["Use a governed fixture for research evaluation."],
            "review_boundary": "No portfolio effect was created.",
        },
        "assignment_summary": "Test synthetic behavior provenance",
        "portfolio_id": None,
        "as_of": None,
        "created_at": "2026-08-03T00:00:00+00:00",
        "elapsed_ms": 1.0,
        "interrupted": False,
        "auto_approved": False,
        "checkpoint_release": {
            "released": False,
            "actor_type": None,
            "status": "not_released",
            "human_approval": False,
        },
        "operating_profile": "development",
        "authority_boundary": "findings_and_proposals_only",
        "external_effects": [],
        "persistence_class": "temporary_local_run",
    }
    manifest = _persist_run(result)
    saved_manifest = json.loads((Path(manifest["folder"]) / "manifest.json").read_text())
    saved_provenance = json.loads(
        (Path(manifest["folder"]) / "input-provenance.json").read_text()
    )
    assert saved_manifest["data_mode"] == "synthetic_behavior_sample"
    assert saved_manifest["data_label"] == provenance["label"]
    assert saved_manifest["scenario"] == "concentration"
    assert saved_provenance["reviewed_fixture"] is False


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


def test_cycle_keeps_finding_proposal_decision_and_consequence_distinct() -> None:
    session = SyntheticWorkflowSession("cycle-decision-contract", _configuration())
    session.current_nav = session.open_nav * 0.95
    session._evaluate_review_proposal()

    proposed = session.snapshot()
    assert proposed["decisions"] == []
    assert proposed["consequence_receipts"] == []
    assert len(proposed["decision_proposals"]) == 1
    proposal = proposed["decision_proposals"][0]
    frozen_proposal = deepcopy(proposal)
    assert proposal["artifact_type"] == "decision_proposal"
    assert proposal["status"] == "awaiting_human_resolution"
    assert "decision_id" not in proposal
    assert proposal["effects"] == []
    assert session.status == "paused_for_review"

    session.resolve_proposal(
        proposal["proposal_id"],
        "investigate",
        resolver_id="qa-human-reviewer",
        resolver_type="human",
    )
    resolved = session.snapshot()
    assert resolved["decision_proposals"][0] == frozen_proposal
    assert len(resolved["decisions"]) == 1
    decision = resolved["decisions"][0]
    assert decision["artifact_type"] == "decision"
    assert decision["proposal_id"] == proposal["proposal_id"]
    assert decision["resolver"] == {
        "resolver_id": "qa-human-reviewer",
        "resolver_type": "human",
    }
    assert decision["effects"] == []
    receipt = resolved["consequence_receipts"][0]
    assert receipt["artifact_type"] == "decision_consequence_receipt"
    assert receipt["decision_id"] == decision["decision_id"]
    assert receipt["workflow_effect"] == "workflow_remains_paused"
    assert receipt["portfolio_effects"] == []
    assert receipt["external_effects"] == []
    assert "no investigation workspace is opened automatically" in receipt[
        "consequence"
    ]
    with pytest.raises(ValueError, match="already been resolved"):
        session.resolve_proposal(
            proposal["proposal_id"],
            "accepted",
            resolver_id="qa-human-reviewer",
            resolver_type="human",
        )
