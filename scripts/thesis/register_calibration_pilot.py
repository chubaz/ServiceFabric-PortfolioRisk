#!/usr/bin/env python3
"""Preview or admit the exact calibration pilot to the local Registry."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
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


DEFAULT_ROOT = Path.home() / ".servicefabric-portfolio-risk" / "registry-v1"
DEFAULT_FIXTURE_ROOT = (
    Path.home() / ".servicefabric-portfolio-risk" / "fixture-contexts-v1"
)
ACTOR = "local.researcher.delegated-review"
RATIONALE = (
    "Accepted under explicit user delegation for apparatus calibration and P7 Fixture "
    "Context development only; thesis inference and effect claims remain prohibited."
)


def _repository_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--registry-root",
        type=Path,
        default=Path(os.environ.get("PORTFOLIO_RISK_REGISTRY_ROOT", DEFAULT_ROOT)),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Index and validate the two accepted top-level definitions.",
    )
    parser.add_argument(
        "--fixture-root",
        type=Path,
        default=Path(
            os.environ.get("PORTFOLIO_RISK_FIXTURE_ROOT", DEFAULT_FIXTURE_ROOT)
        ),
    )
    args = parser.parse_args()
    observed_at = datetime.now(timezone.utc)
    candidate = build_calibration_pilot()
    acceptance = calibration_acceptance_record(candidate)
    sources = calibration_source_manifest()
    projections = calibration_registry_projections(
        ROOT,
        discovered_at=observed_at,
        repository_commit=_repository_commit(),
    )
    payload: dict[str, object] = {
        "mode": "apply" if args.apply else "preview",
        "registry_root": str(args.registry_root.expanduser().absolute()),
        "fixture_root": str(args.fixture_root.expanduser().absolute()),
        "scientific_design": candidate.scientific_design.registry_identity.reference,
        "scientific_design_digest": candidate.scientific_design.pack_digest,
        "experiment_object_set": candidate.registry_identity.reference,
        "fixture_context_digest": candidate.fixture_context_digest,
        "acceptance_reference": acceptance.reference,
        "source_manifest_digest": sources.manifest_digest,
        "approved_use": list(acceptance.approved_uses),
        "prohibited_claims": list(acceptance.prohibited_claims),
    }
    if args.apply:
        store = LocalRegistryStore(args.registry_root)
        documents, conflicts = store.index_many(
            projections,
            actor=ACTOR,
        )
        if conflicts:
            raise RuntimeError("; ".join(conflicts))
        validated = []
        for document in documents:
            if document.state is LifecycleState.CANDIDATE:
                document = store.transition(
                    document.projection.identity,
                    LifecycleState.VALIDATED,
                    actor=ACTOR,
                    rationale=RATIONALE,
                    expected_revision=document.receipts[-1].receipt_digest,
                    occurred_at=observed_at,
                )
            if document.state not in {LifecycleState.VALIDATED, LifecycleState.PUBLISHED}:
                raise RuntimeError(
                    f"unexpected admission state: {document.projection.identity.reference} "
                    f"is {document.state.value}"
                )
            validated.append(document)
        resolved = FixtureContextResolver(store, ROOT).resolve(
            candidate,
            acceptance,
            sources,
            resolved_at=observed_at,
        )
        LocalFixtureContextStore(args.fixture_root).save(resolved)
        payload["registry_states"] = {
            document.projection.identity.reference: document.state.value
            for document in validated
        }
        payload["resolution_receipt"] = resolved.receipt.model_dump(mode="json")
        payload["fixture_persisted"] = True
        payload["status"] = "VALIDATED_AND_RESOLVED"
    else:
        payload["status"] = "PREVIEW_ONLY"
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
