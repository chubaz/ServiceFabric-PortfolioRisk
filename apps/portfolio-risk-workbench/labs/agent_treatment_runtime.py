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
    AgentCapabilityUse,
    AgentDecisionByproduct,
    AgentEvaluationByproducts,
    AgentExecutionEnvelope,
    AgentFindingByproduct,
    AgentRuntimeTelemetry,
    AgentStructuredOutput,
    CapabilityReceipt,
    wrap_agent_execution,
)
from risk_capabilities import EvidenceReference
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
LUNA_INPUT_USD_PER_MILLION = 0.20
LUNA_OUTPUT_USD_PER_MILLION = 1.20
LUNA_PRICING_REFERENCE = "openai-model-compare:gpt-5.6-luna:2026-08-11"
SINGLE_AGENT_ID = "risk.agent.portfolio_risk_synthesizer"
GRAPH_AGENT_IDS = ROLES
ARCHITECTURE_IDS = {
    "B1": "b1-single-agent",
    "A1": "a1-four-agent-graph",
}
CONTEXT_CAPABILITY_ID = "capability:risk:historical-replay-context@1.0.0"


def _slug(value: str, fallback: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:63]
    if not result or not result[0].isalpha() or len(result) < 3:
        return fallback
    return result


def _canonical_metric_id(value: Any, fallback: str) -> str:
    """Map model references onto the shared identifier-safe metric vocabulary."""

    normalized = str(value or "").casefold().replace("_", "-")
    for metric_id in (
        "daily-return",
        "annualised-volatility",
        "drawdown",
        "cash-weight",
        "largest-issuer-weight",
        "largest-sector-weight",
    ):
        if metric_id in normalized:
            return metric_id
    return _slug(normalized, fallback)


def _configuration() -> ModelConfiguration:
    return ModelConfiguration(
        provider_id="openai_responses",
        model_id=MODEL_ID,
        model_snapshot=MODEL_ID,
        prompt_manifest_digest=prompt_manifest_digest(),
        temperature=None,
        temperature_supported=False,
        maximum_output_tokens=2400,
        timeout_seconds=90,
        retry_count=1,
        store=False,
        tools=(),
    )


def _receipt_cost(input_tokens: int, output_tokens: int) -> float:
    return round(
        input_tokens * LUNA_INPUT_USD_PER_MILLION / 1_000_000
        + output_tokens * LUNA_OUTPUT_USD_PER_MILLION / 1_000_000,
        8,
    )


