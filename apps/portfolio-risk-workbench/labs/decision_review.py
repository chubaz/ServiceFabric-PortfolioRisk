"""Application projection for persistent, human-owned Decision Review records."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from risk_decisions import DecisionRecord, LocalDecisionStore


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
