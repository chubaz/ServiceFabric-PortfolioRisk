"""Selective, governed Gold references for planned historical experiments.

Gold references are retrospective evaluation material.  They are never an
architecture input and they are prepared only after a label and its proposed
context have both received their own human reviews.  The module deliberately
compiles accepted references into the existing :class:`ExperimentalCase`
instead of introducing a second experimental case hierarchy.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .context_work import (
    CandidateReviewOutcome,
    ContextExecutionRecord,
    ContextReviewOutcome,
)
from .hierarchy import CaseEvaluationState, ExperimentalCase, ObservableCaseState
from .labelling import LabellingBatch, ReviewOutcome
from .models import DIGEST, IDENTIFIER, FrozenModel, canonical_digest


class GoldCaseConflict(ValueError):
    pass


class GoldCaseNotFound(KeyError):
    pass


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Gold-reference timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


class GoldReviewOutcome(str, Enum):
    ACCEPT = "accept"
    REQUEST_CHANGES = "request_changes"
    EXCLUDE = "exclude"


class PlannedExperimentSelection(FrozenModel):
    """Human decision to spend Gold-lab effort on one planned experiment."""

    selection_id: str = Field(pattern=IDENTIFIER)
    study_id: str = Field(pattern=IDENTIFIER)
    experiment_id: str = Field(pattern=IDENTIFIER)
    research_use: str = Field(min_length=10, max_length=1000)
    selected_by: str = Field(min_length=2, max_length=120)
    selected_at: datetime
    selection_digest: str | None = Field(default=None, pattern=DIGEST)

    _selected_at = field_validator("selected_at")(_utc)

    @model_validator(mode="after")
    def bind_digest(self) -> "PlannedExperimentSelection":
        expected = canonical_digest(self.model_dump(mode="json", exclude={"selection_digest"}))
        if self.selection_digest is not None and self.selection_digest != expected:
            raise ValueError("selection_digest does not match canonical content")
        object.__setattr__(self, "selection_digest", expected)
        return self


class GoldEvidenceItem(FrozenModel):
    """Reviewed evidence retained from the context proposal."""

    evidence_item_id: str = Field(pattern=IDENTIFIER)
    source_record_id: str = Field(min_length=1, max_length=240)
    source_kind: Literal["event", "fundamental"]
    title: str = Field(min_length=1, max_length=240)
    summary: str = Field(min_length=1, max_length=800)
    observed_at: datetime
    available_at: datetime
    replay_visibility: Literal["ex_ante_eligible", "retrospective_only"]
    role: Literal[
        "precursor", "trigger", "amplifier", "confirmation", "response",
        "mitigation", "aftermath", "unrelated", "unresolved",
    ]
    position: Literal["supporting", "contradicting", "alternative", "unresolved"]
    reviewer_rationale: str = Field(min_length=3, max_length=1200)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    quality_limits: tuple[str, ...] = ()

    _times = field_validator("observed_at", "available_at")(_utc)

    @model_validator(mode="after")
    def evidence_is_consistent(self) -> "GoldEvidenceItem":
        if self.available_at < self.observed_at:
            raise ValueError("evidence availability cannot precede observation")
        if self.evidence_ids != tuple(sorted(set(self.evidence_ids))):
            raise ValueError("Gold evidence references must be unique and sorted")
        return self


class GoldDecisionCheckpoint(FrozenModel):
    """Retrospective evaluation checkpoint; never an instruction to trade."""

    checkpoint_id: str = Field(pattern=IDENTIFIER)
    label: str = Field(min_length=3, max_length=160)
    information_cutoff: datetime
    acceptable_actions: tuple[
        Literal[
            "no_action", "monitor", "investigate", "request_data",
            "run_scenario", "escalate", "review_exposure", "abstain",
        ], ...
    ] = Field(min_length=1)
    required_evidence_ids: tuple[str, ...] = ()

    _cutoff = field_validator("information_cutoff")(_utc)

    @field_validator("acceptable_actions", "required_evidence_ids")
    @classmethod
    def unique_sorted(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if values != tuple(sorted(set(values))):
            raise ValueError("checkpoint values must be unique and sorted")
        return values


class GoldCaseBundle(FrozenModel):
    """Immutable retrospective reference proposed for independent review."""

    gold_reference_id: str = Field(pattern=IDENTIFIER)
    supersedes_gold_reference_id: str | None = Field(default=None, pattern=IDENTIFIER)
    batch_id: str = Field(pattern=IDENTIFIER)
    unit_id: str = Field(pattern=IDENTIFIER)
    selection: PlannedExperimentSelection
    annotation_id: str = Field(pattern=IDENTIFIER)
    annotation_digest: str = Field(pattern=DIGEST)
    annotation_review_id: str = Field(pattern=IDENTIFIER)
    annotation_review_digest: str = Field(pattern=DIGEST)
    context_execution_id: str = Field(pattern=IDENTIFIER)
    context_execution_digest: str = Field(pattern=DIGEST)
    context_review_id: str = Field(pattern=IDENTIFIER)
    context_review_digest: str = Field(pattern=DIGEST)
    scope_type: Literal["instrument", "issuer", "group", "market", "uncertain"]
    scope_id: str = Field(min_length=1, max_length=200)
    outcome: Literal["materialised_risk", "non_material_move", "ambiguous", "data_quality_error"]
    direction: Literal["downside", "upside", "two_sided", "uncertain"]
    morphology: Literal[
        "punctual_shock", "clustered_shocks", "slow_burn",
        "persistent_deterioration", "regime_transition", "data_artifact", "unresolved",
    ]
    manifestation_start: datetime | None = None
    manifestation_peak: datetime | None = None
    manifestation_end: datetime | None = None
    manifestation_censored: bool = False
    severity_level: int | None = Field(default=None, ge=0, le=3)
    severity_basis_points: float | None = Field(default=None, ge=0)
    severity_horizon_sessions: int | None = Field(default=None, ge=1, le=252)
    evidence: tuple[GoldEvidenceItem, ...] = Field(min_length=1)
    checkpoints: tuple[GoldDecisionCheckpoint, ...] = ()
    unresolved_limits: tuple[str, ...] = ()
    data_truth: Literal["licensed_historical", "public_historical", "reviewed_synthetic", "mixed"]
    prepared_by: str = Field(min_length=2, max_length=120)
    prepared_at: datetime
    state: Literal["awaiting_independent_review"] = "awaiting_independent_review"
    architecture_access: Literal[False] = False
    bundle_digest: str | None = Field(default=None, pattern=DIGEST)

    _prepared_at = field_validator("prepared_at")(_utc)

    @field_validator("manifestation_start", "manifestation_peak", "manifestation_end")
    @classmethod
    def normalize_optional_times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value)

    @model_validator(mode="after")
    def bundle_is_consistent(self) -> "GoldCaseBundle":
        if self.supersedes_gold_reference_id == self.gold_reference_id:
            raise ValueError("a Gold reference cannot supersede itself")
        if (self.manifestation_start is None) != (self.manifestation_peak is None):
            raise ValueError("manifestation start and peak must be supplied together")
        if self.manifestation_start and self.manifestation_peak and self.manifestation_peak < self.manifestation_start:
            raise ValueError("manifestation peak cannot precede start")
        if self.manifestation_end and self.manifestation_peak and self.manifestation_end < self.manifestation_peak:
            raise ValueError("manifestation end cannot precede peak")
        if self.manifestation_censored != (self.manifestation_start is not None and self.manifestation_end is None):
            raise ValueError("censored manifestation requires a start and no end")
        if len({item.evidence_item_id for item in self.evidence}) != len(self.evidence):
            raise ValueError("Gold evidence items must be unique")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"bundle_digest"}))
        if self.bundle_digest is not None and self.bundle_digest != expected:
            raise ValueError("bundle_digest does not match canonical content")
        object.__setattr__(self, "bundle_digest", expected)
        return self


class GoldCaseReview(FrozenModel):
    review_id: str = Field(pattern=IDENTIFIER)
    gold_reference_id: str = Field(pattern=IDENTIFIER)
    bundle_digest: str = Field(pattern=DIGEST)
    revision: int = Field(ge=1)
    supersedes_review_id: str | None = Field(default=None, pattern=IDENTIFIER)
    outcome: GoldReviewOutcome
    label_reconciled: bool
    evidence_reconciled: bool
    temporal_firewall_verified: bool
    limitations_acceptable: bool
    rationale: str = Field(min_length=10, max_length=2000)
    reviewed_by: str = Field(min_length=2, max_length=120)
    reviewed_at: datetime
    review_digest: str | None = Field(default=None, pattern=DIGEST)

    _reviewed_at = field_validator("reviewed_at")(_utc)

    @model_validator(mode="after")
    def accepted_review_is_complete(self) -> "GoldCaseReview":
        if self.revision == 1 and self.supersedes_review_id is not None:
            raise ValueError("first Gold review cannot supersede another review")
        if self.revision > 1 and self.supersedes_review_id is None:
            raise ValueError("later Gold reviews must supersede the previous review")
        if self.outcome is GoldReviewOutcome.ACCEPT and not all((
            self.label_reconciled,
            self.evidence_reconciled,
            self.temporal_firewall_verified,
            self.limitations_acceptable,
        )):
            raise ValueError("Gold acceptance requires all scientific checks")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"review_digest"}))
        if self.review_digest is not None and self.review_digest != expected:
            raise ValueError("review_digest does not match canonical content")
        object.__setattr__(self, "review_digest", expected)
        return self


class GoldCaseRecord(FrozenModel):
    record_id: str = Field(pattern=IDENTIFIER)
    bundle: GoldCaseBundle
    reviews: tuple[GoldCaseReview, ...] = ()
    compiled_case_id: str | None = Field(default=None, pattern=IDENTIFIER)
    compiled_case_digest: str | None = Field(default=None, pattern=DIGEST)
    record_digest: str | None = Field(default=None, pattern=DIGEST)

    @model_validator(mode="after")
    def record_is_consistent(self) -> "GoldCaseRecord":
        if (self.compiled_case_id is None) != (self.compiled_case_digest is None):
            raise ValueError("compiled case identity and digest must be supplied together")
        for index, review in enumerate(self.reviews, start=1):
            if review.gold_reference_id != self.bundle.gold_reference_id or review.bundle_digest != self.bundle.bundle_digest:
                raise ValueError("Gold review must bind to the exact immutable bundle")
            if review.revision != index:
                raise ValueError("Gold review revisions must be contiguous")
            if index > 1 and review.supersedes_review_id != self.reviews[index - 2].review_id:
                raise ValueError("Gold review supersession chain is invalid")
            if review.reviewed_by == self.bundle.prepared_by:
                raise ValueError("Gold preparer cannot independently approve their own bundle")
        if self.compiled_case_id is not None:
            if not self.reviews or self.reviews[-1].outcome is not GoldReviewOutcome.ACCEPT:
                raise ValueError("only an accepted Gold reference can compile an ExperimentalCase")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"record_digest"}))
        if self.record_digest is not None and self.record_digest != expected:
            raise ValueError("record_digest does not match canonical content")
        object.__setattr__(self, "record_digest", expected)
        return self

    @property
    def latest_review(self) -> GoldCaseReview | None:
        return self.reviews[-1] if self.reviews else None

    @property
    def state(self) -> str:
        if self.compiled_case_id:
            return "experimental_case_compiled"
        if not self.reviews:
            return "awaiting_independent_review"
        return {
            GoldReviewOutcome.ACCEPT: "accepted",
            GoldReviewOutcome.REQUEST_CHANGES: "changes_requested",
            GoldReviewOutcome.EXCLUDE: "excluded",
        }[self.reviews[-1].outcome]


def prepare_gold_case_bundle(
    *,
    batch: LabellingBatch,
    unit_id: str,
    context_record: ContextExecutionRecord,
    selection: PlannedExperimentSelection,
    checkpoints: tuple[GoldDecisionCheckpoint, ...],
    data_truth: Literal["licensed_historical", "public_historical", "reviewed_synthetic", "mixed"],
    prepared_by: str,
    prepared_at: datetime,
    supersedes_gold_reference_id: str | None = None,
) -> GoldCaseBundle:
    """Compile reviewed source records; never infer, approve, or mutate them."""

    readiness = batch.readiness(unit_id)
    if readiness.state != "ready" or readiness.annotation_id is None or readiness.review_id is None:
        raise GoldCaseConflict("the label requires accepted independent review before Gold preparation")
    annotation = batch.latest_annotation(unit_id)
    review = next((item for item in batch.reviews if item.review_id == readiness.review_id), None)
    if annotation is None or review is None or review.outcome is not ReviewOutcome.ACCEPT_FOR_GOLD_PREPARATION:
        raise GoldCaseConflict("the accepted label review is unavailable")
    context_review = context_record.latest_review
    if context_review is None or context_review.outcome is not ContextReviewOutcome.ACCEPT_CONTEXT:
        raise GoldCaseConflict("the evidence context requires accepted human review before Gold preparation")
    if context_record.execution.unit_id != unit_id:
        raise GoldCaseConflict("evidence context belongs to a different review item")
    review_by_candidate = {item.candidate_id: item for item in context_review.candidate_reviews}
    retained = []
    for candidate in context_record.execution.proposal.candidates:
        decision = review_by_candidate[candidate.candidate_id]
        if decision.outcome is not CandidateReviewOutcome.RETAIN:
            continue
        retained.append(GoldEvidenceItem(
            evidence_item_id=candidate.candidate_id,
            source_record_id=candidate.source_record_id,
            source_kind="event" if candidate.channel.value == "events" else "fundamental",
            title=candidate.display_title,
            summary=candidate.display_summary,
            observed_at=candidate.observed_at,
            available_at=candidate.available_at,
            replay_visibility="ex_ante_eligible" if candidate.eligible_at_replay_time else "retrospective_only",
            role=decision.evidence_role.value,
            position=decision.evidence_position.value,
            reviewer_rationale=decision.rationale,
            evidence_ids=candidate.evidence_ids,
            quality_limits=candidate.quality_flags,
        ))
    if not retained:
        raise GoldCaseConflict("Gold preparation requires at least one retained evidence item")
    interval = annotation.manifestation_interval
    identity = canonical_digest({
        "batch": batch.batch_id,
        "unit": unit_id,
        "selection": selection.selection_digest,
        "annotation": annotation.annotation_digest,
        "context": context_record.execution.execution_digest,
        "supersedes": supersedes_gold_reference_id,
    })
    return GoldCaseBundle(
        gold_reference_id=f"gold-reference-{identity[7:31]}",
        supersedes_gold_reference_id=supersedes_gold_reference_id,
        batch_id=batch.batch_id,
        unit_id=unit_id,
        selection=selection,
        annotation_id=annotation.annotation_id,
        annotation_digest=annotation.annotation_digest,
        annotation_review_id=review.review_id,
        annotation_review_digest=review.review_digest,
        context_execution_id=context_record.execution.execution_id,
        context_execution_digest=context_record.execution.execution_digest,
        context_review_id=context_review.review_id,
        context_review_digest=context_review.review_digest,
        scope_type=annotation.scope_type,
        scope_id=annotation.scope_id,
        outcome=annotation.outcome.value,
        direction=annotation.direction.value,
        morphology=annotation.morphology.value,
        manifestation_start=None if interval is None else interval.start,
        manifestation_peak=None if interval is None else interval.peak,
        manifestation_end=None if interval is None else interval.end,
        manifestation_censored=False if interval is None else interval.censored,
        severity_level=annotation.severity_level,
        severity_basis_points=None if annotation.severity_basis_points is None else float(annotation.severity_basis_points),
        severity_horizon_sessions=annotation.severity_horizon_sessions,
        evidence=tuple(retained),
        checkpoints=checkpoints,
        unresolved_limits=tuple(sorted(set(context_record.execution.proposal.unresolved_questions))),
        data_truth=data_truth,
        prepared_by=prepared_by,
        prepared_at=prepared_at,
    )


def compile_experimental_case(
    record: GoldCaseRecord,
    *,
    portfolio_reference: str,
    mandate_reference: str,
    risk_policy_reference: str,
    data_references: tuple[str, ...],
    evaluation_horizon_end: datetime,
    observable_observation_ids: tuple[str, ...] | None = None,
    observable_as_of: datetime | None = None,
) -> ExperimentalCase:
    """Bind accepted truth to hidden evaluation state and a separately supplied replay stream.

    The Gold evidence set is a retrospective selection and must not define what
    the evaluated architecture gets to observe.  Application compilers should
    therefore supply the complete bounded ex-ante stream.  The Gold-derived
    fallback remains for older callers and stored references.
    """

    if record.state not in {"accepted", "experimental_case_compiled"}:
        raise GoldCaseConflict("independent Gold acceptance is required before case compilation")
    bundle = record.bundle
    gold_eligible_evidence = tuple(sorted({
        evidence_id
        for item in bundle.evidence
        if item.replay_visibility == "ex_ante_eligible"
        for evidence_id in item.evidence_ids
    }))
    replay_evidence = (
        gold_eligible_evidence
        if observable_observation_ids is None
        else tuple(sorted(set(observable_observation_ids)))
    )
    if not replay_evidence:
        raise GoldCaseConflict("the ExperimentalCase requires at least one ex-ante eligible observation")
    if observable_as_of is None:
        observable_as_of = min(
            item.available_at for item in bundle.evidence
            if item.replay_visibility == "ex_ante_eligible"
        )
    case_identity = canonical_digest({
        "gold_reference": bundle.gold_reference_id,
        "experiment": bundle.selection.experiment_id,
        "portfolio": portfolio_reference,
    })
    return ExperimentalCase(
        case_id=f"experimental-case-{case_identity[7:31]}",
        experiment_id=bundle.selection.experiment_id,
        observable_state=ObservableCaseState(
            portfolio_reference=portfolio_reference,
            mandate_reference=mandate_reference,
            risk_policy_reference=risk_policy_reference,
            data_references=tuple(sorted(set(data_references))),
            observation_ids=replay_evidence,
            as_of=observable_as_of,
        ),
        evaluation_state=CaseEvaluationState(
            evaluation_horizon_end=evaluation_horizon_end,
            label_state="admitted",
            reference_label_ids=(bundle.gold_reference_id,),
            outcome_observation_ids=tuple(sorted({
                evidence_id for item in bundle.evidence for evidence_id in item.evidence_ids
            })),
            architecture_access=False,
        ),
    )


class LocalGoldCaseStore:
    """Small append-only local store for Gold bundle review and case binding."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().absolute()
        self.records = self.root / "gold-references"
        self.cases = self.root / "experimental-cases"
        self._thread_lock = threading.RLock()

    @staticmethod
    def _key(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def _ensure_root(self) -> None:
        current = Path(self.root.anchor)
        for part in self.root.parts[1:]:
            current /= part
            if os.path.lexists(current) and current.is_symlink():
                raise GoldCaseConflict("Gold-reference storage path may not contain symbolic links")
        for directory in (self.records, self.cases):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if directory.is_symlink() or not directory.resolve().is_relative_to(self.root.resolve()):
                raise GoldCaseConflict("Gold-reference storage must remain beneath its configured root")

    @contextmanager
    def _lock(self):  # type: ignore[no-untyped-def]
        with self._thread_lock:
            self._ensure_root()
            flags = os.O_RDWR | os.O_CREAT
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(self.root / ".gold-reference.lock", flags, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    def _path(self, reference_id: str) -> Path:
        return self.records / f"{self._key(reference_id)}.json"

    def _case_path(self, case_id: str) -> Path:
        return self.cases / f"{self._key(case_id)}.json"

    @staticmethod
    def _write(path: Path, record: GoldCaseRecord) -> None:
        descriptor, temporary = tempfile.mkstemp(prefix=".gold-", suffix=".json", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(record.model_dump(mode="json"), handle, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def get_optional(self, reference_id: str) -> GoldCaseRecord | None:
        with self._lock():
            path = self._path(reference_id)
            if not path.exists():
                return None
            if path.is_symlink():
                raise GoldCaseConflict("Gold-reference record may not be a symbolic link")
            return GoldCaseRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def get(self, reference_id: str) -> GoldCaseRecord:
        record = self.get_optional(reference_id)
        if record is None:
            raise GoldCaseNotFound(reference_id)
        return record

    def list_for_batch(self, batch_id: str) -> tuple[GoldCaseRecord, ...]:
        with self._lock():
            values = []
            for path in self.records.glob("*.json"):
                if path.is_symlink():
                    raise GoldCaseConflict("Gold-reference record may not be a symbolic link")
                record = GoldCaseRecord.model_validate_json(path.read_text(encoding="utf-8"))
                if record.bundle.batch_id == batch_id:
                    values.append(record)
            return tuple(sorted(values, key=lambda item: item.bundle.prepared_at))

    def list(self) -> tuple[GoldCaseRecord, ...]:
        """Catalogue governed references without exposing them to a RunInput."""
        with self._lock():
            values = []
            for path in self.records.glob("*.json"):
                if path.is_symlink():
                    raise GoldCaseConflict("Gold-reference record may not be a symbolic link")
                values.append(GoldCaseRecord.model_validate_json(path.read_text(encoding="utf-8")))
            return tuple(sorted(values, key=lambda item: item.bundle.prepared_at, reverse=True))

    def create(self, bundle: GoldCaseBundle) -> GoldCaseRecord:
        with self._lock():
            path = self._path(bundle.gold_reference_id)
            candidate = GoldCaseRecord(record_id=f"gold-record-{bundle.gold_reference_id[15:]}", bundle=bundle)
            if path.exists():
                existing = GoldCaseRecord.model_validate_json(path.read_text(encoding="utf-8"))
                if existing.bundle.bundle_digest == bundle.bundle_digest:
                    return existing
                raise GoldCaseConflict("Gold reference already exists with different content")
            self._write(path, candidate)
            return candidate

    def review(self, reference_id: str, review: GoldCaseReview, *, expected_revision: int) -> GoldCaseRecord:
        with self._lock():
            path = self._path(reference_id)
            if not path.exists():
                raise GoldCaseNotFound(reference_id)
            current = GoldCaseRecord.model_validate_json(path.read_text(encoding="utf-8"))
            if current.compiled_case_id is not None:
                raise GoldCaseConflict("a compiled Gold reference cannot receive another review")
            if len(current.reviews) != expected_revision:
                raise GoldCaseConflict("Gold review changed; reload before saving")
            revised = GoldCaseRecord(
                record_id=current.record_id,
                bundle=current.bundle,
                reviews=current.reviews + (review,),
                compiled_case_id=current.compiled_case_id,
                compiled_case_digest=current.compiled_case_digest,
            )
            self._write(path, revised)
            return revised

    def bind_case(self, reference_id: str, case: ExperimentalCase) -> GoldCaseRecord:
        with self._lock():
            path = self._path(reference_id)
            if not path.exists():
                raise GoldCaseNotFound(reference_id)
            current = GoldCaseRecord.model_validate_json(path.read_text(encoding="utf-8"))
            if current.compiled_case_id is not None:
                if current.compiled_case_id == case.case_id and current.compiled_case_digest == case.context_digest:
                    return current
                raise GoldCaseConflict("a Gold reference cannot be rebound to a different ExperimentalCase")
            case_path = self._case_path(case.case_id)
            if case_path.exists():
                existing_case = ExperimentalCase.model_validate_json(case_path.read_text(encoding="utf-8"))
                if existing_case.context_digest != case.context_digest:
                    raise GoldCaseConflict("ExperimentalCase identity already exists with different content")
            else:
                descriptor, temporary = tempfile.mkstemp(prefix=".case-", suffix=".json", dir=case_path.parent)
                try:
                    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                        json.dump(case.model_dump(mode="json"), handle, sort_keys=True, separators=(",", ":"))
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.chmod(temporary, 0o600)
                    os.replace(temporary, case_path)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
            revised = GoldCaseRecord(
                record_id=current.record_id,
                bundle=current.bundle,
                reviews=current.reviews,
                compiled_case_id=case.case_id,
                compiled_case_digest=case.context_digest,
            )
            self._write(path, revised)
            return revised

    def get_case(self, case_id: str) -> ExperimentalCase:
        with self._lock():
            path = self._case_path(case_id)
            if not path.exists():
                raise GoldCaseNotFound(case_id)
            if path.is_symlink():
                raise GoldCaseConflict("ExperimentalCase record may not be a symbolic link")
            return ExperimentalCase.model_validate_json(path.read_text(encoding="utf-8"))

    def list_cases(self) -> tuple[ExperimentalCase, ...]:
        """Return only Cases that passed the Gold-reference binding workflow."""
        with self._lock():
            values = []
            for path in self.cases.glob("*.json"):
                if path.is_symlink():
                    raise GoldCaseConflict("ExperimentalCase record may not be a symbolic link")
                values.append(ExperimentalCase.model_validate_json(path.read_text(encoding="utf-8")))
            return tuple(sorted(values, key=lambda item: item.case_id))
