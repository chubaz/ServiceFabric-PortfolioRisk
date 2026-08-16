"""Dormant, review-first plans for later case-context retrieval and association.

The plan is an executable specification, not an execution.  Saving or revising
one never reads evidence rows, generates controls, associates records, modifies
a label, or creates a Gold/experimental Case.
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

from .models import DIGEST, IDENTIFIER, FrozenModel, canonical_digest


class ContextWorkConflict(ValueError):
    pass


class ContextWorkNotFound(KeyError):
    pass


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("context-work timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


class ContextPurpose(str, Enum):
    EXPLAIN_MANIFESTATION = "explain_manifestation"
    TEST_COMPETING_EXPLANATIONS = "test_competing_explanations"
    PREPARE_CASE_CONTEXT = "prepare_case_context"


class ContextChannel(str, Enum):
    EVENTS = "events"
    FUNDAMENTALS = "fundamentals"


class ControlKind(str, Enum):
    IRRELEVANT_EVENT = "irrelevant_event"
    AMBIGUOUS_EVENT = "ambiguous_event"
    IMMATERIAL_EVENT = "immaterial_event"
    NO_MATERIAL_EVENT = "no_material_event"
    EVENT_SHUFFLE = "event_shuffle"


class EvidenceRole(str, Enum):
    PRECURSOR = "precursor"
    TRIGGER = "trigger"
    AMPLIFIER = "amplifier"
    CONFIRMATION = "confirmation"
    RESPONSE = "response"
    MITIGATION = "mitigation"
    AFTERMATH = "aftermath"
    UNRELATED = "unrelated"
    UNRESOLVED = "unresolved"


class EvidencePosition(str, Enum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    ALTERNATIVE = "alternative"
    UNRESOLVED = "unresolved"


class CandidateReviewOutcome(str, Enum):
    RETAIN = "retain"
    REJECT = "reject"
    NEEDS_MORE_WORK = "needs_more_work"


class ContextReviewOutcome(str, Enum):
    ACCEPT_CONTEXT = "accept_context"
    REQUEST_CHANGES = "request_changes"
    EXCLUDE_CONTEXT = "exclude_context"


class ContextWindow(FrozenModel):
    event_days_before: int = Field(default=20, ge=0, le=365)
    event_days_after: int = Field(default=20, ge=0, le=365)
    fundamental_lookback_quarters: int = Field(default=8, ge=1, le=40)
    retrospective_cutoff_policy: Literal["labelling_batch_end"] = "labelling_batch_end"
    replay_eligibility_policy: Literal["available_at_lte_replay_time"] = "available_at_lte_replay_time"


class AssociationMethod(FrozenModel):
    entity_matching: Literal["exact_canonical_identifier"] = "exact_canonical_identifier"
    temporal_ranking: Literal["bounded_distance_from_manifestation"] = "bounded_distance_from_manifestation"
    event_features: tuple[
        Literal["entity", "time", "relevance", "novelty", "taxonomy", "intensity"], ...
    ] = ("entity", "time", "relevance", "novelty", "taxonomy", "intensity")
    causal_claims_allowed: Literal[False] = False
    alternatives_required: bool = True
    human_review_required: Literal[True] = True

    @field_validator("event_features")
    @classmethod
    def unique_features(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if values != tuple(dict.fromkeys(values)) or "entity" not in values or "time" not in values:
            raise ValueError("association features must be unique and retain entity and time")
        return values


class ControlSpecification(FrozenModel):
    requested: tuple[ControlKind, ...] = ()
    generation_policy: Literal["only_when_case_design_requires"] = "only_when_case_design_requires"
    synthetic_marking_required: Literal[True] = True
    generated_count: Literal[0] = 0

    @field_validator("requested")
    @classmethod
    def unique_sorted(cls, values: tuple[ControlKind, ...]) -> tuple[ControlKind, ...]:
        if values != tuple(sorted(set(values), key=lambda item: item.value)):
            raise ValueError("requested controls must be unique and sorted")
        return values


class ContextWorkPlan(FrozenModel):
    plan_id: str = Field(pattern=IDENTIFIER)
    batch_id: str = Field(pattern=IDENTIFIER)
    unit_id: str = Field(pattern=IDENTIFIER)
    revision: int = Field(ge=1)
    supersedes_plan_id: str | None = Field(default=None, pattern=IDENTIFIER)
    purpose: ContextPurpose
    channels: tuple[ContextChannel, ...] = Field(min_length=1)
    window: ContextWindow
    method: AssociationMethod
    controls: ControlSpecification
    required_outputs: tuple[
        Literal["supporting", "contradicting", "alternatives", "unresolved", "quality_limit"], ...
    ]
    source_readiness_digest: str = Field(pattern=DIGEST)
    readiness_state: Literal["ready_for_later_execution", "prepared_with_blockers"]
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_status: Literal["not_started"] = "not_started"
    retrieval_count: Literal[0] = 0
    association_count: Literal[0] = 0
    controls_generated_count: Literal[0] = 0
    label_modified: Literal[False] = False
    gold_case_created: Literal[False] = False
    prepared_by: str = Field(min_length=2, max_length=120)
    prepared_at: datetime
    plan_digest: str | None = Field(default=None, pattern=DIGEST)

    _prepared_at = field_validator("prepared_at")(_utc)

    @field_validator("channels")
    @classmethod
    def channels_are_unique_and_sorted(cls, values: tuple[ContextChannel, ...]) -> tuple[ContextChannel, ...]:
        if values != tuple(sorted(set(values), key=lambda item: item.value)):
            raise ValueError("context channels must be unique and sorted")
        return values

    @field_validator("required_outputs")
    @classmethod
    def outputs_are_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if values != tuple(dict.fromkeys(values)):
            raise ValueError("required outputs must be unique")
        if "supporting" not in values or "quality_limit" not in values:
            raise ValueError("context work must retain supporting evidence and quality limits")
        return values

    @model_validator(mode="after")
    def no_execution_and_revision_chain(self) -> "ContextWorkPlan":
        if self.revision == 1 and self.supersedes_plan_id is not None:
            raise ValueError("first plan revision cannot supersede another plan")
        if self.revision > 1 and self.supersedes_plan_id is None:
            raise ValueError("later plan revisions must supersede an earlier plan")
        if self.readiness_state == "ready_for_later_execution" and self.blockers:
            raise ValueError("a ready plan cannot retain blockers")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"plan_digest"}))
        if self.plan_digest is not None and self.plan_digest != expected:
            raise ValueError("plan_digest does not match canonical content")
        object.__setattr__(self, "plan_digest", expected)
        return self


class ContextEvidenceCandidate(FrozenModel):
    """Provider-neutral proposal output; never establishes reference truth."""

    candidate_id: str = Field(pattern=IDENTIFIER)
    plan_id: str = Field(pattern=IDENTIFIER)
    unit_id: str = Field(pattern=IDENTIFIER)
    channel: ContextChannel
    canonical_entity_id: str = Field(min_length=1, max_length=200)
    source_record_id: str = Field(default="unavailable", min_length=1, max_length=240)
    display_title: str = Field(default="Evidence candidate", min_length=1, max_length=240)
    display_summary: str = Field(default="Review the source context.", min_length=1, max_length=800)
    observed_at: datetime
    available_at: datetime
    eligible_at_replay_time: bool
    distance_days: int = Field(default=0, ge=-3650, le=3650)
    proposed_role: EvidenceRole
    proposed_position: EvidencePosition
    relevance_score: float = Field(ge=0, le=1)
    association_score: float = Field(ge=0, le=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    quality_flags: tuple[str, ...] = ()
    proposal_only: Literal[True] = True
    human_review_required: Literal[True] = True

    _times = field_validator("observed_at", "available_at")(_utc)

    @model_validator(mode="after")
    def temporal_and_reference_integrity(self) -> "ContextEvidenceCandidate":
        if self.available_at < self.observed_at:
            raise ValueError("evidence availability cannot precede observation time")
        if self.evidence_ids != tuple(sorted(set(self.evidence_ids))):
            raise ValueError("candidate evidence references must be unique and sorted")
        return self


class ContextAssociationProposal(FrozenModel):
    """Future review payload; its presence never modifies a label."""

    proposal_id: str = Field(pattern=IDENTIFIER)
    plan_id: str = Field(pattern=IDENTIFIER)
    plan_digest: str = Field(pattern=DIGEST)
    unit_id: str = Field(pattern=IDENTIFIER)
    candidates: tuple[ContextEvidenceCandidate, ...]
    unresolved_questions: tuple[str, ...] = ()
    proposal_only: Literal[True] = True
    accepted: Literal[False] = False
    label_modified: Literal[False] = False
    gold_case_created: Literal[False] = False

    @model_validator(mode="after")
    def candidates_bind_to_plan(self) -> "ContextAssociationProposal":
        if any(item.plan_id != self.plan_id or item.unit_id != self.unit_id for item in self.candidates):
            raise ValueError("association candidates must bind to the exact plan and review unit")
        return self


class ContextWorkExecution(FrozenModel):
    """One immutable preparation result for one exact saved plan revision."""

    execution_id: str = Field(pattern=IDENTIFIER)
    batch_id: str = Field(pattern=IDENTIFIER)
    unit_id: str = Field(pattern=IDENTIFIER)
    plan_id: str = Field(pattern=IDENTIFIER)
    plan_digest: str = Field(pattern=DIGEST)
    plan_revision: int = Field(ge=1)
    retrospective_cutoff: datetime
    prepared_at: datetime
    prepared_by: str = Field(min_length=2, max_length=120)
    proposal: ContextAssociationProposal
    excluded_missing_availability: int = Field(ge=0)
    excluded_temporal_violations: int = Field(ge=0)
    excluded_after_cutoff: int = Field(ge=0)
    source_revisions: tuple[str, ...]
    query_receipts: tuple[str, ...]
    controls_generated_count: Literal[0] = 0
    label_modified: Literal[False] = False
    gold_case_created: Literal[False] = False
    state: Literal["awaiting_human_review"] = "awaiting_human_review"
    execution_digest: str | None = Field(default=None, pattern=DIGEST)

    _times = field_validator("retrospective_cutoff", "prepared_at")(_utc)

    @model_validator(mode="after")
    def execution_reconciles(self) -> "ContextWorkExecution":
        if self.proposal.plan_id != self.plan_id or self.proposal.plan_digest != self.plan_digest:
            raise ValueError("context proposal must bind to the exact executed plan")
        if self.proposal.unit_id != self.unit_id:
            raise ValueError("context proposal must bind to the exact review unit")
        if self.source_revisions != tuple(sorted(set(self.source_revisions))):
            raise ValueError("source revisions must be unique and sorted")
        if self.query_receipts != tuple(dict.fromkeys(self.query_receipts)):
            raise ValueError("query receipts must be unique")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"execution_digest"}))
        if self.execution_digest is not None and self.execution_digest != expected:
            raise ValueError("execution_digest does not match canonical content")
        object.__setattr__(self, "execution_digest", expected)
        return self


class ContextCandidateReview(FrozenModel):
    candidate_id: str = Field(pattern=IDENTIFIER)
    outcome: CandidateReviewOutcome
    evidence_role: EvidenceRole
    evidence_position: EvidencePosition
    rationale: str = Field(min_length=3, max_length=1200)


class ContextExecutionReview(FrozenModel):
    review_id: str = Field(pattern=IDENTIFIER)
    execution_id: str = Field(pattern=IDENTIFIER)
    execution_digest: str = Field(pattern=DIGEST)
    revision: int = Field(ge=1)
    supersedes_review_id: str | None = Field(default=None, pattern=IDENTIFIER)
    outcome: ContextReviewOutcome
    candidate_reviews: tuple[ContextCandidateReview, ...]
    limitations_acknowledged: bool
    reviewed_by: str = Field(min_length=2, max_length=120)
    reviewed_at: datetime
    summary: str = Field(min_length=10, max_length=1600)
    label_modified: Literal[False] = False
    gold_case_created: Literal[False] = False
    review_digest: str | None = Field(default=None, pattern=DIGEST)

    _reviewed_at = field_validator("reviewed_at")(_utc)

    @model_validator(mode="after")
    def review_reconciles(self) -> "ContextExecutionReview":
        candidate_ids = tuple(item.candidate_id for item in self.candidate_reviews)
        if candidate_ids != tuple(sorted(set(candidate_ids))):
            raise ValueError("candidate reviews must be unique and sorted")
        if self.revision == 1 and self.supersedes_review_id is not None:
            raise ValueError("first context review cannot supersede another review")
        if self.revision > 1 and self.supersedes_review_id is None:
            raise ValueError("later context reviews must supersede the prior review")
        if self.outcome == ContextReviewOutcome.ACCEPT_CONTEXT:
            if not self.limitations_acknowledged:
                raise ValueError("accepted context must acknowledge its limitations")
            if not any(item.outcome == CandidateReviewOutcome.RETAIN for item in self.candidate_reviews):
                raise ValueError("accepted context must retain at least one candidate")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"review_digest"}))
        if self.review_digest is not None and self.review_digest != expected:
            raise ValueError("review_digest does not match canonical content")
        object.__setattr__(self, "review_digest", expected)
        return self


class ContextExecutionRecord(FrozenModel):
    record_id: str = Field(pattern=IDENTIFIER)
    execution: ContextWorkExecution
    reviews: tuple[ContextExecutionReview, ...] = ()
    record_digest: str | None = Field(default=None, pattern=DIGEST)

    @model_validator(mode="after")
    def review_chain_is_valid(self) -> "ContextExecutionRecord":
        expected_candidates = tuple(sorted(item.candidate_id for item in self.execution.proposal.candidates))
        for index, review in enumerate(self.reviews, start=1):
            if review.execution_id != self.execution.execution_id or review.execution_digest != self.execution.execution_digest:
                raise ValueError("context review must bind to the exact execution")
            if review.revision != index:
                raise ValueError("context review revisions must be contiguous")
            if index > 1 and review.supersedes_review_id != self.reviews[index - 2].review_id:
                raise ValueError("context review supersession chain is invalid")
            if tuple(item.candidate_id for item in review.candidate_reviews) != expected_candidates:
                raise ValueError("context review must account for every candidate exactly once")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"record_digest"}))
        if self.record_digest is not None and self.record_digest != expected:
            raise ValueError("context execution record digest does not match canonical content")
        object.__setattr__(self, "record_digest", expected)
        return self

    @property
    def latest_review(self) -> ContextExecutionReview | None:
        return self.reviews[-1] if self.reviews else None


class ContextWorkRecord(FrozenModel):
    record_id: str = Field(pattern=IDENTIFIER)
    batch_id: str = Field(pattern=IDENTIFIER)
    unit_id: str = Field(pattern=IDENTIFIER)
    revisions: tuple[ContextWorkPlan, ...] = Field(min_length=1)
    record_digest: str | None = Field(default=None, pattern=DIGEST)

    @model_validator(mode="after")
    def revision_chain_is_contiguous(self) -> "ContextWorkRecord":
        for index, item in enumerate(self.revisions, start=1):
            if item.batch_id != self.batch_id or item.unit_id != self.unit_id or item.revision != index:
                raise ValueError("context-work revisions must be contiguous and bind to one review unit")
            if index > 1 and item.supersedes_plan_id != self.revisions[index - 2].plan_id:
                raise ValueError("context-work supersession chain is invalid")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"record_digest"}))
        if self.record_digest is not None and self.record_digest != expected:
            raise ValueError("record_digest does not match canonical content")
        object.__setattr__(self, "record_digest", expected)
        return self

    @property
    def latest(self) -> ContextWorkPlan:
        return self.revisions[-1]


def compile_context_work_plan(
    *,
    batch_id: str,
    unit_id: str,
    purpose: ContextPurpose,
    channels: tuple[ContextChannel, ...],
    window: ContextWindow,
    method: AssociationMethod,
    controls: ControlSpecification,
    source_readiness_digest: str,
    blockers: tuple[str, ...],
    warnings: tuple[str, ...] = (),
    prepared_by: str,
    prepared_at: datetime,
    prior: ContextWorkPlan | None = None,
) -> ContextWorkPlan:
    revision = 1 if prior is None else prior.revision + 1
    identity = canonical_digest({
        "batch": batch_id, "unit": unit_id, "revision": revision,
        "purpose": purpose.value, "channels": [item.value for item in channels],
        "window": window, "method": method, "controls": controls,
        "source_readiness": source_readiness_digest, "blockers": blockers, "warnings": warnings,
    })
    return ContextWorkPlan(
        plan_id=f"context-plan-{identity[7:31]}", batch_id=batch_id, unit_id=unit_id,
        revision=revision, supersedes_plan_id=None if prior is None else prior.plan_id,
        purpose=purpose, channels=tuple(sorted(set(channels), key=lambda item: item.value)),
        window=window, method=method, controls=controls,
        required_outputs=("supporting", "contradicting", "alternatives", "unresolved", "quality_limit"),
        source_readiness_digest=source_readiness_digest,
        readiness_state="prepared_with_blockers" if blockers else "ready_for_later_execution",
        blockers=tuple(sorted(set(blockers))), warnings=tuple(sorted(set(warnings))),
        prepared_by=prepared_by, prepared_at=prepared_at,
    )


class LocalContextWorkStore:
    """Atomic local store for append-only plan revisions; contains no evidence rows."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().absolute()
        self.records = self.root / "context-work"
        self._thread_lock = threading.RLock()

    @staticmethod
    def _key(batch_id: str, unit_id: str) -> str:
        return hashlib.sha256(f"{batch_id}:{unit_id}".encode()).hexdigest()

    def _ensure(self) -> None:
        current = Path(self.root.anchor)
        for part in self.root.parts[1:]:
            current /= part
            if os.path.lexists(current) and current.is_symlink():
                raise ContextWorkConflict("context-work storage path may not contain symbolic links")
        self.records.mkdir(mode=0o700, parents=True, exist_ok=True)

    @contextmanager
    def _lock(self):  # type: ignore[no-untyped-def]
        with self._thread_lock:
            self._ensure()
            flags = os.O_RDWR | os.O_CREAT | (getattr(os, "O_NOFOLLOW", 0))
            descriptor = os.open(self.root / ".context-work.lock", flags, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    def _path(self, batch_id: str, unit_id: str) -> Path:
        return self.records / f"{self._key(batch_id, unit_id)}.json"

    @staticmethod
    def _read(path: Path) -> ContextWorkRecord:
        if path.is_symlink():
            raise ContextWorkConflict("context-work records may not be symbolic links")
        try:
            return ContextWorkRecord.model_validate_json(path.read_bytes())
        except FileNotFoundError as error:
            raise ContextWorkNotFound(path.stem) from error

    @staticmethod
    def _write(path: Path, record: ContextWorkRecord) -> None:
        payload = (json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode()
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(payload); stream.flush(); os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            if path.is_symlink():
                raise ContextWorkConflict("context-work records may not be symbolic links")
            os.replace(temporary, path)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if os.path.exists(temporary):
                os.unlink(temporary)

    def get(self, batch_id: str, unit_id: str) -> ContextWorkRecord:
        return self._read(self._path(batch_id, unit_id))

    def get_optional(self, batch_id: str, unit_id: str) -> ContextWorkRecord | None:
        try:
            return self.get(batch_id, unit_id)
        except ContextWorkNotFound:
            return None

    def list_for_batch(self, batch_id: str) -> tuple[ContextWorkRecord, ...]:
        self._ensure()
        return tuple(sorted(
            (record for path in self.records.glob("*.json") if (record := self._read(path)).batch_id == batch_id),
            key=lambda item: item.unit_id,
        ))

    def save(self, plan: ContextWorkPlan, *, expected_record_digest: str | None = None) -> ContextWorkRecord:
        with self._lock():
            path = self._path(plan.batch_id, plan.unit_id)
            current = self._read(path) if path.exists() else None
            if current is None:
                if plan.revision != 1 or plan.supersedes_plan_id is not None:
                    raise ContextWorkConflict("new context-work records must begin at revision 1")
                record = ContextWorkRecord(
                    record_id=f"context-work-{self._key(plan.batch_id, plan.unit_id)[:24]}",
                    batch_id=plan.batch_id, unit_id=plan.unit_id, revisions=(plan,),
                )
            else:
                if expected_record_digest != current.record_digest:
                    raise ContextWorkConflict("context-work plan changed; reload before revising")
                if plan.revision != current.latest.revision + 1 or plan.supersedes_plan_id != current.latest.plan_id:
                    raise ContextWorkConflict("context-work plan must be the next immutable revision")
                if plan.plan_digest == current.latest.plan_digest:
                    return current
                record = ContextWorkRecord(
                    record_id=current.record_id, batch_id=current.batch_id,
                    unit_id=current.unit_id, revisions=(*current.revisions, plan),
                )
            self._write(path, record)
            return record


class LocalContextExecutionStore:
    """Local immutable preparation results and append-only human reviews."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().absolute()
        self.records = self.root / "context-executions"
        self._thread_lock = threading.RLock()

    @staticmethod
    def _key(batch_id: str, unit_id: str, plan_id: str) -> str:
        return hashlib.sha256(f"{batch_id}:{unit_id}:{plan_id}".encode()).hexdigest()

    def _ensure(self) -> None:
        current = Path(self.root.anchor)
        for part in self.root.parts[1:]:
            current /= part
            if os.path.lexists(current) and current.is_symlink():
                raise ContextWorkConflict("context execution storage path may not contain symbolic links")
        self.records.mkdir(mode=0o700, parents=True, exist_ok=True)

    @contextmanager
    def _lock(self):  # type: ignore[no-untyped-def]
        with self._thread_lock:
            self._ensure()
            descriptor = os.open(
                self.root / ".context-execution.lock",
                os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    def _path(self, batch_id: str, unit_id: str, plan_id: str) -> Path:
        return self.records / f"{self._key(batch_id, unit_id, plan_id)}.json"

    @staticmethod
    def _read(path: Path) -> ContextExecutionRecord:
        if path.is_symlink():
            raise ContextWorkConflict("context execution records may not be symbolic links")
        try:
            return ContextExecutionRecord.model_validate_json(path.read_bytes())
        except FileNotFoundError as error:
            raise ContextWorkNotFound(path.stem) from error

    @staticmethod
    def _write(path: Path, record: ContextExecutionRecord) -> None:
        payload = (json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode()
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            if path.is_symlink():
                raise ContextWorkConflict("context execution records may not be symbolic links")
            os.replace(temporary, path)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if os.path.exists(temporary):
                os.unlink(temporary)

    def get(self, batch_id: str, unit_id: str, plan_id: str) -> ContextExecutionRecord:
        return self._read(self._path(batch_id, unit_id, plan_id))

    def get_optional(self, batch_id: str, unit_id: str, plan_id: str) -> ContextExecutionRecord | None:
        try:
            return self.get(batch_id, unit_id, plan_id)
        except ContextWorkNotFound:
            return None

    def save_execution(self, execution: ContextWorkExecution) -> ContextExecutionRecord:
        with self._lock():
            path = self._path(execution.batch_id, execution.unit_id, execution.plan_id)
            if path.exists():
                current = self._read(path)
                if current.execution.execution_digest != execution.execution_digest:
                    raise ContextWorkConflict("the saved plan revision already has a different execution")
                return current
            record = ContextExecutionRecord(
                record_id=f"context-execution-{self._key(execution.batch_id, execution.unit_id, execution.plan_id)[:24]}",
                execution=execution,
            )
            self._write(path, record)
            return record

    def save_review(
        self,
        *,
        batch_id: str,
        unit_id: str,
        plan_id: str,
        review: ContextExecutionReview,
        expected_record_digest: str,
    ) -> ContextExecutionRecord:
        with self._lock():
            path = self._path(batch_id, unit_id, plan_id)
            current = self._read(path)
            if current.record_digest != expected_record_digest:
                raise ContextWorkConflict("context review changed; reload before saving")
            if review.revision != len(current.reviews) + 1:
                raise ContextWorkConflict("context review must be the next immutable revision")
            revised = ContextExecutionRecord(
                record_id=current.record_id,
                execution=current.execution,
                reviews=(*current.reviews, review),
            )
            self._write(path, revised)
            return revised
