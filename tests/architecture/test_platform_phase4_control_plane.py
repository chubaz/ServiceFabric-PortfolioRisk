from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_phase4_is_active_on_exact_phase3_closure() -> None:
    status = json.loads(read("config/agent/platform-development/status.json"))
    assert status["current"] == "PLATFORM-P4"
    assert status["phase_3"] == "accepted"
    assert status["phase_4"] in {"in_progress", "accepted"}
    assert status["phase_4_baseline_commit"] == "19ccf123bd210eae1763f1fd5a332cfd3cb44d72"
    assert status["external_effects"] == "disabled"


def test_report_layer_is_separate_safe_and_attachment_bound() -> None:
    composer = read("packages/risk_reports/src/risk_reports/composer.py")
    renderer = read("packages/risk_reports/src/risk_reports/renderer.py")
    models = read("packages/risk_reports/src/risk_reports/models.py")
    assert "class MarkdownReport" in models
    assert "class ReportAttachment" in models
    assert "artifact_id" in models and "content_digest" in models
    assert "default_daily_risk_plan" in composer
    assert "evidence_coverage" in composer
    assert "html.escape" in renderer
    assert "javascript" not in renderer.lower()
    for forbidden in ("submit_order", "execute_trade", "rebalance_portfolio"):
        assert forbidden not in composer
        assert forbidden not in renderer


def test_run_review_persists_typed_markdown_and_safe_html() -> None:
    studio = read("apps/portfolio-risk-workbench/labs/agent_studio.py")
    javascript = read("apps/portfolio-risk-workbench/labs/labs.js")
    assert '"report.json"' in studio
    assert '"review-brief.md"' in studio
    assert '"review-brief.html"' in studio
    assert "Never trust persisted HTML" in studio
    assert "portfolio-risk.safe-markdown/v1" in javascript
    assert "report-section-nav" in javascript
    assert "report-validation" in javascript


def test_phase4_gate_is_focused_and_phase5_is_deferred() -> None:
    makefile = read("Makefile")
    gate = makefile.split(".PHONY: verify-platform-phase4", maxsplit=1)[1]
    assert "tests/reports" in gate
    assert "test_report_composer_api.py" in gate
    assert "test_artifact_api.py" in gate
    assert "update_manifest_hashes.py" in gate
    assert "git diff --check" in gate
    plan = read("docs/workplans/platform-development/phase-4-markdown-report-composer.md")
    assert "no Phase 5 work" in plan
    assert "next exhaustive cross-phase suite until Phase 5" in plan
