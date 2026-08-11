"""Application projection for persistent, human-owned Decision Review records."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from risk_decisions import DUE_DILIGENCE_MODULES, FINAL_STATES, POLICY_ID, DecisionRecord, LocalDecisionStore


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def decision_store() -> LocalDecisionStore:
    configured = os.getenv("PORTFOLIO_RISK_DECISION_ROOT")
    root = (
        Path(configured).expanduser().absolute()
        if configured
        else Path.home() / ".servicefabric-portfolio-risk" / "decisions-v1"
    )
    if root == REPOSITORY_ROOT or root.is_relative_to(REPOSITORY_ROOT):
        raise ValueError("PORTFOLIO_RISK_DECISION_ROOT must remain outside Git")
    return LocalDecisionStore(root)


def record_payload(record: DecisionRecord) -> dict[str, Any]:
    proposal = record.proposal.model_dump(mode="json")
    proposal.update({"artifact_type": "decision_proposal", "status": record.state.value})
    resolutions = []
    for item in record.resolutions:
        value = item.model_dump(mode="json")
        value.update({
            "artifact_type": "decision",
            "resolver": {"resolver_id": item.resolver_id, "resolver_type": item.resolver_type},
        })
        resolutions.append(value)
    consequences = []
    for item in record.consequences:
        value = item.model_dump(mode="json")
        value["artifact_type"] = "decision_consequence_receipt"
        consequences.append(value)
    return {
        "proposal": proposal,
        "state": record.state.value,
        "revision": record.record_revision,
        "lifecycle": [item.model_dump(mode="json") for item in record.lifecycle],
        "decisions": resolutions,
        "consequence_receipts": consequences,
        "context_revisions": [item.model_dump(mode="json") for item in record.context_revisions],
        "follow_up_runs": [item.model_dump(mode="json") for item in record.follow_up_runs],
        "supplemental_evidence": [item.model_dump(mode="json") for item in record.supplemental_evidence],
        "investigation_runs": [item.model_dump(mode="json") for item in record.investigation_runs],
        "proposal_revisions": [item.model_dump(mode="json") for item in record.proposal_revisions],
    }


def due_diligence_payload(record: DecisionRecord) -> dict[str, Any]:
    proposal = record.proposal
    synthetic = "synthetic" in " ".join((proposal.why_now, *proposal.uncertainties)).casefold()
    declared_truth = "synthetic" if synthetic else "reference_only"

    def references(values: tuple[str, ...], *, kind: str, note: str, truth: str = "reference_only") -> list[dict[str, str]]:
        return [
            {
                "reference_id": value,
                "kind": kind,
                "status": "declared_reference",
                "data_truth": truth,
                "note": note,
            }
            for value in values
        ]

    policy_ids = proposal.policy_ids or (POLICY_ID,)
    alternatives = [
        {
            "reference_id": item.outcome.value,
            "kind": "decision_alternative",
            "status": "available",
            "data_truth": "policy",
            "label": item.label,
            "note": item.consequence,
            "workflow_effect": item.workflow_effect,
            "portfolio_effects": [],
            "external_effects": [],
        }
        for item in proposal.options
    ]
    groups = [
        {
            "group_id": "evidence",
            "title": "Direct evidence",
            "explanation": "References declared by the immutable proposal. A reference is not represented as a verified payload unless its owning repository supplies one.",
            "items": references(
                proposal.evidence_ids,
                kind="evidence",
                truth=declared_truth,
                note="Eligible proposal evidence reference; payload verification is outside this bounded view.",
            ),
        },
        {
            "group_id": "artifacts",
            "title": "Artifacts and analytical lineage",
            "explanation": "Run-local or retained analytical artifact identities. Missing manifests remain explicit and cannot be treated as inspected content.",
            "items": references(
                tuple(sorted(set(proposal.artifact_ids + proposal.scenario_ids + proposal.model_receipt_ids))),
                kind="artifact_or_model_lineage",
                note="Identity retained for lineage; open the owning repository to verify content and rights.",
            ),
        },
        {
            "group_id": "capabilities",
            "title": "Capability receipts",
            "explanation": "Receipts identify reviewed calculations used upstream. Due diligence checks their presence without rerunning the calculation.",
            "items": references(
                proposal.capability_receipt_ids,
                kind="capability_receipt",
                note="Declared upstream capability receipt; receipt payload is not duplicated here.",
            ),
        },
        {
            "group_id": "policy",
            "title": "Mandate and policy",
            "explanation": proposal.mandate_relevance,
            "items": references(
                policy_ids,
                kind="policy",
                note="Human-only D1 review policy with financial and external effects disabled.",
            ),
        },
        {
            "group_id": "alternatives",
            "title": "Alternatives and consequences",
            "explanation": "All available reviewer outcomes remain distinct from the finding and from any later action.",
            "items": alternatives,
        },
    ]
    return {
        "workspace": {
            "schema_version": "portfolio-risk.decision-due-diligence-workspace/v1",
            "proposal_id": proposal.proposal_id,
            "proposal_digest": proposal.proposal_digest,
            "record_revision": record.record_revision,
            "state": record.state.value,
            "inspectable": True,
            "executable": record.state not in FINAL_STATES,
            "authority": "human_review_only_D1",
            "publication": "temporary_not_publishable",
            "external_effects": "disabled",
            "portfolio_effects": "disabled",
        },
        "proposal": proposal.model_dump(mode="json"),
        "reference_groups": groups,
        "modules": list(DUE_DILIGENCE_MODULES),
        "supplemental_evidence": [item.model_dump(mode="json") for item in record.supplemental_evidence],
        "investigation_runs": [item.model_dump(mode="json") for item in record.investigation_runs],
        "proposal_revisions": [item.model_dump(mode="json") for item in record.proposal_revisions],
        "lifecycle": [item.model_dump(mode="json") for item in record.lifecycle],
        "resolutions": [item.model_dump(mode="json") for item in record.resolutions],
    }


def catalogue_payload() -> dict[str, Any]:
    records = decision_store().list()
    return {
        "runtime": {
            "storage": "external_local_decision_repository",
            "authority": "human_review_only",
            "external_effects": "disabled",
            "portfolio_effects": "disabled",
            "follow_up_workflows": ["decision.investigate.effect-free.v1"],
        },
        "summary": {
            "proposals": len(records),
            "awaiting_review": sum(item.state.value == "awaiting_review" for item in records),
            "resolved": sum(item.state.value in {"resolved", "rejected"} for item in records),
        },
        "records": [record_payload(item) for item in records],
    }
