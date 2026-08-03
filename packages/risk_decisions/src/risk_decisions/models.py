"""Strict contracts for the human-owned portfolio-risk decision lifecycle."""

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


class DecisionOutcome(StrEnum):
    INVESTIGATE = "investigate"
    ACCEPT_AND_MONITOR = "accept_and_monitor"
    DEFER = "defer"
    REJECT = "reject"
    ESCALATE = "escalate"


class DecisionState(StrEnum):
    PROPOSED = "proposed"
    POLICY_VALIDATED = "policy_validated"
    AWAITING_REVIEW = "awaiting_review"
    UNDER_INVESTIGATION = "under_investigation"
    DEFERRED = "deferred"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


FINAL_STATES = frozenset({DecisionState.RESOLVED, DecisionState.REJECTED, DecisionState.EXPIRED, DecisionState.SUPERSEDED})


class DueDiligenceCapability(StrEnum):
    EVIDENCE_COVERAGE = "decision.evidence.coverage.inspect"
    CAPABILITY_RECEIPTS = "decision.capability.receipts.inspect"
    POLICY_ALIGNMENT = "decision.policy.alignment.inspect"
    ALTERNATIVES = "decision.alternatives.compare"
    ARTIFACT_LINEAGE = "decision.artifacts.lineage.inspect"


class EvidenceTruth(StrEnum):
    REAL = "real"
    SYNTHETIC = "synthetic"
    MIXED = "mixed"
    REFERENCE_ONLY = "reference_only"
    UNAVAILABLE = "unavailable"


class DecisionOption(FrozenModel):
    outcome: DecisionOutcome
    label: str = Field(min_length=2, max_length=80)
    consequence: str = Field(min_length=5, max_length=600)
    workflow_effect: Literal[
        "effect_free_investigation_then_review",
        "manual_resume_permitted_with_monitoring_receipt",
        "workflow_remains_paused_until_review",
        "manual_resume_permitted_finding_retained",
        "workflow_remains_paused_for_escalation",
    ]
    portfolio_effects: tuple[()] = ()
    external_effects: tuple[()] = ()


def standard_options() -> tuple[DecisionOption, ...]:
    return (
        DecisionOption(
            outcome=DecisionOutcome.INVESTIGATE,
            label="Investigate",
            consequence="Run the registered effect-free evidence review, add a supplemental context revision, and return this proposal to human review.",
            workflow_effect="effect_free_investigation_then_review",
        ),
        DecisionOption(
            outcome=DecisionOutcome.ACCEPT_AND_MONITOR,
            label="Accept & monitor",
            consequence="Record acceptance and a monitoring obligation. Manual cycle resume is permitted; no portfolio state changes.",
            workflow_effect="manual_resume_permitted_with_monitoring_receipt",
        ),
        DecisionOption(
            outcome=DecisionOutcome.DEFER,
            label="Defer",
            consequence="Keep the workflow paused and retain the proposal for a later human review.",
            workflow_effect="workflow_remains_paused_until_review",
        ),
        DecisionOption(
            outcome=DecisionOutcome.REJECT,
            label="Reject",
            consequence="Reject the proposal while retaining its finding and evidence. Manual cycle resume is permitted.",
            workflow_effect="manual_resume_permitted_finding_retained",
        ),
        DecisionOption(
            outcome=DecisionOutcome.ESCALATE,
            label="Escalate",
            consequence="Keep the workflow paused and record an in-application escalation for another eligible human reviewer.",
            workflow_effect="workflow_remains_paused_for_escalation",
        ),
    )