def _receipt_errors(receipt: Any) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in receipt.warnings))


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
    positive_values = [max(float(item["market_value"]), 0.0) for item in holdings]
    total_value = sum(positive_values)
    weights = [Decimal("0") for _item in holdings]
    if total_value > 0 and holdings:
        weights = [
            (Decimal(str(value)) / Decimal(str(total_value))).quantize(Decimal("0.0000000001"))
            for value in positive_values
        ]
        weights[-1] = Decimal("1") - sum(weights[:-1], Decimal("0"))
    for index, item in enumerate(holdings, start=1):
        alias = _slug(str(item["company_name"]), f"holding-{index:02d}")
        while alias in alias_to_name:
            alias = f"{alias[:58]}-{index:02d}"
        alias_to_name[alias] = str(item["company_name"])
        exposures.append(PositionExposure(
            position_alias=alias,
            weight=weights[index - 1],
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
        source_reference = item.get("evidence_id") or "dataset:ravenpack-derived-classification"
        evidence_refs.add(event_digest)
        evidence_refs.add(source_reference)
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
            source_reference=source_reference,
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


def _warning_risk_type(warning: dict[str, Any]) -> str:
    metric = str(warning.get("metric") or "")
    if "volatility" in metric:
        return "volatility"
    if "drawdown" in metric or "return" in metric:
        return "loss"
    if "cash" in metric:
        return "liquidity"
    if "weight" in metric or "concentration" in metric:
        return "concentration"
    return "market"


def _context_capability_use(
    bundle: ArchitectureInputBundle,
    row: dict[str, Any],
    *,
    started_at: datetime,
    completed_at: datetime,
) -> AgentCapabilityUse:
    evidence_id = f"point-in-time-context:{row['date']}"
    return AgentCapabilityUse(
        receipt=CapabilityReceipt(
            capability_id=CONTEXT_CAPABILITY_ID,
            status="succeeded",
            input_digest=sha256_digest({
                "portfolio_id": bundle.portfolio_id,
                "as_of": bundle.as_of,
                "source_revision": row.get("source_revision"),
            }),
            output_digest=sha256_digest({
                "metrics": bundle.metrics,
                "warnings": row["warnings"],
                "events": bundle.events,
                "exposures": bundle.exposures,
            }),
            evidence=(EvidenceReference(
                evidence_id=evidence_id,
                reference=evidence_id,
                source_type="point_in_time_replay_context",
                description="Deterministically assembled portfolio, metric, mandate and classified-event context.",
            ),),
            methodology="Point-in-time replay context assembly and mandate-rule evaluation.",
            limitations=("Raw licensed news text is excluded from model input.",),
        ),
        started_at=started_at,
        completed_at=completed_at,
    )


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
    portfolio_id: str,
    deterministic_warnings: tuple[dict[str, Any], ...] = (),
    capability_use: AgentCapabilityUse | None = None,
) -> AgentStructuredOutput:
    claims = [item for item in output.supporting_claims if item.evidence_refs]
    warning_metric_ids = {
        _canonical_metric_id(warning["metric"], "metric")
        for warning in deterministic_warnings
    }
    model_findings = tuple(
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
            metric_id=_canonical_metric_id(claim.metric_ref, f"metric-{index}") if claim.metric_ref else None,
            observed_value=float(claim.reported_metric_value) if claim.reported_metric_value is not None else None,
        )
        for index, claim in enumerate(claims, start=1)
        if _canonical_metric_id(claim.metric_ref, f"metric-{index}") not in warning_metric_ids
    )
    deterministic_findings = tuple(
        AgentFindingByproduct(
            finding_id=f"{cycle_id}-{suffix}-rule-{index}",
            cluster_key=_slug(str(warning["rule_id"]), f"rule-{index}"),
            claim=f"Mandate rule '{warning['reason']}' was breached by the deterministic point-in-time calculation.",
            risk_type=_warning_risk_type(warning),
            affected_asset=portfolio_id,
            direction="negative",
            materiality=min(1.0, float(warning["threshold_distance"])),
            severity=3 if warning["level"] == "urgent" else 2,
            confidence=0.95,
            confidence_method="Deterministic rule result retained from the reviewed replay capability; confidence is not an outcome probability.",
            evidence_ids=tuple(sorted(set(warning["evidence_ids"]))),
            observed_at=cycle_at,
            metric_id=_canonical_metric_id(warning["metric"], f"metric-{index}"),
            observed_value=float(warning["observed_value"]),
            threshold_value=float(warning["threshold"]),
        )
        for index, warning in enumerate(deterministic_warnings, start=1)
    )
    findings = deterministic_findings + model_findings
    admitted = output.status not in {"ABSTAIN", "ABSTAINED_AGENT_OUTPUT"}
    maximum_severity = max((item.severity for item in findings), default=0)
    state = "alert" if maximum_severity == 3 else "watch" if findings or output.status in {"REVIEW", "URGENT_REVIEW"} or not admitted else "clear"
    capability_evidence = set()
    if capability_use is not None:
        capability_evidence = {item.evidence_id for item in capability_use.receipt.evidence}
    evidence = tuple(sorted(
        set(output.evidence_refs)
        | {item for claim in claims for item in claim.evidence_refs}
        | {item for finding in deterministic_findings for item in finding.evidence_ids}
        | capability_evidence
    ))
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
            risk_interpretation=(
                f"Deterministic capabilities retained {len(deterministic_findings)} mandate finding(s). "
                f"Model interpretation: {output.summary}"
                if deterministic_findings else output.summary
            ),
            expectations="The output supports monitoring and human review; it does not predict or execute a portfolio action.",
            confidence=0.8 if admitted else 0.2,
            confidence_kind="ordinal_judgement",
            confidence_method="Ordinal confidence reflects schema and deterministic critic admission, not outcome calibration.",
            decision=decision,
            supporting_evidence_ids=evidence,
            classified_context_ids=classified_context_ids,
            missing_information=tuple(dict.fromkeys(output.uncertainties)),
            assumptions=(),
            warnings=(),
            limitations=("Model interpretation is bounded to the supplied point-in-time context.",),
        ),
        agent_ids=all_agent_ids if experimental_role == "final_decision_agent" else (role_id,),
        capability_uses=(() if capability_use is None else (capability_use,)),
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
    cycle_id: str | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Execute B1 or A1 and return its canonically mapped ArchitectureOutput."""

    if workflow_id not in {"B1", "A1"}:
        raise ValueError("agent treatment must be B1 or A1")
    processing_started_at = datetime.now(timezone.utc)
    processing_started_clock = perf_counter()
    bundle, alias_to_name = build_bundle(
        portfolio_id=portfolio_id, row=row, holdings=holdings, cycle_at=cycle_at,
    )
    classified_ids = (
        row["classified_context"]["context_id"],
        row["classified_context"]["fundamentals"]["context_id"],
    )
    event_evidence_times = {
        evidence_id: event.available_at
        for event in bundle.events
        for evidence_id in (event.evidence_digest, event.source_reference)
    }
    evidence_ids = tuple(dict.fromkeys(
        bundle.evidence_refs + tuple(event.evidence_digest for event in bundle.events)
    ))
    evidence = tuple(
        KernelEvidence(evidence_id=item, available_at=event_evidence_times.get(item, cycle_at))
        for item in evidence_ids
    )
    architecture_type = "single_agent" if workflow_id == "B1" else "agent_graph"
    allowed_agents = (SINGLE_AGENT_ID,) if workflow_id == "B1" else GRAPH_AGENT_IDS
    # Validate the complete experimental boundary before any external model call.
    context = ArchitectureMappingContext(
        run_id=run_id,
        cycle_id=cycle_id or f"cycle-{row['date']}",
        architecture_id=ARCHITECTURE_IDS[workflow_id],
        architecture_type=architecture_type,
        as_of=cycle_at,
        trigger_available_at=min(trigger_available_at, cycle_at),
        input_context_digest=sha256_digest(bundle.model_dump(mode="python")),
        case_id=case_id,
        repetition=1,
        eligible_evidence=evidence,
        allowed_capability_ids=(CONTEXT_CAPABILITY_ID,),
        allowed_agent_ids=allowed_agents,
        classified_context_ids=classified_ids,
        previous_assessment_state=previous_assessment_state,
        previous_severity=previous_severity,
    )
    api_key = _keychain_key(include_value=True)
    if not isinstance(api_key, str) or not api_key:
        raise ValueError("OpenAI API key is unavailable; store it in the ServiceFabric keychain before running B1 or A1")
    provider = OpenAIResponsesProvider(_configuration(), api_key=api_key)
    context_completed_at = datetime.now(timezone.utc)
    capability_use = _context_capability_use(
        bundle,
        row,
        started_at=processing_started_at,
        completed_at=context_completed_at,
    )
    context_processing_ms = (context_completed_at - processing_started_at).total_seconds() * 1000
    started_at = datetime.now(timezone.utc)
    treatment = b1(bundle, provider) if workflow_id == "B1" else a1(bundle, provider)
    completed_at = datetime.now(timezone.utc)
    if completed_at <= started_at:
        completed_at = started_at + timedelta(microseconds=1)
    total_tokens = sum(item.input_tokens + item.output_tokens for item in treatment.receipts)
    provider_request_attempts = sum(
        not any(value.startswith("skipped_after_terminal_error:") for value in item.warnings)
        for item in treatment.receipts
    )
    successful_model_calls = sum(not item.warnings for item in treatment.receipts)
    estimated_cost_usd = round(
        sum(item.input_tokens for item in treatment.receipts)
        * LUNA_INPUT_USD_PER_MILLION / 1_000_000
        + sum(item.output_tokens for item in treatment.receipts)
        * LUNA_OUTPUT_USD_PER_MILLION / 1_000_000,
        8,
    )
    if workflow_id == "B1":
        structured = _structured_output(
            treatment.output, workflow_id=workflow_id, run_id=run_id,
            cycle_id=context.cycle_id, cycle_at=cycle_at, produced_at=completed_at,
            role_id=SINGLE_AGENT_ID, experimental_role="final_decision_agent",
            alias_to_name=alias_to_name, all_agent_ids=(SINGLE_AGENT_ID,),
            classified_context_ids=classified_ids, suffix="final",
            portfolio_id=portfolio_id,
            deterministic_warnings=tuple(row["warnings"]),
            capability_use=capability_use,
        )
        telemetry = AgentRuntimeTelemetry(
            agent_id=SINGLE_AGENT_ID, agent_version="1.0.0",
            started_at=started_at, completed_at=completed_at,
            first_finding_at=completed_at if structured.evaluation_byproducts.findings else None,
            model_calls=1,
            input_tokens=sum(item.input_tokens for item in treatment.receipts),
            output_tokens=sum(item.output_tokens for item in treatment.receipts),
            cost_usd=estimated_cost_usd,
            route=(SINGLE_AGENT_ID,),
            capability_calls=1,
            schema_validation_failures=sum(
                any("invalid_structured_output" in value for value in item.warnings)
                for item in treatment.receipts
            ),
            semantic_verification_failures=0 if treatment.critic.passed else 1,
            errors=tuple(dict.fromkeys(
                value for item in treatment.receipts for value in _receipt_errors(item)
            )),
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
                portfolio_id=portfolio_id,
                deterministic_warnings=tuple(row["warnings"]) if is_final else (),
                capability_use=capability_use if is_final else None,
            )
            receipt = treatment.receipts[index]
            executions.append(wrap_agent_execution(
                structured,
                AgentRuntimeTelemetry(
                    agent_id=role_id, agent_version="1.0.0",
                    started_at=item_start, completed_at=item_end,
                    first_finding_at=item_end if structured.evaluation_byproducts.findings else None,
                    model_calls=1, input_tokens=receipt.input_tokens,
                    output_tokens=receipt.output_tokens,
                    cost_usd=_receipt_cost(receipt.input_tokens, receipt.output_tokens),
                    route=GRAPH_AGENT_IDS[: index + 1],
                    capability_calls=1 if is_final else 0,
                    schema_validation_failures=int(any(
                        "invalid_structured_output" in value for value in receipt.warnings
                    )),
                    semantic_verification_failures=0 if is_final and treatment.critic.passed else int(is_final),
                    errors=_receipt_errors(receipt),
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
    # Provider receipts can be rounded to whole milliseconds; keep the timing
    # decomposition physically bounded by the measured cycle wall clock.
    model_processing_ms = min(
        elapsed_ms,
        float(sum(item.elapsed_ms for item in treatment.receipts)),
    )
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
        "provider_request_attempts": provider_request_attempts,
        "successful_model_calls": successful_model_calls,
        "input_tokens": sum(item.input_tokens for item in treatment.receipts),
        "output_tokens": sum(item.output_tokens for item in treatment.receipts),
        "tokens": total_tokens,
        "estimated_cost_usd": estimated_cost_usd,
        "pricing_reference": LUNA_PRICING_REFERENCE,
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
        "provider_receipts": [
            {
                "role_id": item.role_id,
                "response_id": item.response_id,
                "input_tokens": item.input_tokens,
                "output_tokens": item.output_tokens,
                "elapsed_ms": item.elapsed_ms,
                "warnings": list(item.warnings),
            }
            for item in treatment.receipts
        ],
    }
