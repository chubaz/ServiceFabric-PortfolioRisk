from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LABS_ROOT = ROOT / "apps" / "portfolio-risk-workbench" / "labs"
sys.path.insert(0, str(LABS_ROOT))

import agent_studio  # noqa: E402


def test_run_report_uses_only_existing_evidence_and_has_no_effects() -> None:
    result = {
        "run_id": "run-20260803T090000Z-1234abcd",
        "presentation": {
            "title": "Daily review",
            "outcome_sought": "Review portfolio risk",
            "as_of": "2026-08-03",
            "executive_conclusion": "Concentration requires review.",
            "observations": [],
            "findings": ["Concentration requires review."],
            "limitations": [],
            "next_steps": [],
            "review_boundary": "No effect was created.",
        },
        "input_context": {
            "portfolio_capability_input": {"evidence_id": "evidence:portfolio-1"},
        },
        "final_state": {
            "capability_results": [
                {"receipt": {"evidence_ids": ["evidence:capability-1"]}}
            ],
            "model_output": {
                "material_findings": [
                    {"claim": "Concentration requires review.", "evidence_ids": ["evidence:portfolio-1"]}
                ]
            },
        },
    }
    report, validation = agent_studio._compose_run_report(result)
    assert report["effects"] == []
    assert "evidence:portfolio-1" in report["sections"][1]["evidence_ids"]
    assert validation["evidence_coverage"] == 1
    assert "<script" not in report["rendered_html"]
