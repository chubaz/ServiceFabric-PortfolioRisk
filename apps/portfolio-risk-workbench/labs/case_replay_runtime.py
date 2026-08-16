"""Resolve a governed Case into the complete ex-ante stream used by Session 8.

This adapter deliberately reads neither Gold roles nor Gold reviewer findings.
Those remain evaluation truth.  Replay inputs come from the detector review
unit and every context candidate that was eligible at its recorded
``available_at`` time, including candidates later rejected by Gold review.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from case_labelling_runtime import context_execution_store, context_work_store, labelling_store
from gold_case_runtime import gold_case_store
from risk_experiments import (
    GoldCaseConflict, ReplayObservation, ReplayTrigger, canonical_digest,
)


def _reference_for_case(case_id: str) -> Any:
    reference = next(
        (item for item in gold_case_store().list() if item.compiled_case_id == case_id), None,
    )
    if reference is None:
        raise GoldCaseConflict("the Case has no governed Gold-reference binding")
    return reference


def _case_sources(case_id: str) -> tuple[Any, Any, Any, Any, Any]:
    case = gold_case_store().get_case(case_id)
    reference = _reference_for_case(case_id)
    bundle = reference.bundle
    batch = labelling_store().get(bundle.batch_id)
    unit = next((item for item in batch.selected_units if item.unit_id == bundle.unit_id), None)
    if unit is None:
        raise GoldCaseConflict("the Case review unit is unavailable")
    plan = context_work_store().get_optional(bundle.batch_id, bundle.unit_id)
    if plan is None:
        raise GoldCaseConflict("the Case context plan is unavailable")
    context = context_execution_store().get_optional(bundle.batch_id, bundle.unit_id, plan.latest.plan_id)
    if context is None or context.execution.execution_id != bundle.context_execution_id:
        raise GoldCaseConflict("the Case context execution no longer matches its accepted reference")
    return case, reference, batch, unit, context


def resolve_case_replay_inputs(case_id: str) -> tuple[tuple[ReplayObservation, ...], tuple[ReplayTrigger, ...]]:
    """Return auditable observations and chronological triggers for one Case."""

    case, _reference, batch, unit, context = _case_sources(case_id)

    observations: list[ReplayObservation] = []
    seen: set[str] = set()
    for evidence_id in unit.evidence_ids:
        if evidence_id in seen:
            continue
        seen.add(evidence_id)
        packet = {
            "kind": "market", "review_unit_id": unit.unit_id,
            "scope_type": unit.scope_type.value, "scope_id": unit.scope_id,
            "direction": unit.direction.value, "score_band": unit.score_band.value,
            "evidence_id": evidence_id,
        }
        observations.append(ReplayObservation(
            observation_id=evidence_id, kind="market",
            observed_at=unit.observation_time, available_at=unit.available_at,
            evidence_ids=(evidence_id,),
            content_reference=f"label-source:{batch.plan.dataset_snapshot_id}:{unit.unit_id}",
            content_digest=canonical_digest(packet),
        ))
    for candidate in context.execution.proposal.candidates:
        if not candidate.eligible_at_replay_time:
            continue
        packet = {
            "kind": candidate.channel.value,
            "candidate_id": candidate.candidate_id,
            "canonical_entity_id": candidate.canonical_entity_id,
            "source_record_id": candidate.source_record_id,
            "title": candidate.display_title,
            "summary": candidate.display_summary,
            "quality_flags": candidate.quality_flags,
        }
        kind = {
            "events": "event", "fundamentals": "fundamental",
            "market": "market", "macro": "derived",
            "peer_group": "derived", "portfolio": "portfolio",
        }[candidate.channel.value]
        for evidence_id in candidate.evidence_ids:
            if evidence_id in seen:
                continue
            seen.add(evidence_id)
            observations.append(ReplayObservation(
                observation_id=evidence_id, kind=kind,
                observed_at=candidate.observed_at, available_at=candidate.available_at,
                evidence_ids=(evidence_id,),
                content_reference=f"context-candidate:{candidate.candidate_id}",
                content_digest=canonical_digest(packet),
            ))
    observations.sort(key=lambda item: item.observation_id)
    declared = set(case.observable_state.observation_ids)
    resolved = {item.observation_id for item in observations}
    if declared != resolved:
        missing = ", ".join(sorted(declared - resolved)[:5])
        extra = ", ".join(sorted(resolved - declared)[:5])
        raise GoldCaseConflict(
            f"Case replay stream does not reconcile (missing: {missing or 'none'}; extra: {extra or 'none'})"
        )
    triggers = tuple(sorted((
        ReplayTrigger(
            trigger_id=f"trigger-{canonical_digest({'case': case_id, 'observation': item.observation_id, 'at': item.available_at})[7:31]}",
            kind="event_available" if item.kind == "event" else "scheduled_cycle",
            replay_at=item.available_at,
            event_id=(
                f"event-{canonical_digest({'observation': item.observation_id})[7:31]}"
                if item.kind == "event" else None
            ),
        )
        for item in observations
    ), key=lambda item: (item.replay_at, item.trigger_id)))
    return tuple(observations), triggers


def case_observation_details(case_id: str) -> dict[str, dict[str, Any]]:
    """Return architecture-visible source facts; never Gold roles or reviewer conclusions."""

    _case, _reference, _batch, unit, context = _case_sources(case_id)
    details = {
        evidence_id: {
            "kind": "market", "scope_id": unit.scope_id,
            "direction": unit.direction.value, "score_band": unit.score_band.value,
        }
        for evidence_id in unit.evidence_ids
    }
    for candidate in context.execution.proposal.candidates:
        if not candidate.eligible_at_replay_time:
            continue
        for evidence_id in candidate.evidence_ids:
            details[evidence_id] = {
                "kind": candidate.channel.value,
                "entity_id": candidate.canonical_entity_id,
                "title": candidate.display_title,
                "summary": candidate.display_summary,
                "relevance": candidate.relevance_score,
                "quality_flags": candidate.quality_flags,
            }
    return details


def case_replay_preview(case_id: str) -> dict[str, Any]:
    """Small user-facing preflight; detailed packets stay in technical storage."""

    observations, triggers = resolve_case_replay_inputs(case_id)
    kinds = Counter(item.kind for item in observations)
    return {
        "case_id": case_id,
        "ready": True,
        "source": "licensed historical records",
        "observations": len(observations),
        "by_type": dict(sorted(kinds.items())),
        "workflow_cycles": len(triggers),
        "first_available_at": min(item.available_at for item in observations).isoformat(),
        "last_available_at": max(item.available_at for item in observations).isoformat(),
        "temporal_rule": "Each cycle sees only observations available at or before that cycle.",
        "gold_reference_visible_to_architecture": False,
    }
