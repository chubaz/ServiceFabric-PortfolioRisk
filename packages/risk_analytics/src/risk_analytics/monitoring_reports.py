"""Deterministic Markdown and semantic HTML monitoring/replay reports."""

from __future__ import annotations

from html import escape
from typing import Literal

from pydantic import Field, model_validator

from risk_domain.common import ImmutableDomainModel, NonEmptyString
from risk_domain.digests import sha256_digest
from risk_domain.models import SHA256_DIGEST_PATTERN
from risk_domain.monitoring import (
    ContextualMonitoringRun,
    MonitoringEvaluation,
    MonitoringEvidence,
    MonitoringPolicyVersion,
    ReplayRun,
)


class MonitoringReportRequest(ImmutableDomainModel):
    report_id: NonEmptyString
    title: NonEmptyString
    monitoring_run: ContextualMonitoringRun
    policy_version: MonitoringPolicyVersion
    replay_run: ReplayRun | None = None
    evaluation: MonitoringEvaluation | None = None
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def policy_and_replay_are_consistent(self) -> "MonitoringReportRequest":
        if self.monitoring_run.policy_revision != self.policy_version.revision:
            raise ValueError("monitoring report policy revision does not match its run")
        if self.evaluation is not None and self.replay_run is None:
            raise ValueError("replay evaluation requires its replay run")
        if (
            self.evaluation is not None
            and self.replay_run is not None
            and self.evaluation.replay_run_digest != self.replay_run.digest
        ):
            raise ValueError("evaluation must identify the supplied replay run")
        return self


class MonitoringReport(ImmutableDomainModel):
    report_id: NonEmptyString
    report_type: Literal["monitoring", "monitoring_and_replay"]
    title: NonEmptyString
    source_digest: str = Field(pattern=rf"^{SHA256_DIGEST_PATTERN}$")
    markdown: str = Field(min_length=1)
    html: str = Field(min_length=1)
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)
    human_review_required: Literal[True] = True
    effects: tuple[()] = ()
    digest: str | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    @model_validator(mode="after")
    def deterministic_report_digest(self) -> "MonitoringReport":
        expected = sha256_digest(self)
        if self.digest is not None and self.digest != expected:
            raise ValueError("digest must equal the canonical monitoring-report digest")
        object.__setattr__(self, "digest", expected)
        return self


def _md_list(values: tuple[str, ...]) -> str:
    return "\n".join(f"- {value}" for value in values) if values else "- None recorded."


def _html_list(values: tuple[str, ...]) -> str:
    if not values:
        return "<p>None recorded.</p>"
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in values) + "</ul>"