class DecisionProposal(FrozenModel):
    schema_version: Literal["portfolio-risk.decision-proposal/v1"] = "portfolio-risk.decision-proposal/v1"
    proposal_id: str = Field(pattern=IDENTIFIER)
    version: int = Field(default=1, ge=1)
    finding_id: str = Field(pattern=IDENTIFIER)
    finding_digest: str = Field(pattern=DIGEST)
    question: str = Field(min_length=5, max_length=800)
    why_now: str = Field(min_length=5, max_length=1200)
    proposing_agent_id: str = Field(pattern=IDENTIFIER)
    proposing_workflow_id: str = Field(pattern=IDENTIFIER)
    recommendation: DecisionOutcome
    options: tuple[DecisionOption, ...] = Field(default_factory=standard_options)
    mandate_relevance: str = Field(min_length=3, max_length=1000)
    portfolio_relevance: str = Field(min_length=3, max_length=1000)
    risk_environment_relevance: str = Field(min_length=3, max_length=1000)
    evidence_ids: tuple[str, ...] = ()
    artifact_ids: tuple[str, ...] = ()
    capability_receipt_ids: tuple[str, ...] = ()
    model_receipt_ids: tuple[str, ...] = ()
    policy_ids: tuple[str, ...] = ()
    scenario_ids: tuple[str, ...] = ()
    counter_evidence: tuple[str, ...] = ()
    uncertainties: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()
    as_of: datetime
    available_at: datetime
    created_at: datetime
    expires_at: datetime
    authority_level: Literal["D1"] = "D1"
    eligible_resolver_types: tuple[Literal["human"], ...] = ("human",)
    human_review_required: Literal[True] = True
    downstream_workflow_preview: str = Field(min_length=3, max_length=1000)
    effects: tuple[()] = ()
    proposal_digest: str | None = Field(default=None, pattern=DIGEST)

    _as_of = field_validator("as_of")(_aware)
    _available = field_validator("available_at")(_aware)
    _created = field_validator("created_at")(_aware)
    _expires = field_validator("expires_at")(_aware)

    @model_validator(mode="after")
    def validate_and_bind(self) -> "DecisionProposal":
        outcomes = tuple(item.outcome for item in self.options)
        if outcomes != tuple(DecisionOutcome):
            raise ValueError("options must contain the five standard human outcomes in canonical order")
        if self.available_at > self.as_of:
            raise ValueError("proposal evidence cannot become available after the as-of time")
        if self.expires_at <= self.created_at:
            raise ValueError("proposal expiry must follow creation")
        for values in (
            self.evidence_ids,
            self.artifact_ids,
            self.capability_receipt_ids,
            self.model_receipt_ids,
            self.policy_ids,
            self.scenario_ids,
        ):
            if values != tuple(sorted(set(values))):
                raise ValueError("proposal references must be sorted and unique")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"proposal_digest"}))
        if self.proposal_digest is not None and self.proposal_digest != expected:
            raise ValueError("proposal_digest does not match canonical content")
        object.__setattr__(self, "proposal_digest", expected)
        return self


class DecisionLifecycleReceipt(FrozenModel):
    schema_version: Literal["portfolio-risk.decision-lifecycle-receipt/v1"] = "portfolio-risk.decision-lifecycle-receipt/v1"
    receipt_id: str = Field(pattern=IDENTIFIER)
    proposal_id: str = Field(pattern=IDENTIFIER)
    sequence: int = Field(ge=1)
    from_state: DecisionState | None
    to_state: DecisionState
    actor_id: str = Field(pattern=IDENTIFIER)
    actor_type: Literal["system", "human", "workflow"]
    rationale: str = Field(min_length=3, max_length=1200)
    occurred_at: datetime
    idempotency_key: str = Field(pattern=IDENTIFIER)
    prior_receipt_digest: str | None = Field(default=None, pattern=DIGEST)
    receipt_digest: str | None = Field(default=None, pattern=DIGEST)

    _occurred = field_validator("occurred_at")(_aware)

    @model_validator(mode="after")
    def bind_digest(self) -> "DecisionLifecycleReceipt":
        expected = canonical_digest(self.model_dump(mode="json", exclude={"receipt_digest"}))
        if self.receipt_digest is not None and self.receipt_digest != expected:
            raise ValueError("receipt_digest does not match canonical content")
        object.__setattr__(self, "receipt_digest", expected)
        return self


