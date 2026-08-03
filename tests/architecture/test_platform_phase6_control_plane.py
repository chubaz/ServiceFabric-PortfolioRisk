from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_phase6_is_active_on_exact_phase5_closure() -> None:
    status = json.loads(read("config/agent/platform-development/status.json"))
    assert status["current"] == "PLATFORM-P6"
    assert status["phase_5"] == "accepted"
    assert status["phase_5_accepted_candidate_commit"] == "57e6a397231c8a1327fba4c6856edd2373f45e80"
    assert status["phase_6_baseline_commit"] == "b07c7f8a0abac713d5d50158d6bd3ce24421eca3"
    assert status["phase_6"] in {"in_progress", "accepted"}
    assert status["development_profile_only"] is True
    assert status["external_effects"] == "disabled"


def test_due_diligence_is_additive_temporary_and_effect_free() -> None:
    models = read("packages/risk_decisions/src/risk_decisions/models.py")
    service = read("packages/risk_decisions/src/risk_decisions/due_diligence.py")
    assert "class DecisionSupplementalEvidence" in models
    assert "class DecisionInvestigationWorkflowRun" in models
    assert "class DecisionProposalRevision" in models
    assert 'temporary: Literal[True] = True' in models
    assert 'registry_publication: Literal[False] = False' in models
    assert 'effects: tuple[()] = ()' in models
    for capability in (
        "decision.evidence.coverage.inspect",
        "decision.capability.receipts.inspect",
        "decision.policy.alignment.inspect",
        "decision.alternatives.compare",
        "decision.artifacts.lineage.inspect",
    ):
        assert capability in models
    for forbidden in ("subprocess", "OPENAI_API_KEY", "execute_trade", "submit_order", "rebalance_portfolio"):
        assert forbidden not in service


def test_due_diligence_reuses_decision_repository_and_has_dedicated_workspace() -> None:
    projection = read("apps/portfolio-risk-workbench/labs/decision_review.py")
    server = read("apps/portfolio-risk-workbench/labs/duckdb_server.py")
    html = read("apps/portfolio-risk-workbench/labs/index.html")
    javascript = read("apps/portfolio-risk-workbench/labs/labs.js")
    assert "due_diligence_payload" in projection
    assert "/api/decisions/{proposal_id}/due-diligence" in server
    assert "/api/decisions/{proposal_id}/due-diligence/runs" in server
    assert 'data-workspace="decision-diligence"' in html
    assert 'id="lab-decision-diligence"' in html
    assert "function renderDueDiligenceWorkspace" in javascript
    assert "The output is a candidate proposal revision for review." in javascript


def test_phase6_gate_is_focused_and_later_phases_remain_deferred() -> None:
    makefile = read("Makefile")
    gate = makefile.split(".PHONY: verify-platform-phase6", 1)[1]
    assert "test_platform_phase6_control_plane.py" in gate
    assert "tests/decisions" in gate
    assert "test_decision_review_api.py" in gate
    assert "test_labs_runtime.py" in gate
    assert "update_manifest_hashes.py" in gate
    plan = read("docs/workplans/platform-development/phase-6-decision-due-diligence.md")
    assert "no deciding agent, supra-agent or non-human resolver" in plan
    assert "no Phase 7 context-boundary model or Phase 8 vertical-slice expansion" in plan
