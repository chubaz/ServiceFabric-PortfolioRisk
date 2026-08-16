"""Minimal research UI projection over the selective signal-labelling system."""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from artifact_repository import artifact_root
from case_discovery_runtime import CRSP_SNAPSHOT_ID, execute_detector_scan
from historical_replay_runtime import _current_security_context, _database, _positions
from risk_analytics import PathObservation, StudyDirection, build_label_study
from risk_data import qualify_case_context_sources, query_crsp_label_study_market, query_selected_case_context
from risk_experiments import (
    AssociationMethod,
    CandidateReviewOutcome,
    ContextAssociationProposal,
    ContextCandidateReview,
    ContextChannel,
    ContextEvidenceCandidate,
    ContextExecutionReview,
    ContextPurpose,
    ContextReviewOutcome,
    ContextWindow,
    ContextWorkConflict,
    ContextWorkExecution,
    ContextWorkNotFound,
    ControlKind,
    ControlSpecification,
    LabelAnnotationReview,
    LabelDirection,
    LabelOutcome,
    LabelProductionConflict,
    LabelProductionNotFound,
    EvidencePosition,
    EvidenceRole,
    LocalContextExecutionStore,
    LocalLabellingStore,
    LocalContextWorkStore,
    ManifestationInterval,
    RelevanceLabel,
    ReviewOutcome,
    SignalAnnotation,
    TemporalMorphology,
    canonical_digest,
    compile_signal_selection,
    compile_context_work_plan,
    default_labelling_protocol,
)


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LabellingBatchRequest(RequestModel):
    portfolio_id: str = Field(min_length=2, max_length=160)
    start_date: date
    end_date: date
    target_count: int = Field(default=12, ge=4, le=40)
    actor: str = Field(default="researcher-primary", min_length=2, max_length=120)

    @model_validator(mode="after")
    def ordered(self) -> "LabellingBatchRequest":
        if self.end_date < self.start_date:
            raise ValueError("end date cannot precede start date")
        return self


class SignalAnnotationRequest(RequestModel):
    idempotency_key: str = Field(min_length=8, max_length=200)
    expected_revision: int = Field(ge=1)
    unit_id: str = Field(min_length=3, max_length=160)
    outcome: LabelOutcome
    relevance: RelevanceLabel
    scope_type: Literal["instrument", "issuer", "group", "market", "uncertain"]
    direction: LabelDirection
    morphology: TemporalMorphology
    interval_start: date | None = None
    interval_peak: date | None = None
    interval_end: date | None = None
    interval_censored: bool = False
    severity_level: int | None = Field(default=None, ge=0, le=3)
    severity_basis_points: Decimal | None = Field(default=None, ge=0)
    severity_horizon_sessions: int | None = Field(default=None, ge=1, le=252)
    data_quality_flags: tuple[str, ...] = ()
    review_confidence: Decimal = Field(default=Decimal("0.75"), ge=0, le=1)
    notes: str = Field(default="No additional note.", min_length=3, max_length=2000)
    annotated_by: str = Field(default="researcher-primary", min_length=2, max_length=120)
    annotator_role: Literal["case_lab_agent", "human_researcher"] = "human_researcher"

    @field_validator("data_quality_flags")
    @classmethod
    def flags_are_normalized(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(values)))

    @model_validator(mode="after")
    def interval_fields_are_coherent(self) -> "SignalAnnotationRequest":
        supplied = (self.interval_start, self.interval_peak)
        if any(supplied) and not all(supplied):
            raise ValueError("interval start and peak must be supplied together")
        if self.interval_censored and self.interval_end is not None:
            raise ValueError("a censored interval cannot have an end date")
        return self


class LabelReviewRequest(RequestModel):
    idempotency_key: str = Field(min_length=8, max_length=200)
    expected_revision: int = Field(ge=1)
    annotation_id: str = Field(min_length=3, max_length=160)
    outcome: ReviewOutcome
    detection_fields_verified: bool
    severity_fields_verified: bool
    evidence_fields_verified: bool
    temporal_fields_verified: bool
    reviewer_confidence: Decimal = Field(ge=0, le=1)
    rationale: str = Field(min_length=10, max_length=2000)
    reviewed_by: str = Field(default="reviewer-independent", min_length=2, max_length=120)


class LabelStudyRequest(RequestModel):
    unit_id: str = Field(min_length=3, max_length=160)
    actor: str = Field(default="researcher-primary", min_length=2, max_length=120)
    recalculate: bool = False


class ContextReadinessRequest(RequestModel):
    actor: str = Field(default="researcher-primary", min_length=2, max_length=120)


class ContextWorkPlanRequest(RequestModel):
    unit_id: str = Field(min_length=3, max_length=160)
    purpose: ContextPurpose = ContextPurpose.PREPARE_CASE_CONTEXT
    channels: tuple[ContextChannel, ...] = (ContextChannel.EVENTS, ContextChannel.FUNDAMENTALS)
    event_days_before: int = Field(default=20, ge=0, le=365)
    event_days_after: int = Field(default=20, ge=0, le=365)
    fundamental_lookback_quarters: int = Field(default=8, ge=1, le=40)
    alternatives_required: bool = True
    controls: tuple[ControlKind, ...] = ()
    expected_revision: int = Field(default=0, ge=0)
    actor: str = Field(default="researcher-primary", min_length=2, max_length=120)

    @field_validator("channels", "controls")
    @classmethod
    def unique_values(cls, values: tuple[Any, ...]) -> tuple[Any, ...]:
        if len(values) != len(set(values)):
            raise ValueError("context-work selections must be unique")
        return values


