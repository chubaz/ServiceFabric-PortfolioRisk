"""Operational B1 and A1 treatments for the licensed-data replay.

The module reuses the frozen Day 3 treatment definitions.  Deterministic
capabilities assemble one point-in-time bundle first; B1 receives that bundle
once and A1 receives the four frozen role slices.  The legacy treatment output
is adapted into the canonical headless experimental wrapper and only then
mapped to ``ArchitectureOutput``.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from time import perf_counter
from typing import Any

from portfolio_risk_thesis.day3.contracts import (
    ArchitectureInputBundle,
    ArchitectureReviewOutput,
    EligibleAgentEvent,
    ModelConfiguration,
    PositionExposure,
    digest as thesis_digest,
)
from portfolio_risk_thesis.day3.prompts import prompt_manifest_digest
from portfolio_risk_thesis.day3.providers.openai_responses import OpenAIResponsesProvider
from portfolio_risk_thesis.day3.treatments import ROLES, a1, b1
from risk_agents import (
    AgentDecisionByproduct,
    AgentEvaluationByproducts,
    AgentExecutionEnvelope,
    AgentFindingByproduct,
    AgentRuntimeTelemetry,
    AgentStructuredOutput,
    wrap_agent_execution,
)
from risk_domain.digests import sha256_digest
from risk_experiments import (
    ArchitectureMappingContext,
    KernelEvidence,
    finalize_agent_graph_execution,
    finalize_single_agent_execution,
    wrap_agent_graph,
)
from agent_studio import _keychain_key


MODEL_ID = "gpt-5.6-luna"
SINGLE_AGENT_ID = "risk.agent.portfolio_risk_synthesizer"
GRAPH_AGENT_IDS = ROLES
ARCHITECTURE_IDS = {
    "B1": "b1-single-agent",
    "A1": "a1-four-agent-graph",
}


def _slug(value: str, fallback: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:63]
    if not result or not result[0].isalpha() or len(result) < 3:
        return fallback
    return result


def _configuration() -> ModelConfiguration:
    return ModelConfiguration(
        provider_id="openai_responses",
        model_id=MODEL_ID,
        model_snapshot=MODEL_ID,
        prompt_manifest_digest=prompt_manifest_digest(),
        temperature=None,
        temperature_supported=False,
        maximum_output_tokens=1600,
        timeout_seconds=90,
        retry_count=1,
        store=False,
        tools=(),
    )


def build_bundle(
    *,
    portfolio_id: str,
    row: dict[str, Any],
    holdings: tuple[dict[str, Any], ...],
    cycle_at: datetime,
) -> tuple[ArchitectureInputBundle, dict[str, str]]:
    """Build the exact model-safe point-in-time context for one cycle."""

    alias_to_name: dict[str, str] = {}
    exposures = []
    total_value = sum(max(float(item["market_value"]), 0.0) for item in holdings)
    for index, item in enumerate(holdings, start=1):
        alias = _slug(str(item["company_name"]), f"holding-{index:02d}")
        while alias in alias_to_name:
            alias = f"{alias[:58]}-{index:02d}"
        alias_to_name[alias] = str(item["company_name"])
        weight = 0 if total_value <= 0 else float(item["market_value"]) / total_value
        exposures.append(PositionExposure(
            position_alias=alias,
            weight=Decimal(str(round(weight, 10))),
            evidence_refs=(f"portfolio-exposure:{row['date']}",),
        ))

    evidence_refs = {
        f"point-in-time-context:{row['date']}",
        f"portfolio-exposure:{row['date']}",
        f"classified-event-context:{row['date']}",
        f"classified-fundamental-context:{row['date']}",
    }
    for warning in row["warnings"]:
        evidence_refs.update(warning["evidence_ids"])

    event_values_list: list[EligibleAgentEvent] = []
    name_to_alias = {name: alias for alias, name in alias_to_name.items()}
    for item in row["ravenpack_events"].get("event_stream", ()):
        event_time = datetime.fromisoformat(item["event_time"])
        event_available = datetime.fromisoformat(item["information_available_at"])
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        if event_available.tzinfo is None:
            event_available = event_available.replace(tzinfo=timezone.utc)
        event_time = event_time.astimezone(timezone.utc)
        event_available = min(event_available.astimezone(timezone.utc), cycle_at)
        affected_alias = name_to_alias.get(item["company_name"])
        if affected_alias is None:
            continue
        event_digest = thesis_digest((item["event_id"], item["event_time"], item["information_available_at"], item["maximum_relevance"], item["average_sentiment"]))
        evidence_refs.add(event_digest)
        sentiment_value = item.get("average_sentiment")
        event_values_list.append(EligibleAgentEvent(
            event_id=item["event_id"],
            event_time=event_time,
            available_at=event_available,
            entity_alias=affected_alias,
            instrument_aliases=(affected_alias,),
            title="Point-in-time classified portfolio event cluster",
            short_summary=(
                "The provider classifier identified a material negative event cluster."
                if sentiment_value is not None and sentiment_value < -0.2
                else "The provider classifier identified a material event cluster."
            ),
            sentiment="negative" if sentiment_value is not None and sentiment_value < -0.2 else "positive" if sentiment_value is not None and sentiment_value > 0.2 else "neutral",
            relevance=Decimal(str(item.get("maximum_relevance") or 0.8)),
            source_reference="dataset:ravenpack-derived-classification",
            evidence_digest=event_digest,
            profile="private_curated",
            publication_state="reviewed",
            limitations=("Derived event classification only; raw licensed news text is not sent to the model.",),
        ))
    event_values = tuple(sorted(event_values_list, key=lambda item: (item.available_at, item.event_id)))

    metrics = {
        key: Decimal(str(value))
        for key, value in {
            "daily_return": row.get("daily_return"),
            "annualised_volatility": row.get("annualised_volatility"),
            "drawdown": row.get("drawdown"),
            "cash_weight": row.get("cash_weight"),
            "largest_issuer_weight": row.get("largest_issuer_weight"),
            "largest_sector_weight": row.get("largest_sector_weight"),
        }.items()
        if value is not None
    }
    highest = max((3 if item["level"] == "urgent" else 2 for item in row["warnings"]), default=0)
    decision = "URGENT_REVIEW" if highest == 3 else "REVIEW" if highest else "NO_ISSUE"
    finding = (
        "Mandate-linked deterministic calculations identified material review conditions."
        if highest
        else "Mandate-linked deterministic calculations identified no review condition."
    )
    review = (
        "Interpret the supplied metrics, mandate results, classified events and fundamentals; "
        "state only evidence-backed portfolio-risk implications."
    )
    return ArchitectureInputBundle(
        portfolio_id=portfolio_id.replace("_", "-"),
        as_of=cycle_at,
        metrics=metrics,
        deterministic_finding=finding,
        review_item=review,
        decision_point=decision,
        exposures=tuple(exposures),
        events=event_values,
        evidence_refs=tuple(sorted(evidence_refs)),
        warnings=tuple(str(item["reason"]) for item in row["warnings"]),
        limitations=(
            "Daily CRSP closes bound market-response measurement to trading sessions.",
            "Raw licensed news text is excluded from model input; reviewed classifications are supplied.",
        ),
    ), alias_to_name


def _risk_type(claim: Any) -> str:
    metric = str(claim.metric_ref or "")
    if "volatility" in metric:
        return "volatility"
    if "drawdown" in metric or "return" in metric:
        return "loss"
    if "cash" in metric:
        return "liquidity"
    if "weight" in metric or "concentration" in metric:
        return "concentration"
    if claim.claim_type == "event":
        return "event"
    return "market"


def _structured_output(
    output: ArchitectureReviewOutput,
    *,
    workflow_id: str,
    run_id: str,
    cycle_id: str,
    cycle_at: datetime,
    produced_at: datetime,
    role_id: str,
    experimental_role: str,
    alias_to_name: dict[str, str],
    all_agent_ids: tuple[str, ...],
    classified_context_ids: tuple[str, ...],
    suffix: str,
) -> AgentStructuredOutput:
    claims = [item for item in output.supporting_claims if item.evidence_refs]
    findings = tuple(
        AgentFindingByproduct(
            finding_id=f"{cycle_id}-{suffix}-{index}",
            cluster_key=_slug(str(claim.metric_ref or claim.event_ref or claim.claim_id), f"claim-{index}"),
            claim=claim.statement if len(claim.statement) >= 12 else f"Observed finding: {claim.statement}",
            risk_type=_risk_type(claim),
            affected_asset=", ".join(alias_to_name.get(item, item) for item in claim.affected_positions) or "portfolio",
            direction="negative" if output.status in {"REVIEW", "URGENT_REVIEW"} else "unknown",
            materiality=min(1.0, output.severity / 3),
            severity=output.severity,
            confidence=0.8 if output.status not in {"ABSTAIN", "ABSTAINED_AGENT_OUTPUT"} else 0.2,
            confidence_method="Ordinal confidence assigned from deterministic critic admission; it is not a calibrated probability.",
            evidence_ids=tuple(sorted(set(claim.evidence_refs))),
            observed_at=cycle_at,
            metric_id=claim.metric_ref,
            observed_value=float(claim.reported_metric_value) if claim.reported_metric_value is not None else None,
        )
        for index, claim in enumerate(claims, start=1)
    )
    admitted = output.status not in {"ABSTAIN", "ABSTAINED_AGENT_OUTPUT"}
    state = "alert" if output.status == "URGENT_REVIEW" and findings else "watch" if output.status in {"REVIEW", "URGENT_REVIEW"} or not admitted else "clear"
    evidence = tuple(sorted(set(output.evidence_refs) | {item for claim in claims for item in claim.evidence_refs}))
    rationale = tuple(item.finding_id for item in findings)
    decision = None
    if experimental_role == "final_decision_agent":
        decision = AgentDecisionByproduct(
            decision_id=f"{cycle_id}-{workflow_id.lower()}-decision",
            monitoring_action="urgent_human_review" if state == "alert" else "increase_monitoring" if state == "watch" else "continue_monitoring",
            portfolio_action="review_exposure" if findings else "none",
            rationale_finding_ids=rationale,
            alternatives_considered=("continue_monitoring", "increase_monitoring", "urgent_human_review"),
            human_review_required=bool(findings),
        )
    return AgentStructuredOutput(
        output_id=f"agent-output-{run_id.lower()}-{cycle_id}-{suffix}",
        run_id=run_id,
        cycle_id=cycle_id,
        architecture_id=ARCHITECTURE_IDS[workflow_id],
        architecture_type="single_agent" if workflow_id == "B1" else "agent_graph",
        experimental_role=experimental_role,
        as_of=cycle_at,
        produced_at=produced_at,
        output_contract="portfolio-risk-thesis.ArchitectureReviewOutput/v1",
        primary_artifact=output.model_dump(mode="json"),
        evaluation_byproducts=AgentEvaluationByproducts(
            assessment_state=state,
            findings=findings,
            risk_interpretation=output.summary,
            expectations="The output supports monitoring and human review; it does not predict or execute a portfolio action.",
            confidence=0.8 if admitted else 0.2,
            confidence_kind="ordinal_judgement",
            confidence_method="Ordinal confidence reflects schema and deterministic critic admission, not outcome calibration.",
            decision=decision,
            supporting_evidence_ids=evidence,
            classified_context_ids=classified_context_ids,
            missing_information=tuple(output.uncertainties),
            assumptions=(),
            warnings=(),
            limitations=("Model interpretation is bounded to the supplied point-in-time context.",),
        ),
        agent_ids=all_agent_ids if experimental_role == "final_decision_agent" else (role_id,),
        capability_uses=(),
        effects=(),
    )


def execute_agent_cycle(
    *,
    workflow_id: str,
    run_id: str,
    case_id: str,
    portfolio_id: str,
    row: dict[str, Any],
    holdings: tuple[dict[str, Any], ...],
    cycle_at: datetime,
    trigger_available_at: datetime,
    previous_assessment_state: str | None,
    previous_severity: int | None,
) -> tuple[Any, dict[str, Any]]:
    """Execute B1 or A1 and return its canonically mapped ArchitectureOutput."""

    if workflow_id not in {"B1", "A1"}:
        raise ValueError("agent treatment must be B1 or A1")
    processing_started_at = datetime.now(timezone.utc)
    processing_started_clock = perf_counter()
    bundle, alias_to_name = build_bundle(
        portfolio_id=portfolio_id, row=row, holdings=holdings, cycle_at=cycle_at,
    )
    api_key = _keychain_key(include_value=True)
    if not isinstance(api_key, str) or not api_key:
        raise ValueError("OpenAI API key is unavailable; store it in the ServiceFabric keychain before running B1 or A1")
    provider = OpenAIResponsesProvider(_configuration(), api_key=api_key)
    context_completed_at = datetime.now(timezone.utc)
    context_processing_ms = (context_completed_at - processing_started_at).total_seconds() * 1000
    started_at = datetime.now(timezone.utc)
    treatment = b1(bundle, provider) if workflow_id == "B1" else a1(bundle, provider)
    completed_at = datetime.now(timezone.utc)
    if completed_at <= started_at:
        completed_at = started_at + timedelta(microseconds=1)
    classified_ids = (
        row["classified_context"]["context_id"],
        row["classified_context"]["fundamentals"]["context_id"],
    )
    event_evidence_times = {event.evidence_digest: event.available_at for event in bundle.events}
    evidence = tuple(
        KernelEvidence(evidence_id=item, available_at=event_evidence_times.get(item, cycle_at))
        for item in bundle.evidence_refs + tuple(event.evidence_digest for event in bundle.events)
    )
    architecture_type = "single_agent" if workflow_id == "B1" else "agent_graph"
    allowed_agents = (SINGLE_AGENT_ID,) if workflow_id == "B1" else GRAPH_AGENT_IDS
    context = ArchitectureMappingContext(
        run_id=run_id,
        cycle_id=f"cycle-{row['date']}",
        architecture_id=ARCHITECTURE_IDS[workflow_id],
        architecture_type=architecture_type,
        as_of=cycle_at,
        trigger_available_at=min(trigger_available_at, cycle_at),
        input_context_digest=sha256_digest(bundle.model_dump(mode="python")),
        case_id=case_id,
        repetition=1,
        eligible_evidence=evidence,
        allowed_capability_ids=(),
        allowed_agent_ids=allowed_agents,
        classified_context_ids=classified_ids,
        previous_assessment_state=previous_assessment_state,
        previous_severity=previous_severity,
    )

    total_tokens = sum(item.input_tokens + item.output_tokens for item in treatment.receipts)
    if workflow_id == "B1":
        structured = _structured_output(
            treatment.output, workflow_id=workflow_id, run_id=run_id,
            cycle_id=context.cycle_id, cycle_at=cycle_at, produced_at=completed_at,
            role_id=SINGLE_AGENT_ID, experimental_role="final_decision_agent",
            alias_to_name=alias_to_name, all_agent_ids=(SINGLE_AGENT_ID,),
            classified_context_ids=classified_ids, suffix="final",
        )
        telemetry = AgentRuntimeTelemetry(
            agent_id=SINGLE_AGENT_ID, agent_version="1.0.0",
            started_at=started_at, completed_at=completed_at,
            first_finding_at=completed_at if structured.evaluation_byproducts.findings else None,
            model_calls=1,
            input_tokens=sum(item.input_tokens for item in treatment.receipts),
            output_tokens=sum(item.output_tokens for item in treatment.receipts),
            route=(SINGLE_AGENT_ID,),
            semantic_verification_failures=0 if treatment.critic.passed else 1,
        )
        mapped = finalize_single_agent_execution(
            wrap_agent_execution(structured, telemetry), context, mapped_at=completed_at,
        )
    else:
        source_outputs = [item.output for item in treatment.specialist_outputs] + [treatment.output]
        wall_us = max(4, int((completed_at - started_at).total_seconds() * 1_000_000))
        executions: list[AgentExecutionEnvelope] = []
        for index, (role_id, source) in enumerate(zip(GRAPH_AGENT_IDS, source_outputs, strict=True)):
            item_start = started_at + timedelta(microseconds=wall_us * index // 4)
            item_end = started_at + timedelta(microseconds=wall_us * (index + 1) // 4)
            if item_end <= item_start:
                item_end = item_start + timedelta(microseconds=1)
            is_final = index == 3
            structured = _structured_output(
                source, workflow_id=workflow_id, run_id=run_id,
                cycle_id=context.cycle_id, cycle_at=cycle_at, produced_at=item_end,
                role_id=role_id,
                experimental_role="final_decision_agent" if is_final else "specialist_node",
                alias_to_name=alias_to_name, all_agent_ids=GRAPH_AGENT_IDS,
                classified_context_ids=classified_ids, suffix=f"node-{index + 1}",
            )
            receipt = treatment.receipts[index]
            executions.append(wrap_agent_execution(
                structured,
                AgentRuntimeTelemetry(
                    agent_id=role_id, agent_version="1.0.0",
                    started_at=item_start, completed_at=item_end,
                    first_finding_at=item_end if structured.evaluation_byproducts.findings else None,
                    model_calls=1, input_tokens=receipt.input_tokens,
                    output_tokens=receipt.output_tokens, route=GRAPH_AGENT_IDS[: index + 1],
                    semantic_verification_failures=0 if is_final and treatment.critic.passed else int(is_final),
                ),
            ))
        graph = wrap_agent_graph(
            tuple(executions), final_output_id=executions[-1].output.output_id,
            started_at=started_at, completed_at=executions[-1].telemetry.completed_at,
            edge_traversals=tuple(f"{left}->{right}" for left, right in zip(GRAPH_AGENT_IDS, GRAPH_AGENT_IDS[1:])),
            handoff_count=3,
            synthesis_ms=(executions[-1].telemetry.completed_at - executions[-1].telemetry.started_at).total_seconds() * 1000,
        )
        mapped = finalize_agent_graph_execution(graph, context, mapped_at=completed_at)
    finalized_at = datetime.now(timezone.utc)
    elapsed_ms = (perf_counter() - processing_started_clock) * 1000
    model_processing_ms = float(sum(item.elapsed_ms for item in treatment.receipts))
    validation_processing_ms = max(0.0, elapsed_ms - context_processing_ms - model_processing_ms)
    event_available_values = [item.available_at for item in bundle.events]
    earliest_event_available = min(event_available_values) if event_available_values else cycle_at
    execution_close = cycle_at.replace(hour=21, minute=0, second=0, microsecond=0)
    if execution_close < cycle_at:
        execution_close += timedelta(days=1)
        while execution_close.weekday() >= 5:
            execution_close += timedelta(days=1)
    return mapped, {
        "model_calls": len(treatment.receipts),
        "input_tokens": sum(item.input_tokens for item in treatment.receipts),
        "output_tokens": sum(item.output_tokens for item in treatment.receipts),
        "tokens": total_tokens,
        "elapsed_ms": round(elapsed_ms, 3),
        "processing_clock": {
            "replay_triggered_at": cycle_at.isoformat(),
            "replay_paused_at": cycle_at.isoformat(),
            "replay_resumed_at": cycle_at.isoformat(),
            "wall_started_at": processing_started_at.isoformat(),
            "wall_completed_at": finalized_at.isoformat(),
            "processing_wall_ms": round(elapsed_ms, 3),
            "context_and_capability_processing_ms": round(context_processing_ms, 3),
            "model_processing_ms": round(model_processing_ms, 3),
            "validation_and_mapping_ms": round(validation_processing_ms, 3),
            "clock_policy": "replay_time_frozen_from_trigger_through_architecture_output",
        },
        "event_timing": {
            "earliest_event_available_at": earliest_event_available.isoformat(),
            "analysis_triggered_at": cycle_at.isoformat(),
            "queued_before_analysis_ms": max(0.0, (cycle_at - earliest_event_available).total_seconds() * 1000),
            "material_event_clusters": len(bundle.events),
            "events_ordered_by": "available_at",
        },
        "execution_timing": {
            "price_policy": "first_eligible_end_of_day_close",
            "earliest_execution_at": execution_close.isoformat(),
            "market_response_unit": "trading_session",
            "intraday_alpha_decay_identifiable": False,
            "measurable_with_daily_prices": "post_execution_close_to_close_signal_persistence",
        },
        "critic_passed": treatment.critic.passed,
        "critic_violations": [item.model_dump(mode="json") for item in treatment.critic.violations],
        "provider": "openai_responses",
        "model": MODEL_ID,
    }
