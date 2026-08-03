"""Strict contracts for reviewable Markdown-first analytical reports."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,159}$"
DIGEST = r"^sha256:[a-f0-9]{64}$"


def canonical_digest(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReportSeverity(StrEnum):
    INFORMATIVE = "informative"
    NOTABLE = "notable"
    MATERIAL = "material"
    CRITICAL = "critical"


class SectionStatus(StrEnum):
    PLANNED = "planned"
    DRAFT = "draft"
    COMPLETED = "completed"
    VALIDATED = "validated"


class ReportSectionPlan(FrozenModel):
    section_id: str = Field(pattern=IDENTIFIER)
    title: str = Field(min_length=1, max_length=120)
    purpose: str = Field(min_length=3, max_length=500)
    max_words: int = Field(default=180, ge=20, le=1000)
    required: bool = True
    evidence_required: bool = False
    dependencies: tuple[str, ...] = ()


class ReportPlan(FrozenModel):
    schema_version: Literal["portfolio-risk.report-plan/v1"] = "portfolio-risk.report-plan/v1"
    plan_id: str = Field(pattern=IDENTIFIER)
    report_type: str = Field(pattern=IDENTIFIER)
    version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
    sections: tuple[ReportSectionPlan, ...] = Field(min_length=1, max_length=32)
    plan_digest: str | None = Field(default=None, pattern=DIGEST)

    @model_validator(mode="after")
    def bind_plan(self) -> "ReportPlan":
        ids = [item.section_id for item in self.sections]
        if len(ids) != len(set(ids)):
            raise ValueError("section IDs must be unique")
        seen: set[str] = set()
        for section in self.sections:
            if any(item not in seen for item in section.dependencies):
                raise ValueError("section dependencies must refer to earlier sections")
            seen.add(section.section_id)
        expected = canonical_digest(self.model_dump(mode="json", exclude={"plan_digest"}))
        if self.plan_digest is not None and self.plan_digest != expected:
            raise ValueError("plan_digest does not match canonical content")
        object.__setattr__(self, "plan_digest", expected)
        return self


class ReportSection(FrozenModel):
    section_id: str = Field(pattern=IDENTIFIER)
    title: str = Field(min_length=1, max_length=120)
    markdown: str = Field(max_length=30_000)
    evidence_ids: tuple[str, ...] = ()
    severity: ReportSeverity = ReportSeverity.INFORMATIVE
    status: SectionStatus = SectionStatus.COMPLETED
    revision: int = Field(default=1, ge=1)
    word_count: int | None = Field(default=None, ge=0)

    @field_validator("evidence_ids")
    @classmethod
    def unique_evidence(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("evidence IDs must be sorted and unique")
        return value

    @model_validator(mode="after")
    def bind_word_count(self) -> "ReportSection":
        observed = len(self.markdown.split())
        if self.word_count is not None and self.word_count != observed:
            raise ValueError("word_count does not match Markdown")
        object.__setattr__(self, "word_count", observed)
        return self


class ReportAttachment(FrozenModel):
    kind: Literal["chart", "table"]
    artifact_id: str = Field(pattern=IDENTIFIER)
    file_id: str = Field(pattern=IDENTIFIER)
    content_digest: str = Field(pattern=DIGEST)
    title: str = Field(min_length=1, max_length=160)
    caption: str = Field(default="", max_length=500)
    registry_reference: str | None = Field(default=None, max_length=500)


class MarkdownReport(FrozenModel):
    schema_version: Literal["portfolio-risk.markdown-report/v1"] = "portfolio-risk.markdown-report/v1"
    report_id: str = Field(pattern=IDENTIFIER)
    report_type: str = Field(pattern=IDENTIFIER)
    title: str = Field(min_length=1, max_length=200)
    as_of: str = Field(min_length=1, max_length=80)
    outcome_sought: str = Field(min_length=3, max_length=1200)
    plan_id: str = Field(pattern=IDENTIFIER)
    plan_digest: str = Field(pattern=DIGEST)
    sections: tuple[ReportSection, ...] = Field(min_length=1, max_length=32)
    attachments: tuple[ReportAttachment, ...] = ()
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    human_review_required: Literal[True] = True
    effects: tuple[()] = ()
    renderer_version: Literal["portfolio-risk.safe-markdown/v1"] = "portfolio-risk.safe-markdown/v1"
    rendered_html: str = ""
    report_digest: str | None = Field(default=None, pattern=DIGEST)

    @model_validator(mode="after")
    def bind_report(self) -> "MarkdownReport":
        ids = [item.section_id for item in self.sections]
        if len(ids) != len(set(ids)):
            raise ValueError("report section IDs must be unique")
        attachment_keys = [(item.artifact_id, item.file_id) for item in self.attachments]
        if attachment_keys != sorted(set(attachment_keys)):
            raise ValueError("attachments must be uniquely and deterministically ordered")
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"report_digest", "rendered_html"})
        )
        if self.report_digest is not None and self.report_digest != expected:
            raise ValueError("report_digest does not match canonical content")
        object.__setattr__(self, "report_digest", expected)
        return self


class ReportValidation(FrozenModel):
    schema_version: Literal["portfolio-risk.report-validation/v1"] = "portfolio-risk.report-validation/v1"
    report_id: str = Field(pattern=IDENTIFIER)
    report_digest: str = Field(pattern=DIGEST)
    valid: bool
    required_sections_complete: bool
    evidence_coverage: float = Field(ge=0, le=1)
    missing_required_sections: tuple[str, ...] = ()
    missing_evidence_by_section: dict[str, tuple[str, ...]] = {}
    repetition_pairs: tuple[tuple[str, str], ...] = ()
    length_violations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class SectionRevision(FrozenModel):
    schema_version: Literal["portfolio-risk.report-section-revision/v1"] = (
        "portfolio-risk.report-section-revision/v1"
    )
    report_id: str = Field(pattern=IDENTIFIER)
    section_id: str = Field(pattern=IDENTIFIER)
    expected_revision: int = Field(ge=1)
    markdown: str = Field(max_length=30_000)
    evidence_ids: tuple[str, ...] = ()
    severity: ReportSeverity
    actor: str = Field(pattern=IDENTIFIER)
    occurred_at: datetime

    _occurred = field_validator("occurred_at")(_aware)