class ContextPreparationRequest(RequestModel):
    unit_id: str = Field(min_length=3, max_length=160)
    expected_plan_revision: int = Field(ge=1)
    actor: str = Field(default="context-preparation-kernel", min_length=2, max_length=120)


class ContextCandidateReviewRequest(RequestModel):
    candidate_id: str = Field(min_length=3, max_length=160)
    outcome: CandidateReviewOutcome
    evidence_role: EvidenceRole
    evidence_position: EvidencePosition
    rationale: str = Field(min_length=3, max_length=1200)


class ContextReviewRequest(RequestModel):
    unit_id: str = Field(min_length=3, max_length=160)
    expected_plan_revision: int = Field(ge=1)
    expected_review_revision: int = Field(ge=0)
    outcome: ContextReviewOutcome
    candidate_reviews: tuple[ContextCandidateReviewRequest, ...]
    limitations_acknowledged: bool
    summary: str = Field(min_length=10, max_length=1600)
    reviewed_by: str = Field(default="researcher-primary", min_length=2, max_length=120)

    @field_validator("candidate_reviews")
    @classmethod
    def candidate_reviews_are_unique(cls, values: tuple[ContextCandidateReviewRequest, ...]) -> tuple[ContextCandidateReviewRequest, ...]:
        ids = [item.candidate_id for item in values]
        if len(ids) != len(set(ids)):
            raise ValueError("each context candidate may be reviewed once")
        return values


def labelling_store() -> LocalLabellingStore:
    configured = os.environ.get("PORTFOLIO_RISK_LABEL_ROOT")
    root = Path(configured).expanduser().absolute() if configured else artifact_root().parent / "label-production-v1"
    return LocalLabellingStore(root)


def context_work_store() -> LocalContextWorkStore:
    configured = os.environ.get("PORTFOLIO_RISK_LABEL_ROOT")
    root = Path(configured).expanduser().absolute() if configured else artifact_root().parent / "label-production-v1"
    return LocalContextWorkStore(root)


def context_execution_store() -> LocalContextExecutionStore:
    configured = os.environ.get("PORTFOLIO_RISK_LABEL_ROOT")
    root = Path(configured).expanduser().absolute() if configured else artifact_root().parent / "label-production-v1"
    return LocalContextExecutionStore(root)


