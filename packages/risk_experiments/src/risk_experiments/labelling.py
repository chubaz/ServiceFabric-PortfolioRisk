"""Selective, reviewable signal labelling before experimental case design.

The module deliberately stops before Gold-case construction.  It turns a large
detector output into a reproducible review sample, retains immutable annotation
revisions, requires independent review, and reports whether an item is ready
for a later Gold-preparation workflow.  It never promotes a label to Gold and
never exposes reference labels to an evaluated architecture.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
import threading
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator

from risk_analytics import AnomalySignal, DetectorRun, LabelStudyProposal, SignalDirection, SignalScope

from .models import DIGEST, IDENTIFIER, FrozenModel, canonical_digest


class LabelProductionConflict(ValueError):
    pass


class LabelProductionNotFound(KeyError):
    pass


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("labelling timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


class SignalScoreBand(str, Enum):
    BOUNDARY = "boundary"
    ELEVATED = "elevated"
    EXTREME = "extreme"


class LabelOutcome(str, Enum):
    MATERIALISED_RISK = "materialised_risk"
    NON_MATERIAL_MOVE = "non_material_move"
    AMBIGUOUS = "ambiguous"
    DATA_QUALITY_ERROR = "data_quality_error"


class RelevanceLabel(str, Enum):
    RELEVANT = "relevant"
    NOT_RELEVANT = "not_relevant"
    UNCERTAIN = "uncertain"


class LabelDirection(str, Enum):
    DOWNSIDE = "downside"
    UPSIDE = "upside"
    TWO_SIDED = "two_sided"
    UNCERTAIN = "uncertain"


class TemporalMorphology(str, Enum):
    PUNCTUAL_SHOCK = "punctual_shock"
    CLUSTERED_SHOCKS = "clustered_shocks"
    SLOW_BURN = "slow_burn"
    PERSISTENT_DETERIORATION = "persistent_deterioration"
    REGIME_TRANSITION = "regime_transition"
    DATA_ARTIFACT = "data_artifact"
    UNRESOLVED = "unresolved"


class ReviewOutcome(str, Enum):
    ACCEPT_FOR_GOLD_PREPARATION = "accept_for_gold_preparation"
    CHANGES_REQUESTED = "changes_requested"
    REJECT = "reject"


class LabelFieldRule(FrozenModel):
    """One label field and the evaluation dimensions it can support."""

    field_id: Literal[
        "manifestation_outcome",
        "relevance",
        "scope",
        "direction",
        "morphology",
        "manifestation_interval",
        "severity",
        "evidence",
        "data_quality",
        "review_confidence",
    ]
    evaluation_dimensions: tuple[
        Literal[
            "detection_quality",
            "severity_understanding",
            "timeliness",
            "evidence_quality",
            "confidence_calibration",
        ],
        ...,
    ]
    required_for_gold_preparation: bool
    guidance: str = Field(min_length=10, max_length=600)


class LabellingProtocol(FrozenModel):
    """Versioned rules for producing labels compatible with evaluation."""

    protocol_id: str = Field(pattern=IDENTIFIER)
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    purpose: str = Field(min_length=20, max_length=1200)
    unit_of_review: Literal["same_scope_date_direction_signal_group"]
    selection_method: Literal["stratified_detector_direction_score_support"]
    field_rules: tuple[LabelFieldRule, ...] = Field(min_length=10, max_length=10)
    architecture_output_mapping: tuple[str, ...] = Field(min_length=5)
    gold_creation: Literal[False] = False
    labels_reachable_by_experimental_architecture: Literal[False] = False
    protocol_digest: str | None = Field(default=None, pattern=DIGEST)

    @model_validator(mode="after")
    def complete_and_content_addressed(self) -> "LabellingProtocol":
        fields = [item.field_id for item in self.field_rules]
        if fields != sorted(set(fields)):
            raise ValueError("labelling field rules must be complete, unique, and sorted")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"protocol_digest"}))
        if self.protocol_digest is not None and self.protocol_digest != expected:
            raise ValueError("protocol_digest does not match canonical content")
        object.__setattr__(self, "protocol_digest", expected)
        return self


def default_labelling_protocol() -> LabellingProtocol:
    rules = (
        LabelFieldRule(
            field_id="data_quality",
            evaluation_dimensions=("evidence_quality",),
            required_for_gold_preparation=True,
            guidance="Record missing, stale, duplicated, mapping, or price-quality limitations before interpreting the move.",
        ),
        LabelFieldRule(
            field_id="direction",
            evaluation_dimensions=("detection_quality",),
            required_for_gold_preparation=True,
            guidance="Confirm downside, upside, two-sided instability, or uncertainty from the reviewed path.",
        ),
        LabelFieldRule(
            field_id="evidence",
            evaluation_dimensions=("evidence_quality",),
            required_for_gold_preparation=True,
            guidance="Retain the eligible market observations and later supporting or contradicting evidence used by the reviewer.",
        ),
        LabelFieldRule(
            field_id="manifestation_interval",
            evaluation_dimensions=("detection_quality", "timeliness"),
            required_for_gold_preparation=True,
            guidance="Mark onset, peak, and resolution or censoring; do not invent a universal warning date.",
        ),
        LabelFieldRule(
            field_id="manifestation_outcome",
            evaluation_dimensions=("detection_quality",),
            required_for_gold_preparation=True,
            guidance="Distinguish a materialised risk, a non-material move, an ambiguous observation, and a data-quality error.",
        ),
        LabelFieldRule(
            field_id="morphology",
            evaluation_dimensions=("detection_quality", "timeliness"),
            required_for_gold_preparation=True,
            guidance="Describe the observed path shape without asserting a unique economic cause.",
        ),
        LabelFieldRule(
            field_id="relevance",
            evaluation_dimensions=("detection_quality",),
            required_for_gold_preparation=True,
            guidance="Judge instrument relevance here; portfolio relevance is projected separately for each experimental portfolio.",
        ),
        LabelFieldRule(
            field_id="review_confidence",
            evaluation_dimensions=("confidence_calibration",),
            required_for_gold_preparation=True,
            guidance="Express confidence in the retrospective label, not the confidence that an experimental architecture should produce.",
        ),
        LabelFieldRule(
            field_id="scope",
            evaluation_dimensions=("detection_quality",),
            required_for_gold_preparation=True,
            guidance="Identify the smallest defensible instrument, issuer, group, or market scope supported by evidence.",
        ),
        LabelFieldRule(
            field_id="severity",
            evaluation_dimensions=("severity_understanding", "confidence_calibration"),
            required_for_gold_preparation=True,
            guidance="Use a reviewed ordinal level and, when available, a separately calculated forward adverse-impact measure.",
        ),
    )
    return LabellingProtocol(
        protocol_id="risk-episode-signal-labelling",
        version="1.0.0",
        purpose=(
            "Select and annotate an informative subset of detector signals before experimental case design, "
            "so later reference labels are reproducible and aligned with the fields produced by evaluated architectures."
        ),
        unit_of_review="same_scope_date_direction_signal_group",
        selection_method="stratified_detector_direction_score_support",
        field_rules=rules,
        architecture_output_mapping=(
            "assessment_state<-manifestation_outcome",
            "severity<-severity_level",
            "confidence<-review_confidence_for_reference_only",
            "findings.scope<-scope_type+scope_id",
            "findings.direction<-direction",
            "findings.evidence_ids<-supporting_evidence_ids",
            "trigger_available_at<-review_unit.available_at",
            "case_id<-assigned_only_after_gold_preparation",
        ),
    )


class SignalReference(FrozenModel):
    signal_id: str = Field(pattern=IDENTIFIER)
    detector_run_id: str = Field(pattern=IDENTIFIER)
    detector_output_digest: str = Field(pattern=DIGEST)
    detector_id: str = Field(pattern=IDENTIFIER)
    detector_version: str = Field(min_length=1, max_length=64)
    series_id: str = Field(min_length=1, max_length=200)
    scope_type: SignalScope
    scope_id: str = Field(min_length=1, max_length=200)
    observation_time: datetime
    available_at: datetime
    direction: SignalDirection
    standardised_score: Decimal
    threshold: Decimal = Field(gt=0)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    quality_flags: tuple[str, ...] = ()

    _times = field_validator("observation_time", "available_at")(_utc)

    @property
    def score_ratio(self) -> Decimal:
        return abs(self.standardised_score) / self.threshold


class SignalReviewUnit(FrozenModel):
    """Detector-agreement group reviewed once to avoid duplicate labelling work."""

    unit_id: str = Field(pattern=IDENTIFIER)
    scope_type: SignalScope
    scope_id: str = Field(min_length=1, max_length=200)
    observation_time: datetime
    available_at: datetime
    direction: SignalDirection
    score_band: SignalScoreBand
    signals: tuple[SignalReference, ...] = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    quality_flags: tuple[str, ...] = ()
    unit_digest: str | None = Field(default=None, pattern=DIGEST)

    _times = field_validator("observation_time", "available_at")(_utc)

    @model_validator(mode="after")
    def group_is_consistent(self) -> "SignalReviewUnit":
        signal_ids = [item.signal_id for item in self.signals]
        if signal_ids != sorted(set(signal_ids)):
            raise ValueError("review-unit signals must be unique and sorted")
        for item in self.signals:
            if (
                item.scope_type != self.scope_type
                or item.scope_id != self.scope_id
                or item.observation_time != self.observation_time
                or item.direction != self.direction
            ):
                raise ValueError("review-unit signals must share scope, date, and direction")
        expected_evidence = tuple(sorted({value for item in self.signals for value in item.evidence_ids}))
        expected_quality = tuple(sorted({value for item in self.signals for value in item.quality_flags}))
        if self.evidence_ids != expected_evidence or self.quality_flags != expected_quality:
            raise ValueError("review-unit evidence and quality flags must reconcile to its signals")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"unit_digest"}))
        if self.unit_digest is not None and self.unit_digest != expected:
            raise ValueError("unit_digest does not match canonical content")
        object.__setattr__(self, "unit_digest", expected)
        return self


class SignalSelectionPlan(FrozenModel):
    plan_id: str = Field(pattern=IDENTIFIER)
    protocol_digest: str = Field(pattern=DIGEST)
    source_run_ids: tuple[str, ...] = Field(min_length=1)
    source_output_digests: tuple[str, ...] = Field(min_length=1)
    portfolio_id: str = Field(pattern=IDENTIFIER)
    dataset_snapshot_id: str = Field(pattern=IDENTIFIER)
    seed: str = Field(min_length=1, max_length=200)
    selection_start: datetime
    selection_end: datetime
    target_count: int = Field(ge=1, le=500)
    observed_signal_count: int = Field(ge=0)
    review_unit_count: int = Field(ge=0)
    selected_unit_ids: tuple[str, ...]
    excluded_unit_ids: tuple[str, ...]
    selection_note: str = Field(min_length=20, max_length=1000)
    created_at: datetime
    plan_digest: str | None = Field(default=None, pattern=DIGEST)

    _times = field_validator("selection_start", "selection_end", "created_at")(_utc)

    @model_validator(mode="after")
    def selection_reconciles(self) -> "SignalSelectionPlan":
        if self.selection_end < self.selection_start:
            raise ValueError("selection end cannot precede selection start")
        if self.source_run_ids != tuple(sorted(set(self.source_run_ids))):
            raise ValueError("source run IDs must be unique and sorted")
        if self.source_output_digests != tuple(sorted(set(self.source_output_digests))):
            raise ValueError("source output digests must be unique and sorted")
        if set(self.selected_unit_ids) & set(self.excluded_unit_ids):
            raise ValueError("selected and excluded units must be disjoint")
        if len(self.selected_unit_ids) + len(self.excluded_unit_ids) != self.review_unit_count:
            raise ValueError("selection must account for every review unit")
        if len(self.selected_unit_ids) > self.target_count:
            raise ValueError("selected units cannot exceed the target")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"plan_digest"}))
        if self.plan_digest is not None and self.plan_digest != expected:
            raise ValueError("plan_digest does not match canonical content")
        object.__setattr__(self, "plan_digest", expected)
        return self


class ManifestationInterval(FrozenModel):
    start: datetime
    peak: datetime
    end: datetime | None = None
    censored: bool = False

    _start = field_validator("start")(_utc)
    _peak = field_validator("peak")(_utc)

    @field_validator("end")
    @classmethod
    def normalize_end(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value)

    @model_validator(mode="after")
    def ordered(self) -> "ManifestationInterval":
        if self.peak < self.start:
            raise ValueError("manifestation peak cannot precede its start")
        if self.end is not None and self.end < self.peak:
            raise ValueError("manifestation end cannot precede its peak")
        if self.censored != (self.end is None):
            raise ValueError("censored intervals must have no end; resolved intervals require one")
        return self


class SignalAnnotation(FrozenModel):
    annotation_id: str = Field(pattern=IDENTIFIER)
    unit_id: str = Field(pattern=IDENTIFIER)
    revision: int = Field(ge=1)
    supersedes_annotation_id: str | None = Field(default=None, pattern=IDENTIFIER)
    outcome: LabelOutcome
    relevance: RelevanceLabel
    scope_type: Literal["instrument", "issuer", "group", "market", "uncertain"]
    scope_id: str = Field(min_length=1, max_length=200)
    direction: LabelDirection
    morphology: TemporalMorphology
    manifestation_interval: ManifestationInterval | None = None
    severity_level: int | None = Field(default=None, ge=0, le=3)
    severity_basis_points: Decimal | None = Field(default=None, ge=0)
    severity_horizon_sessions: int | None = Field(default=None, ge=1, le=252)
    supporting_evidence_ids: tuple[str, ...]
    conflicting_evidence_ids: tuple[str, ...] = ()
    data_quality_flags: tuple[str, ...] = ()
    review_confidence: Decimal = Field(ge=0, le=1)
    notes: str = Field(default="No additional note.", min_length=3, max_length=2000)
    annotated_by: str = Field(min_length=2, max_length=120)
    annotator_role: Literal["case_lab_agent", "human_researcher"]
    created_at: datetime
    annotation_digest: str | None = Field(default=None, pattern=DIGEST)

    _created_at = field_validator("created_at")(_utc)

    @field_validator("supporting_evidence_ids", "conflicting_evidence_ids", "data_quality_flags")
    @classmethod
    def unique_sorted(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if values != tuple(sorted(set(values))):
            raise ValueError("annotation references and flags must be unique and sorted")
        return values

    @model_validator(mode="after")
    def annotation_is_semantically_complete(self) -> "SignalAnnotation":
        if self.revision == 1 and self.supersedes_annotation_id is not None:
            raise ValueError("the first annotation revision cannot supersede another annotation")
        if self.revision > 1 and self.supersedes_annotation_id is None:
            raise ValueError("later annotation revisions must name the annotation they supersede")
        if set(self.supporting_evidence_ids) & set(self.conflicting_evidence_ids):
            raise ValueError("supporting and conflicting evidence must be disjoint")
        if self.outcome is LabelOutcome.MATERIALISED_RISK:
            if self.relevance is RelevanceLabel.NOT_RELEVANT:
                raise ValueError("a materialised instrument label cannot be marked not relevant")
            if self.manifestation_interval is None or self.severity_level not in {1, 2, 3}:
                raise ValueError("materialised risk requires an interval and severity from 1 to 3")
            if not self.supporting_evidence_ids:
                raise ValueError("materialised risk requires supporting evidence")
            if self.morphology in {TemporalMorphology.DATA_ARTIFACT, TemporalMorphology.UNRESOLVED}:
                raise ValueError("materialised risk requires a resolved morphology")
        elif self.outcome is LabelOutcome.NON_MATERIAL_MOVE:
            if self.severity_level != 0 or self.manifestation_interval is not None:
                raise ValueError("a non-material move requires severity 0 and no manifestation interval")
        elif self.outcome is LabelOutcome.DATA_QUALITY_ERROR:
            if not self.data_quality_flags or self.morphology is not TemporalMorphology.DATA_ARTIFACT:
                raise ValueError("a data-quality error requires flags and data-artifact morphology")
            if self.severity_level not in {None, 0}:
                raise ValueError("a data-quality error cannot carry positive severity")
        if (self.severity_basis_points is None) != (self.severity_horizon_sessions is None):
            raise ValueError("severity basis points and horizon must be supplied together")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"annotation_digest"}))
        if self.annotation_digest is not None and self.annotation_digest != expected:
            raise ValueError("annotation_digest does not match canonical content")
        object.__setattr__(self, "annotation_digest", expected)
        return self


class LabelAnnotationReview(FrozenModel):
    review_id: str = Field(pattern=IDENTIFIER)
    annotation_id: str = Field(pattern=IDENTIFIER)
    annotation_digest: str = Field(pattern=DIGEST)
    outcome: ReviewOutcome
    detection_fields_verified: bool
    severity_fields_verified: bool
    evidence_fields_verified: bool
    temporal_fields_verified: bool
    reviewer_confidence: Decimal = Field(ge=0, le=1)
    rationale: str = Field(min_length=10, max_length=2000)
    reviewed_by: str = Field(min_length=2, max_length=120)
    reviewed_at: datetime
    review_digest: str | None = Field(default=None, pattern=DIGEST)

    _reviewed_at = field_validator("reviewed_at")(_utc)

    @model_validator(mode="after")
    def accepted_review_is_complete(self) -> "LabelAnnotationReview":
        checks = (
            self.detection_fields_verified,
            self.severity_fields_verified,
            self.evidence_fields_verified,
            self.temporal_fields_verified,
        )
        if self.outcome is ReviewOutcome.ACCEPT_FOR_GOLD_PREPARATION:
            if not all(checks) or self.reviewer_confidence < Decimal("0.5"):
                raise ValueError("acceptance requires every field family and reviewer confidence of at least 0.5")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"review_digest"}))
        if self.review_digest is not None and self.review_digest != expected:
            raise ValueError("review_digest does not match canonical content")
        object.__setattr__(self, "review_digest", expected)
        return self


class GoldPreparationReadiness(FrozenModel):
    unit_id: str = Field(pattern=IDENTIFIER)
    state: Literal["unlabelled", "awaiting_independent_review", "changes_requested", "excluded", "ready"]
    annotation_id: str | None = Field(default=None, pattern=IDENTIFIER)
    review_id: str | None = Field(default=None, pattern=IDENTIFIER)
    missing_requirements: tuple[str, ...] = ()
    gold_case_created: Literal[False] = False


class LabellingEvent(FrozenModel):
    event_id: str = Field(pattern=IDENTIFIER)
    event_type: Literal["batch_created", "study_proposal_recorded", "annotation_recorded", "review_recorded"]
    actor: str = Field(min_length=2, max_length=120)
    idempotency_key: str = Field(min_length=8, max_length=200)
    occurred_at: datetime
    record_digest: str = Field(pattern=DIGEST)

    _occurred_at = field_validator("occurred_at")(_utc)


class LabellingBatch(FrozenModel):
    batch_id: str = Field(pattern=IDENTIFIER)
    protocol: LabellingProtocol
    plan: SignalSelectionPlan
    selected_units: tuple[SignalReviewUnit, ...]
    study_proposals: tuple[LabelStudyProposal, ...] = ()
    annotations: tuple[SignalAnnotation, ...] = ()
    reviews: tuple[LabelAnnotationReview, ...] = ()
    events: tuple[LabellingEvent, ...] = ()
    revision: int = Field(default=1, ge=1)
    batch_digest: str | None = Field(default=None, pattern=DIGEST)

    @model_validator(mode="after")
    def batch_reconciles(self) -> "LabellingBatch":
        unit_ids = tuple(item.unit_id for item in self.selected_units)
        if unit_ids != self.plan.selected_unit_ids:
            raise ValueError("selected units must exactly match the selection plan")
        known_units = set(unit_ids)
        if any(item.unit_id not in known_units for item in self.study_proposals):
            raise ValueError("study proposals must belong to selected review units")
        study_ids = [item.study_id for item in self.study_proposals]
        if len(study_ids) != len(set(study_ids)):
            raise ValueError("study proposal IDs must be unique")
        if any(item.unit_id not in known_units for item in self.annotations):
            raise ValueError("annotations must belong to selected review units")
        annotations_by_id = {item.annotation_id: item for item in self.annotations}
        if len(annotations_by_id) != len(self.annotations):
            raise ValueError("annotation IDs must be unique")
        for item in self.annotations:
            if item.supersedes_annotation_id is not None:
                prior = annotations_by_id.get(item.supersedes_annotation_id)
                if prior is None or prior.unit_id != item.unit_id or prior.revision + 1 != item.revision:
                    raise ValueError("annotation revision chain is invalid")
        review_ids = [item.review_id for item in self.reviews]
        if len(review_ids) != len(set(review_ids)):
            raise ValueError("review IDs must be unique")
        for review in self.reviews:
            annotation = annotations_by_id.get(review.annotation_id)
            if annotation is None or annotation.annotation_digest != review.annotation_digest:
                raise ValueError("reviews must bind to an exact retained annotation")
            if annotation.annotated_by == review.reviewed_by:
                raise ValueError("an annotator cannot independently review their own annotation")
        event_keys = [item.idempotency_key for item in self.events]
        if len(event_keys) != len(set(event_keys)):
            raise ValueError("labelling idempotency keys must be unique")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"batch_digest"}))
        # S03 batches predate the proposal-only study field. Empty legacy
        # batches are upgraded in memory and receive the current digest on the
        # next atomic write; their annotation/review content is unchanged.
        legacy = canonical_digest(
            self.model_dump(mode="json", exclude={"batch_digest", "study_proposals"})
        )
        if self.batch_digest is not None and self.batch_digest not in {expected, legacy}:
            raise ValueError("batch_digest does not match canonical content")
        object.__setattr__(self, "batch_digest", expected)
        return self

    def latest_annotation(self, unit_id: str) -> SignalAnnotation | None:
        values = [item for item in self.annotations if item.unit_id == unit_id]
        return max(values, key=lambda item: item.revision, default=None)

    def study_proposal(self, unit_id: str) -> LabelStudyProposal | None:
        return next((item for item in reversed(self.study_proposals) if item.unit_id == unit_id), None)

    def readiness(self, unit_id: str) -> GoldPreparationReadiness:
        annotation = self.latest_annotation(unit_id)
        if annotation is None:
            return GoldPreparationReadiness(unit_id=unit_id, state="unlabelled")
        reviews = [item for item in self.reviews if item.annotation_id == annotation.annotation_id]
        review = reviews[-1] if reviews else None
        if review is None:
            return GoldPreparationReadiness(
                unit_id=unit_id,
                state="awaiting_independent_review",
                annotation_id=annotation.annotation_id,
                missing_requirements=("independent_review",),
            )
        if review.outcome is ReviewOutcome.CHANGES_REQUESTED:
            return GoldPreparationReadiness(
                unit_id=unit_id,
                state="changes_requested",
                annotation_id=annotation.annotation_id,
                review_id=review.review_id,
                missing_requirements=("revised_annotation",),
            )
        if review.outcome is ReviewOutcome.REJECT:
            return GoldPreparationReadiness(
                unit_id=unit_id,
                state="excluded",
                annotation_id=annotation.annotation_id,
                review_id=review.review_id,
            )
        return GoldPreparationReadiness(
            unit_id=unit_id,
            state="ready",
            annotation_id=annotation.annotation_id,
            review_id=review.review_id,
        )


def _score_band(signals: tuple[SignalReference, ...]) -> SignalScoreBand:
    ratio = max(item.score_ratio for item in signals)
    if ratio >= Decimal("2"):
        return SignalScoreBand.EXTREME
    if ratio >= Decimal("1.25"):
        return SignalScoreBand.ELEVATED
    return SignalScoreBand.BOUNDARY


def build_review_units(runs: tuple[DetectorRun, ...]) -> tuple[SignalReviewUnit, ...]:
    groups: dict[tuple[str, str, datetime, str], list[SignalReference]] = defaultdict(list)
    for run in sorted(runs, key=lambda item: item.run_id):
        for signal in run.signals:
            reference = SignalReference(
                signal_id=signal.signal_id,
                detector_run_id=run.run_id,
                detector_output_digest=run.output_digest,
                detector_id=signal.detector_id,
                detector_version=signal.detector_version,
                series_id=signal.series_id,
                scope_type=signal.scope_type,
                scope_id=signal.scope_id,
                observation_time=signal.observation_time,
                available_at=signal.available_at,
                direction=signal.direction,
                standardised_score=signal.standardised_score,
                threshold=signal.threshold,
                evidence_ids=signal.evidence_ids,
                quality_flags=signal.quality_flags,
            )
            key = (
                signal.scope_type.value,
                signal.scope_id,
                signal.observation_time,
                signal.direction.value,
            )
            groups[key].append(reference)
    units: list[SignalReviewUnit] = []
    for key, members in sorted(groups.items()):
        signals = tuple(sorted(members, key=lambda item: item.signal_id))
        identity = canonical_digest({"key": key, "signal_ids": [item.signal_id for item in signals]})
        units.append(
            SignalReviewUnit(
                unit_id=f"signal-review-{identity[7:31]}",
                scope_type=signals[0].scope_type,
                scope_id=signals[0].scope_id,
                observation_time=signals[0].observation_time,
                available_at=max(item.available_at for item in signals),
                direction=signals[0].direction,
                score_band=_score_band(signals),
                signals=signals,
                evidence_ids=tuple(sorted({value for item in signals for value in item.evidence_ids})),
                quality_flags=tuple(sorted({value for item in signals for value in item.quality_flags})),
            )
        )
    return tuple(units)


def compile_signal_selection(
    runs: tuple[DetectorRun, ...],
    *,
    target_count: int,
    seed: str,
    portfolio_id: str,
    dataset_snapshot_id: str,
    selection_start: datetime,
    selection_end: datetime,
    created_at: datetime,
) -> tuple[SignalSelectionPlan, tuple[SignalReviewUnit, ...]]:
    if not runs:
        raise ValueError("at least one detector run is required")
    protocol = default_labelling_protocol()
    selection_start = _utc(selection_start)
    selection_end = _utc(selection_end)
    if selection_end < selection_start:
        raise ValueError("selection end cannot precede selection start")
    units = tuple(
        item
        for item in build_review_units(runs)
        if selection_start <= item.observation_time <= selection_end
    )
    strata: dict[tuple[str, str, str], list[SignalReviewUnit]] = defaultdict(list)
    for unit in units:
        support = "multi_detector" if len({item.detector_id for item in unit.signals}) > 1 else "single_detector"
        strata[(unit.direction.value, unit.score_band.value, support)].append(unit)
    for key, values in strata.items():
        values.sort(
            key=lambda item: hashlib.sha256(f"{seed}|{key}|{item.unit_id}".encode()).hexdigest()
        )
    selected: list[SignalReviewUnit] = []
    ordered_strata = sorted(strata)
    while len(selected) < min(target_count, len(units)):
        progressed = False
        for key in ordered_strata:
            if strata[key] and len(selected) < target_count:
                selected.append(strata[key].pop(0))
                progressed = True
        if not progressed:
            break
    selected = sorted(selected, key=lambda item: item.unit_id)
    selected_ids = tuple(item.unit_id for item in selected)
    excluded_ids = tuple(sorted(set(item.unit_id for item in units) - set(selected_ids)))
    source_ids = tuple(sorted(run.run_id for run in runs))
    output_digests = tuple(sorted(run.output_digest for run in runs))
    plan_identity = canonical_digest(
        {
            "protocol": protocol.protocol_digest,
            "source_outputs": output_digests,
            "seed": seed,
            "portfolio_id": portfolio_id,
            "dataset_snapshot_id": dataset_snapshot_id,
            "target_count": target_count,
            "selection_start": selection_start,
            "selection_end": selection_end,
            "selected": selected_ids,
        }
    )
    plan = SignalSelectionPlan(
        plan_id=f"signal-selection-{plan_identity[7:31]}",
        protocol_digest=protocol.protocol_digest,
        source_run_ids=source_ids,
        source_output_digests=output_digests,
        portfolio_id=portfolio_id,
        dataset_snapshot_id=dataset_snapshot_id,
        seed=seed,
        selection_start=selection_start,
        selection_end=selection_end,
        target_count=target_count,
        observed_signal_count=sum(len(run.signals) for run in runs),
        review_unit_count=len(units),
        selected_unit_ids=selected_ids,
        excluded_unit_ids=excluded_ids,
        selection_note=(
            "Signals on the same scope, date, and direction are reviewed once. Selection rotates across "
            "direction, score band, and single- versus multi-detector support before filling remaining capacity."
        ),
        created_at=created_at,
    )
    return plan, tuple(selected)


class LocalLabellingStore:
    """Restart-safe, append-only labelling snapshots with optimistic concurrency."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().absolute()
        self.batches = self.root / "batches"
        self._thread_lock = threading.RLock()

    @staticmethod
    def _key(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def _ensure_root(self) -> None:
        current = Path(self.root.anchor)
        for part in self.root.parts[1:]:
            current /= part
            if os.path.lexists(current) and current.is_symlink():
                raise LabelProductionConflict("labelling storage path may not contain symbolic links")
        self.batches.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.batches.is_symlink() or not self.batches.resolve().is_relative_to(self.root.resolve()):
            raise LabelProductionConflict("labelling storage must remain beneath its configured root")

    @contextmanager
    def _lock(self):  # type: ignore[no-untyped-def]
        with self._thread_lock:
            self._ensure_root()
            flags = os.O_RDWR | os.O_CREAT
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(self.root / ".labelling.lock", flags, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    def _path(self, batch_id: str) -> Path:
        return self.batches / f"{self._key(batch_id)}.json"

    @staticmethod
    def _read(path: Path) -> LabellingBatch:
        if path.is_symlink():
            raise LabelProductionConflict("stored label batches may not be symbolic links")
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags)
        except FileNotFoundError as error:
            raise LabelProductionNotFound(path.stem) from error
        with os.fdopen(descriptor, "rb") as stream:
            return LabellingBatch.model_validate_json(stream.read())

    @staticmethod
    def _write(path: Path, batch: LabellingBatch, *, exclusive: bool = False) -> None:
        payload = (json.dumps(batch.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode()
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            if path.is_symlink():
                raise LabelProductionConflict("stored label batches may not be symbolic links")
            if exclusive:
                try:
                    os.link(temporary, path, follow_symlinks=False)
                except FileExistsError as error:
                    raise LabelProductionConflict("labelling batch already exists") from error
            else:
                os.replace(temporary, path)
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if os.path.exists(temporary):
                os.unlink(temporary)

    def create(
        self,
        *,
        protocol: LabellingProtocol,
        plan: SignalSelectionPlan,
        units: tuple[SignalReviewUnit, ...],
        actor: str,
        idempotency_key: str,
        occurred_at: datetime,
    ) -> LabellingBatch:
        batch_id = f"label-batch-{plan.plan_digest[7:31]}"
        event = LabellingEvent(
            event_id=f"label-event-{canonical_digest({'batch': batch_id, 'key': idempotency_key})[7:31]}",
            event_type="batch_created",
            actor=actor,
            idempotency_key=idempotency_key,
            occurred_at=occurred_at,
            record_digest=plan.plan_digest,
        )
        batch = LabellingBatch(
            batch_id=batch_id,
            protocol=protocol,
            plan=plan,
            selected_units=units,
            events=(event,),
        )
        with self._lock():
            path = self._path(batch_id)
            if path.exists():
                current = self._read(path)
                if current.plan.plan_digest == plan.plan_digest and any(
                    item.idempotency_key == idempotency_key for item in current.events
                ):
                    return current
                raise LabelProductionConflict("labelling batch identity conflicts with retained content")
            self._write(path, batch, exclusive=True)
        return batch

    def get(self, batch_id: str) -> LabellingBatch:
        return self._read(self._path(batch_id))

    def list(self) -> tuple[LabellingBatch, ...]:
        self._ensure_root()
        return tuple(
            sorted(
                (self._read(path) for path in self.batches.glob("*.json")),
                key=lambda item: item.events[0].occurred_at,
                reverse=True,
            )
        )

    def record_annotation(
        self,
        batch_id: str,
        annotation: SignalAnnotation,
        *,
        idempotency_key: str,
        expected_batch_digest: str,
    ) -> LabellingBatch:
        with self._lock():
            path = self._path(batch_id)
            current = self._read(path)
            prior_event = next(
                (item for item in current.events if item.idempotency_key == idempotency_key), None
            )
            if prior_event:
                if prior_event.record_digest == annotation.annotation_digest:
                    return current
                raise LabelProductionConflict("idempotency key was used for different annotation content")
            if current.batch_digest != expected_batch_digest:
                raise LabelProductionConflict("labelling batch changed; reload before saving")
            latest = current.latest_annotation(annotation.unit_id)
            expected_revision = 1 if latest is None else latest.revision + 1
            expected_supersedes = None if latest is None else latest.annotation_id
            if annotation.revision != expected_revision or annotation.supersedes_annotation_id != expected_supersedes:
                raise LabelProductionConflict("annotation must be the next immutable revision")
            event = LabellingEvent(
                event_id=f"label-event-{canonical_digest({'batch': batch_id, 'key': idempotency_key})[7:31]}",
                event_type="annotation_recorded",
                actor=annotation.annotated_by,
                idempotency_key=idempotency_key,
                occurred_at=annotation.created_at,
                record_digest=annotation.annotation_digest,
            )
            revised = LabellingBatch.model_validate(
                {
                    **current.model_dump(mode="python", exclude={"batch_digest"}),
                    "annotations": (*current.annotations, annotation),
                    "events": (*current.events, event),
                    "revision": current.revision + 1,
                }
            )
            self._write(path, revised)
            return revised

    def record_study_proposal(
        self,
        batch_id: str,
        proposal: LabelStudyProposal,
        *,
        idempotency_key: str,
        expected_batch_digest: str,
        actor: str,
        occurred_at: datetime,
    ) -> LabellingBatch:
        """Retain an immutable analytical proposal without touching annotations."""

        with self._lock():
            path = self._path(batch_id)
            current = self._read(path)
            prior_event = next((item for item in current.events if item.idempotency_key == idempotency_key), None)
            if prior_event:
                if prior_event.record_digest == proposal.study_digest:
                    return current
                raise LabelProductionConflict("idempotency key was used for different study content")
            if current.batch_digest != expected_batch_digest:
                raise LabelProductionConflict("labelling batch changed; reload before studying")
            if proposal.unit_id not in {item.unit_id for item in current.selected_units}:
                raise LabelProductionConflict("study proposal does not belong to this batch")
            retained = current.study_proposal(proposal.unit_id)
            if retained is not None:
                if retained.study_digest == proposal.study_digest:
                    return current
            event = LabellingEvent(
                event_id=f"label-event-{canonical_digest({'batch': batch_id, 'key': idempotency_key})[7:31]}",
                event_type="study_proposal_recorded",
                actor=actor,
                idempotency_key=idempotency_key,
                occurred_at=occurred_at,
                record_digest=proposal.study_digest,
            )
            revised = LabellingBatch.model_validate(
                {
                    **current.model_dump(mode="python", exclude={"batch_digest"}),
                    "study_proposals": (*current.study_proposals, proposal),
                    "events": (*current.events, event),
                    "revision": current.revision + 1,
                }
            )
            self._write(path, revised)
            return revised

    def record_review(
        self,
        batch_id: str,
        review: LabelAnnotationReview,
        *,
        idempotency_key: str,
        expected_batch_digest: str,
    ) -> LabellingBatch:
        with self._lock():
            path = self._path(batch_id)
            current = self._read(path)
            prior_event = next(
                (item for item in current.events if item.idempotency_key == idempotency_key), None
            )
            if prior_event:
                if prior_event.record_digest == review.review_digest:
                    return current
                raise LabelProductionConflict("idempotency key was used for different review content")
            if current.batch_digest != expected_batch_digest:
                raise LabelProductionConflict("labelling batch changed; reload before reviewing")
            annotation = next(
                (item for item in current.annotations if item.annotation_id == review.annotation_id), None
            )
            if annotation is None:
                raise LabelProductionConflict("review annotation is not retained in this batch")
            if annotation != current.latest_annotation(annotation.unit_id):
                raise LabelProductionConflict("only the latest annotation revision may be reviewed")
            if any(item.annotation_id == review.annotation_id for item in current.reviews):
                raise LabelProductionConflict("this annotation revision already has a review")
            event = LabellingEvent(
                event_id=f"label-event-{canonical_digest({'batch': batch_id, 'key': idempotency_key})[7:31]}",
                event_type="review_recorded",
                actor=review.reviewed_by,
                idempotency_key=idempotency_key,
                occurred_at=review.reviewed_at,
                record_digest=review.review_digest,
            )
            revised = LabellingBatch.model_validate(
                {
                    **current.model_dump(mode="python", exclude={"batch_digest"}),
                    "reviews": (*current.reviews, review),
                    "events": (*current.events, event),
                    "revision": current.revision + 1,
                }
            )
            self._write(path, revised)
            return revised
