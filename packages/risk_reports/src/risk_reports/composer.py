"""Deterministic report planning, composition, revision, and validation."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable

from .models import (
    MarkdownReport,
    ReportAttachment,
    ReportPlan,
    ReportSection,
    ReportSectionPlan,
    ReportSeverity,
    ReportValidation,
    SectionRevision,
    SectionStatus,
)


DAILY_REPORT_TYPE = "DailyPortfolioRiskReview"


def default_daily_risk_plan() -> ReportPlan:
    specs = (
        ("outcome_sought", "Outcome sought", "State the requested analytical outcome and scope.", 90, False),
        ("executive_message", "Executive message", "Lead with the decision-relevant portfolio conclusion.", 130, True),
        ("what_changed", "What changed", "Identify only material changes in state or evidence.", 150, True),
        ("risk_mechanisms", "Risk mechanisms and non-trivial findings", "Explain how observed conditions transmit into portfolio risk.", 240, True),
        ("portfolio_mandate_relevance", "Portfolio and mandate relevance", "Connect findings to exposures, constraints and mandate purpose.", 190, True),
        ("evidence_models_scenarios", "Evidence, models, and scenario results", "Show calculations, models, scenarios and stable evidence references.", 240, True),
        ("uncertainty_limitations", "Counter-evidence, uncertainty, and limitations", "Qualify conclusions and show what could invalidate them.", 180, False),
        ("decision_implications", "Decision implications", "Explain the human decision or review implication without creating an effect.", 150, True),
        ("recommended_monitoring", "Recommended monitoring or next work", "Give a short, prioritized follow-up list.", 140, False),
    )
    sections = []
    prior: list[str] = []
    for section_id, title, purpose, max_words, evidence_required in specs:
        sections.append(
            ReportSectionPlan(
                section_id=section_id,
                title=title,
                purpose=purpose,
                max_words=max_words,
                evidence_required=evidence_required,
                dependencies=tuple(prior[-1:]),
            )
        )
        prior.append(section_id)
    return ReportPlan(
        plan_id="portfolio-risk.daily-review.v1",
        report_type=DAILY_REPORT_TYPE,
        version="1.0.0",
        sections=tuple(sections),
    )


def _bullets(values: Iterable[Any], empty: str) -> str:
    items = [str(item).strip() for item in values if str(item).strip()]
    return "\n".join(f"- {item}" for item in items) if items else empty


def _section_lookup(presentation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("section_id")): item
        for item in presentation.get("report_sections", [])
        if isinstance(item, dict) and item.get("section_id")
    }


def _section_text(item: dict[str, Any] | None, fallback: str) -> str:
    if not item:
        return fallback
    if item.get("content"):
        return str(item["content"]).strip()
    if item.get("items"):
        return _bullets(item["items"], fallback)
    return fallback


def compose_daily_risk_report(
    presentation: dict[str, Any],
    *,
    report_id: str,
    evidence_ids: Iterable[str] = (),
    finding_evidence: dict[str, Iterable[str]] | None = None,
    attachments: Iterable[ReportAttachment] = (),
) -> MarkdownReport:
    """Compile the existing presentation into the roadmap's report structure."""

    plan = default_daily_risk_plan()
    existing = _section_lookup(presentation)
    evidence = tuple(sorted(set(str(item) for item in evidence_ids if item)))
    finding_evidence = finding_evidence or {}
    findings = presentation.get("findings", [])
    # Claims belong to the analytical sections above. The evidence section
    # records references without restating those claims and creating repetition.
    evidence_lines = [f"- [evidence:{item}]" for item in evidence]
    observations = presentation.get("observations", [])
    metric_table = ["| Measure | Result | Interpretation |", "|---|---:|---|"]
    metric_table.extend(
        f"| {item.get('label', 'Measure')} | {item.get('value', '—')} | {item.get('note', '')} |"
        for item in observations
    )
    sections_by_id = {
        "outcome_sought": f"**Requested outcome:** {presentation.get('outcome_sought', 'Review the supplied portfolio-risk context.')}",
        "executive_message": "**Primary conclusion:** " + _section_text(existing.get("executive_signal"), presentation.get("executive_conclusion", "No conclusion was produced.")),
        "what_changed": _section_text(existing.get("what_changed"), "No separately evidenced change was supplied."),
        "risk_mechanisms": _section_text(existing.get("risk_interpretation"), _bullets(findings, "No non-trivial risk mechanism was identified.")),
        "portfolio_mandate_relevance": _section_text(existing.get("exposure_and_mandate"), "Mandate relevance requires human confirmation against the effective mandate."),
        "evidence_models_scenarios": "\n".join(metric_table + ([""] + evidence_lines if evidence_lines else [])),
        "uncertainty_limitations": _section_text(existing.get("uncertainty"), _bullets(presentation.get("limitations", []), "No additional limitation was recorded.")),
        "decision_implications": "> **Human review required.** " + str(presentation.get("review_boundary", "The report has no portfolio effect.")),
        "recommended_monitoring": _section_text(existing.get("review_actions"), _bullets(presentation.get("next_steps", []), "No next work was proposed.")),
    }
    material = {"executive_message", "risk_mechanisms", "portfolio_mandate_relevance", "decision_implications"}
    sections = tuple(
        ReportSection(
            section_id=item.section_id,
            title=item.title,
            markdown=sections_by_id[item.section_id],
            evidence_ids=evidence if item.evidence_required else (),
            severity=ReportSeverity.MATERIAL if item.section_id in material else ReportSeverity.NOTABLE,
        )
        for item in plan.sections
    )
    return MarkdownReport(
        report_id=report_id,
        report_type=plan.report_type,
        title=str(presentation.get("title") or "Daily Portfolio Risk Review"),
        as_of=str(presentation.get("as_of") or "Not specified"),
        outcome_sought=str(presentation.get("outcome_sought") or "Review the supplied portfolio-risk context."),
        plan_id=plan.plan_id,
        plan_digest=str(plan.plan_digest),
        sections=sections,
        attachments=tuple(sorted(attachments, key=lambda item: (item.artifact_id, item.file_id))),
        warnings=tuple(sorted(set(presentation.get("warnings", [])))),
        limitations=tuple(sorted(set(presentation.get("limitations", [])))),
    )