def render_monitoring_report(request: MonitoringReportRequest) -> MonitoringReport:
    """Render stable local review material without PDF, notebooks, or publication."""

    run = request.monitoring_run
    context_lines = (
        f"Context digest: {run.context_digest}",
        f"As of: {run.as_of.isoformat()}",
        *tuple(f"Dataset revision: {item}" for item in run.dataset_revisions),
    )
    policy = request.policy_version
    policy_lines = (
        f"Policy revision: {policy.revision}",
        f"Daily percentage-move threshold: {policy.daily_percentage_move_threshold}",
        f"Concentration threshold: {policy.concentration_threshold}",
        f"Event relevance minimum: {policy.event_relevance_minimum}",
        f"Negative-sentiment threshold: {policy.negative_sentiment_threshold}",
        f"Stale-data maximum age (seconds): {policy.stale_data_maximum_age_seconds}",
        f"Historical VaR limit: {policy.historical_var_limit if policy.historical_var_limit is not None else 'Not configured'}",
        f"Scenario-loss limit: {policy.scenario_loss_limit if policy.scenario_loss_limit is not None else 'Not configured'}",
        f"Cadence metadata: {policy.cadence} — {policy.cadence_metadata}",
    )
    finding_lines = tuple(
        f"{item.severity}: {item.finding_type}: {item.summary}"
        for item in run.findings.findings
    )
    alert_lines = (
        f"State: {run.alert_draft.state}",
        f"Summary: {run.alert_draft.summary}",
        "Suggested analytical next steps: "
        + ", ".join(run.alert_draft.suggested_next_steps),
        "Investment advice: false",
    )
    if request.evaluation is None:
        replay_lines = ("Replay metrics: Not included in this monitoring-only report.",)
        methodology_lines = (
            "Explicitly invoked deterministic point-in-time monitoring using available_at <= as_of.",
            "No predictive claim is made.",
        )
        sample_lines = ("Monitoring run sample: one explicit point-in-time context.",)
    else:
        evaluation = request.evaluation
        replay_lines = (
            f"Alert count: {evaluation.alert_count}",
            f"Labelled outcome count: {evaluation.labelled_outcome_count}",
            f"Evaluated alert count: {evaluation.evaluated_alert_count}",
            f"True positive: {evaluation.true_positive}",
            f"False positive: {evaluation.false_positive}",
            f"False negative: {evaluation.false_negative}",
            f"Precision: {evaluation.precision if evaluation.precision is not None else 'null'}",
            f"Recall: {evaluation.recall if evaluation.recall is not None else 'null'}",
            f"Median lead time (seconds): {evaluation.median_lead_time_seconds if evaluation.median_lead_time_seconds is not None else 'null'}",
            f"Median detection delay (seconds): {evaluation.median_detection_delay_seconds if evaluation.median_detection_delay_seconds is not None else 'null'}",
            f"Coverage: {evaluation.coverage if evaluation.coverage is not None else 'null'}",
            f"Abstention count: {evaluation.abstention_count}",
        )
        methodology_lines = (evaluation.methodology,)
        sample_lines = (
            f"Replay steps: {len(request.replay_run.steps) if request.replay_run else 0}",
            f"Labelled-outcome method: {request.replay_run.specification.labelled_outcome_method if request.replay_run else 'Not available'}",
            f"Labelled outcomes: {evaluation.labelled_outcome_count}",
        )
    assumptions = tuple(
        sorted(
            set(run.evidence_bundle.assumptions)
            | set(run.findings.findings[0].assumptions if run.findings.findings else ())
        )
    )
    warning_values = set(run.warnings)
    limitation_values = set(run.limitations)
    if request.evaluation is not None:
        warning_values.update(f"{item.code}: {item.message}" for item in request.evaluation.warnings)
        limitation_values.update(request.evaluation.limitations)
    evidence_lines = tuple(
        f"{item.evidence_id} — {item.description or 'Evidence'} ({item.reference}; {item.digest or 'digest unavailable'})"
        for item in request.evidence
    )
    sections = (
        ("Data context", context_lines),
        ("Policy", policy_lines),
        ("Findings", finding_lines),
        ("Alert state", alert_lines),
        ("Replay metrics", replay_lines),
        ("Methodology", methodology_lines),
        ("Sample", sample_lines),
        ("Assumptions", assumptions),
        ("Warnings", tuple(sorted(warning_values))),
        ("Limitations", tuple(sorted(limitation_values))),
        ("Evidence", evidence_lines),
        ("Human-review state", ("Human review required: true",)),
        ("Effects", ("Effects: empty",)),
    )
    markdown = f"# {request.title}\n\n" + "\n\n".join(
        f"## {title}\n\n{_md_list(values)}" for title, values in sections
    ) + "\n"
    html_sections = "".join(
        f'<section aria-labelledby="{title.lower().replace(" ", "-")}">'
        f'<h2 id="{title.lower().replace(" ", "-")}">{escape(title)}</h2>'
        f"{_html_list(values)}</section>"
        for title, values in sections
    )
    html = (
        f'<article class="monitoring-report" data-report-id="{escape(request.report_id)}">'
        f"<header><h1>{escape(request.title)}</h1>"
        "<p>This local analytical report is not investment advice.</p></header>"
        f"{html_sections}</article>"
    )
    source_digest = sha256_digest(
        {
            "monitoring_run": run.digest,
            "policy": policy.digest,
            "replay": request.replay_run.digest if request.replay_run else None,
            "evaluation": request.evaluation.digest if request.evaluation else None,
        }
    )
    return MonitoringReport(
        report_id=request.report_id,
        report_type="monitoring_and_replay" if request.replay_run else "monitoring",
        title=request.title,
        source_digest=source_digest,
        markdown=markdown,
        html=html,
        evidence=request.evidence,
    )
