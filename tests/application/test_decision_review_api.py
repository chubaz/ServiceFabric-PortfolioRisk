from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
LABS_ROOT = ROOT / "apps" / "portfolio-risk-workbench" / "labs"
sys.path.insert(0, str(LABS_ROOT))

import duckdb_server  # noqa: E402
from risk_decisions import LocalDecisionStore, admit_proposal  # noqa: E402
from tests.decisions.test_lifecycle import make_proposal  # noqa: E402


def test_decision_catalogue_and_effect_free_investigation_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "decision-repository"
    monkeypatch.setenv("PORTFOLIO_RISK_DECISION_ROOT", str(root))
    created = LocalDecisionStore(root).create(admit_proposal(make_proposal("proposal-api-review")))
    catalogue = duckdb_server.decision_catalogue()
    assert catalogue["runtime"]["authority"] == "human_review_only"
    assert catalogue["runtime"]["external_effects"] == "disabled"
    assert catalogue["summary"]["awaiting_review"] == 1
    result = duckdb_server.resolve_persisted_decision(
        created.proposal.proposal_id,
        duckdb_server.DecisionResolveRequest(
            outcome="investigate", resolver_id="api.reviewer", resolver_type="human",
            rationale="Review the available evidence before choosing a final outcome.",
            idempotency_key="api-investigate-1", expected_revision=created.record_revision,
        ),
    )
    assert result["state"] == "awaiting_review"
    assert result["context_revisions"][0]["effects"] == []
    assert result["follow_up_runs"][0]["workflow_id"] == "decision.investigate.effect-free.v1"


def test_stale_decision_resolution_returns_conflict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "decision-repository"
    monkeypatch.setenv("PORTFOLIO_RISK_DECISION_ROOT", str(root))
    created = LocalDecisionStore(root).create(admit_proposal(make_proposal("proposal-api-stale")))
    with pytest.raises(duckdb_server.HTTPException) as denied:
        duckdb_server.resolve_persisted_decision(
            created.proposal.proposal_id,
            duckdb_server.DecisionResolveRequest(
                outcome="defer", resolver_id="api.reviewer", resolver_type="human",
                rationale="Wait for another released observation.",
                idempotency_key="api-defer-stale",
                expected_revision="sha256:" + "0" * 64,
            ),
        )
    assert denied.value.status_code == 409


def test_decision_workspace_exposes_five_outcomes_and_context_revision() -> None:
    html = (LABS_ROOT / "index.html").read_text(encoding="utf-8")
    javascript = (LABS_ROOT / "labs.js").read_text(encoding="utf-8")
    assert 'data-workspace="decisions"' in html
    assert 'id="decision-detail-panel"' in html
    assert "Supplemental context revision" in javascript
    assert "The immutable proposal was not rewritten." in javascript
    for outcome in ("investigate", "accept_and_monitor", "defer", "reject", "escalate"):
        assert outcome in javascript
