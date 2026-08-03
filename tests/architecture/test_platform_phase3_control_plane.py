from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_phase3_is_stacked_on_recorded_phase2_closure() -> None:
    status = json.loads(read("config/agent/platform-development/status.json"))
    assert int(status["current"].removeprefix("PLATFORM-P")) >= 3
    assert status["phase_2"] == "accepted"
    assert status["phase_2_accepted_candidate_commit"] == "b8eacc67ca9344944631c425e133c639395df9cf"
    assert status["phase_2_qa_commit"] == "3d1617a033104a91d8da48e5a50664dcb9f8ba09"
    assert status["phase_3_baseline_commit"] == "5426cacee004817c17215ec8bff3747d5d00c2c2"
    assert status["phase_3"] in {"in_progress", "accepted"}
    assert status["external_effects"] == "disabled"


def test_phase3_contract_reuses_registry_identity_and_separates_state() -> None:
    models = read("packages/risk_experiments/src/risk_experiments/models.py")
    assert "from risk_registry import RegistryIdentity" in models
    assert "class ExperimentDefinition" in models
    assert "class ExperimentRecord" in models
    assert "class ExperimentSet" in models
    assert "class QueueEntry" in models
    assert 'Literal["disabled"]' in models
    assert "evaluation_only" in models
    assert "evaluate_existing_outputs" in models
    assert "submit_order" not in models
    assert "execute_trade" not in models


def test_phase3_storage_and_application_boundaries_are_explicit() -> None:
    workspace = read("apps/portfolio-risk-workbench/labs/experiment_workspace.py")
    server = read("apps/portfolio-risk-workbench/labs/duckdb_server.py")
    html = read("apps/portfolio-risk-workbench/labs/index.html")
    assert "PORTFOLIO_RISK_EXPERIMENT_ROOT" in workspace
    assert "must remain outside Git" in workspace
    assert '"automatic_scheduler": False' in workspace
    assert "/api/experiments/draft" in server
    assert "/api/experiment-queue/" in server
    assert 'data-workspace="experiments"' in html
    assert "System assets" in html
    assert "Experiment overlays" in html
    assert "Run outputs" in html
    assert "Promotion" in html
    launcher = read("apps/portfolio-risk-workbench/labs/start_live_data.sh")
    assert "packages/risk_experiments/src" in launcher
    assert 'git -C "$prototype_dir" rev-parse --show-toplevel' in launcher


def test_phase3_gate_is_focused_and_network_free() -> None:
    makefile = read("Makefile")
    gate = makefile.split(".PHONY: verify-platform-phase3", maxsplit=1)[1]
    assert "tests/experiments" in gate
    assert "test_experiment_api.py" in gate
    assert "git diff --check" in gate
    for forbidden in ("OPENAI_API_KEY", "curl ", "gh ", "submit_order", "execute_trade"):
        assert forbidden not in gate


def test_phase3_plan_defers_execution_and_phase4() -> None:
    plan = read("docs/workplans/platform-development/phase-3-experiment-workspace.md")
    assert "Queue admission is explicit" in plan
    assert "Evaluation-only mode" in plan
    assert "no actual agent, workflow, model, capability, SQL, or scheduler execution" in plan
    assert "no Phase 4 work" in plan