class DecisionResolution(FrozenModel):
    schema_version: Literal["portfolio-risk.decision-resolution/v1"] = "portfolio-risk.decision-resolution/v1"
    decision_id: str = Field(pattern=IDENTIFIER)
    proposal_id: str = Field(pattern=IDENTIFIER)
    proposal_digest: str = Field(pattern=DIGEST)
    outcome: DecisionOutcome
    resolver_id: str = Field(pattern=IDENTIFIER)
    resolver_type: Literal["human"] = "human"
    idempotency_key: str = Field(pattern=IDENTIFIER)
    rationale: str = Field(min_length=3, max_length=2000)
    decided_at: datetime
    policy_id: str = Field(pattern=IDENTIFIER)
    effects: tuple[()] = ()
    decision_digest: str | None = Field(default=None, pattern=DIGEST)

    _decided = field_validator("decided_at")(_aware)

    @model_validator(mode="after")
    def bind_digest(self) -> "DecisionResolution":
        expected = canonical_digest(self.model_dump(mode="json", exclude={"decision_digest"}))
        if self.decision_digest is not None and self.decision_digest != expected:
            raise ValueError("decision_digest does not match canonical content")
        object.__setattr__(self, "decision_digest", expected)
        return self


class DecisionConsequenceReceipt(FrozenModel):
    schema_version: Literal["portfolio-risk.decision-consequence/v1"] = "portfolio-risk.decision-consequence/v1"
    receipt_id: str = Field(pattern=IDENTIFIER)
    decision_id: str = Field(pattern=IDENTIFIER)
    proposal_id: str = Field(pattern=IDENTIFIER)
    outcome: DecisionOutcome
    consequence: str = Field(min_length=3, max_length=1000)
    workflow_effect: str = Field(min_length=3, max_length=120)
    recorded_at: datetime
    portfolio_effects: tuple[()] = ()
    external_effects: tuple[()] = ()

    _recorded = field_validator("recorded_at")(_aware)


class DecisionContextRevision(FrozenModel):
    schema_version: Literal["portfolio-risk.decision-context-revision/v1"] = "portfolio-risk.decision-context-revision/v1"
    revision_id: str = Field(pattern=IDENTIFIER)
    proposal_id: str = Field(pattern=IDENTIFIER)
    parent_context_digest: str = Field(pattern=DIGEST)
    generated_by_workflow: Literal["decision.investigate.effect-free.v1"] = "decision.investigate.effect-free.v1"
    supplemental_findings: tuple[str, ...] = Field(min_length=1, max_length=20)
    supplemental_evidence_ids: tuple[str, ...] = ()
    unresolved_questions: tuple[str, ...] = ()
    created_at: datetime
    effects: tuple[()] = ()
    revision_digest: str | None = Field(default=None, pattern=DIGEST)

    _created = field_validator("created_at")(_aware)

    @model_validator(mode="after")
    def bind_digest(self) -> "DecisionContextRevision":
        expected = canonical_digest(self.model_dump(mode="json", exclude={"revision_digest"}))
        if self.revision_digest is not None and self.revision_digest != expected:
            raise ValueError("revision_digest does not match canonical content")
        object.__setattr__(self, "revision_digest", expected)
        return self


class DecisionFollowUpRun(FrozenModel):
    schema_version: Literal["portfolio-risk.decision-follow-up-run/v1"] = "portfolio-risk.decision-follow-up-run/v1"
    run_id: str = Field(pattern=IDENTIFIER)
    proposal_id: str = Field(pattern=IDENTIFIER)
    workflow_id: Literal["decision.investigate.effect-free.v1"] = "decision.investigate.effect-free.v1"
    status: Literal["completed"] = "completed"
    capability_receipts_reviewed: tuple[str, ...] = ()
    output_context_revision_id: str = Field(pattern=IDENTIFIER)
    completed_at: datetime
    effects: tuple[()] = ()

    _completed = field_validator("completed_at")(_aware)


class DecisionSupplementalEvidence(FrozenModel):
    schema_version: Literal["portfolio-risk.decision-supplemental-evidence/v1"] = "portfolio-risk.decision-supplemental-evidence/v1"
    evidence_id: str = Field(pattern=IDENTIFIER)
    proposal_id: str = Field(pattern=IDENTIFIER)
    source_type: Literal[
        "coverage_analysis",
        "capability_receipt_analysis",
        "policy_analysis",
        "alternative_analysis",
        "artifact_lineage_analysis",
    ]
    title: str = Field(min_length=3, max_length=160)
    finding: str = Field(min_length=5, max_length=1800)
    source_reference_ids: tuple[str, ...] = ()
    data_truth: EvidenceTruth
    as_of: datetime
    available_at: datetime
    created_at: datetime
    created_by: str = Field(pattern=IDENTIFIER)
    effects: tuple[()] = ()
    evidence_digest: str | None = Field(default=None, pattern=DIGEST)

    _as_of = field_validator("as_of")(_aware)
    _available = field_validator("available_at")(_aware)
    _created = field_validator("created_at")(_aware)

    @model_validator(mode="after")
    def validate_and_bind(self) -> "DecisionSupplementalEvidence":
        if self.available_at > self.as_of:
            raise ValueError("supplemental evidence cannot be available after its as-of time")
        if self.source_reference_ids != tuple(sorted(set(self.source_reference_ids))):
            raise ValueError("supplemental evidence references must be sorted and unique")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"evidence_digest"}))
        if self.evidence_digest is not None and self.evidence_digest != expected:
            raise ValueError("evidence_digest does not match canonical content")
        object.__setattr__(self, "evidence_digest", expected)
        return self