def apply_section_revision(report: MarkdownReport, revision: SectionRevision) -> MarkdownReport:
    if revision.report_id != report.report_id:
        raise ValueError("revision targets another report")
    replacements = []
    matched = False
    for section in report.sections:
        if section.section_id != revision.section_id:
            replacements.append(section)
            continue
        matched = True
        if section.revision != revision.expected_revision:
            raise ValueError("section revision conflict")
        replacements.append(
            ReportSection(
                section_id=section.section_id,
                title=section.title,
                markdown=revision.markdown,
                evidence_ids=tuple(sorted(set(revision.evidence_ids))),
                severity=revision.severity,
                status=SectionStatus.COMPLETED,
                revision=section.revision + 1,
            )
        )
    if not matched:
        raise ValueError("unknown report section")
    payload = report.model_dump(mode="json", exclude={"report_digest"})
    payload.update({"sections": [item.model_dump(mode="json") for item in replacements], "rendered_html": ""})
    return MarkdownReport.model_validate(payload)


def _sentences(markdown: str) -> set[str]:
    normalized = re.sub(r"[`*_>#|\[\]():-]", " ", markdown.lower())
    return {
        " ".join(item.split())
        for item in re.split(r"[.!?]\s+|\n+", normalized)
        if len(item.split()) >= 10
    }


def validate_report(
    report: MarkdownReport,
    *,
    available_evidence_ids: Iterable[str] = (),
    plan: ReportPlan | None = None,
) -> ReportValidation:
    plan = plan or default_daily_risk_plan()
    available = set(str(item) for item in available_evidence_ids)
    by_id = {item.section_id: item for item in report.sections}
    missing_sections = tuple(
        item.section_id
        for item in plan.sections
        if item.required and (
            item.section_id not in by_id
            or by_id[item.section_id].status not in {SectionStatus.COMPLETED, SectionStatus.VALIDATED}
            or not by_id[item.section_id].markdown.strip()
        )
    )
    required_evidence = [item for item in plan.sections if item.evidence_required]
    missing_evidence: dict[str, tuple[str, ...]] = {}
    covered = 0
    for spec in required_evidence:
        section = by_id.get(spec.section_id)
        if section and section.evidence_ids and set(section.evidence_ids).issubset(available):
            covered += 1
        else:
            absent = tuple(sorted(set(section.evidence_ids if section else ()) - available))
            missing_evidence[spec.section_id] = absent or ("no_evidence_reference",)
    length_violations = tuple(
        spec.section_id
        for spec in plan.sections
        if spec.section_id in by_id and int(by_id[spec.section_id].word_count or 0) > spec.max_words
    )
    section_sentences = {item.section_id: _sentences(item.markdown) for item in report.sections}
    repeated: list[tuple[str, str]] = []
    ids = list(section_sentences)
    for index, left in enumerate(ids):
        for right in ids[index + 1 :]:
            if section_sentences[left] & section_sentences[right]:
                repeated.append((left, right))
    coverage = covered / len(required_evidence) if required_evidence else 1.0
    warnings = []
    if missing_evidence:
        warnings.append("One or more evidence-required sections lack available evidence references.")
    if repeated:
        warnings.append("Substantive wording is repeated across report sections.")
    if length_violations:
        warnings.append("One or more sections exceed the plan's word budget.")
    valid = not (missing_sections or missing_evidence or repeated or length_violations)
    return ReportValidation(
        report_id=report.report_id,
        report_digest=str(report.report_digest),
        valid=valid,
        required_sections_complete=not missing_sections,
        evidence_coverage=coverage,
        missing_required_sections=missing_sections,
        missing_evidence_by_section=missing_evidence,
        repetition_pairs=tuple(repeated),
        length_violations=length_violations,
        warnings=tuple(warnings),
    )


def repeated_term_counts(report: MarkdownReport) -> Counter[str]:
    """Small diagnostic for tests and future authoring guidance."""
    return Counter(re.findall(r"\b[a-z]{5,}\b", " ".join(s.markdown.lower() for s in report.sections)))
