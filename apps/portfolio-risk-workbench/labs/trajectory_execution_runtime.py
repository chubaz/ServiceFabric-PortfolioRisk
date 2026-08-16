"""Execute Session 8 trajectories from saved matched plans.

The first admitted adapter is B0. It consumes only architecture-visible source
facts and fixed rules. B1/A1 remain closed until their bounded model adapters
and an explicit paid-call authorization are present.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any

from case_replay_runtime import case_observation_details, resolve_case_replay_inputs
from agent_treatment_runtime import execute_agent_cycle
from artifact_repository import artifact_store
from gold_case_runtime import gold_case_store
from historical_replay_runtime import EVALUATION_ID, run_replay
from matched_run_runtime import matched_run_store
from risk_experiments import (
    ArchitectureDecision, ArchitectureFinding, ArchitectureOutput,
    CycleExecutionResult, LocalTrajectoryStore, MatchedRunConflict,
    PerturbationCondition, ReplayTrigger, TrajectoryNotFound, canonical_digest,
    execute_point_in_time_trajectory,
)
from risk_artifacts import (
    ArtifactKind, ArtifactManifest, ArtifactNotFound, DataTruthClass,
    PreviewMode, PublicationState, RetentionClass, RightsState, SourceRevision,
    file_manifest,
)


B0_CAPABILITY = "capability:risk:case-stream-fixed-rules@1.0.0"
PRESENTATION_FILE = "run-summary.md"


def trajectory_store() -> LocalTrajectoryStore:
    return LocalTrajectoryStore(gold_case_store().root)


def _presentation_artifact_id(trajectory_id: str) -> str:
    return f"trajectory-presentation-{canonical_digest(trajectory_id)[7:31]}"


def _trajectory_timeline(trajectory: Any, treatment_id: str) -> dict[str, Any]:
    """Create a readable projection; the retained trajectory remains authoritative."""
    cycles: list[dict[str, Any]] = []
    prior_observations: set[str] = set()
    active_streak = maximum_streak = 0
    first_warning = first_actionable = first_alert = first_high_confidence = None
    prior_confidence: float | None = None
    confidence_decay_events = 0
    for index, cycle in enumerate(trajectory.cycles, start=1):
        output = cycle.result.architecture_output
        current = {item.observation_id for item in cycle.context.eligible_observations}
        incoming = [
            item for item in cycle.context.eligible_observations
            if item.observation_id in current - prior_observations
        ]
        incoming_types: dict[str, int] = {}
        for item in incoming:
            incoming_types[item.kind] = incoming_types.get(item.kind, 0) + 1
        prior_observations = current
        state = None if output is None else output.assessment_state
        if state in {"watch", "alert"}:
            active_streak += 1
            maximum_streak = max(maximum_streak, active_streak)
            first_warning = first_warning or cycle.context.replay_at.isoformat()
        else:
            active_streak = 0
        if state == "alert":
            first_alert = first_alert or cycle.context.replay_at.isoformat()
        if output is not None and state in {"watch", "alert"} and output.confidence >= 0.8:
            first_high_confidence = first_high_confidence or cycle.context.replay_at.isoformat()
        if output is not None and (
            output.decision.monitoring_action in {"increase_monitoring", "urgent_human_review"}
            or output.decision.portfolio_action != "none"
        ):
            first_actionable = first_actionable or cycle.context.replay_at.isoformat()
        if output is not None:
            if prior_confidence is not None and output.confidence < prior_confidence:
                confidence_decay_events += 1
            prior_confidence = output.confidence
        behavior = None if output is None else output.architecture_behavior
        cycles.append({
            "sequence": index,
            "cycle_id": cycle.context.cycle_id,
            "replay_at": cycle.context.replay_at.isoformat(),
            "trigger": cycle.context.trigger.kind,
            "incoming_observations": len(incoming),
            "incoming_by_type": incoming_types,
            "eligible_observations": len(current),
            "status": cycle.result.status,
            "reason": cycle.result.reason,
            "assessment": state,
            "severity": None if output is None else output.severity,
            "confidence": None if output is None else output.confidence,
            "interpretation": None if output is None else output.risk_interpretation,
            "monitoring_action": None if output is None else output.decision.monitoring_action,
            "portfolio_action": None if output is None else output.decision.portfolio_action,
            "change": None if output is None else output.change_since_previous,
            "findings": 0 if output is None else len(output.findings),
            "capability_calls": cycle.result.capability_calls,
            "model_calls": cycle.result.model_calls,
            "processing_ms": round(cycle.processing_receipt.processing_wall_ms, 3),
            "simulated_time_frozen": (
                cycle.processing_receipt.replay_triggered_at
                == cycle.processing_receipt.replay_paused_at
                == cycle.processing_receipt.replay_resumed_at
            ),
            "agent_contributions": 0 if behavior is None else len(behavior.contributions),
            "finding_disagreement": None if behavior is None else behavior.finding_disagreement,
            "coordination_overhead_ms": None if behavior is None else round(behavior.coordination_overhead_ms, 3),
            "critic_corrections": 0 if behavior is None else len(behavior.critic_corrections),
        })
    return {
        "trajectory_id": trajectory.trajectory_id,
        "run_id": trajectory.run_id,
        "matrix_id": trajectory.matrix_id,
        "cell_id": trajectory.cell_id,
        "architecture": treatment_id,
        "status": trajectory.status,
        "case_id": trajectory.case_id,
        "first_warning_at": first_warning,
        "first_actionable_at": first_actionable,
        "first_alert_at": first_alert,
        "first_high_confidence_at": first_high_confidence,
        "maximum_active_streak_cycles": maximum_streak,
        "confidence_decay_events": confidence_decay_events,
        "cycles": cycles,
        "presentation_excluded_from_evaluation": True,
        "gold_reference_visible": False,
    }


def _markdown_timeline(timeline: dict[str, Any]) -> bytes:
    def clean(value: Any) -> str:
        return str(value or "—").replace("|", "\\|").replace("\n", " ")

    lines = [
        f"# {timeline['architecture']} risk-outlook trajectory",
        "",
        "This is a human-readable rendering. Evaluation uses the retained structured trajectory, not this file.",
        "",
        f"- Status: **{clean(timeline['status'])}**",
        f"- Workflow cycles: **{len(timeline['cycles'])}**",
        f"- First warning: **{clean(timeline['first_warning_at'])}**",
        f"- First actionable output: **{clean(timeline['first_actionable_at'])}**",
        f"- First alert: **{clean(timeline['first_alert_at'])}**",
        f"- Confidence-decay events: **{timeline['confidence_decay_events']}**",
        f"- Longest active streak: **{timeline['maximum_active_streak_cycles']} cycles**",
        "- Gold reference available to architecture: **No**",
        "",
        "| Replay time | New evidence | Outlook | Confidence | Decision | Processing |",
        "|---|---:|---|---:|---|---:|",
    ]
    for cycle in timeline["cycles"]:
        outlook = cycle["assessment"] or cycle["status"]
        confidence = "—" if cycle["confidence"] is None else f"{cycle['confidence']:.2f}"
        decision = cycle["monitoring_action"] or cycle["reason"] or "—"
        lines.append(
            f"| {clean(cycle['replay_at'])} | {cycle['incoming_observations']} | "
            f"{clean(outlook)} | {confidence} | {clean(decision)} | {cycle['processing_ms']:.1f} ms |"
        )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _ensure_presentation_artifact(trajectory: Any, treatment_id: str) -> str:
    artifact_id = _presentation_artifact_id(trajectory.trajectory_id)
    store = artifact_store()
    try:
        store.get(artifact_id)
        return artifact_id
    except ArtifactNotFound:
        pass
    timeline = _trajectory_timeline(trajectory, treatment_id)
    raw = _markdown_timeline(timeline)
    file = file_manifest(
        path=PRESENTATION_FILE, content=raw, media_type="text/markdown",
        role="trajectory_presentation", preview_mode=PreviewMode.ESCAPED_TEXT,
        download_allowed=False, sensitive=False,
    )
    plan = matched_run_store().get(trajectory.matrix_id)
    manifest = ArtifactManifest(
        artifact_id=artifact_id,
        title=f"{treatment_id} · risk-outlook trajectory",
        kind=ArtifactKind.RETAINED_RUN,
        created_at=trajectory.completed_at,
        created_by="experiment-kernel",
        creation_method="experiment-kernel.trajectory-presentation",
        run_id=trajectory.run_id,
        experiment_id=plan.experiment_id,
        data_truth=DataTruthClass.LICENSED_REAL,
        rights=RightsState.LICENSED_RESTRICTED,
        rights_policy_id="rights.research.licensed-derived.v1",
        publication=PublicationState.RESTRICTED,
        retention=RetentionClass.RUN_RETAINED,
        entry_file=PRESENTATION_FILE,
        files=(file,), total_size_bytes=len(raw),
        source_revisions=(SourceRevision(
            kind="run_trajectory", source_id=trajectory.trajectory_id,
            revision="1.0.0", digest=trajectory.trajectory_digest,
        ),),
        approvals=("research-lead.derived-context-authority",),
        restrictions=tuple(sorted((
            "derived_licensed_context_only", "excluded_from_evaluation",
            "no_external_effects", "raw_licensed_text_excluded",
        ))),
        source_manifest_digest=trajectory.trajectory_digest,
    )
    store.admit(
        manifest, {PRESENTATION_FILE: raw}, actor="experiment-kernel",
        rationale="Retained a human-readable rendering outside architecture evaluation fields.",
        occurred_at=trajectory.completed_at,
    )
    return artifact_id


def _payload(
    trajectory: Any,
    treatment_id: str,
    *,
    idempotent: bool,
    presentation_artifact_id: str | None = None,
    cell: Any | None = None,
) -> dict[str, Any]:
    outputs = tuple(
        cycle.result.architecture_output for cycle in trajectory.cycles
        if cycle.result.architecture_output is not None
    )
    alerts = sum(output.assessment_state == "alert" for output in outputs)
    watches = sum(output.assessment_state == "watch" for output in outputs)
    return {
        "trajectory_id": trajectory.trajectory_id, "run_id": trajectory.run_id,
        "cell_id": trajectory.cell_id,
        "architecture": treatment_id, "status": trajectory.status,
        "repetition": None if cell is None else cell.repetition,
        "perturbation": (
            None if cell is None else cell.perturbation_condition.value
        ),
        "cycles": len(trajectory.cycles), "alerts": alerts, "watches": watches,
        "outputs": len(outputs),
        "abstentions": sum(cycle.result.status == "abstained" for cycle in trajectory.cycles),
        "model_calls": trajectory.total_model_calls, "cost_usd": trajectory.total_cost_usd,
        "first_cycle": trajectory.cycles[0].context.replay_at.isoformat(),
        "last_cycle": trajectory.cycles[-1].context.replay_at.isoformat(),
        "gold_reference_visible": False, "idempotent": idempotent,
        "presentation_artifact_id": presentation_artifact_id,
    }


def list_trajectory_results(matrix_id: str) -> dict[str, Any]:
    """Project retained Run results for people; keep contracts and receipts internal."""
    plan = matched_run_store().get(matrix_id)
    cell_by_id = {item.cell_id: item for item in plan.cells}
    treatment_by_cell = {item.cell_id: item.treatment_id for item in plan.cells}
    known_artifacts = {record.manifest.artifact_id for record in artifact_store().list()}
    results = []
    for item in trajectory_store().list():
        if item.matrix_id != matrix_id or item.cell_id not in treatment_by_cell:
            continue
        artifact_id = _presentation_artifact_id(item.trajectory_id)
        results.append(_payload(
            item, treatment_by_cell[item.cell_id], idempotent=True,
            presentation_artifact_id=artifact_id if artifact_id in known_artifacts else None,
            cell=cell_by_id[item.cell_id],
        ))
    results.sort(key=lambda item: (item["architecture"], item["run_id"]))
    return {
        "matrix_id": matrix_id,
        "complete": len(results) == len(plan.cells),
        "completed_runs": len(results),
        "planned_runs": len(plan.cells),
        "results": results,
    }


def get_trajectory_result(matrix_id: str, cell_id: str) -> dict[str, Any]:
    plan = matched_run_store().get(matrix_id)
    cell = next((item for item in plan.cells if item.cell_id == cell_id), None)
    if cell is None:
        raise MatchedRunConflict("matched Run cell was not found")
    run_id = f"run-{canonical_digest({'matrix': matrix_id, 'cell': cell.cell_id})[7:31]}"
    identity = canonical_digest({"matrix": matrix_id, "cell": cell.cell_id, "run": run_id})
    trajectory = trajectory_store().get(f"trajectory-{identity[7:31]}")
    timeline = _trajectory_timeline(trajectory, cell.treatment_id)
    artifact_id = _presentation_artifact_id(trajectory.trajectory_id)
    try:
        artifact_store().get(artifact_id)
    except ArtifactNotFound:
        artifact_id = None
    timeline["presentation_artifact_id"] = artifact_id
    return timeline


def _b0_processor(cell: Any, details: dict[str, dict[str, Any]]):  # type: ignore[no-untyped-def]
    previous_severity = 0

    def process(context):  # type: ignore[no-untyped-def]
        nonlocal previous_severity
        started = perf_counter()
        findings: list[ArchitectureFinding] = []
        conflicting: list[str] = []
        for observation in context.eligible_observations:
            item = details[observation.observation_id]
            if item["kind"] == "market":
                findings.append(ArchitectureFinding(
                    finding_id=f"finding-{canonical_digest({'cycle': context.cycle_id, 'evidence': observation.observation_id})[7:31]}",
                    claim="A pre-registered market detector crossed its downside threshold.",
                    risk_type="market", affected_asset=item["scope_id"], direction="negative",
                    materiality=0.75, severity=2, confidence=0.9,
                    confidence_method="Fixed detector-threshold support; not a probability.",
                    evidence_ids=(observation.observation_id,), observed_at=observation.observed_at,
                ))
            elif item["kind"] == "events" and item["relevance"] >= 0.75:
                text = f"{item['title']} {item['summary']}".lower()
                if "surrender" in text or "sentiment -" in text:
                    findings.append(ArchitectureFinding(
                        finding_id=f"finding-{canonical_digest({'cycle': context.cycle_id, 'evidence': observation.observation_id})[7:31]}",
                        claim="A high-relevance adverse event met the fixed event-watch rule.",
                        risk_type="event", affected_asset=item["entity_id"], direction="negative",
                        materiality=0.45, severity=1, confidence=0.65,
                        confidence_method="Provider relevance and deterministic adverse-text rule; not calibrated probability.",
                        evidence_ids=(observation.observation_id,), observed_at=observation.observed_at,
                    ))
                elif "insider-buy" in text or "sentiment +" in text:
                    conflicting.append(observation.observation_id)
        findings_tuple = tuple(findings)
        severity = max((item.severity for item in findings_tuple), default=0)
        state = "alert" if severity >= 2 else "watch" if severity == 1 else "clear"
        supporting = tuple(sorted({value for item in findings_tuple for value in item.evidence_ids}))
        change = (
            "initial" if not context.previous_output_ids else
            "deteriorated" if severity > previous_severity else
            "improved" if severity < previous_severity else "unchanged"
        )
        previous_severity = severity
        output = ArchitectureOutput(
            output_id=f"output-{canonical_digest({'cycle': context.cycle_id, 'architecture': cell.architecture.architecture_id})[7:31]}",
            run_id=context.run_id, architecture_type="deterministic",
            assessment_state=state, severity=severity,
            confidence=0.9 if severity >= 2 else 0.65 if severity == 1 else 0.5,
            confidence_kind="ordinal_judgement",
            confidence_method="Fixed-rule evidence sufficiency score; not calibrated probability.",
            findings=findings_tuple, supporting_evidence_ids=supporting,
            conflicting_evidence_ids=tuple(sorted(set(conflicting) - set(supporting))),
            risk_interpretation=(
                "The fixed baseline reports threshold-qualified market or adverse event evidence "
                "without inferring a unique cause or reading the hidden Gold reference."
            ),
            expectations="Continue monitoring until a fixed detector or event rule changes state.",
            decision=ArchitectureDecision(
                monitoring_action="increase_monitoring" if findings_tuple else "continue_monitoring",
                portfolio_action="review_exposure" if severity >= 2 else "none",
                alternatives_considered=("continue_monitoring", "investigate", "request_data"),
                human_review_required=bool(findings_tuple),
                rationale_finding_ids=tuple(item.finding_id for item in findings_tuple),
            ),
            missing_information=("point-in-time fundamentals", "verified event lifecycle"),
            assumptions=("Provider relevance is used only as a preconfigured event filter.",),
            limitations=("No causal attribution is produced by B0.",),
            trigger_available_at=context.trigger.replay_at,
            produced_at=datetime.now(timezone.utc), input_context_digest=context.input_context_digest,
            case_id=context.case_id, repetition=cell.repetition,
            perturbation_id=(
                None if cell.perturbation_condition is PerturbationCondition.NONE
                else cell.perturbation_condition.value
            ),
            architecture_id=cell.architecture.architecture_id,
            capabilities_used=tuple(dict.fromkeys((*cell.run_input.capability_references, B0_CAPABILITY))),
            cycle_id=context.cycle_id, as_of=context.replay_at,
            change_since_previous=change,
        )
        elapsed = (perf_counter() - started) * 1000
        return CycleExecutionResult(
            cycle_id=context.cycle_id, status="output", architecture_output=output,
            capability_calls=1, model_calls=0, capability_processing_ms=elapsed,
            model_processing_ms=0, validation_processing_ms=0,
            input_tokens=0, cached_input_tokens=0, output_tokens=0,
            estimated_cost_usd=0, pricing_reference=None,
        )

    return process


def _private_root() -> Path:
    configured = os.environ.get("PORTFOLIO_RISK_PRIVATE_DATA_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    for candidate in Path(__file__).resolve().parents:
        private_root = candidate / "private-data" / "crsp-compustat"
        if (private_root / "raw").is_dir():
            return private_root.resolve()
    raise MatchedRunConflict("licensed CRSP/Compustat root is unavailable")


def _agent_rows(case_id: str) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    observations, _triggers = resolve_case_replay_inputs(case_id)
    start = min(item.available_at.date() for item in observations)
    end = max(item.available_at.date() for item in observations)
    warmup = date.fromordinal(start.toordinal() - 10)
    baseline = run_replay(
        _private_root(), workflow_id="B0", portfolio_id="diversified",
        start_date=warmup, end_date=end, evaluation_id=EVALUATION_ID,
        study_id="study-session8-context", experiment_id="experiment-session8-context",
        study_title="Session 8 point-in-time context preparation",
        research_question="Prepare the identical deterministic context used by matched architecture cells.",
        hypothesis="Context preparation is architecture-neutral and contains no model interpretation.",
    )
    return baseline["clock"], {item.observation_id: item.model_dump(mode="python") for item in observations}


def _apply_perturbation(
    cell: Any,
    observations: tuple[Any, ...],
    triggers: tuple[ReplayTrigger, ...],
    details: dict[str, dict[str, Any]],
) -> tuple[tuple[Any, ...], tuple[ReplayTrigger, ...]]:
    """Apply one declared, architecture-neutral evidence-delay condition."""

    if cell.perturbation_condition is PerturbationCondition.NONE:
        return observations, triggers
    if cell.perturbation_condition is not PerturbationCondition.DELAY_ADVERSE_EVENT_ONE_CYCLE:
        raise MatchedRunConflict("unsupported matched-run perturbation")
    candidates = [
        item for item in observations
        if item.kind == "event"
        and details[item.observation_id].get("relevance", 0) >= 0.75
        and any(
            marker in (
                f"{details[item.observation_id].get('title', '')} "
                f"{details[item.observation_id].get('summary', '')}"
            ).lower()
            for marker in ("sentiment -", "surrender", "negative")
        )
    ]
    if not candidates:
        raise MatchedRunConflict("the declared evidence-delay perturbation has no eligible adverse event")
    target = min(candidates, key=lambda item: (item.available_at, item.observation_id))
    next_times = sorted({item.replay_at for item in triggers if item.replay_at > target.available_at})
    if not next_times:
        raise MatchedRunConflict("the adverse event cannot be delayed because no later workflow cycle exists")
    delayed_at = next_times[0]
    perturbed = tuple(sorted((
        item.model_copy(update={"available_at": delayed_at})
        if item.observation_id == target.observation_id else item
        for item in observations
    ), key=lambda item: item.observation_id))
    rebuilt_values = []
    for item in perturbed:
        trigger_digest = canonical_digest({
            "case": cell.run_input.case_id,
            "observation": item.observation_id,
            "at": item.available_at,
            "perturbation": cell.perturbation_condition.value,
        })
        rebuilt_values.append(ReplayTrigger(
            trigger_id=f"trigger-{trigger_digest[7:31]}",
            kind="event_available" if item.kind == "event" else "scheduled_cycle",
            replay_at=item.available_at,
            event_id=(
                f"event-{canonical_digest({'observation': item.observation_id})[7:31]}"
                if item.kind == "event" else None
            ),
        ))
    rebuilt = tuple(sorted(rebuilt_values, key=lambda item: (item.replay_at, item.trigger_id)))
    return perturbed, rebuilt


def _agent_processor(cell: Any, details: dict[str, dict[str, Any]], rows: list[dict[str, Any]], observations: dict[str, dict[str, Any]]):  # type: ignore[no-untyped-def]
    workflow_id = cell.treatment_id
    previous_state: str | None = None
    previous_severity: int | None = None
    seen_families: set[str] = set()
    used_calls = used_input = used_output = 0
    used_cost = 0.0

    def process(context):  # type: ignore[no-untyped-def]
        nonlocal previous_state, previous_severity, used_calls, used_input, used_output, used_cost
        newly_available = [
            item for item in context.eligible_observations
            if item.available_at == context.replay_at
        ]
        active = False
        for item in newly_available:
            detail = details[item.observation_id]
            if detail["kind"] == "market":
                active = True
            elif detail["kind"] == "events" and detail["relevance"] >= 0.9:
                family = detail["title"].split(" · ", 1)[0].lower()
                if family not in seen_families:
                    seen_families.add(family)
                    active = True
        if not active:
            return CycleExecutionResult(
                cycle_id=context.cycle_id, status="abstained",
                reason="No newly eligible distinct high-relevance event family or market detector signal.",
                capability_calls=0, model_calls=0, capability_processing_ms=0,
                model_processing_ms=0, validation_processing_ms=0,
                input_tokens=0, cached_input_tokens=0, output_tokens=0,
                estimated_cost_usd=0,
            )
        expected_calls = 1 if workflow_id == "B1" else 4
        if used_calls + expected_calls > cell.budget.max_model_calls:
            return CycleExecutionResult(
                cycle_id=context.cycle_id, status="error",
                reason="The pre-registered model-call budget would be exceeded.",
                capability_calls=0, model_calls=0, capability_processing_ms=0,
                model_processing_ms=0, validation_processing_ms=0,
                input_tokens=0, cached_input_tokens=0, output_tokens=0,
                estimated_cost_usd=0,
            )
        eligible_rows = [row for row in rows if date.fromisoformat(row["date"]) <= context.replay_at.date()]
        if not eligible_rows:
            raise MatchedRunConflict("no eligible market context exists before the workflow cycle")
        row = dict(eligible_rows[-1])
        event_stream = []
        for observation in context.eligible_observations:
            detail = details[observation.observation_id]
            if detail["kind"] != "events":
                continue
            summary = detail["summary"]
            sentiment = -0.3 if "sentiment -" in summary.lower() else 0.3 if "sentiment +" in summary.lower() else 0.0
            event_stream.append({
                "event_id": f"event-{canonical_digest({'evidence': observation.observation_id})[7:31]}",
                "event_time": observation.observed_at.isoformat(),
                "information_available_at": observation.available_at.isoformat(),
                "company_name": next(
                    (item["company_name"] for item in row["position_values"] if "ADAMS" in item["company_name"].upper()),
                    row["position_values"][0]["company_name"],
                ),
                "maximum_relevance": detail["relevance"],
                "average_sentiment": sentiment,
                "evidence_id": observation.observation_id,
            })
        row["ravenpack_events"] = {
            **row["ravenpack_events"], "event_stream": event_stream,
            "count": len(event_stream),
            "high_relevance": sum(item["maximum_relevance"] >= 0.75 for item in event_stream),
            "high_relevance_negative": sum(item["maximum_relevance"] >= 0.75 and item["average_sentiment"] < -0.2 for item in event_stream),
            "first_available_at": min((item["information_available_at"] for item in event_stream), default=None),
            "last_available_at": max((item["information_available_at"] for item in event_stream), default=None),
        }
        mapped, receipt = execute_agent_cycle(
            workflow_id=workflow_id, run_id=context.run_id, case_id=context.case_id,
            portfolio_id="diversified", row=row, holdings=tuple(row["position_values"]),
            cycle_at=context.replay_at, trigger_available_at=context.trigger.replay_at,
            previous_assessment_state=previous_state, previous_severity=previous_severity,
            cycle_id=context.cycle_id,
        )
        mapped = mapped.model_copy(update={
            "input_context_digest": context.input_context_digest,
            "architecture_id": cell.architecture.architecture_id,
            "perturbation_id": (
                None if cell.perturbation_condition is PerturbationCondition.NONE
                else cell.perturbation_condition.value
            ),
            "capabilities_used": tuple(dict.fromkeys((*mapped.capabilities_used, *cell.run_input.capability_references))),
        })
        calls = int(receipt["model_calls"])
        input_tokens = int(receipt["input_tokens"])
        output_tokens = int(receipt["output_tokens"])
        cost = float(receipt["estimated_cost_usd"])
        used_calls += calls; used_input += input_tokens; used_output += output_tokens; used_cost += cost
        if (
            used_calls > cell.budget.max_model_calls
            or used_input > cell.budget.max_input_tokens
            or used_output > cell.budget.max_output_tokens
            or used_cost > cell.budget.max_cost_usd
        ):
            raise MatchedRunConflict("the agent treatment exceeded its pre-registered resource budget")
        previous_state, previous_severity = mapped.assessment_state, mapped.severity
        clock = receipt["processing_clock"]
        return CycleExecutionResult(
            cycle_id=context.cycle_id, status="output", architecture_output=mapped,
            capability_calls=1, model_calls=calls,
            capability_processing_ms=float(clock["context_and_capability_processing_ms"]),
            model_processing_ms=float(clock["model_processing_ms"]),
            validation_processing_ms=float(clock["validation_and_mapping_ms"]),
            input_tokens=input_tokens, cached_input_tokens=0, output_tokens=output_tokens,
            estimated_cost_usd=cost, pricing_reference=receipt["pricing_reference"],
        )

    return process


def execute_trajectory_cell(matrix_id: str, cell_id: str) -> dict[str, Any]:
    plan = matched_run_store().get(matrix_id)
    cell = next((item for item in plan.cells if item.cell_id == cell_id), None)
    if cell is None:
        raise MatchedRunConflict("matched Run cell was not found")
    if cell.treatment_id != "B0" and not plan.external_model_authorized:
        raise MatchedRunConflict("paid model calls were not authorised for this matched plan")
    run_id = f"run-{canonical_digest({'matrix': matrix_id, 'cell': cell.cell_id})[7:31]}"
    identity = canonical_digest({"matrix": matrix_id, "cell": cell.cell_id, "run": run_id})
    trajectory_id = f"trajectory-{identity[7:31]}"
    store = trajectory_store()
    try:
        existing = store.get(trajectory_id)
        artifact_id = _ensure_presentation_artifact(existing, cell.treatment_id)
        return _payload(
            existing, cell.treatment_id, idempotent=True,
            presentation_artifact_id=artifact_id,
            cell=cell,
        )
    except TrajectoryNotFound:
        pass
    observations, triggers = resolve_case_replay_inputs(plan.case_id)
    details = case_observation_details(plan.case_id)
    observations, triggers = _apply_perturbation(cell, observations, triggers, details)
    processor = _b0_processor(cell, details)
    if cell.treatment_id in {"B1", "A1"}:
        rows, observation_records = _agent_rows(plan.case_id)
        processor = _agent_processor(cell, details, rows, observation_records)
    trajectory = execute_point_in_time_trajectory(
        matrix_id=matrix_id, cell=cell, triggers=triggers, observations=observations,
        processor=processor,
    )
    retained = store.save(trajectory)
    artifact_id = _ensure_presentation_artifact(retained, cell.treatment_id)
    return _payload(
        retained, cell.treatment_id, idempotent=False,
        presentation_artifact_id=artifact_id,
        cell=cell,
    )
