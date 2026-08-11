"""Headless experimental wrappers and deterministic ArchitectureOutput mapping.

Wrappers observe execution and normalize evaluation data. They do not approve,
rewrite, or improve agent conclusions. Presentation artifacts remain explicitly
excluded from scientific evaluation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import combinations
from statistics import pstdev
from typing import Literal

from pydantic import Field, field_validator, model_validator

from risk_agents import AgentExecutionEnvelope, AgentStructuredOutput

from .hierarchy import (
    AgentContributionSummary,
    ArchitectureBehaviorSummary,
    ArchitectureDecision,
    ArchitectureExecutionSummary,
    ArchitectureFinding,
    ArchitectureOutput,
    CriticCorrectionSummary,
)
from .models import DIGEST, IDENTIFIER, FrozenModel, canonical_digest


MAPPER_VERSION = "headless-agent-wrapper-to-architecture-output-v2"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("kernel timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


class KernelEvidence(FrozenModel):
    evidence_id: str = Field(min_length=1, max_length=300)
    available_at: datetime
    content_digest: str | None = Field(default=None, pattern=DIGEST)

    _available_at = field_validator("available_at")(_utc)


class EpisodeBinding(FrozenModel):
    cluster_key: str = Field(pattern=IDENTIFIER)
    episode_id: str = Field(pattern=IDENTIFIER)


class ArchitectureMappingContext(FrozenModel):
    """Observable experiment facts available to the architecture."""

    run_id: str = Field(pattern=IDENTIFIER)
    cycle_id: str = Field(pattern=IDENTIFIER)
    architecture_id: str = Field(pattern=IDENTIFIER)
    architecture_type: Literal["single_agent", "agent_graph"]
    as_of: datetime
    trigger_available_at: datetime
    input_context_digest: str = Field(pattern=DIGEST)
    case_id: str = Field(pattern=IDENTIFIER)
    repetition: int = Field(ge=1, le=100)
    perturbation_id: str | None = Field(default=None, pattern=IDENTIFIER)
    eligible_evidence: tuple[KernelEvidence, ...]
    allowed_capability_ids: tuple[str, ...]
    allowed_agent_ids: tuple[str, ...]
    classified_context_ids: tuple[str, ...] = ()
    active_episode_bindings: tuple[EpisodeBinding, ...] = ()
    previous_assessment_state: Literal["clear", "watch", "alert"] | None = None
    previous_severity: int | None = Field(default=None, ge=0, le=3)

    _as_of = field_validator("as_of")(_utc)

    @field_validator("trigger_available_at")
    @classmethod
    def trigger_is_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value)

    @field_validator("allowed_capability_ids", "allowed_agent_ids", "classified_context_ids")
    @classmethod
    def unique_values(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("mapping context values must be unique")
        return values

    @model_validator(mode="after")
    def catalogues_are_unambiguous(self) -> "ArchitectureMappingContext":
        if len({item.evidence_id for item in self.eligible_evidence}) != len(self.eligible_evidence):
            raise ValueError("eligible evidence IDs must be unique")
        if len({item.cluster_key for item in self.active_episode_bindings}) != len(self.active_episode_bindings):
            raise ValueError("active episode cluster keys must be unique")
        if len({item.episode_id for item in self.active_episode_bindings}) != len(self.active_episode_bindings):
            raise ValueError("active episode IDs must be unique")
        if self.trigger_available_at > self.as_of:
            raise ValueError("trigger must be available no later than the cycle as-of time")
        return self


class ArchitectureMappingError(ValueError):
    """The execution cannot truthfully be mapped into this experiment cycle."""

    def __init__(self, violations: list[tuple[str, str]]) -> None:
        self.violations = tuple(violations)
        super().__init__("; ".join(f"{code}: {message}" for code, message in violations))


class GraphExecutionEnvelope(FrozenModel):
    """Observed executions for one graph and its final architecture result."""

    schema_version: Literal["portfolio-risk.graph-execution-envelope/v1"] = "portfolio-risk.graph-execution-envelope/v1"
    graph_execution_id: str = Field(pattern=IDENTIFIER)
    executions: tuple[AgentExecutionEnvelope, ...] = Field(min_length=2)
    final_output_id: str = Field(pattern=IDENTIFIER)
    started_at: datetime
    completed_at: datetime
    edge_traversals: tuple[str, ...] = ()
    handoff_count: int = Field(default=0, ge=0)
    synthesis_ms: float = Field(default=0, ge=0)
    critic_corrections: tuple[CriticCorrectionSummary, ...] = ()

    _started = field_validator("started_at")(_utc)
    _completed = field_validator("completed_at")(_utc)

    @model_validator(mode="after")
    def graph_is_coherent(self) -> "GraphExecutionEnvelope":
        if self.completed_at < self.started_at:
            raise ValueError("graph completion cannot precede its start")
        outputs = [item.output for item in self.executions]
        if len({item.envelope_id for item in self.executions}) != len(self.executions):
            raise ValueError("graph wrapper execution-envelope IDs must be unique")
        if len({item.output_id for item in outputs}) != len(outputs):
            raise ValueError("graph wrapper output IDs must be unique")
        if len({item.telemetry.agent_id for item in self.executions}) != len(self.executions):
            raise ValueError("graph wrapper requires one execution per unique agent")
        if sum(item.experimental_role == "final_decision_agent" for item in outputs) != 1:
            raise ValueError("graph wrapper requires exactly one final decision contribution")
        final = [item for item in outputs if item.output_id == self.final_output_id]
        if len(final) != 1 or final[0].experimental_role != "final_decision_agent":
            raise ValueError("graph wrapper requires exactly one final decision output")
        identities = {(item.run_id, item.cycle_id, item.architecture_id, item.as_of) for item in outputs}
        if len(identities) != 1 or any(item.architecture_type != "agent_graph" for item in outputs):
            raise ValueError("all wrapped graph outputs must belong to the same graph cycle")
        participants = {item.telemetry.agent_id for item in self.executions}
        if set(final[0].agent_ids) != participants:
            raise ValueError("final graph output must identify every wrapped participant")
        if any(
            item.telemetry.started_at < self.started_at
            or item.telemetry.completed_at > self.completed_at
            for item in self.executions
        ):
            raise ValueError("every agent execution must fall inside graph execution time")
        wall_clock_ms = (self.completed_at - self.started_at).total_seconds() * 1000
        if self.synthesis_ms > wall_clock_ms + 1e-6:
            raise ValueError("graph synthesis time cannot exceed graph wall-clock duration")
        return self

    @property
    def final_execution(self) -> AgentExecutionEnvelope:
        return next(item for item in self.executions if item.output.output_id == self.final_output_id)


def wrap_agent_graph(
    executions: tuple[AgentExecutionEnvelope, ...],
    *,
    final_output_id: str,
    started_at: datetime,
    completed_at: datetime,
    edge_traversals: tuple[str, ...] = (),
    handoff_count: int = 0,
    synthesis_ms: float = 0,
    critic_corrections: tuple[CriticCorrectionSummary, ...] = (),
) -> GraphExecutionEnvelope:
    identity = canonical_digest(tuple(item.envelope_digest for item in executions))[7:23]
    return GraphExecutionEnvelope(
        graph_execution_id=f"graph-execution-{identity}",
        executions=executions,
        final_output_id=final_output_id,
        started_at=started_at,
        completed_at=completed_at,
        edge_traversals=edge_traversals,
        handoff_count=handoff_count,
        synthesis_ms=synthesis_ms,
        critic_corrections=critic_corrections,
    )


def compare_critic_revision(
    before: AgentStructuredOutput,
    after: AgentStructuredOutput,
    *,
    critic_agent_id: str,
    accepted: bool,
) -> CriticCorrectionSummary:
    """Measure a critic revision from structured diffs, never model self-report."""

    if (before.run_id, before.cycle_id, before.architecture_id) != (
        after.run_id, after.cycle_id, after.architecture_id
    ):
        raise ValueError("critic comparison outputs must belong to one architecture cycle")
    before_findings = {item.finding_id: item for item in before.evaluation_byproducts.findings}
    after_findings = {item.finding_id: item for item in after.evaluation_byproducts.findings}
    before_ids, after_ids = set(before_findings), set(after_findings)
    before_severity = max((item.severity for item in before_findings.values()), default=0)
    after_severity = max((item.severity for item in after_findings.values()), default=0)
    return CriticCorrectionSummary(
        critic_agent_id=critic_agent_id,
        target_output_id=before.output_id,
        revised_output_id=after.output_id,
        findings_added=tuple(sorted(after_ids - before_ids)),
        findings_removed=tuple(sorted(before_ids - after_ids)),
        findings_retained=tuple(sorted(before_ids & after_ids)),
        severity_delta=after_severity - before_severity,
        confidence_delta=round(
            after.evaluation_byproducts.confidence - before.evaluation_byproducts.confidence, 6
        ),
        evidence_coverage_delta=0.0,
        accepted=accepted,
    )


def _change_state(context: ArchitectureMappingContext, state: str, severity: int) -> str:
    if context.previous_assessment_state is None or context.previous_severity is None:
        return "initial"
    if state == context.previous_assessment_state and severity == context.previous_severity:
        return "unchanged"
    if severity > context.previous_severity:
        return "deteriorated"
    if severity < context.previous_severity:
        return "improved"
    return "mixed"


def _verify_mapping_boundary(
    output: AgentStructuredOutput,
    context: ArchitectureMappingContext,
    mapped_at: datetime,
) -> None:
    violations: list[tuple[str, str]] = []
    for field in ("run_id", "cycle_id", "architecture_id", "architecture_type", "as_of"):
        if getattr(output, field) != getattr(context, field):
            violations.append(("context-mismatch", f"output {field} does not match the experiment cycle"))
    if output.experimental_role != "final_decision_agent":
        violations.append(("not-final-output", "specialist node output cannot become ArchitectureOutput"))
    if output.produced_at > mapped_at:
        violations.append(("future-production-time", "output was produced after its mapping time"))

    evidence_by_id = {item.evidence_id: item for item in context.eligible_evidence}
    byproducts = output.evaluation_byproducts
    referenced = set(byproducts.supporting_evidence_ids) | set(byproducts.conflicting_evidence_ids)
    for evidence_id in sorted(referenced):
        evidence = evidence_by_id.get(evidence_id)
        if evidence is None:
            violations.append(("evidence-not-eligible", f"{evidence_id} is outside the cycle evidence catalogue"))
        elif evidence.available_at > context.as_of:
            violations.append(("look-ahead-evidence", f"{evidence_id} was unavailable at the cycle as-of time"))
    for use in output.capability_uses:
        if use.completed_at > output.produced_at:
            violations.append(("late-capability-result", f"{use.receipt.capability_id} completed after output production"))
        if use.receipt.status != "succeeded":
            violations.append(("unsuccessful-capability", f"{use.receipt.capability_id} did not succeed"))
        if use.receipt.capability_id not in context.allowed_capability_ids:
            violations.append(("capability-not-available", f"{use.receipt.capability_id} was unavailable to the architecture"))
    if not set(output.agent_ids).issubset(context.allowed_agent_ids):
        violations.append(("agent-not-available", "output names an agent outside the experiment architecture"))
    if not set(byproducts.classified_context_ids).issubset(context.classified_context_ids):
        violations.append(("context-not-eligible", "output references classified context outside the cycle"))
    if violations:
        raise ArchitectureMappingError(violations)


def _contribution(execution: AgentExecutionEnvelope) -> AgentContributionSummary:
    output, telemetry = execution.output, execution.telemetry
    byproducts = output.evaluation_byproducts
    decision = byproducts.decision
    return AgentContributionSummary(
        agent_id=telemetry.agent_id,
        agent_version=telemetry.agent_version,
        experimental_role=output.experimental_role,
        output_id=output.output_id,
        output_digest=output.output_digest,
        started_at=telemetry.started_at,
        completed_at=telemetry.completed_at,
        first_finding_at=telemetry.first_finding_at,
        elapsed_ms=(telemetry.completed_at - telemetry.started_at).total_seconds() * 1000,
        finding_ids=tuple(item.finding_id for item in byproducts.findings),
        confidence=byproducts.confidence,
        proposed_monitoring_action=None if decision is None else decision.monitoring_action,
        capability_ids=tuple(dict.fromkeys(item.receipt.capability_id for item in output.capability_uses)),
        model_calls=telemetry.model_calls,
        input_tokens=telemetry.input_tokens,
        cached_input_tokens=telemetry.cached_input_tokens,
        output_tokens=telemetry.output_tokens,
        cost_usd=telemetry.cost_usd,
        retries=telemetry.retries,
        timeouts=telemetry.timeouts,
        schema_validation_failures=telemetry.schema_validation_failures,
        semantic_verification_failures=telemetry.semantic_verification_failures,
        errors=telemetry.errors,
    )


def _execution_summary(
    executions: tuple[AgentExecutionEnvelope, ...],
    *,
    started_at: datetime,
    completed_at: datetime,
    critical_path_ms: float,
) -> ArchitectureExecutionSummary:
    telemetry = [item.telemetry for item in executions]
    first_findings = [item.first_finding_at for item in telemetry if item.first_finding_at is not None]
    return ArchitectureExecutionSummary(
        started_at=started_at,
        completed_at=completed_at,
        first_finding_at=min(first_findings) if first_findings else None,
        wall_clock_ms=(completed_at - started_at).total_seconds() * 1000,
        critical_path_ms=critical_path_ms,
        model_calls=sum(item.model_calls for item in telemetry),
        input_tokens=sum(item.input_tokens for item in telemetry),
        cached_input_tokens=sum(item.cached_input_tokens for item in telemetry),
        output_tokens=sum(item.output_tokens for item in telemetry),
        cost_usd=round(sum(item.cost_usd for item in telemetry), 8),
        capability_calls=sum(item.capability_calls for item in telemetry),
        retries=sum(item.retries for item in telemetry),
        timeouts=sum(item.timeouts for item in telemetry),
        schema_validation_failures=sum(item.schema_validation_failures for item in telemetry),
        semantic_verification_failures=sum(item.semantic_verification_failures for item in telemetry),
        errors=tuple(dict.fromkeys(error for item in telemetry for error in item.errors)),
    )


def _pairwise_finding_disagreement(executions: tuple[AgentExecutionEnvelope, ...]) -> float:
    specialists = [
        {finding.cluster_key for finding in item.output.evaluation_byproducts.findings}
        for item in executions
        if item.output.experimental_role == "specialist_node"
    ]
    if len(specialists) < 2:
        return 0.0
    scores = []
    for left, right in combinations(specialists, 2):
        union = left | right
        scores.append(0.0 if not union else 1 - len(left & right) / len(union))
    return round(sum(scores) / len(scores), 6)


def _behavior_summary(
    executions: tuple[AgentExecutionEnvelope, ...],
    *,
    architecture_type: Literal["single_agent", "agent_graph"],
    edge_traversals: tuple[str, ...] = (),
    handoff_count: int = 0,
    synthesis_ms: float = 0,
    coordination_overhead_ms: float = 0,
    critic_corrections: tuple[CriticCorrectionSummary, ...] = (),
) -> ArchitectureBehaviorSummary:
    contributions = tuple(_contribution(item) for item in executions)
    specialists = [item.output.evaluation_byproducts for item in executions if item.output.experimental_role == "specialist_node"]
    severities = [max((finding.severity for finding in item.findings), default=0) for item in specialists]
    confidences = [item.confidence for item in specialists]
    decisions = [
        (item.decision.monitoring_action, item.decision.portfolio_action)
        for item in specialists if item.decision is not None
    ]
    decision_disagreement = 0.0
    if len(decisions) > 1:
        decision_disagreement = (len(set(decisions)) - 1) / (len(decisions) - 1)
    return ArchitectureBehaviorSummary(
        architecture_type=architecture_type,
        contributions=contributions,
        edge_traversals=edge_traversals,
        handoff_count=handoff_count,
        synthesis_ms=synthesis_ms,
        coordination_overhead_ms=coordination_overhead_ms,
        finding_disagreement=_pairwise_finding_disagreement(executions),
        severity_dispersion=round(pstdev(severities), 6) if len(severities) > 1 else 0.0,
        confidence_dispersion=round(pstdev(confidences), 6) if len(confidences) > 1 else 0.0,
        decision_disagreement=round(decision_disagreement, 6),
        critic_corrections=critic_corrections,
    )


def _map_final_output(
    output: AgentStructuredOutput,
    context: ArchitectureMappingContext,
    *,
    mapped_at: datetime,
    execution_summary: ArchitectureExecutionSummary | None,
    behavior_summary: ArchitectureBehaviorSummary | None,
) -> ArchitectureOutput:
    _verify_mapping_boundary(output, context, mapped_at)
    byproducts = output.evaluation_byproducts
    decision = byproducts.decision
    assert decision is not None
    episode_by_cluster = {item.cluster_key: item.episode_id for item in context.active_episode_bindings}
    findings = tuple(
        ArchitectureFinding(
            finding_id=item.finding_id,
            claim=item.claim,
            episode_id=episode_by_cluster.get(
                item.cluster_key,
                f"episode-{canonical_digest((context.run_id, context.cycle_id, item.cluster_key))[7:23]}",
            ),
            risk_type=item.risk_type,
            affected_asset=item.affected_asset,
            direction=item.direction,
            materiality=item.materiality,
            severity=item.severity,
            confidence=item.confidence,
            confidence_method=item.confidence_method,
            evidence_ids=item.evidence_ids,
            metric_id=item.metric_id,
            observed_value=item.observed_value,
            threshold_value=item.threshold_value,
            observed_at=item.observed_at,
        )
        for item in byproducts.findings
    )
    severity = max((item.severity for item in findings), default=0)
    output_id = f"architecture-output-{output.output_digest[7:23]}"
    branch_id = f"branch-{decision.decision_id}-selected"
    return ArchitectureOutput(
        output_id=output_id,
        run_id=context.run_id,
        architecture_type=context.architecture_type,
        cycle_id=context.cycle_id,
        as_of=context.as_of,
        trigger_available_at=context.trigger_available_at,
        assessment_state=byproducts.assessment_state,
        severity=severity,
        confidence=byproducts.confidence,
        confidence_kind=byproducts.confidence_kind,
        confidence_method=byproducts.confidence_method,
        findings=findings,
        supporting_evidence_ids=byproducts.supporting_evidence_ids,
        conflicting_evidence_ids=byproducts.conflicting_evidence_ids,
        risk_interpretation=byproducts.risk_interpretation,
        expectations=byproducts.expectations,
        decision=ArchitectureDecision(
            decision_id=decision.decision_id,
            monitoring_action=decision.monitoring_action,
            portfolio_action=decision.portfolio_action,
            alternatives_considered=decision.alternatives_considered,
            human_review_required=decision.human_review_required,
            rationale_finding_ids=decision.rationale_finding_ids,
            branch_id=branch_id,
            counterfactual_branch_ids=(f"branch-{decision.decision_id}-counterfactual",),
        ),
        missing_information=byproducts.missing_information,
        assumptions=byproducts.assumptions,
        warnings=byproducts.warnings,
        limitations=byproducts.limitations,
        data_quality_score=byproducts.data_quality_score,
        produced_at=output.produced_at,
        input_context_digest=context.input_context_digest,
        case_id=context.case_id,
        repetition=context.repetition,
        perturbation_id=context.perturbation_id,
        execution_summary=execution_summary,
        architecture_behavior=behavior_summary,
        architecture_id=context.architecture_id,
        capabilities_used=tuple(dict.fromkeys(use.receipt.capability_id for use in output.capability_uses)),
        agents_used=output.agent_ids,
        change_since_previous=_change_state(context, byproducts.assessment_state, severity),
        classified_context_ids=byproducts.classified_context_ids,
        source_output_id=output.output_id,
        source_output_digest=output.output_digest,
        mapper_version=MAPPER_VERSION,
    )


def finalize_single_agent_execution(
    execution: AgentExecutionEnvelope,
    context: ArchitectureMappingContext,
    *,
    mapped_at: datetime | None = None,
) -> ArchitectureOutput:
    output, telemetry = execution.output, execution.telemetry
    if output.architecture_type != "single_agent" or context.architecture_type != "single_agent":
        raise ArchitectureMappingError([("architecture-type", "single-agent wrapper requires single_agent output and context")])
    elapsed = (telemetry.completed_at - telemetry.started_at).total_seconds() * 1000
    summary = _execution_summary(
        (execution,), started_at=telemetry.started_at, completed_at=telemetry.completed_at,
        critical_path_ms=elapsed,
    )
    behavior = _behavior_summary((execution,), architecture_type="single_agent")
    return _map_final_output(
        output, context, mapped_at=_utc(mapped_at or datetime.now(timezone.utc)),
        execution_summary=summary, behavior_summary=behavior,
    )


def finalize_agent_graph_execution(
    graph: GraphExecutionEnvelope,
    context: ArchitectureMappingContext,
    *,
    mapped_at: datetime | None = None,
) -> ArchitectureOutput:
    if context.architecture_type != "agent_graph":
        raise ArchitectureMappingError([("architecture-type", "graph wrapper requires an agent_graph context")])
    longest_agent_ms = max(
        (item.telemetry.completed_at - item.telemetry.started_at).total_seconds() * 1000
        for item in graph.executions
    )
    critical_path_ms = min(
        (graph.completed_at - graph.started_at).total_seconds() * 1000,
        longest_agent_ms + graph.synthesis_ms,
    )
    wall_ms = (graph.completed_at - graph.started_at).total_seconds() * 1000
    coordination_ms = max(0.0, wall_ms - critical_path_ms)
    summary = _execution_summary(
        graph.executions, started_at=graph.started_at, completed_at=graph.completed_at,
        critical_path_ms=critical_path_ms,
    )
    behavior = _behavior_summary(
        graph.executions,
        architecture_type="agent_graph",
        edge_traversals=graph.edge_traversals,
        handoff_count=graph.handoff_count,
        synthesis_ms=graph.synthesis_ms,
        coordination_overhead_ms=coordination_ms,
        critic_corrections=graph.critic_corrections,
    )
    return _map_final_output(
        graph.final_execution.output, context,
        mapped_at=_utc(mapped_at or datetime.now(timezone.utc)),
        execution_summary=summary, behavior_summary=behavior,
    )


def map_agent_output(
    output: AgentStructuredOutput,
    context: ArchitectureMappingContext,
    *,
    mapped_at: datetime | None = None,
) -> ArchitectureOutput:
    """Compatibility mapper. Experiment runners must use wrapped finalizers."""

    return _map_final_output(
        output, context, mapped_at=_utc(mapped_at or datetime.now(timezone.utc)),
        execution_summary=None, behavior_summary=None,
    )


def finalize_single_agent_output(output: AgentStructuredOutput, context: ArchitectureMappingContext, *, mapped_at: datetime | None = None) -> ArchitectureOutput:
    """Deprecated compatibility entry point; lacks behavioral observations."""
    return map_agent_output(output, context, mapped_at=mapped_at)


def finalize_agent_graph_output(output: AgentStructuredOutput, context: ArchitectureMappingContext, *, mapped_at: datetime | None = None) -> ArchitectureOutput:
    """Deprecated compatibility entry point; lacks graph aggregation."""
    return map_agent_output(output, context, mapped_at=mapped_at)


ArchitectureProjectionContext = ArchitectureMappingContext