class DecisionInvestigationStep(FrozenModel):
    schema_version: Literal["portfolio-risk.decision-investigation-step/v1"] = "portfolio-risk.decision-investigation-step/v1"
    step_id: str = Field(pattern=IDENTIFIER)
    capability_id: DueDiligenceCapability
    objective: str = Field(min_length=3, max_length=600)
    input_reference_ids: tuple[str, ...] = ()
    result_summary: str = Field(min_length=5, max_length=1800)
    output_evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=5)
    status: Literal["completed"] = "completed"
    started_at: datetime
    completed_at: datetime
    effects: tuple[()] = ()

    _started = field_validator("started_at")(_aware)
    _completed = field_validator("completed_at")(_aware)

    @model_validator(mode="after")
    def validate_step(self) -> "DecisionInvestigationStep":
        if self.completed_at < self.started_at:
            raise ValueError("investigation step cannot complete before it starts")
        for values in (self.input_reference_ids, self.output_evidence_ids):
            if values != tuple(sorted(set(values))):
                raise ValueError("investigation step references must be sorted and unique")
        return self


class DecisionInvestigationWorkflowRun(FrozenModel):
    schema_version: Literal["portfolio-risk.decision-investigation-run/v1"] = "portfolio-risk.decision-investigation-run/v1"
    run_id: str = Field(pattern=IDENTIFIER)
    proposal_id: str = Field(pattern=IDENTIFIER)
    base_proposal_digest: str = Field(pattern=DIGEST)
    name: str = Field(min_length=3, max_length=160)
    investigation_question: str = Field(min_length=5, max_length=1200)
    created_by: str = Field(pattern=IDENTIFIER)
    actor_type: Literal["human"] = "human"
    candidate_recommendation: DecisionOutcome
    idempotency_key: str = Field(pattern=IDENTIFIER)
    steps: tuple[DecisionInvestigationStep, ...] = Field(min_length=1, max_length=5)
    temporary: Literal[True] = True
    registry_publication: Literal[False] = False
    started_at: datetime
    completed_at: datetime
    effects: tuple[()] = ()
    run_digest: str | None = Field(default=None, pattern=DIGEST)

    _started = field_validator("started_at")(_aware)
    _completed = field_validator("completed_at")(_aware)

    @model_validator(mode="after")
    def validate_and_bind(self) -> "DecisionInvestigationWorkflowRun":
        capabilities = tuple(item.capability_id for item in self.steps)
        if len(capabilities) != len(set(capabilities)):
            raise ValueError("temporary investigation capabilities must be unique")
        if self.completed_at < self.started_at:
            raise ValueError("investigation workflow cannot complete before it starts")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"run_digest"}))
        if self.run_digest is not None and self.run_digest != expected:
            raise ValueError("run_digest does not match canonical content")
        object.__setattr__(self, "run_digest", expected)
        return self


