"""Registered local-only capabilities for contextual monitoring and replay."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import Field, field_validator, model_validator

from risk_analytics import MonitoringReportRequest, render_monitoring_report
from risk_data import EventDatasetSnapshot, EventQueryRequest, query_event_snapshot
from risk_domain.common import normalize_utc
from risk_domain.digests import sha256_digest
from risk_domain.monitoring import (
    ContextualMonitoringRequest,
    MonitoringCapabilityReceipt,
    MonitoringEvidence,
    MonitoringEventSignal,
    MonitoringMetric,
    MonitoringPolicyVersion,
    OutcomeLabel,
    PolicyEvaluationRequest,
    PolicyEvaluationResult,
    PortfolioDataContextRequest,
    ReplayRun,
    ReplaySpecification,
    ReplayStep,
    create_portfolio_data_context,
    evaluate_monitoring_policy,
    evaluate_replay,
    run_contextual_monitoring,
    synthesize_monitoring_alert,
)

from .contracts import CapabilityContract, EvidenceReference

if TYPE_CHECKING:
    from .registry import CapabilityRegistry, CapabilityResult


class PortfolioDataContextCapabilityRequest(CapabilityContract):
    request: PortfolioDataContextRequest
    evidence_references: tuple[EvidenceReference, ...] = Field(min_length=1)


class EventQueryCapabilityRequest(CapabilityContract):
    request: EventQueryRequest | None = None
    snapshot: EventDatasetSnapshot | None = None
    as_of: datetime | None = None
    evidence_references: tuple[EvidenceReference, ...] = Field(min_length=1)

    _as_of = field_validator("as_of")(
        lambda value: normalize_utc(value) if value is not None else None
    )

    @model_validator(mode="after")
    def query_and_snapshot_are_paired(self) -> "EventQueryCapabilityRequest":
        if (self.request is None) != (self.snapshot is None):
            raise ValueError("event query and snapshot must be supplied together")
        if self.request is None and self.as_of is None:
            raise ValueError("as_of is required when no event snapshot is selected")
        return self


class PolicyEvaluationCapabilityRequest(CapabilityContract):
    request: PolicyEvaluationRequest
    evidence_references: tuple[EvidenceReference, ...] = Field(min_length=1)


class ContextualMonitoringCapabilityRequest(CapabilityContract):
    request: ContextualMonitoringRequest
    evidence_references: tuple[EvidenceReference, ...] = Field(min_length=1)


class MonitoringAlertSynthesisCapabilityRequest(CapabilityContract):
    policy_evaluation: PolicyEvaluationResult
    run_at: datetime
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)
    evidence_references: tuple[EvidenceReference, ...] = Field(min_length=1)

    _run_at = field_validator("run_at")(normalize_utc)


class ContextualMonitoringWorkflowRequest(CapabilityContract):
    run_id: str = Field(min_length=1)
    context_request: PortfolioDataContextRequest
    policy_version: MonitoringPolicyVersion
    evaluation_id: str = Field(min_length=1)
    run_at: datetime
    metrics: tuple[MonitoringMetric, ...] = ()
    event_query_request: EventQueryRequest | None = None
    event_snapshot: EventDatasetSnapshot | None = None
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    evidence_references: tuple[EvidenceReference, ...] = Field(min_length=1)

    _run_at = field_validator("run_at")(normalize_utc)

    @model_validator(mode="after")
    def selected_event_revision_is_consistent(
        self,
    ) -> "ContextualMonitoringWorkflowRequest":
        if (self.event_query_request is None) != (self.event_snapshot is None):
            raise ValueError("event query and snapshot must be supplied together")
        if self.event_snapshot is not None:
            if (
                self.event_query_request is None
                or self.event_query_request.snapshot_id != self.event_snapshot.snapshot_id
                or self.context_request.event_snapshot_id
                != self.event_snapshot.snapshot_id
                or self.context_request.event_dataset_revision
                != self.event_snapshot.dataset_revision
            ):
                raise ValueError(
                    "workflow event inputs must match the context's selected snapshot and revision"
                )
        elif self.context_request.event_snapshot_id is not None:
            raise ValueError("the selected context event snapshot must be queried")
        return self


class MonitoringReportCapabilityRequest(CapabilityContract):
    request: MonitoringReportRequest
    evidence_references: tuple[EvidenceReference, ...] = Field(min_length=1)


class ReplayStepInput(CapabilityContract):
    context_request: PortfolioDataContextRequest
    evaluation_id: str = Field(min_length=1)
    metrics: tuple[MonitoringMetric, ...] = ()
    event_query_request: EventQueryRequest | None = None
    event_snapshot: EventDatasetSnapshot | None = None

    @model_validator(mode="after")
    def event_inputs_are_paired(self) -> "ReplayStepInput":
        if (self.event_query_request is None) != (self.event_snapshot is None):
            raise ValueError("replay event query and snapshot must be supplied together")
        return self


class ReplayCapabilityRequest(CapabilityContract):
    run_id: str = Field(min_length=1)
    specification: ReplaySpecification
    policy_version: MonitoringPolicyVersion
    step_inputs: tuple[ReplayStepInput, ...]
    evidence_references: tuple[EvidenceReference, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def inputs_match_deterministic_times_and_revisions(self) -> "ReplayCapabilityRequest":
        times = self.specification.replay_times()
        if tuple(item.context_request.as_of for item in self.step_inputs) != times:
            raise ValueError("replay inputs must exactly match deterministic replay times")
        if self.policy_version.revision != self.specification.policy_revision:
            raise ValueError("replay policy version must match the specification revision")
        for item in self.step_inputs:
            request = item.context_request
            if (
                request.portfolio_snapshot_id != self.specification.portfolio_snapshot_id
                or request.market_dataset_snapshot_id
                != self.specification.market_dataset_snapshot_id
                or request.market_dataset_revision
                != self.specification.market_dataset_revision
                or request.crosswalk_snapshot_id != self.specification.crosswalk_snapshot_id
                or request.crosswalk_dataset_revision
                != self.specification.crosswalk_dataset_revision
                or request.fundamental_dataset_snapshot_id
                != self.specification.fundamental_dataset_snapshot_id
                or request.fundamental_dataset_revision
                != self.specification.fundamental_dataset_revision
                or request.event_snapshot_id != self.specification.event_snapshot_id
                or request.event_dataset_revision
                != self.specification.event_dataset_revision
            ):
                raise ValueError("replay cannot fall back to a different current or future snapshot")
        return self


class ReplayEvaluationCapabilityRequest(CapabilityContract):
    evaluation_id: str = Field(min_length=1)
    replay_run: ReplayRun
    outcomes: tuple[OutcomeLabel, ...]
    evaluated_at: datetime
    evidence_references: tuple[EvidenceReference, ...] = Field(min_length=1)

    _evaluated_at = field_validator("evaluated_at")(normalize_utc)


def create_data_context(request: PortfolioDataContextCapabilityRequest):  # type: ignore[no-untyped-def]
    from .registry import CapabilityResult

    result = create_portfolio_data_context(request.request)
    return CapabilityResult(
        capability_id="portfolio.data_context.create",
        status="stopped" if result.blocked else "succeeded",
        data=result,
        evidence_references=request.evidence_references,
        assumptions=result.assumptions,
        warnings=result.warnings
        + tuple(
            item.message for item in result.quality_issues if item.severity == "blocking"
        ),
        limitations=result.limitations,
        output_digest=result.digest,
        human_review_required=True,
    )


def query_events_as_of(request: EventQueryCapabilityRequest):  # type: ignore[no-untyped-def]
    from .registry import CapabilityResult

    if request.request is None or request.snapshot is None:
        disclosure = {
            "as_of": request.as_of,
            "state": "no_event_snapshot_selected",
        }
        return CapabilityResult(
            capability_id="events.query.as_of",
            status="stopped",
            evidence_references=request.evidence_references,
            warnings=("No optional event snapshot was selected; no event was inferred.",),
            limitations=("Event intelligence is unavailable for this invocation.",),
            output_digest=sha256_digest(disclosure),
            human_review_required=True,
        )
    result = query_event_snapshot(request.request, request.snapshot)
    return CapabilityResult(
        capability_id="events.query.as_of",
        data=result,
        evidence_references=request.evidence_references,
        warnings=result.warnings,
        limitations=result.limitations,
        output_digest=result.digest,
        human_review_required=True,
    )


def evaluate_policy(request: PolicyEvaluationCapabilityRequest):  # type: ignore[no-untyped-def]
    from .registry import CapabilityResult

    result = evaluate_monitoring_policy(request.request)
    return CapabilityResult(
        capability_id="monitoring.policy.evaluate",
        status="stopped" if result.abstained else "succeeded",
        data=result,
        evidence_references=request.evidence_references,
        assumptions=result.assumptions,
        warnings=result.warnings,
        limitations=result.limitations,
        output_digest=result.digest,
        human_review_required=True,
    )


def synthesize_alert(
    request: MonitoringAlertSynthesisCapabilityRequest,
):  # type: ignore[no-untyped-def]
    from .registry import CapabilityResult

    alert = synthesize_monitoring_alert(
        policy_evaluation=request.policy_evaluation,
        run_at=request.run_at,
        evidence=request.evidence,
    )
    return CapabilityResult(
        capability_id="monitoring.alert.synthesize",
        status="stopped" if request.policy_evaluation.abstained else "succeeded",
        data=alert,
        evidence_references=request.evidence_references,
        warnings=request.policy_evaluation.warnings,
        limitations=(
            "The alert is an effect-free analytical draft requiring human review.",
        ),
        output_digest=alert.digest,
        human_review_required=True,
    )


def _receipt_from_result(
    request: CapabilityContract,
    result: "CapabilityResult[object]",
    evidence: tuple[MonitoringEvidence, ...],
) -> MonitoringCapabilityReceipt:
    if result.status == "failed":
        raise ValueError(
            f"{result.capability_id} failed and cannot support a successful audit receipt"
        )
    if result.output_digest is None:
        raise ValueError(
            f"{result.capability_id} must expose an output digest for an audit receipt"
        )
    return MonitoringCapabilityReceipt(
        capability_id=result.capability_id,
        status="stopped" if result.status == "stopped" else "succeeded",
        input_digest=sha256_digest(request),
        output_digest=result.output_digest,
        evidence=evidence,
    )


def event_signals_from_result(
    result: "CapabilityResult[object]",
    *,
    context,
) -> tuple[MonitoringEventSignal, ...]:  # type: ignore[no-untyped-def]
    if result.data is None:
        return ()
    instrument_by_entity = {
        item.entity_id: item.instrument_id
        for item in context.bindings
        if item.entity_id is not None
    }
    return tuple(
        MonitoringEventSignal(
            event_id=item.local_event_id,
            entity_id=item.entity_id,
            instrument_id=instrument_by_entity.get(item.entity_id),
            event_time=item.event_time,
            available_at=item.available_at,
            relevance=item.relevance,
            sentiment=item.sentiment,
            novelty=item.novelty,
            amendment_state=item.amendment_state,
            evidence=item.evidence,
        )
        for item in result.data.records
        if item.available_at is not None
    )


def build_contextual_monitoring_request(
    workflow: ContextualMonitoringWorkflowRequest,
    *,
    context_result: "CapabilityResult[object]",
    policy_result: "CapabilityResult[object]",
    event_result: "CapabilityResult[object]",
    alert_result: "CapabilityResult[object]",
) -> ContextualMonitoringRequest:
    """Bind one contextual run to four completed registered results."""

    if context_result.data is None or policy_result.data is None or alert_result.data is None:
        raise ValueError("context, policy, and alert capabilities must return auditable data")
    evidence = workflow.context_request.evidence
    receipts = tuple(
        _receipt_from_result(request, result, evidence)
        for request, result in (
            (
                PortfolioDataContextCapabilityRequest(
                    request=workflow.context_request,
                    evidence_references=workflow.evidence_references,
                ),
                context_result,
            ),
            (
                PolicyEvaluationCapabilityRequest(
                    request=PolicyEvaluationRequest(
                        evaluation_id=workflow.evaluation_id,
                        policy_version=workflow.policy_version,
                        context=context_result.data,
                        evaluated_at=workflow.run_at,
                        metrics=workflow.metrics,
                        events=event_signals_from_result(
                            event_result, context=context_result.data
                        ),
                        evidence=evidence,
                    ),
                    evidence_references=workflow.evidence_references,
                ),
                policy_result,
            ),
            (
                EventQueryCapabilityRequest(
                    request=workflow.event_query_request,
                    snapshot=workflow.event_snapshot,
                    as_of=workflow.context_request.as_of,
                    evidence_references=workflow.evidence_references,
                ),
                event_result,
            ),
            (
                MonitoringAlertSynthesisCapabilityRequest(
                    policy_evaluation=policy_result.data,
                    run_at=workflow.run_at,
                    evidence=evidence,
                    evidence_references=workflow.evidence_references,
                ),
                alert_result,
            ),
        )
    )
    events = event_signals_from_result(event_result, context=context_result.data)
    return ContextualMonitoringRequest(
        run_id=workflow.run_id,
        context=context_result.data,
        policy_evaluation=policy_result.data,
        run_at=workflow.run_at,
        metrics=workflow.metrics,
        events=events,
        capability_receipts=receipts,
        alert_draft=alert_result.data,
        evidence=evidence,
        assumptions=workflow.assumptions,
        limitations=workflow.limitations,
    )


def _invoke_contextual_monitoring_workflow(
    registry: "CapabilityRegistry",
    workflow: ContextualMonitoringWorkflowRequest,
) -> tuple["CapabilityResult[object]", ContextualMonitoringRequest]:
    """Invoke all four roles and the enclosing run through one registry."""

    context_request = PortfolioDataContextCapabilityRequest(
        request=workflow.context_request,
        evidence_references=workflow.evidence_references,
    )
    context_result = registry.invoke("portfolio.data_context.create", context_request)
    if context_result.data is None:
        raise ValueError("portfolio data-context capability returned no context")
    event_request = EventQueryCapabilityRequest(
        request=workflow.event_query_request,
        snapshot=workflow.event_snapshot,
        as_of=workflow.context_request.as_of,
        evidence_references=workflow.evidence_references,
    )
    event_result = registry.invoke("events.query.as_of", event_request)
    events = event_signals_from_result(event_result, context=context_result.data)
    policy_request = PolicyEvaluationCapabilityRequest(
        request=PolicyEvaluationRequest(
            evaluation_id=workflow.evaluation_id,
            policy_version=workflow.policy_version,
            context=context_result.data,
            evaluated_at=workflow.run_at,
            metrics=workflow.metrics,
            events=events,
            evidence=workflow.context_request.evidence,
        ),
        evidence_references=workflow.evidence_references,
    )
    policy_result = registry.invoke("monitoring.policy.evaluate", policy_request)
    if policy_result.data is None:
        raise ValueError("monitoring policy capability returned no evaluation")
    alert_request = MonitoringAlertSynthesisCapabilityRequest(
        policy_evaluation=policy_result.data,
        run_at=workflow.run_at,
        evidence=workflow.context_request.evidence,
        evidence_references=workflow.evidence_references,
    )
    alert_result = registry.invoke("monitoring.alert.synthesize", alert_request)
    contextual_request = build_contextual_monitoring_request(
        workflow,
        context_result=context_result,
        policy_result=policy_result,
        event_result=event_result,
        alert_result=alert_result,
    )
    result = registry.invoke(
        "monitoring.run.contextual",
        ContextualMonitoringCapabilityRequest(
            request=contextual_request,
            evidence_references=workflow.evidence_references,
        ),
    )
    return result, contextual_request


def invoke_contextual_monitoring_workflow(
    registry: "CapabilityRegistry",
    workflow: ContextualMonitoringWorkflowRequest,
):  # type: ignore[no-untyped-def]
    result, _request = _invoke_contextual_monitoring_workflow(registry, workflow)
    return result


def run_monitoring(request: ContextualMonitoringCapabilityRequest):  # type: ignore[no-untyped-def]
    from .registry import CapabilityResult

    result = run_contextual_monitoring(request.request)
    return CapabilityResult(
        capability_id="monitoring.run.contextual",
        status=result.status,
        data=result,
        evidence_references=request.evidence_references,
        warnings=result.warnings,
        limitations=result.limitations,
        output_digest=result.digest,
        human_review_required=True,
    )


def render_report(request: MonitoringReportCapabilityRequest):  # type: ignore[no-untyped-def]
    from .registry import CapabilityResult

    result = render_monitoring_report(request.request)
    return CapabilityResult(
        capability_id="monitoring.report.render",
        data=result,
        evidence_references=request.evidence_references,
        limitations=(
            "Report output is local Markdown and semantic HTML only; no PDF or publication occurred.",
        ),
        output_digest=result.digest,
        human_review_required=True,
    )


def run_replay(
    request: ReplayCapabilityRequest,
    registry: "CapabilityRegistry | None" = None,
):  # type: ignore[no-untyped-def]
    from .registry import CapabilityResult

    if registry is None:
        raise ValueError("monitoring replay requires the canonical capability registry")
    steps: list[ReplayStep] = []
    for sequence, step_input in enumerate(request.step_inputs, start=1):
        monitoring_result, contextual_request = _invoke_contextual_monitoring_workflow(
            registry,
            ContextualMonitoringWorkflowRequest(
                run_id=f"{request.run_id}:step:{sequence}",
                context_request=step_input.context_request,
                policy_version=request.policy_version,
                evaluation_id=step_input.evaluation_id,
                run_at=step_input.context_request.as_of,
                metrics=step_input.metrics,
                event_query_request=step_input.event_query_request,
                event_snapshot=step_input.event_snapshot,
                evidence_references=request.evidence_references,
                limitations=(
                    "Replay step uses only the specification's pinned local revisions.",
                ),
            ),
        )
        if monitoring_result.data is None:
            raise ValueError("registered contextual monitoring returned no replay step")
        context = contextual_request.context
        monitoring_run = monitoring_result.data
        abstained = monitoring_run.status == "stopped"
        steps.append(
            ReplayStep(
                sequence=sequence,
                as_of=step_input.context_request.as_of,
                data_context=context,
                monitoring_run=monitoring_run,
                abstained=abstained,
                warnings=monitoring_run.warnings,
                evidence=step_input.context_request.evidence,
            )
        )
    evidence = request.step_inputs[0].context_request.evidence if request.step_inputs else ()
    if not evidence:
        raise ValueError("replay requires retained monitoring evidence")
    replay = ReplayRun(
        run_id=request.run_id,
        specification=request.specification,
        steps=tuple(steps),
        warnings=tuple(
            sorted(
                {
                    warning
                    for step in steps
                    for warning in step.warnings
                }
            )
        ),
        limitations=(
            "Replay uses only supplied revisions and available_at <= step as_of.",
            "Replay makes no predictive claim and produces no portfolio effects.",
        ),
        evidence=evidence,
    )
    return CapabilityResult(
        capability_id="monitoring.replay",
        data=replay,
        evidence_references=request.evidence_references,
        warnings=replay.warnings,
        limitations=replay.limitations,
        output_digest=replay.digest,
        human_review_required=True,
    )


def evaluate_replay_capability(request: ReplayEvaluationCapabilityRequest):  # type: ignore[no-untyped-def]
    from .registry import CapabilityResult

    evaluation = evaluate_replay(
        evaluation_id=request.evaluation_id,
        replay_run=request.replay_run,
        outcomes=request.outcomes,
        evaluated_at=request.evaluated_at,
    )
    return CapabilityResult(
        capability_id="monitoring.evaluate",
        data=evaluation,
        evidence_references=request.evidence_references,
        warnings=tuple(f"{item.code}: {item.message}" for item in evaluation.warnings),
        limitations=evaluation.limitations,
        output_digest=evaluation.digest,
        human_review_required=True,
    )


MONITORING_REQUEST_TYPES = {
    "portfolio.data_context.create": PortfolioDataContextCapabilityRequest,
    "events.query.as_of": EventQueryCapabilityRequest,
    "monitoring.policy.evaluate": PolicyEvaluationCapabilityRequest,
    "monitoring.alert.synthesize": MonitoringAlertSynthesisCapabilityRequest,
    "monitoring.run.contextual": ContextualMonitoringCapabilityRequest,
    "monitoring.report.render": MonitoringReportCapabilityRequest,
    "monitoring.replay": ReplayCapabilityRequest,
    "monitoring.evaluate": ReplayEvaluationCapabilityRequest,
}

MONITORING_HANDLERS = {
    "portfolio.data_context.create": create_data_context,
    "events.query.as_of": query_events_as_of,
    "monitoring.policy.evaluate": evaluate_policy,
    "monitoring.alert.synthesize": synthesize_alert,
    "monitoring.run.contextual": run_monitoring,
    "monitoring.report.render": render_report,
    "monitoring.replay": run_replay,
    "monitoring.evaluate": evaluate_replay_capability,
}
