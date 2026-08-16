"""Application workflow for selective Gold references and Experimental Cases."""

from __future__ import annotations

import os
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from artifact_repository import artifact_root
from case_labelling_runtime import context_execution_store, context_work_store, labelling_store
from historical_replay_runtime import _mandate_payload
from risk_experiments import (
    GoldCaseConflict,
    GoldCaseReview,
    GoldDecisionCheckpoint,
    GoldReviewOutcome,
    LocalGoldCaseStore,
    PlannedExperimentSelection,
    canonical_digest,
    compile_experimental_case,
    prepare_gold_case_bundle,
)


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GoldPreparationRequest(RequestModel):
    unit_id: str = Field(min_length=3, max_length=160)
    study_id: str = Field(min_length=3, max_length=160)
    experiment_id: str = Field(min_length=3, max_length=160)
    research_use: str = Field(min_length=10, max_length=1000)
    checkpoint_label: str = Field(min_length=3, max_length=160)
    checkpoint_date: date
    acceptable_actions: tuple[
        Literal[
            "no_action", "monitor", "investigate", "request_data",
            "run_scenario", "escalate", "review_exposure", "abstain",
        ], ...
    ] = Field(min_length=1)
    selected_by: str = Field(default="research-lead", min_length=2, max_length=120)
    prepared_by: str = Field(default="gold-preparation-kernel", min_length=2, max_length=120)

    @field_validator("acceptable_actions")
    @classmethod
    def actions_are_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted(set(values)))
        if normalized != values:
            raise ValueError("acceptable actions must be unique and sorted")
        return values


class GoldReviewRequest(RequestModel):
    reference_id: str = Field(min_length=3, max_length=160)
    expected_review_revision: int = Field(ge=0)
    outcome: GoldReviewOutcome
    label_reconciled: bool
    evidence_reconciled: bool
    temporal_firewall_verified: bool
    limitations_acceptable: bool
    rationale: str = Field(min_length=10, max_length=2000)
    reviewed_by: str = Field(default="gold-reviewer-independent", min_length=2, max_length=120)


class ExperimentalCaseCompileRequest(RequestModel):
    reference_id: str = Field(min_length=3, max_length=160)
    evaluation_horizon_end: date


def gold_case_store() -> LocalGoldCaseStore:
    configured = os.environ.get("PORTFOLIO_RISK_LABEL_ROOT")
    root = Path(configured).expanduser().absolute() if configured else artifact_root().parent / "label-production-v1"
    return LocalGoldCaseStore(root)


def _record_for_unit(batch_id: str, unit_id: str) -> Any | None:
    return next(
        (item for item in reversed(gold_case_store().list_for_batch(batch_id)) if item.bundle.unit_id == unit_id),
        None,
    )


def _gate_payload(batch_id: str, unit_id: str) -> dict[str, Any]:
    batch = labelling_store().get(batch_id)
    readiness = batch.readiness(unit_id)
    blockers = []
    if readiness.state != "ready":
        blockers.append("The retrospective label needs an accepted independent review.")
    plan_record = context_work_store().get_optional(batch_id, unit_id)
    context_record = None
    if plan_record is None:
        blockers.append("Prepare and review the evidence context.")
    else:
        context_record = context_execution_store().get_optional(batch_id, unit_id, plan_record.latest.plan_id)
        if context_record is None or context_record.latest_review is None:
            blockers.append("The prepared evidence needs a human review.")
        elif context_record.latest_review.outcome.value != "accept_context":
            blockers.append("The evidence review must be accepted before Gold preparation.")
    return {
        "ready": not blockers,
        "blockers": blockers,
        "label_state": readiness.state,
        "context_state": (
            "not_prepared" if context_record is None else
            "awaiting_review" if context_record.latest_review is None else
            context_record.latest_review.outcome.value
        ),
    }


