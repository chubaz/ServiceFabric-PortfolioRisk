"""Bounded, effect-free due diligence over an immutable Decision Proposal."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from .models import (
    FINAL_STATES,
    DecisionInvestigationStep,
    DecisionInvestigationWorkflowRun,
    DecisionLifecycleReceipt,
    DecisionOutcome,
    DecisionProposalRevision,
    DecisionRecord,
    DecisionSupplementalEvidence,
    DueDiligenceCapability,
    EvidenceTruth,
    canonical_digest,
)
from .store import DecisionConflict, LocalDecisionStore


DUE_DILIGENCE_MODULES: tuple[dict[str, str], ...] = (
    {
        "capability_id": DueDiligenceCapability.EVIDENCE_COVERAGE.value,
        "label": "Evidence coverage",
        "purpose": "Count direct references, expose missing information and distinguish reference coverage from payload verification.",
    },
    {
        "capability_id": DueDiligenceCapability.CAPABILITY_RECEIPTS.value,
        "label": "Capability receipts",
        "purpose": "Inspect which reviewed capability receipts support the proposal and which payloads remain unavailable.",
    },
    {
        "capability_id": DueDiligenceCapability.POLICY_ALIGNMENT.value,
        "label": "Mandate and policy",
        "purpose": "Compare the proposal with its declared mandate relevance, D1 authority and effect-free review policy.",
    },
    {
        "capability_id": DueDiligenceCapability.ALTERNATIVES.value,
        "label": "Alternative consequences",
        "purpose": "Compare all five canonical reviewer outcomes without choosing or executing one.",
    },
    {
        "capability_id": DueDiligenceCapability.ARTIFACT_LINEAGE.value,
        "label": "Artifact lineage",
        "purpose": "Inventory retained artifact, scenario and model-receipt references without claiming unavailable content was read.",
    },
)


def _token(*values: object) -> str:
    return hashlib.sha256("\0".join(str(value) for value in values).encode("utf-8")).hexdigest()[:20]


def _all_references(record: DecisionRecord) -> tuple[str, ...]:
    proposal = record.proposal
    return tuple(sorted(set(
        proposal.evidence_ids
        + proposal.artifact_ids
        + proposal.capability_receipt_ids
        + proposal.model_receipt_ids
        + proposal.policy_ids
        + proposal.scenario_ids
    )))


def _context_digest(record: DecisionRecord) -> str:
    return canonical_digest({
        "proposal": record.proposal.proposal_digest,
        "context_revisions": [item.revision_digest for item in record.context_revisions],
        "supplemental_evidence": [item.evidence_digest for item in record.supplemental_evidence],
        "proposal_revisions": [item.revision_digest for item in record.proposal_revisions],
    })


def _truth(record: DecisionRecord) -> EvidenceTruth:
    premise = " ".join((
        record.proposal.why_now,
        *record.proposal.uncertainties,
        record.proposal.portfolio_relevance,
    )).casefold()
    if "synthetic" in premise or "simulated" in premise or "fixture" in premise:
        return EvidenceTruth.SYNTHETIC
    if "real" in premise and "synthetic" not in premise:
        return EvidenceTruth.REAL
    return EvidenceTruth.REFERENCE_ONLY


def _analysis(
    record: DecisionRecord,
    capability: DueDiligenceCapability,
    candidate: DecisionOutcome,
) -> tuple[str, str, str, tuple[str, ...], EvidenceTruth]:
    proposal = record.proposal
    if capability == DueDiligenceCapability.EVIDENCE_COVERAGE:
        references = proposal.evidence_ids
        finding = (
            f"The proposal declares {len(references)} direct evidence reference(s) and "
            f"{len(proposal.missing_information)} unresolved information need(s). This module "
            "checks reference coverage only; it does not represent an unavailable evidence payload as verified."
        )
        return "Evidence coverage", "Assess direct evidence coverage and declared gaps.", finding, references, _truth(record)
    if capability == DueDiligenceCapability.CAPABILITY_RECEIPTS:
        references = proposal.capability_receipt_ids
        finding = (
            f"The proposal cites {len(references)} capability receipt(s). "
            + (f"The declared references are {', '.join(references)}. " if references else "No capability receipt is attached. ")
            + "Receipt identity establishes lineage, not independent verification of a payload that is not present in this workspace."
        )
        return "Capability receipt review", "Inspect declared capability execution lineage.", finding, references, EvidenceTruth.REFERENCE_ONLY
    if capability == DueDiligenceCapability.POLICY_ALIGNMENT:
        references = proposal.policy_ids or ("risk.policy.human-decision-review.v1",)
        finding = (
            f"The proposal is D1, human-only and effect-free. Its declared mandate relevance is: "
            f"{proposal.mandate_relevance} The candidate recommendation '{candidate.value}' remains analysis only and cannot resolve the proposal."
        )
        return "Mandate and policy alignment", "Test declared authority and mandate alignment.", finding, references, EvidenceTruth.REFERENCE_ONLY
    if capability == DueDiligenceCapability.ALTERNATIVES:
        references = tuple(item.outcome.value for item in proposal.options)
        consequences = "; ".join(f"{item.label}: {item.consequence}" for item in proposal.options)
        finding = (
            f"All five human outcomes remain available. The candidate revision prefers '{candidate.value}' for further review. "
            f"Consequences compared: {consequences} No alternative creates a portfolio or external effect."
        )
        return "Alternative consequence comparison", "Compare every canonical reviewer alternative.", finding, references, EvidenceTruth.REFERENCE_ONLY
    references = tuple(sorted(set(proposal.artifact_ids + proposal.scenario_ids + proposal.model_receipt_ids)))
    finding = (
        f"The proposal declares {len(proposal.artifact_ids)} artifact, {len(proposal.scenario_ids)} scenario and "
        f"{len(proposal.model_receipt_ids)} model-receipt reference(s). "
        + ("Their identities are retained for lineage; content must be opened through its owning repository."
           if references else "No retained artifact lineage is attached, so no artifact content can support the proposal here.")
    )
    return "Artifact lineage", "Inventory retained analytical artifact references.", finding, references, EvidenceTruth.REFERENCE_ONLY


def run_due_diligence(
    store: LocalDecisionStore,
    proposal_id: str,
    *,
    name: str,
    investigation_question: str,
    capability_ids: tuple[DueDiligenceCapability, ...],
    candidate_recommendation: DecisionOutcome,
    actor_id: str,
    idempotency_key: str,
    expected_revision: str,
) -> DecisionRecord:
    current = store.get(proposal_id)
    existing = next((item for item in current.investigation_runs if item.idempotency_key == idempotency_key), None)
    if existing is not None:
        same_request = (
            existing.name == name
            and existing.investigation_question == investigation_question
            and existing.created_by == actor_id
            and existing.candidate_recommendation == candidate_recommendation
            and tuple(item.capability_id for item in existing.steps) == capability_ids
        )
        if same_request:
            return current
        raise DecisionConflict("idempotency key was used for another due-diligence workflow")
    if current.record_revision != expected_revision:
        raise DecisionConflict("decision record changed; reload before investigating")
    if current.state in FINAL_STATES:
        raise DecisionConflict("final decision proposals are inspectable but cannot run new due diligence")
    if not capability_ids:
        raise DecisionConflict("temporary investigation requires at least one registered module")
    if len(capability_ids) != len(set(capability_ids)):
        raise DecisionConflict("temporary investigation modules must be unique")

    now = datetime.now(timezone.utc)
    run_number = len(current.investigation_runs) + 1
    identity = _token(proposal_id, idempotency_key, current.record_revision)
    run_id = f"dd-run-{identity}"
    new_evidence: list[DecisionSupplementalEvidence] = []
    steps: list[DecisionInvestigationStep] = []
    for index, capability in enumerate(capability_ids, start=1):
        title, objective, finding, references, truth = _analysis(current, capability, candidate_recommendation)
        evidence_id = f"dd-evidence-{identity}-{index}"
        evidence = DecisionSupplementalEvidence(
            evidence_id=evidence_id,
            proposal_id=proposal_id,
            source_type={
                DueDiligenceCapability.EVIDENCE_COVERAGE: "coverage_analysis",
                DueDiligenceCapability.CAPABILITY_RECEIPTS: "capability_receipt_analysis",
                DueDiligenceCapability.POLICY_ALIGNMENT: "policy_analysis",
                DueDiligenceCapability.ALTERNATIVES: "alternative_analysis",
                DueDiligenceCapability.ARTIFACT_LINEAGE: "artifact_lineage_analysis",
            }[capability],
            title=title,
            finding=finding,
            source_reference_ids=tuple(sorted(set(references))),
            data_truth=truth,
            as_of=current.proposal.as_of,
            available_at=current.proposal.available_at,
            created_at=now,
            created_by=actor_id,
        )
        new_evidence.append(evidence)
        steps.append(DecisionInvestigationStep(
            step_id=f"dd-step-{identity}-{index}",
            capability_id=capability,
            objective=objective,
            input_reference_ids=tuple(sorted(set(references))),
            result_summary=finding,
            output_evidence_ids=(evidence_id,),
            started_at=now,
            completed_at=now,
        ))

    run = DecisionInvestigationWorkflowRun(
        run_id=run_id,
        proposal_id=proposal_id,
        base_proposal_digest=current.proposal.proposal_digest,
        name=name,
        investigation_question=investigation_question,
        created_by=actor_id,
        candidate_recommendation=candidate_recommendation,
        idempotency_key=idempotency_key,
        steps=tuple(steps),
        started_at=now,
        completed_at=now,
    )
    revision = DecisionProposalRevision(
        revision_id=f"dd-revision-{identity}",
        proposal_id=proposal_id,
        revision_number=len(current.proposal_revisions) + 2,
        base_proposal_digest=current.proposal.proposal_digest,
        based_on_context_digest=_context_digest(current),
        recommendation=candidate_recommendation,
        rationale=(
            f"Candidate interpretation after temporary workflow '{name}': {investigation_question} "
            f"The workflow completed {len(steps)} effect-free inspection step(s). This revision informs human review and is not a resolution."
        ),
        supplemental_evidence_ids=tuple(sorted(item.evidence_id for item in new_evidence)),
        alternatives_considered=tuple(DecisionOutcome),
        unresolved_questions=current.proposal.missing_information,
        created_by=actor_id,
        workflow_run_id=run_id,
        created_at=now,
    )
    lifecycle = DecisionLifecycleReceipt(
        receipt_id=f"dd-receipt-{identity}",
        proposal_id=proposal_id,
        sequence=len(current.lifecycle) + 1,
        from_state=current.state,
        to_state=current.state,
        actor_id=actor_id,
        actor_type="human",
        rationale=f"Completed temporary due-diligence workflow {run_number}; decision state is unchanged.",
        occurred_at=now,
        idempotency_key=idempotency_key,
        prior_receipt_digest=current.lifecycle[-1].receipt_digest,
    )
    updated = DecisionRecord(
        proposal=current.proposal,
        lifecycle=(*current.lifecycle, lifecycle),
        resolutions=current.resolutions,
        consequences=current.consequences,
        context_revisions=current.context_revisions,
        follow_up_runs=current.follow_up_runs,
        supplemental_evidence=(*current.supplemental_evidence, *new_evidence),
        investigation_runs=(*current.investigation_runs, run),
        proposal_revisions=(*current.proposal_revisions, revision),
    )
    return store.replace(updated, expected_revision=expected_revision)

