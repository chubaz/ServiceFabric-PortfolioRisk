#!/usr/bin/env python3
"""End-to-end, temporary-store tutorial for the P7 calibration Fixture Context."""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
for path in (
    ROOT / "packages" / "risk_experiments" / "src",
    ROOT / "packages" / "risk_registry" / "src",
):
    sys.path.insert(0, str(path))

from risk_experiments import (  # noqa: E402
    FixtureContextResolver,
    LocalFixtureContextStore,
    build_calibration_pilot,
    calibration_acceptance_record,
    calibration_registry_projections,
    calibration_source_manifest,
)
from risk_registry import LifecycleState, LocalRegistryStore  # noqa: E402


NOW = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)


def main() -> int:
    candidate = build_calibration_pilot()
    acceptance = calibration_acceptance_record(candidate)
    sources = calibration_source_manifest()
    with tempfile.TemporaryDirectory(prefix="portfolio-risk-p7-tutorial-") as temporary:
        root = Path(temporary).resolve()
        registry = LocalRegistryStore(root / "registry")
        documents, conflicts = registry.index_many(
            calibration_registry_projections(
                ROOT,
                discovered_at=NOW,
                repository_commit="tutorial-working-candidate",
            ),
            actor="tutorial.reviewer",
        )
        assert conflicts == []
        for document in documents:
            registry.transition(
                document.projection.identity,
                LifecycleState.VALIDATED,
                actor="tutorial.reviewer",
                rationale="Validate the temporary apparatus-calibration tutorial candidate.",
                expected_revision=document.receipts[-1].receipt_digest,
                occurred_at=NOW,
            )
        resolver = FixtureContextResolver(registry, ROOT)
        first = resolver.resolve(candidate, acceptance, sources, resolved_at=NOW)
        second = resolver.resolve(
            candidate,
            acceptance,
            sources,
            resolved_at=NOW + timedelta(minutes=1),
        )
        store = LocalFixtureContextStore(root / "fixture-contexts")
        store.save(first)
        store.save(second)
        reopened = LocalFixtureContextStore(root / "fixture-contexts")
        result = {
            "status": "PASS",
            "purpose": "apparatus_calibration_only",
            "not_thesis_evidence": True,
            "acceptance": {
                "reference": acceptance.reference,
                "approved_uses": acceptance.approved_uses,
                "prohibited_claims": acceptance.prohibited_claims,
            },
            "context": {
                "digest": first.context.fixture_context_digest,
                "same_on_repeat": first.context == second.context,
                "reachable_capabilities": first.context.reachable_capability_references,
                "reachable_datasets": first.context.reachable_dataset_references,
                "denied_references": first.context.sources.denied_references,
                "external_effects": first.context.external_effects,
                "supra_agent_enabled": first.context.supra_agent_enabled,
            },
            "persistence": {
                "restart_safe": reopened.get(candidate.fixture_context_digest) == first.context,
                "resolution_receipts": len(
                    reopened.receipts(candidate.fixture_context_digest)
                ),
            },
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
