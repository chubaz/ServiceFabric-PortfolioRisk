from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_phase5_is_active_on_exact_phase4_closure() -> None:
    status = json.loads(read("config/agent/platform-development/status.json"))
    assert int(status["current"].removeprefix("PLATFORM-P")) >= 5
    assert status["phase_4"] == "accepted"
    assert status["phase_5"] == "accepted"
    assert status["phase_5_baseline_commit"] == "8ec4ed5501d5a322439237be4207068c96347fca"
    assert status["development_profile_only"] is True
    assert status["external_effects"] == "disabled"


def test_decision_contract_keeps_four_stages_and_effects_empty() -> None:
    models = read("packages/risk_decisions/src/risk_decisions/models.py")
    service = read("packages/risk_decisions/src/risk_decisions/service.py")
    assert "class DecisionProposal" in models
    assert "class DecisionResolution" in models
    assert "class DecisionConsequenceReceipt" in models
    assert "finding_id" in models and "finding_digest" in models
    assert 'portfolio_effects: tuple[()] = ()' in models
    assert 'external_effects: tuple[()] = ()' in models
    assert 'effects: tuple[()] = ()' in models
    assert "decision.investigate.effect-free.v1" in service
    for outcome in ("INVESTIGATE", "ACCEPT_AND_MONITOR", "DEFER", "REJECT", "ESCALATE"):
        assert outcome in models


def test_decision_storage_is_external_atomic_and_symlink_safe() -> None:
    projection = read("apps/portfolio-risk-workbench/labs/decision_review.py")
    store = read("packages/risk_decisions/src/risk_decisions/store.py")
    assert "PORTFOLIO_RISK_DECISION_ROOT must remain outside Git" in projection
    assert "os.O_NOFOLLOW" in store
    assert "os.replace" in store
    assert "os.fsync" in store
    assert "fcntl.flock" in store


def test_decision_review_is_visible_and_phase6_is_not_implemented() -> None:
    html = read("apps/portfolio-risk-workbench/labs/index.html")
    javascript = read("apps/portfolio-risk-workbench/labs/labs.js")
    plan = read("docs/workplans/platform-development/phase-5-decision-review.md")
    assert 'data-workspace="decisions"' in html
    assert "Decision Review" in html
    assert "function renderDecisionWorkspace" in javascript
    assert "effects none" in javascript
    assert "no Phase 6 due-diligence workspace" in plan
    assert "no deciding agent, supra-agent or non-human resolver" in plan


def test_phase5_gate_includes_focused_and_cross_phase_checkpoints() -> None:
    makefile = read("Makefile")
    focused = makefile.split(".PHONY: verify-platform-phase5", 1)[1]
    assert "tests/decisions" in focused
    assert "test_decision_review_api.py" in focused
    assert "test_labs_runtime.py" in focused
    assert "update_manifest_hashes.py" in focused
    cross = makefile.split(".PHONY: verify-platform-phase5-cross-phase", 1)[1]
    assert "verify-day0" in cross
    assert "verify-platform-phase3" in cross
    assert "verify-platform-phase4" in cross
    assert "verify-platform-phase5" in cross
