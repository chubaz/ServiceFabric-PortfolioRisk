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


def test_unified_application_separates_development_application_and_research() -> None:
    server = read("apps/portfolio-risk-workbench/labs/duckdb_server.py")
    html = read("apps/portfolio-risk-workbench/labs/index.html")
    javascript = read("apps/portfolio-risk-workbench/labs/labs.js")
    architecture = read("docs/architecture/platform-operating-zones.md")
    for zone in ("system", "application", "research"):
        assert f'data-zone="{zone}"' in html
    assert 'id="lab-system"' in html
    assert 'id="lab-application"' in html
    assert 'id="lab-experiments"' in html
    assert "/api/platform/workspaces" in server
    assert "_require_experiment_registry_assets" in server
    assert "Only explicitly indexed, versioned definitions" in server
    assert "function switchZone" in javascript
    assert "function renderApplicationBoundary" in javascript
    assert "A discovered source is not a saved definition" in architecture
    assert "Artifact retention is explicit and does not promote an object" in architecture


def test_future_zone_dependencies_are_visible_and_non_executable() -> None:
    html = read("apps/portfolio-risk-workbench/labs/index.html")
    architecture = read("docs/architecture/platform-operating-zones.md")
    for phase in ("PLATFORM-P7", "PLATFORM-P8", "PLATFORM-P9", "PLATFORM-P14", "PLATFORM-P15"):
        assert phase in architecture
    assert "PLATFORM-P9 Mandate Lab" in html
    assert "Executable composition · PLATFORM-P14" in html
    assert "fractioned_human\" disabled" in html
    assert "parallel_headless\" disabled" in html


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
