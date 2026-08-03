from __future__ import annotations

from datetime import datetime, timezone

import pytest

from risk_reports import (
    ReportSeverity,
    SectionRevision,
    apply_section_revision,
    compose_daily_risk_report,
    default_daily_risk_plan,
    validate_report,
)


def presentation() -> dict:
    return {
        "title": "Concentration remains the dominant review issue",
        "outcome_sought": "Determine the material portfolio-risk effects",
        "as_of": "2026-08-03",
        "executive_conclusion": "The largest position dominates priced-sleeve risk.",
        "report_sections": [
            {"section_id": "what_changed", "title": "What changed", "items": ["Daily return fell to -1.20%."]},
            {"section_id": "risk_interpretation", "title": "Risk", "content": "Concentration amplifies issuer-specific downside."},
            {"section_id": "exposure_and_mandate", "title": "Mandate", "content": "Compare the 31.0% weight with the effective limit."},
        ],
        "observations": [
            {"label": "Largest position", "value": "31.0%", "note": "Compare with mandate"},
        ],
        "findings": ["The priced sleeve is concentrated."],
        "limitations": ["Two holdings lack eligible prices."],
        "next_steps": ["Confirm the effective mandate limit."],
        "review_boundary": "No portfolio effect was created.",
    }


def test_default_plan_and_report_are_digest_bound() -> None:
    plan = default_daily_risk_plan()
    report = compose_daily_risk_report(
        presentation(), report_id="report:test-run", evidence_ids=["evidence:exposure-1"]
    )
    assert len(plan.sections) == len(report.sections) == 9
    assert report.plan_digest == plan.plan_digest
    assert report.effects == ()
    assert report.human_review_required is True
    assert report.report_digest.startswith("sha256:")


def test_section_revision_is_optimistic_and_replaces_one_section() -> None:
    report = compose_daily_risk_report(presentation(), report_id="report:test-run")
    revision = SectionRevision(
        report_id=report.report_id,
        section_id="executive_message",
        expected_revision=1,
        markdown="**Primary conclusion:** downside is concentrated in one issuer.",
        evidence_ids=("evidence:exposure-1",),
        severity=ReportSeverity.MATERIAL,
        actor="test.reviewer",
        occurred_at=datetime.now(timezone.utc),
    )
    updated = apply_section_revision(report, revision)
    section = next(item for item in updated.sections if item.section_id == revision.section_id)
    assert section.revision == 2
    assert section.markdown == revision.markdown
    assert updated.report_digest != report.report_digest
    with pytest.raises(ValueError, match="revision conflict"):
        apply_section_revision(updated, revision)


def test_validation_discloses_missing_evidence_repetition_and_length() -> None:
    report = compose_daily_risk_report(
        presentation(), report_id="report:test-run", evidence_ids=["evidence:missing"]
    )
    result = validate_report(report, available_evidence_ids=[])
    assert not result.valid
    assert result.required_sections_complete
    assert result.evidence_coverage == 0
    assert "executive_message" in result.missing_evidence_by_section


def test_composer_does_not_repeat_finding_prose_in_evidence_section() -> None:
    report = compose_daily_risk_report(
        presentation(), report_id="report:no-repeat", evidence_ids=["evidence:exposure-1"]
    )
    evidence = next(item for item in report.sections if item.section_id == "evidence_models_scenarios")
    mandate = next(item for item in report.sections if item.section_id == "portfolio_mandate_relevance")
    assert mandate.markdown not in evidence.markdown
    assert "[evidence:evidence:exposure-1]" in evidence.markdown