def _at_start(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _at_end(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=timezone.utc)


def _display_context(private_root: Path, portfolio_id: str) -> dict[str, dict[str, str]]:
    positions, _cash, _config = _positions(private_root, portfolio_id)
    database = _database(private_root)
    with duckdb.connect(str(database), read_only=True) as connection:
        by_permno = _current_security_context(
            connection, {item.alias: item.permno for item in positions}
        )
    return {item.alias: by_permno.get(item.permno, {}) for item in positions}


def _readiness_label(state: str) -> str:
    return {
        "unlabelled": "To label",
        "awaiting_independent_review": "Needs review",
        "changes_requested": "Revise",
        "excluded": "Excluded",
        "ready": "Reference-ready",
    }[state]


def _study_payload(study: Any) -> dict[str, Any]:
    """Project only reviewer-meaningful values; omit IDs, digests and receipts."""

    return {
        "path": [
            {
                "date": item.observed_at.date().isoformat(),
                "value": round(float(item.indexed_value), 3),
                "return_percent": round(float(item.total_return) * 100, 2),
                "signal": item.is_signal_date,
            }
            for item in study.path
        ],
        "change_point": None
        if study.change_point is None
        else {
            "date": study.change_point.observed_at.date().isoformat(),
            "strength": round(float(study.change_point.score), 2),
            "supported": study.change_point.supported,
        },
        "intervals": [
            {
                "kind": item.kind.value,
                "start": item.onset.date().isoformat(),
                "peak": item.peak.date().isoformat(),
                "end": None if item.resolution is None else item.resolution.date().isoformat(),
                "censored": item.censored,
                "confidence": round(float(item.confidence), 2),
            }
            for item in study.interval_proposals
        ],
        "severity": [
            {
                "horizon": item.horizon_sessions,
                "observed": item.observed_sessions,
                "impact_bps": round(float(item.directional_impact_basis_points), 1),
                "return_percent": round(float(item.signed_return) * 100, 2),
                "complete": item.complete_horizon,
            }
            for item in study.severity_observations
        ],
        "maximum_adverse_excursion_bps": round(float(study.maximum_adverse_excursion_basis_points), 1),
        "group": {
            "observed": study.group_context.observed_member_count,
            "members": study.group_context.member_count,
            "breadth_percent": None if study.group_context.adverse_breadth is None else round(float(study.group_context.adverse_breadth) * 100, 1),
            "correlation_before": None if study.group_context.pre_average_correlation is None else round(float(study.group_context.pre_average_correlation), 2),
            "correlation_after": None if study.group_context.post_average_correlation is None else round(float(study.group_context.post_average_correlation), 2),
            "correlation_change": None if study.group_context.correlation_change is None else round(float(study.group_context.correlation_change), 2),
            "limitations": [item.replace("_", " ") for item in study.group_context.quality_flags],
        },
        "limitations": [item.replace("_", " ") for item in study.quality_flags],
        "boundary": "Automated study only — choose, edit or ignore its suggestions before saving a label.",
    }


def labelling_batch_payload(private_root: Path, batch_id: str) -> dict[str, Any]:
    batch = labelling_store().get(batch_id)
    names = _display_context(private_root, batch.plan.portfolio_id)
    context_records = {item.unit_id: item for item in context_work_store().list_for_batch(batch_id)}
    units = []
    for unit in batch.selected_units:
        readiness = batch.readiness(unit.unit_id)
        annotation = batch.latest_annotation(unit.unit_id)
        context = names.get(unit.scope_id, {})
        study = batch.study_proposal(unit.unit_id)
        context_record = context_records.get(unit.unit_id)
        context_execution = None
        if context_record is not None:
            context_execution = context_execution_store().get_optional(
                batch_id, unit.unit_id, context_record.latest.plan_id
            )
        units.append(
            {
                "id": unit.unit_id,
                "company": context.get("company_name", unit.scope_id),
                "ticker": context.get("ticker", "—"),
                "date": unit.observation_time.date().isoformat(),
                "available_date": unit.available_at.date().isoformat(),
                "direction": unit.direction.value,
                "score_band": unit.score_band.value,
                "detector_support": len({item.detector_id for item in unit.signals}),
                "state": readiness.state,
                "state_label": _readiness_label(readiness.state),
                "study": None if study is None else _study_payload(study),
                "context_plan": None if context_record is None else _context_plan_payload(context_record),
                "context_work": None if context_execution is None else _context_execution_payload(context_execution),
                "annotation": None
                if annotation is None
                else {
                    "id": annotation.annotation_id,
                    "revision": annotation.revision,
                    "outcome": annotation.outcome.value,
                    "relevance": annotation.relevance.value,
                    "scope_type": annotation.scope_type,
                    "direction": annotation.direction.value,
                    "morphology": annotation.morphology.value,
                    "interval": None
                    if annotation.manifestation_interval is None
                    else {
                        "start": annotation.manifestation_interval.start.date().isoformat(),
                        "peak": annotation.manifestation_interval.peak.date().isoformat(),
                        "end": None
                        if annotation.manifestation_interval.end is None
                        else annotation.manifestation_interval.end.date().isoformat(),
                        "censored": annotation.manifestation_interval.censored,
                    },
                    "severity_level": annotation.severity_level,
                    "severity_basis_points": None
                    if annotation.severity_basis_points is None
                    else float(annotation.severity_basis_points),
                    "severity_horizon_sessions": annotation.severity_horizon_sessions,
                    "review_confidence": float(annotation.review_confidence),
                    "notes": annotation.notes,
                    "annotated_by": annotation.annotated_by,
                },
            }
        )
    states = [item["state"] for item in units]
    return {
        "batch_id": batch.batch_id,
        "revision": batch.revision,
        "portfolio_id": batch.plan.portfolio_id,
        "period": {
            "start": batch.plan.selection_start.date().isoformat(),
            "end": batch.plan.selection_end.date().isoformat(),
        },
        "summary": {
            "detected_signals": batch.plan.observed_signal_count,
            "review_units": batch.plan.review_unit_count,
            "selected": len(batch.selected_units),
            "to_label": states.count("unlabelled"),
            "needs_review": states.count("awaiting_independent_review"),
            "ready": states.count("ready"),
            "revise": states.count("changes_requested"),
            "excluded": states.count("excluded"),
        },
        "units": units,
        "method_note": (
            "Duplicate detector hits for the same security, date, and direction are reviewed once. "
            "The sample preserves different directions, score strengths, and levels of detector agreement."
        ),
        "boundary_note": (
            "Reference-ready means independently reviewed and eligible for later Gold preparation. "
            "No Gold case or experimental Case has been created."
        ),
    }


def study_review_unit(private_root: Path, batch_id: str, request: LabelStudyRequest) -> dict[str, Any]:
    store = labelling_store()
    batch = store.get(batch_id)
    unit = next((item for item in batch.selected_units if item.unit_id == request.unit_id), None)
    if unit is None:
        raise LabelProductionNotFound(request.unit_id)
    retained = batch.study_proposal(unit.unit_id)
    if retained is not None and not request.recalculate:
        return labelling_batch_payload(private_root, batch_id)

    positions, _cash, _config = _positions(private_root, batch.plan.portfolio_id)
    permno_by_alias = {item.alias: item.permno for item in positions}
    if unit.scope_id not in permno_by_alias:
        raise ValueError("the selected review item is not mapped to a portfolio security")
    # Lookback precedes the sampling period when available; the retrospective
    # cutoff remains the declared batch end and never expands silently.
    window_start = unit.observation_time.date() - timedelta(days=45)
    window_end = min(batch.plan.selection_end.date(), unit.observation_time.date() + timedelta(days=45))
    with duckdb.connect(str(_database(private_root)), read_only=True) as connection:
        market = query_crsp_label_study_market(
            connection,
            dataset_snapshot_id=batch.plan.dataset_snapshot_id,
            permnos=tuple(permno_by_alias.values()),
            start_date=window_start,
            end_date=window_end,
        )
    alias_by_permno = {value: key for key, value in permno_by_alias.items()}
    observations = tuple(
        PathObservation(
            scope_id=alias_by_permno[item.permno],
            observed_at=item.observed_at,
            available_at=item.available_at,
            total_return=item.total_return,
            valuation_price=item.valuation_price,
            evidence_id=f"crsp-market-{item.permno}-{item.observed_at.date().isoformat()}",
        )
        for item in market.rows
    )
    study = build_label_study(
        unit_id=unit.unit_id,
        scope_id=unit.scope_id,
        signal_time=unit.observation_time,
        direction=StudyDirection(unit.direction.value),
        dataset_snapshot_id=batch.plan.dataset_snapshot_id,
        retrospective_cutoff=market.retrospective_cutoff,
        observations=observations,
        peer_observations=observations,
        association_edges=(),
    )
    now = datetime.now(timezone.utc)
    revised = store.record_study_proposal(
        batch_id,
        study,
        idempotency_key=canonical_digest({"batch": batch_id, "study": study.study_digest}),
        expected_batch_digest=batch.batch_digest,
        actor=request.actor,
        occurred_at=now,
    )
    return labelling_batch_payload(private_root, revised.batch_id)


def context_source_readiness(
    private_root: Path, batch_id: str, request: ContextReadinessRequest
) -> dict[str, Any]:
    """Qualify later context work without retrieving or associating evidence."""

    result = _context_readiness_result(private_root, batch_id)
    return _context_readiness_payload(result)


def _context_readiness_result(private_root: Path, batch_id: str) -> Any:
    batch = labelling_store().get(batch_id)
    positions, _cash, _config = _positions(private_root, batch.plan.portfolio_id)
    cutoff = _at_end(batch.plan.selection_end.date())
    with duckdb.connect(str(_database(private_root)), read_only=True) as connection:
        result = qualify_case_context_sources(
            connection,
            batch_id=batch.batch_id,
            portfolio_id=batch.plan.portfolio_id,
            permnos=tuple(item.permno for item in positions),
            start_date=batch.plan.selection_start.date(),
            end_date=batch.plan.selection_end.date(),
            retrospective_cutoff=cutoff,
            checked_at=datetime.now(timezone.utc),
        )
    return result


def _context_readiness_payload(result: Any) -> dict[str, Any]:
    return {
        "state": result.readiness,
        "association_state": "Not started",
        "association_count": result.association_count,
        "sources": [
            {
                "name": "RavenPack events" if item.source == "ravenpack_events" else "Compustat fundamentals",
                "state": item.state,
                "covered": item.covered_security_count,
                "requested": item.requested_security_count,
                "rows": item.row_count,
                "eligible_rows": item.eligible_row_count,
                "limitations": list(item.limitations),
            }
            for item in result.sources
        ],
        "steps": [
            {"name": item.label, "state": item.state, "reason": item.reason}
            for item in result.preparation_steps
        ],
        "message": (
            "Source contracts are ready for a later authorised context task. No event, fundamental, or signal association was performed."
            if result.readiness == "ready_for_authorisation"
            else "Source qualification found blockers. No association was attempted."
        ),
    }


def _context_issues(
    result: Any, channels: tuple[ContextChannel, ...]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    selected = {item.value for item in channels}
    blockers: list[str] = []
    warnings: list[str] = []
    for source in result.sources:
        channel = "events" if source.source == "ravenpack_events" else "fundamentals"
        if channel not in selected:
            continue
        if source.row_count == 0 or source.covered_security_count == 0:
            blockers.append(f"{source.source} has no usable rows for the selected portfolio and period.")
        if source.missing_semantics:
            warnings.append(
                "RavenPack lifecycle fields are unavailable; retrieved candidates will be marked lifecycle-unverified and require human review."
            )
        if source.missing_available_at_count:
            message = f"{source.source} has {source.missing_available_at_count} rows without availability time; those rows will be excluded."
            (blockers if source.eligible_row_count == 0 else warnings).append(message)
        if source.temporal_order_violation_count:
            message = f"{source.source} has invalid observation/availability ordering; those rows will be excluded."
            (blockers if source.eligible_row_count == 0 else warnings).append(message)
        if source.covered_security_count < source.requested_security_count:
            warnings.append(
                f"{source.source} covers {source.covered_security_count} of {source.requested_security_count} portfolio securities."
            )
        if source.eligible_row_count < source.row_count:
            warnings.append(
                f"{source.source} has {source.row_count - source.eligible_row_count} rows that are not eligible by the retrospective cutoff."
            )
    return tuple(sorted(set(blockers))), tuple(sorted(set(warnings)))


def _context_plan_payload(record: Any) -> dict[str, Any]:
    plan = record.latest
    return {
        "revision": plan.revision,
        "purpose": plan.purpose.value,
        "channels": [item.value for item in plan.channels],
        "event_days_before": plan.window.event_days_before,
        "event_days_after": plan.window.event_days_after,
        "fundamental_lookback_quarters": plan.window.fundamental_lookback_quarters,
        "alternatives_required": plan.method.alternatives_required,
        "controls": [item.value for item in plan.controls.requested],
        "state": plan.readiness_state,
        "blockers": list(plan.blockers),
        "warnings": list(plan.warnings),
        "execution": "Not started",
        "retrieved": plan.retrieval_count,
        "associations": plan.association_count,
        "controls_generated": plan.controls_generated_count,
    }


def _context_execution_payload(record: Any) -> dict[str, Any]:
    execution = record.execution
    review = record.latest_review
    decisions = {} if review is None else {item.candidate_id: item for item in review.candidate_reviews}
    candidates = []
    for item in execution.proposal.candidates:
        decision = decisions.get(item.candidate_id)
        candidates.append({
            "key": item.candidate_id,
            "source": "Event" if item.channel == ContextChannel.EVENTS else "Fundamental",
            "title": item.display_title,
            "summary": item.display_summary,
            "observed_at": item.observed_at.isoformat(),
            "available_at": item.available_at.isoformat(),
            "available_during_replay": item.eligible_at_replay_time,
            "distance_days": item.distance_days,
            "relevance": round(float(item.relevance_score), 2),
            "association_strength": round(float(item.association_score), 2),
            "limitations": [value.replace("_", " ") for value in item.quality_flags],
            "review": None if decision is None else {
                "outcome": decision.outcome.value,
                "role": decision.evidence_role.value,
                "position": decision.evidence_position.value,
                "rationale": decision.rationale,
            },
        })
    return {
        "state": "Awaiting review" if review is None else {
            ContextReviewOutcome.ACCEPT_CONTEXT: "Context accepted",
            ContextReviewOutcome.REQUEST_CHANGES: "Changes requested",
            ContextReviewOutcome.EXCLUDE_CONTEXT: "Context excluded",
        }[review.outcome],
        "plan_revision": execution.plan_revision,
        "review_revision": 0 if review is None else review.revision,
        "candidate_count": len(candidates),
        "eligible_during_replay": sum(1 for item in execution.proposal.candidates if item.eligible_at_replay_time),
        "retrospective_only": sum(1 for item in execution.proposal.candidates if not item.eligible_at_replay_time),
        "excluded": {
            "missing_availability": execution.excluded_missing_availability,
            "invalid_time": execution.excluded_temporal_violations,
            "after_cutoff": execution.excluded_after_cutoff,
        },
        "candidates": candidates,
        "unresolved": list(execution.proposal.unresolved_questions),
        "review": None if review is None else {
            "outcome": review.outcome.value,
            "limitations_acknowledged": review.limitations_acknowledged,
            "summary": review.summary,
        },
        "boundary": "Prepared context is a human-reviewed proposal. It has not changed the label or created Gold or an experimental Case.",
    }


def _compile_context_plan(
    private_root: Path, batch_id: str, request: ContextWorkPlanRequest
) -> tuple[Any, Any | None]:
    batch = labelling_store().get(batch_id)
    if request.unit_id not in {item.unit_id for item in batch.selected_units}:
        raise LabelProductionNotFound(request.unit_id)
    if not request.channels:
        raise ValueError("select at least one context source")
    readiness = _context_readiness_result(private_root, batch_id)
    blockers, warnings = _context_issues(readiness, request.channels)
    record = context_work_store().get_optional(batch_id, request.unit_id)
    current_revision = 0 if record is None else record.latest.revision
    if request.expected_revision != current_revision:
        raise ContextWorkConflict("context-work plan changed; reload before revising")
    controls = tuple(sorted(set(request.controls), key=lambda item: item.value))
    plan = compile_context_work_plan(
        batch_id=batch_id,
        unit_id=request.unit_id,
        purpose=request.purpose,
        channels=tuple(sorted(set(request.channels), key=lambda item: item.value)),
        window=ContextWindow(
            event_days_before=request.event_days_before,
            event_days_after=request.event_days_after,
            fundamental_lookback_quarters=request.fundamental_lookback_quarters,
        ),
        method=AssociationMethod(alternatives_required=request.alternatives_required),
        controls=ControlSpecification(requested=controls),
        source_readiness_digest=readiness.digest,
        blockers=blockers,
        warnings=warnings,
        prepared_by=request.actor,
        prepared_at=datetime.now(timezone.utc),
        prior=None if record is None else record.latest,
    )
    return plan, record


def validate_context_work_plan(
    private_root: Path, batch_id: str, request: ContextWorkPlanRequest
) -> dict[str, Any]:
    plan, _record = _compile_context_plan(private_root, batch_id, request)
    return {
        "valid": True,
        "saved": False,
        "plan": {
            "revision": plan.revision,
            "state": plan.readiness_state,
            "blockers": list(plan.blockers),
            "warnings": list(plan.warnings),
            "execution": "Not started",
            "retrieved": 0,
            "associations": 0,
            "controls_generated": 0,
        },
        "summary": (
            "The plan is structurally valid but retains data-readiness blockers. It can be saved for later correction; it cannot be executed."
            if plan.blockers else
            "The plan is structurally valid and ready for a later, separately authorised execution. Nothing has run."
        ),
    }


def save_context_work_plan(
    private_root: Path, batch_id: str, request: ContextWorkPlanRequest
) -> dict[str, Any]:
    plan, record = _compile_context_plan(private_root, batch_id, request)
    saved = context_work_store().save(
        plan, expected_record_digest=None if record is None else record.record_digest
    )
    return {
        "saved": True,
        "plan": _context_plan_payload(saved),
        "summary": "Context work plan saved. No data was retrieved and no associations or controls were created.",
    }


def _bounded_score(value: Any, *, default: float = 0.0) -> float:
    if value is None:
        return default
    return max(0.0, min(1.0, float(value)))


def _context_candidate(
    *,
    plan: Any,
    unit: Any,
    channel: ContextChannel,
    source_record_id: str,
    canonical_entity_id: str,
    observed_at: datetime,
    available_at: datetime,
    title: str,
    summary: str,
    relevance: float,
    novelty: float,
    quality_flags: tuple[str, ...],
) -> ContextEvidenceCandidate:
    distance = (observed_at.date() - unit.observation_time.date()).days
    side_window = plan.window.event_days_before if distance < 0 else plan.window.event_days_after
    temporal = max(0.0, 1.0 - abs(distance) / max(side_window, 1))
    association = 0.5 * relevance + 0.2 * novelty + 0.3 * temporal
    identity = canonical_digest({
        "plan": plan.plan_digest,
        "source_record": source_record_id,
        "channel": channel.value,
        "available_at": available_at,
    })
    evidence_ref = f"context-source-{identity[7:31]}"
    return ContextEvidenceCandidate(
        candidate_id=f"context-candidate-{identity[7:31]}",
        plan_id=plan.plan_id,
        unit_id=unit.unit_id,
        channel=channel,
        canonical_entity_id=canonical_entity_id,
        source_record_id=source_record_id,
        display_title=title,
        display_summary=summary,
        observed_at=observed_at,
        available_at=available_at,
        eligible_at_replay_time=available_at <= unit.available_at,
        distance_days=distance,
        proposed_role=EvidenceRole.UNRESOLVED,
        proposed_position=EvidencePosition.UNRESOLVED,
        relevance_score=relevance,
        association_score=max(0.0, min(1.0, association)),
        evidence_ids=(evidence_ref,),
        quality_flags=tuple(sorted(set(quality_flags))),
    )


def prepare_context_work(
    private_root: Path,
    batch_id: str,
    request: ContextPreparationRequest,
) -> dict[str, Any]:
    """Prepare reviewable context for one saved plan; never change reference labels."""

    batch = labelling_store().get(batch_id)
    unit = next((item for item in batch.selected_units if item.unit_id == request.unit_id), None)
    if unit is None:
        raise LabelProductionNotFound(request.unit_id)
    record = context_work_store().get_optional(batch_id, request.unit_id)
    if record is None:
        raise ContextWorkNotFound(request.unit_id)
    plan = record.latest
    if request.expected_plan_revision != plan.revision:
        raise ContextWorkConflict("context-work plan changed; reload before preparing evidence")
    if plan.blockers:
        raise ContextWorkConflict("resolve the saved plan's data-readiness blockers before preparing evidence")

    positions, _cash, _config = _positions(private_root, batch.plan.portfolio_id)
    position = next((item for item in positions if item.alias == unit.scope_id), None)
    if position is None:
        raise ValueError("the selected review item is not mapped to an exact portfolio security")
    cutoff = _at_end(batch.plan.selection_end.date())
    with duckdb.connect(str(_database(private_root)), read_only=True) as connection:
        inputs = query_selected_case_context(
            connection,
            permno=position.permno,
            manifestation_time=unit.observation_time,
            retrospective_cutoff=cutoff,
            event_days_before=plan.window.event_days_before,
            event_days_after=plan.window.event_days_after,
            fundamental_lookback_quarters=plan.window.fundamental_lookback_quarters,
        )

    candidates: list[ContextEvidenceCandidate] = []
    if ContextChannel.EVENTS in plan.channels:
        for item in inputs.event_rows:
            relevance = _bounded_score(item.relevance)
            novelty = _bounded_score(item.novelty)
            sentiment = "not supplied" if item.sentiment is None else f"{float(item.sentiment):+.2f}"
            candidates.append(_context_candidate(
                plan=plan, unit=unit, channel=ContextChannel.EVENTS,
                source_record_id=item.source_record_id,
                canonical_entity_id=item.canonical_security_id,
                observed_at=item.observed_at, available_at=item.available_at,
                title=f"{item.event_type} · {item.topic}",
                summary=(
                    f"{item.entity_name}; category {item.category}; relevance {relevance:.2f}; "
                    f"novelty {novelty:.2f}; sentiment {sentiment}."
                ),
                relevance=relevance, novelty=novelty, quality_flags=item.quality_flags,
            ))
    if ContextChannel.FUNDAMENTALS in plan.channels:
        for item in inputs.fundamental_rows:
            leverage = None
            if item.total_assets not in (None, 0) and item.total_liabilities is not None:
                leverage = float(item.total_liabilities / item.total_assets)
            margin = None
            if item.revenue not in (None, 0) and item.net_income is not None:
                margin = float(item.net_income / item.revenue)
            facts = []
            if leverage is not None:
                facts.append(f"liabilities/assets {leverage:.1%}")
            if margin is not None:
                facts.append(f"net margin {margin:.1%}")
            if item.common_equity is not None:
                facts.append(f"reported equity {float(item.common_equity):,.0f} {item.currency}")
            candidates.append(_context_candidate(
                plan=plan, unit=unit, channel=ContextChannel.FUNDAMENTALS,
                source_record_id=item.source_record_id,
                canonical_entity_id=item.canonical_issuer_id,
                observed_at=item.observed_at, available_at=item.available_at,
                title=f"Quarterly fundamentals · {item.observed_at.date().isoformat()}",
                summary="; ".join(facts) + ("." if facts else "No comparable headline ratios were available."),
                relevance=0.5, novelty=0.0,
                quality_flags=item.quality_flags,
            ))
    candidates.sort(key=lambda item: (item.available_at, item.channel.value, item.candidate_id))

    unresolved = []
    if any("provider_lifecycle_unverified" in item.quality_flags for item in candidates):
        unresolved.append("Event amendments, retractions and supersession remain unverified; review event candidates conservatively.")
    if inputs.excluded_missing_availability:
        unresolved.append(f"{inputs.excluded_missing_availability} source rows were excluded because availability time was missing.")
    if inputs.excluded_temporal_violations:
        unresolved.append(f"{inputs.excluded_temporal_violations} source rows were excluded because their time ordering was invalid.")
    if inputs.excluded_after_cutoff:
        unresolved.append(f"{inputs.excluded_after_cutoff} source rows were excluded because they were available only after the retrospective cutoff.")
    if not candidates:
        unresolved.append("No eligible candidates were found inside the saved scope and windows.")
    proposal_identity = canonical_digest({
        "plan": plan.plan_digest,
        "inputs": inputs.batch_digest,
        "candidate_ids": [item.candidate_id for item in candidates],
    })
    proposal = ContextAssociationProposal(
        proposal_id=f"context-proposal-{proposal_identity[7:31]}",
        plan_id=plan.plan_id,
        plan_digest=plan.plan_digest,
        unit_id=unit.unit_id,
        candidates=tuple(candidates),
        unresolved_questions=tuple(unresolved),
    )
    execution = ContextWorkExecution(
        execution_id=f"context-execution-{proposal_identity[7:31]}",
        batch_id=batch_id,
        unit_id=unit.unit_id,
        plan_id=plan.plan_id,
        plan_digest=plan.plan_digest,
        plan_revision=plan.revision,
        retrospective_cutoff=cutoff,
        prepared_at=datetime.now(timezone.utc),
        prepared_by=request.actor,
        proposal=proposal,
        excluded_missing_availability=inputs.excluded_missing_availability,
        excluded_temporal_violations=inputs.excluded_temporal_violations,
        excluded_after_cutoff=inputs.excluded_after_cutoff,
        source_revisions=inputs.source_revisions,
        query_receipts=inputs.query_receipts,
    )
    saved = context_execution_store().save_execution(execution)
    return {
        "prepared": True,
        "context_work": _context_execution_payload(saved),
        "summary": f"Prepared {len(candidates)} bounded evidence candidates for human review. The label was not changed.",
    }


def review_prepared_context(
    private_root: Path,
    batch_id: str,
    request: ContextReviewRequest,
) -> dict[str, Any]:
    del private_root  # the review writes only to the local context record
    plan_record = context_work_store().get_optional(batch_id, request.unit_id)
    if plan_record is None:
        raise ContextWorkNotFound(request.unit_id)
    plan = plan_record.latest
    if request.expected_plan_revision != plan.revision:
        raise ContextWorkConflict("context-work plan changed; reload before reviewing")
    store = context_execution_store()
    record = store.get(batch_id, request.unit_id, plan.plan_id)
    if request.expected_review_revision != len(record.reviews):
        raise ContextWorkConflict("context review changed; reload before saving")
    prior = record.latest_review
    decisions = tuple(sorted(
        (
            ContextCandidateReview(
                candidate_id=item.candidate_id,
                outcome=item.outcome,
                evidence_role=item.evidence_role,
                evidence_position=item.evidence_position,
                rationale=item.rationale,
            )
            for item in request.candidate_reviews
        ),
        key=lambda item: item.candidate_id,
    ))
    identity = canonical_digest({
        "execution": record.execution.execution_digest,
        "revision": len(record.reviews) + 1,
        "decisions": decisions,
        "outcome": request.outcome.value,
        "actor": request.reviewed_by,
    })
    review = ContextExecutionReview(
        review_id=f"context-review-{identity[7:31]}",
        execution_id=record.execution.execution_id,
        execution_digest=record.execution.execution_digest,
        revision=len(record.reviews) + 1,
        supersedes_review_id=None if prior is None else prior.review_id,
        outcome=request.outcome,
        candidate_reviews=decisions,
        limitations_acknowledged=request.limitations_acknowledged,
        reviewed_by=request.reviewed_by,
        reviewed_at=datetime.now(timezone.utc),
        summary=request.summary,
    )
    saved = store.save_review(
        batch_id=batch_id,
        unit_id=request.unit_id,
        plan_id=plan.plan_id,
        review=review,
        expected_record_digest=record.record_digest,
    )
    return {
        "saved": True,
        "context_work": _context_execution_payload(saved),
        "summary": "Context review saved. It remains separate from the label and is only eligible for later Gold preparation.",
    }


def create_labelling_batch(private_root: Path, request: LabellingBatchRequest) -> dict[str, Any]:
    scan = execute_detector_scan(
        private_root,
        portfolio_id=request.portfolio_id,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    now = datetime.now(timezone.utc)
    seed = f"{request.portfolio_id}:{request.start_date}:{request.end_date}:label-sample-v1"
    plan, units = compile_signal_selection(
        scan.runs,
        target_count=request.target_count,
        seed=seed,
        portfolio_id=request.portfolio_id,
        dataset_snapshot_id=CRSP_SNAPSHOT_ID,
        selection_start=_at_start(request.start_date),
        selection_end=_at_end(request.end_date),
        created_at=scan.as_of,
    )
    if not units:
        raise ValueError("this scan produced no reviewable threshold crossings")
    idempotency_key = canonical_digest(
        {
            "plan": plan.plan_digest,
            "actor": request.actor,
            "operation": "create_labelling_batch",
        }
    )
    batch = labelling_store().create(
        protocol=default_labelling_protocol(),
        plan=plan,
        units=units,
        actor=request.actor,
        idempotency_key=idempotency_key,
        occurred_at=now,
    )
    return labelling_batch_payload(private_root, batch.batch_id)


def list_labelling_batches(private_root: Path) -> dict[str, Any]:
    values = []
    for batch in labelling_store().list():
        payload = labelling_batch_payload(private_root, batch.batch_id)
        values.append(
            {
                "batch_id": payload["batch_id"],
                "portfolio_id": payload["portfolio_id"],
                "period": payload["period"],
                "summary": payload["summary"],
            }
        )
    return {"batches": values}


def record_signal_annotation(
    private_root: Path,
    batch_id: str,
    request: SignalAnnotationRequest,
) -> dict[str, Any]:
    store = labelling_store()
    batch = store.get(batch_id)
    if any(item.idempotency_key == request.idempotency_key for item in batch.events):
        return labelling_batch_payload(private_root, batch_id)
    if request.expected_revision != batch.revision:
        raise LabelProductionConflict("labelling batch changed; reload before saving")
    unit = next((item for item in batch.selected_units if item.unit_id == request.unit_id), None)
    if unit is None:
        raise LabelProductionNotFound(request.unit_id)
    latest = batch.latest_annotation(unit.unit_id)
    revision = 1 if latest is None else latest.revision + 1
    interval = None
    if request.interval_start is not None and request.interval_peak is not None:
        interval = ManifestationInterval(
            start=_at_start(request.interval_start),
            peak=_at_start(request.interval_peak),
            end=None if request.interval_end is None else _at_end(request.interval_end),
            censored=request.interval_censored,
        )
    identity = canonical_digest(
        {
            "batch": batch_id,
            "unit": request.unit_id,
            "revision": revision,
            "request": request.model_dump(mode="json", exclude={"expected_revision", "idempotency_key"}),
        }
    )
    annotation = SignalAnnotation(
        annotation_id=f"signal-annotation-{identity[7:31]}",
        unit_id=unit.unit_id,
        revision=revision,
        supersedes_annotation_id=None if latest is None else latest.annotation_id,
        outcome=request.outcome,
        relevance=request.relevance,
        scope_type=request.scope_type,
        scope_id=unit.scope_id,
        direction=request.direction,
        morphology=request.morphology,
        manifestation_interval=interval,
        severity_level=request.severity_level,
        severity_basis_points=request.severity_basis_points,
        severity_horizon_sessions=request.severity_horizon_sessions,
        supporting_evidence_ids=unit.evidence_ids,
        data_quality_flags=request.data_quality_flags,
        review_confidence=request.review_confidence,
        notes=request.notes,
        annotated_by=request.annotated_by,
        annotator_role=request.annotator_role,
        created_at=datetime.now(timezone.utc),
    )
    revised = store.record_annotation(
        batch_id,
        annotation,
        idempotency_key=request.idempotency_key,
        expected_batch_digest=batch.batch_digest,
    )
    return labelling_batch_payload(private_root, revised.batch_id)


def review_signal_annotation(
    private_root: Path,
    batch_id: str,
    request: LabelReviewRequest,
) -> dict[str, Any]:
    store = labelling_store()
    batch = store.get(batch_id)
    if any(item.idempotency_key == request.idempotency_key for item in batch.events):
        return labelling_batch_payload(private_root, batch_id)
    if request.expected_revision != batch.revision:
        raise LabelProductionConflict("labelling batch changed; reload before reviewing")
    annotation = next((item for item in batch.annotations if item.annotation_id == request.annotation_id), None)
    if annotation is None:
        raise LabelProductionNotFound(request.annotation_id)
    identity = canonical_digest(
        {
            "batch": batch_id,
            "annotation": annotation.annotation_digest,
            "request": request.model_dump(mode="json", exclude={"expected_revision", "idempotency_key"}),
        }
    )
    review = LabelAnnotationReview(
        review_id=f"label-review-{identity[7:31]}",
        annotation_id=annotation.annotation_id,
        annotation_digest=annotation.annotation_digest,
        outcome=request.outcome,
        detection_fields_verified=request.detection_fields_verified,
        severity_fields_verified=request.severity_fields_verified,
        evidence_fields_verified=request.evidence_fields_verified,
        temporal_fields_verified=request.temporal_fields_verified,
        reviewer_confidence=request.reviewer_confidence,
        rationale=request.rationale,
        reviewed_by=request.reviewed_by,
        reviewed_at=datetime.now(timezone.utc),
    )
    revised = store.record_review(
        batch_id,
        review,
        idempotency_key=request.idempotency_key,
        expected_batch_digest=batch.batch_digest,
    )
    return labelling_batch_payload(private_root, revised.batch_id)