class DecisionProposalRevision(FrozenModel):
    schema_version: Literal["portfolio-risk.decision-proposal-revision/v1"] = "portfolio-risk.decision-proposal-revision/v1"
    revision_id: str = Field(pattern=IDENTIFIER)
    proposal_id: str = Field(pattern=IDENTIFIER)
    revision_number: int = Field(ge=2)
    base_proposal_digest: str = Field(pattern=DIGEST)
    based_on_context_digest: str = Field(pattern=DIGEST)
    recommendation: DecisionOutcome
    rationale: str = Field(min_length=5, max_length=2400)
    supplemental_evidence_ids: tuple[str, ...] = Field(min_length=1)
    alternatives_considered: tuple[DecisionOutcome, ...]
    unresolved_questions: tuple[str, ...] = ()
    created_by: str = Field(pattern=IDENTIFIER)
    workflow_run_id: str = Field(pattern=IDENTIFIER)
    created_at: datetime
    effects: tuple[()] = ()
    revision_digest: str | None = Field(default=None, pattern=DIGEST)

    _created = field_validator("created_at")(_aware)

    @model_validator(mode="after")
    def validate_and_bind(self) -> "DecisionProposalRevision":
        if self.supplemental_evidence_ids != tuple(sorted(set(self.supplemental_evidence_ids))):
            raise ValueError("proposal revision evidence references must be sorted and unique")
        if self.alternatives_considered != tuple(DecisionOutcome):
            raise ValueError("proposal revision must compare all five canonical alternatives")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"revision_digest"}))
        if self.revision_digest is not None and self.revision_digest != expected:
            raise ValueError("revision_digest does not match canonical content")
        object.__setattr__(self, "revision_digest", expected)
        return self


class DecisionRecord(FrozenModel):
    schema_version: Literal["portfolio-risk.decision-record/v1"] = "portfolio-risk.decision-record/v1"
    proposal: DecisionProposal
    lifecycle: tuple[DecisionLifecycleReceipt, ...] = Field(min_length=1)
    resolutions: tuple[DecisionResolution, ...] = ()
    consequences: tuple[DecisionConsequenceReceipt, ...] = ()
    context_revisions: tuple[DecisionContextRevision, ...] = ()
    follow_up_runs: tuple[DecisionFollowUpRun, ...] = ()
    supplemental_evidence: tuple[DecisionSupplementalEvidence, ...] = ()
    investigation_runs: tuple[DecisionInvestigationWorkflowRun, ...] = ()
    proposal_revisions: tuple[DecisionProposalRevision, ...] = ()
    record_revision: str | None = Field(default=None, pattern=DIGEST)

    @property
    def state(self) -> DecisionState:
        return self.lifecycle[-1].to_state

    @model_validator(mode="after")
    def validate_and_bind(self) -> "DecisionRecord":
        if tuple(item.sequence for item in self.lifecycle) != tuple(range(1, len(self.lifecycle) + 1)):
            raise ValueError("lifecycle receipt sequence must be contiguous")
        prior = None
        prior_state = None
        for item in self.lifecycle:
            if item.prior_receipt_digest != prior:
                raise ValueError("lifecycle receipt chain is invalid")
            if item.from_state != prior_state:
                raise ValueError("lifecycle state chain is invalid")
            prior = item.receipt_digest
            prior_state = item.to_state
        evidence_ids = tuple(item.evidence_id for item in self.supplemental_evidence)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("supplemental evidence identities must be unique")
        run_ids = tuple(item.run_id for item in self.investigation_runs)
        if len(run_ids) != len(set(run_ids)):
            raise ValueError("investigation run identities must be unique")
        expected_revision_numbers = tuple(range(2, len(self.proposal_revisions) + 2))
        if tuple(item.revision_number for item in self.proposal_revisions) != expected_revision_numbers:
            raise ValueError("proposal revision numbers must be contiguous and begin at two")
        for run in self.investigation_runs:
            if run.proposal_id != self.proposal.proposal_id or run.base_proposal_digest != self.proposal.proposal_digest:
                raise ValueError("investigation run is not bound to the immutable proposal")
            for step in run.steps:
                if not set(step.output_evidence_ids).issubset(evidence_ids):
                    raise ValueError("investigation step references unknown supplemental evidence")
        for revision in self.proposal_revisions:
            if revision.proposal_id != self.proposal.proposal_id or revision.base_proposal_digest != self.proposal.proposal_digest:
                raise ValueError("proposal revision is not bound to the immutable proposal")
            if revision.workflow_run_id not in run_ids:
                raise ValueError("proposal revision references an unknown investigation run")
            if not set(revision.supplemental_evidence_ids).issubset(evidence_ids):
                raise ValueError("proposal revision references unknown supplemental evidence")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"record_revision"}))
        if self.record_revision is not None and self.record_revision != expected:
            raise ValueError("record_revision does not match canonical content")
        object.__setattr__(self, "record_revision", expected)
        return self
