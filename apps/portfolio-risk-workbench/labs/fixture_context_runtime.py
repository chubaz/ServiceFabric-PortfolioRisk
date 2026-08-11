"""Application projection for the accepted P7 calibration Fixture Context."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from risk_experiments import (
    FixtureContextResolver,
    LocalFixtureContextStore,
    build_calibration_pilot,
    calibration_acceptance_record,
    calibration_source_manifest,
)
from risk_registry import LifecycleState, RegistryNotFound


LABS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = LABS_ROOT.parents[2]
DEFAULT_FIXTURE_ROOT = (
    Path.home() / ".servicefabric-portfolio-risk" / "fixture-contexts-v1"
)
ELIGIBLE = {LifecycleState.VALIDATED, LifecycleState.PUBLISHED}
ACCEPTED_CALIBRATION_FIXTURE_DIGEST = (
    "sha256:2b2c347ecafa775853aad88f49b7565263726c17c61850d22e1b789d984761d9"
)


def fixture_store() -> LocalFixtureContextStore:
    return LocalFixtureContextStore(
        Path(os.environ.get("PORTFOLIO_RISK_FIXTURE_ROOT", DEFAULT_FIXTURE_ROOT))
    )


def calibration_fixture_payload(registry: Any) -> dict[str, Any]:
    try:
        accepted_context = fixture_store().get(ACCEPTED_CALIBRATION_FIXTURE_DIGEST)
    except KeyError:
        accepted_context = None
    candidate = accepted_context.object_set if accepted_context else build_calibration_pilot()
    acceptance = accepted_context.acceptance if accepted_context else calibration_acceptance_record(candidate)
    sources = accepted_context.sources if accepted_context else calibration_source_manifest()
    states: dict[str, str] = {}
    revisions: dict[str, str] = {}
    for identity in (
        candidate.scientific_design.registry_identity,
        candidate.registry_identity,
    ):
        try:
            document = registry.get(identity)
        except RegistryNotFound:
            states[identity.reference] = "not_registered"
            continue
        states[identity.reference] = document.state.value
        revisions[identity.reference] = document.receipts[-1].receipt_digest
    admitted = len(states) == 2 and all(value in {"validated", "published"} for value in states.values())
    try:
        context = fixture_store().get(candidate.fixture_context_digest)
        persisted = True
        receipt_count = len(fixture_store().receipts(candidate.fixture_context_digest))
    except KeyError:
        context = None
        persisted = False
        receipt_count = 0
    return {
        "status": "resolved" if persisted else "admitted" if admitted else "reviewed",
        "admitted": admitted,
        "persisted": persisted,
        "registry_states": states,
        "registry_revisions": revisions,
        "scientific_design": candidate.scientific_design.registry_identity.reference,
        "experiment_object_set": candidate.registry_identity.reference,
        "fixture_context_digest": candidate.fixture_context_digest,
        "source_manifest_digest": sources.manifest_digest,
        "acceptance_reference": acceptance.reference,
        "approved_uses": acceptance.approved_uses,
        "prohibited_claims": acceptance.prohibited_claims,
        "question": candidate.scientific_design.research_question.question,
        "baseline": candidate.scientific_design.baseline.name,
        "outcome_states": [item.label for item in candidate.scientific_design.risk_outcome.states],
        "metric": candidate.scientific_design.metric.name,
        "reachable_capabilities": [
            item.reference
            for item in candidate.resource_envelope.capability_pack.capabilities
        ],
        "reachable_datasets": [
            item.reference for item in candidate.world_context.data_manifest.datasets
        ],
        "denied_references": sources.denied_references,
        "external_effects": "disabled",
        "supra_agent_enabled": False,
        "resolution_receipts": receipt_count,
        "resolved_context_verified": bool(
            context and context.fixture_context_digest == candidate.fixture_context_digest
        ),
    }


def resolve_calibration_fixture(registry: Any) -> dict[str, Any]:
    try:
        accepted_context = fixture_store().get(ACCEPTED_CALIBRATION_FIXTURE_DIGEST)
    except KeyError:
        accepted_context = None
    candidate = accepted_context.object_set if accepted_context else build_calibration_pilot()
    acceptance = accepted_context.acceptance if accepted_context else calibration_acceptance_record(candidate)
    sources = accepted_context.sources if accepted_context else calibration_source_manifest()
    resolved = FixtureContextResolver(registry, REPOSITORY_ROOT).resolve(
        candidate,
        acceptance,
        sources,
        resolved_at=datetime.now(timezone.utc),
    )
    fixture_store().save(resolved)
    payload = calibration_fixture_payload(registry)
    payload["resolution_receipt"] = resolved.receipt.model_dump(mode="json")
    return payload