def _record_payload(record: Any) -> dict[str, Any]:
    bundle = record.bundle
    review = record.latest_review
    return {
        "reference_id": bundle.gold_reference_id,
        "state": record.state,
        "experiment_id": bundle.selection.experiment_id,
        "research_use": bundle.selection.research_use,
        "scope": {"type": bundle.scope_type, "name": bundle.scope_id},
        "finding": {
            "outcome": bundle.outcome,
            "direction": bundle.direction,
            "morphology": bundle.morphology,
            "severity": bundle.severity_level,
            "start": None if bundle.manifestation_start is None else bundle.manifestation_start.date().isoformat(),
            "peak": None if bundle.manifestation_peak is None else bundle.manifestation_peak.date().isoformat(),
            "end": None if bundle.manifestation_end is None else bundle.manifestation_end.date().isoformat(),
            "censored": bundle.manifestation_censored,
        },
        "evidence": [{
            "title": item.title,
            "summary": item.summary,
            "visibility": item.replay_visibility,
            "role": item.role,
            "position": item.position,
            "limitations": [value.replace("_", " ") for value in item.quality_limits],
        } for item in bundle.evidence],
        "checkpoints": [{
            "label": item.label,
            "date": item.information_cutoff.date().isoformat(),
            "acceptable_actions": list(item.acceptable_actions),
        } for item in bundle.checkpoints],
        "limitations": list(bundle.unresolved_limits),
        "data_truth": bundle.data_truth,
        "review_revision": len(record.reviews),
        "review": None if review is None else {
            "outcome": review.outcome.value,
            "rationale": review.rationale,
            "reviewed_by": review.reviewed_by,
        },
        "compiled_case_id": record.compiled_case_id,
        "boundary": "Gold truth remains retrospective and hidden from the architecture. Only replay-eligible evidence enters the observable Case state.",
    }


def gold_work_payload(batch_id: str, unit_id: str) -> dict[str, Any]:
    batch = labelling_store().get(batch_id)
    if unit_id not in {item.unit_id for item in batch.selected_units}:
        raise GoldCaseConflict("the selected review item does not belong to this batch")
    return {
        "gate": _gate_payload(batch_id, unit_id),
        "record": None if (record := _record_for_unit(batch_id, unit_id)) is None else _record_payload(record),
    }


def prepare_gold_reference(batch_id: str, request: GoldPreparationRequest) -> dict[str, Any]:
    gate = _gate_payload(batch_id, request.unit_id)
    if not gate["ready"]:
        raise GoldCaseConflict("Gold preparation is blocked: " + " ".join(gate["blockers"]))
    batch = labelling_store().get(batch_id)
    existing = _record_for_unit(batch_id, request.unit_id)
    if existing is not None and existing.bundle.selection.experiment_id == request.experiment_id:
        if existing.state in {"awaiting_independent_review", "accepted", "experimental_case_compiled"}:
            return {"saved": True, "idempotent": True, "record": _record_payload(existing)}
        if existing.state == "excluded":
            raise GoldCaseConflict("the excluded reference requires a new planned experiment selection")
    plan = context_work_store().get_optional(batch_id, request.unit_id)
    if plan is None:
        raise GoldCaseConflict("context plan is unavailable")
    context = context_execution_store().get_optional(batch_id, request.unit_id, plan.latest.plan_id)
    if context is None:
        raise GoldCaseConflict("prepared context is unavailable")
    now = datetime.now(timezone.utc)
    selection = PlannedExperimentSelection(
        selection_id=f"gold-selection-{canonical_digest({'batch': batch_id, 'unit': request.unit_id, 'experiment': request.experiment_id})[7:31]}",
        study_id=request.study_id,
        experiment_id=request.experiment_id,
        research_use=request.research_use,
        selected_by=request.selected_by,
        selected_at=now,
    )
    checkpoint = GoldDecisionCheckpoint(
        checkpoint_id=f"gold-checkpoint-{canonical_digest({'unit': request.unit_id, 'date': request.checkpoint_date.isoformat(), 'label': request.checkpoint_label})[7:31]}",
        label=request.checkpoint_label,
        information_cutoff=datetime.combine(request.checkpoint_date, time.max, tzinfo=timezone.utc),
        acceptable_actions=request.acceptable_actions,
        required_evidence_ids=tuple(sorted({
            evidence_id
            for candidate in context.execution.proposal.candidates
            if candidate.eligible_at_replay_time
            for evidence_id in candidate.evidence_ids
        })),
    )
    bundle = prepare_gold_case_bundle(
        batch=batch,
        unit_id=request.unit_id,
        context_record=context,
        selection=selection,
        checkpoints=(checkpoint,),
        data_truth="licensed_historical",
        prepared_by=request.prepared_by,
        prepared_at=now,
        supersedes_gold_reference_id=(
            existing.bundle.gold_reference_id
            if existing is not None and existing.state == "changes_requested"
            else None
        ),
    )
    record = gold_case_store().create(bundle)
    return {"saved": True, "record": _record_payload(record)}


