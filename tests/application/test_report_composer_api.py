from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LABS_ROOT = ROOT / "apps" / "portfolio-risk-workbench" / "labs"
sys.path.insert(0, str(LABS_ROOT))

import duckdb_server  # noqa: E402


def _presentation() -> dict:
    return {
        "title": "Daily review",
        "outcome_sought": "Review portfolio concentration",
        "as_of": "2026-08-03",
        "executive_conclusion": "Concentration is material.",
        "observations": [],
        "findings": ["The largest position is 31.0%."],
        "limitations": [],
        "next_steps": ["Compare with the mandate limit."],
        "review_boundary": "No effect was created.",
    }


def test_report_composer_endpoints_plan_compose_validate_and_render() -> None:
    preview = duckdb_server.AgentInputPreviewRequest(scenario="loss")
    assert preview.scenario == "loss"
    plan = duckdb_server.report_composer_plan()
    assert len(plan["sections"]) == 9
    result = duckdb_server.report_composer_compose(
        duckdb_server.ReportComposeRequest(
            report_id="report:api-test",
            presentation=_presentation(),
            evidence_ids=["evidence:exposure-1"],
        )
    )
    assert result["report"]["renderer_version"] == "portfolio-risk.safe-markdown/v1"
    assert result["markdown"].startswith("# Daily review")
    validated = duckdb_server.report_composer_validate(
        duckdb_server.ReportValidationRequest(
            report=result["report"],
            available_evidence_ids=["evidence:exposure-1"],
        )
    )
    assert validated["evidence_coverage"] == 1
    rendered = duckdb_server.report_composer_render(
        duckdb_server.ReportRenderRequest(report=result["report"])
    )
    assert rendered["safe_html"].startswith('<article class="report-document"')
