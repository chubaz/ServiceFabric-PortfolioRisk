"""Structured agent outputs that can be evaluated without flattening their content.

The primary artifact remains the useful work product (for example a brief,
report, dashboard specification, or graph synthesis).  A compact set of
evaluation by-products exposes only the claims needed by an experiment.  The
experiment kernel maps those by-products to ArchitectureOutput; it does not
review or rewrite the primary artifact.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from risk_domain.common import normalize_utc
from risk_domain.digests import sha256_digest

from .contracts import AgentContract
from .timeline import CapabilityReceipt


IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$"
DIGEST = r"^sha256:[a-f0-9]{64}$"


class AgentFindingByproduct(AgentContract):
    """A material, evidence-backed finding exposed for evaluation."""

    finding_id: str = Field(pattern=IDENTIFIER)
    cluster_key: str = Field(pattern=IDENTIFIER)
    claim: str = Field(min_length=12, max_length=2000)
    risk_type: Literal["loss", "volatility", "liquidity", "concentration", "event", "market", "data"]
    affected_asset: str = Field(min_length=1, max_length=300)
    direction: Literal["negative", "positive", "mixed", "unknown"]
    materiality: float = Field(ge=0, le=1)
    severity: int = Field(ge=0, le=3)
    confidence: float = Field(ge=0, le=1)
    confidence_method: str = Field(min_length=3, max_length=300)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    observed_at: datetime
    metric_id: str | None = Field(default=None, pattern=IDENTIFIER)
    observed_value: float | None = None
    threshold_value: float | None = None

    _observed_at = field_validator("observed_at")(normalize_utc)

    @field_validator("evidence_ids")
    @classmethod
    def evidence_is_unique_and_sorted(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if values != tuple(sorted(set(values))):
            raise ValueError("finding evidence must be unique and sorted")
        return values


class AgentDecisionByproduct(AgentContract):
    """The decision proposed by the architecture, retained without rewriting."""

    decision_id: str = Field(pattern=IDENTIFIER)
    decision_scope: Literal["architecture_final", "node_advisory"] = "architecture_final"
    monitoring_action: Literal["no_action", "continue_monitoring", "increase_monitoring", "urgent_human_review"]
    portfolio_action: Literal["none", "review_exposure"]
    rationale_finding_ids: tuple[str, ...]
    alternatives_considered: tuple[str, ...] = Field(min_length=1)
    human_review_required: bool = True

    @field_validator("rationale_finding_ids", "alternatives_considered")
    @classmethod
    def values_are_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("decision values must be unique")
        return values


class AgentCapabilityUse(AgentContract):
    receipt: CapabilityReceipt
    started_at: datetime | None = None
    completed_at: datetime

    @field_validator("started_at")
    @classmethod
    def optional_started_at_is_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else normalize_utc(value)

    _completed_at = field_validator("completed_at")(normalize_utc)

    @model_validator(mode="after")
    def timing_is_ordered(self) -> "AgentCapabilityUse":
        if self.started_at is not None and self.completed_at < self.started_at:
            raise ValueError("capability completion cannot precede its start")
        return self


class AgentPresentationArtifact(AgentContract):
    """Human-facing material retained outside scientific evaluation."""

    artifact_id: str = Field(pattern=IDENTIFIER)
    label: str = Field(min_length=3, max_length=200)
    media_type: str = Field(min_length=3, max_length=120)
    reference: str = Field(min_length=1, max_length=1000)
    content_digest: str = Field(pattern=DIGEST)
    evaluation_status: Literal["excluded_user_facing"] = "excluded_user_facing"


class AgentEvaluationByproducts(AgentContract):
    """Compact, high-quality claims used by the nine evaluation dimensions."""

    assessment_state: Literal["clear", "watch", "alert"]
    findings: tuple[AgentFindingByproduct, ...]
    risk_interpretation: str = Field(min_length=12, max_length=5000)
    expectations: str = Field(min_length=3, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    confidence_kind: Literal["calibrated_probability", "model_score", "ordinal_judgement"]
    confidence_method: str = Field(min_length=12, max_length=500)
    decision: AgentDecisionByproduct | None = None
    supporting_evidence_ids: tuple[str, ...]
    conflicting_evidence_ids: tuple[str, ...] = ()
    classified_context_ids: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    data_quality_score: float | None = Field(default=None, ge=0, le=1)

    @field_validator(
        "supporting_evidence_ids", "conflicting_evidence_ids", "classified_context_ids",
        "missing_information", "assumptions", "warnings", "limitations",
    )
    @classmethod
    def tuple_values_are_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("evaluation by-product values must be unique")
        return values

    @model_validator(mode="after")
    def claims_are_semantically_complete(self) -> "AgentEvaluationByproducts":
        finding_ids = [item.finding_id for item in self.findings]
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("finding IDs must be unique")
        if self.decision is not None and not set(self.decision.rationale_finding_ids).issubset(finding_ids):
            raise ValueError("decision rationale must reference findings in the same output")
        if self.findings and self.assessment_state == "clear":
            raise ValueError("a clear assessment cannot contain findings")
        if not self.findings and self.assessment_state == "alert":
            raise ValueError("an alert assessment requires at least one finding")
        indexed = set(self.supporting_evidence_ids) | set(self.conflicting_evidence_ids)
        cited = {evidence for finding in self.findings for evidence in finding.evidence_ids}
        if not cited.issubset(indexed):
            raise ValueError("the evidence index must include every finding citation")
        return self


class AgentStructuredOutput(AgentContract):
    """One architecture result: useful artifact plus evaluation by-products."""

    schema_version: Literal["portfolio-risk.agent-structured-output/v1"] = "portfolio-risk.agent-structured-output/v1"
    output_id: str = Field(pattern=IDENTIFIER)
    output_digest: str | None = Field(default=None, pattern=DIGEST)
    run_id: str = Field(pattern=IDENTIFIER)
    cycle_id: str = Field(pattern=IDENTIFIER)
    architecture_id: str = Field(pattern=IDENTIFIER)
    architecture_type: Literal["single_agent", "agent_graph"]
    experimental_role: Literal["final_decision_agent", "specialist_node"] = "final_decision_agent"
    execution_mode: Literal["headless"] = "headless"
    as_of: datetime
    produced_at: datetime
    output_contract: str = Field(min_length=3, max_length=300)
    primary_artifact: dict[str, Any]
    primary_artifact_evaluation_status: Literal["evaluated_only_through_byproducts"] = "evaluated_only_through_byproducts"
    presentation_artifacts: tuple[AgentPresentationArtifact, ...] = ()
    evaluation_byproducts: AgentEvaluationByproducts
    agent_ids: tuple[str, ...] = Field(min_length=1)
    capability_uses: tuple[AgentCapabilityUse, ...]
    effects: tuple[str, ...] = ()

    _as_of = field_validator("as_of")(normalize_utc)
    _produced_at = field_validator("produced_at")(normalize_utc)

    @field_validator("agent_ids")
    @classmethod
    def agent_ids_are_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("agent IDs must be unique")
        return values

    @field_validator("effects")
    @classmethod
    def output_is_effect_free(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if values:
            raise ValueError("experimental agent outputs cannot contain effects")
        return values

    @model_validator(mode="after")
    def bind_identity_and_digest(self) -> "AgentStructuredOutput":
        if self.produced_at < self.as_of:
            raise ValueError("agent output cannot be produced before its as-of time")
        if not self.primary_artifact:
            raise ValueError("primary_artifact cannot be empty")
        if self.architecture_type == "single_agent" and len(self.agent_ids) != 1:
            raise ValueError("single-agent outputs require exactly one agent")
        if (
            self.architecture_type == "agent_graph"
            and self.experimental_role == "final_decision_agent"
            and len(self.agent_ids) < 2
        ):
            raise ValueError("final graph outputs require at least two participating agents")
        if self.experimental_role == "specialist_node" and len(self.agent_ids) != 1:
            raise ValueError("specialist node outputs identify exactly one producing agent")
        decision = self.evaluation_byproducts.decision
        if self.experimental_role == "final_decision_agent" and (
            decision is None or decision.decision_scope != "architecture_final"
        ):
            raise ValueError("final decision agents must declare the architecture-final decision")
        if (
            self.experimental_role == "specialist_node"
            and decision is not None
            and decision.decision_scope != "node_advisory"
        ):
            raise ValueError("specialist decisions must be explicitly marked node-advisory")
        for finding in self.evaluation_byproducts.findings:
            if finding.observed_at > self.as_of:
                raise ValueError("findings cannot use observations after the output as-of time")
        indexed = set(self.evaluation_byproducts.supporting_evidence_ids) | set(
            self.evaluation_byproducts.conflicting_evidence_ids
        )
        capability_evidence = {
            evidence.evidence_id
            for use in self.capability_uses
            for evidence in use.receipt.evidence
        }
        if not capability_evidence.issubset(indexed):
            raise ValueError("the evidence index must include every capability receipt citation")
        expected = sha256_digest(self.model_dump(mode="python", exclude={"output_digest"}))
        if self.output_digest is not None and self.output_digest != expected:
            raise ValueError("output_digest does not match canonical content")
        object.__setattr__(self, "output_digest", expected)
        return self


# Transitional import aliases. New code should use the by-product/output names.
AgentFindingArtifact = AgentFindingByproduct
AgentDecisionProposal = AgentDecisionByproduct
AgentWorkArtifact = AgentStructuredOutput