def review_gold_reference(batch_id: str, request: GoldReviewRequest) -> dict[str, Any]:
    store = gold_case_store()
    record = store.get(request.reference_id)
    if record.bundle.batch_id != batch_id:
        raise GoldCaseConflict("Gold reference belongs to a different batch")
    prior = record.latest_review
    review = GoldCaseReview(
        review_id=f"gold-review-{canonical_digest({'reference': request.reference_id, 'revision': request.expected_review_revision + 1, 'outcome': request.outcome.value})[7:31]}",
        gold_reference_id=request.reference_id,
        bundle_digest=record.bundle.bundle_digest,
        revision=request.expected_review_revision + 1,
        supersedes_review_id=None if prior is None else prior.review_id,
        outcome=request.outcome,
        label_reconciled=request.label_reconciled,
        evidence_reconciled=request.evidence_reconciled,
        temporal_firewall_verified=request.temporal_firewall_verified,
        limitations_acceptable=request.limitations_acceptable,
        rationale=request.rationale,
        reviewed_by=request.reviewed_by,
        reviewed_at=datetime.now(timezone.utc),
    )
    revised = store.review(request.reference_id, review, expected_revision=request.expected_review_revision)
    return {"saved": True, "record": _record_payload(revised)}


def compile_gold_experimental_case(
    batch_id: str, request: ExperimentalCaseCompileRequest
) -> dict[str, Any]:
    store = gold_case_store()
    record = store.get(request.reference_id)
    if record.bundle.batch_id != batch_id:
        raise GoldCaseConflict("Gold reference belongs to a different batch")
    batch = labelling_store().get(batch_id)
    mandate = _mandate_payload(batch.plan.portfolio_id)
    plan = context_work_store().get_optional(batch_id, record.bundle.unit_id)
    if plan is None:
        raise GoldCaseConflict("the accepted Gold reference has no retained context plan")
    context = context_execution_store().get_optional(batch_id, record.bundle.unit_id, plan.latest.plan_id)
    if context is None or context.execution.execution_id != record.bundle.context_execution_id:
        raise GoldCaseConflict("the accepted Gold reference has no matching retained context execution")
    unit = next(item for item in batch.selected_units if item.unit_id == record.bundle.unit_id)
    observable_candidates = tuple(
        candidate
        for candidate in context.execution.proposal.candidates
        if candidate.eligible_at_replay_time
    )
    observable_ids = tuple(sorted({
        evidence_id
        for candidate in observable_candidates
        for evidence_id in candidate.evidence_ids
    } | set(unit.evidence_ids)))
    observable_times = tuple(candidate.available_at for candidate in observable_candidates) + (
        unit.available_at,
    )
    case = compile_experimental_case(
        record,
        portfolio_reference=f"portfolio:portfolio-risk.research:{batch.plan.portfolio_id}@{date.today().isoformat()}",
        mandate_reference=mandate["reference"],
        risk_policy_reference=mandate["risk_policy"]["reference"],
        data_references=(
            f"dataset:crsp-compustat:{batch.plan.dataset_snapshot_id}",
            "dataset:compustat-quarterly",
            "dataset:crsp-daily",
            "dataset:ravenpack-events",
        ),
        evaluation_horizon_end=datetime.combine(request.evaluation_horizon_end, time.max, tzinfo=timezone.utc),
        observable_observation_ids=observable_ids,
        observable_as_of=min(observable_times),
    )
    revised = store.bind_case(request.reference_id, case)
    return {
        "saved": True,
        "record": _record_payload(revised),
        "case": {
            "case_id": case.case_id,
            "experiment_id": case.experiment_id,
            "as_of": case.observable_state.as_of.isoformat(),
            "replay_observations": len(case.observable_state.observation_ids),
            "evaluation_reference_admitted": case.evaluation_state.label_state == "admitted",
            "gold_hidden_from_architecture": case.evaluation_state.architecture_access is False,
        },
    }
