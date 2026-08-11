from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError
from risk_experiments import (
    FixtureContextResolver,
    FixtureSourceManifest,
    LocalFixtureContextStore,
    build_calibration_pilot,
    calibration_acceptance_record,
    calibration_registry_projections,
    calibration_source_manifest,
)
from risk_registry import LifecycleState, LocalRegistryStore


ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
RATIONALE = "Accepted for deterministic apparatus calibration only."


def admitted_store(tmp_path: Path, *, validate: bool = True) -> LocalRegistryStore:
    store = LocalRegistryStore(tmp_path / "registry")
    documents, conflicts = store.index_many(
        calibration_registry_projections(
            ROOT,
            discovered_at=NOW,
            repository_commit="a" * 40,
        ),
        actor="test.methodology-reviewer",
    )
    assert conflicts == []
    if validate:
        for document in documents:
            store.transition(
                document.projection.identity,
                LifecycleState.VALIDATED,
                actor="test.methodology-reviewer",
                rationale=RATIONALE,
                expected_revision=document.receipts[-1].receipt_digest,
                occurred_at=NOW + timedelta(seconds=1),
            )
    return store


def test_calibration_acceptance_is_bounded_and_names_the_exact_candidate() -> None:
    candidate = build_calibration_pilot()
    acceptance = calibration_acceptance_record(candidate)
    assert acceptance.decision == "accepted_for_apparatus_calibration"
    assert acceptance.scientific_design_identity == candidate.scientific_design.registry_identity
    assert acceptance.experiment_object_set_identity == candidate.registry_identity
    assert acceptance.fixture_context_digest == candidate.fixture_context_digest
    assert "thesis_inference" in acceptance.prohibited_claims
    assert "risk_mitigation" in acceptance.prohibited_claims
    assert len(acceptance.required_revisions) == 5


def test_calibration_outcome_has_four_operationally_ordered_states() -> None:
    outcome = build_calibration_pilot().scientific_design.risk_outcome
    assert [(item.state_id, item.ordinal) for item in outcome.states] == [
        ("optimal", 0),
        ("good", 1),
        ("bad", 2),
        ("very_bad", 3),
    ]
    assert [item.is_breach for item in outcome.states] == [False, False, True, True]
    assert "cannot claim risk mitigation or avoidance" in outcome.mitigation_rule


def test_fixture_resolution_requires_validated_top_level_definitions(tmp_path: Path) -> None:
    candidate = build_calibration_pilot()
    resolver = FixtureContextResolver(
        admitted_store(tmp_path, validate=False), ROOT
    )
    with pytest.raises(ValueError, match="validated or published"):
        resolver.resolve(
            candidate,
            calibration_acceptance_record(candidate),
            calibration_source_manifest(),
            resolved_at=NOW,
        )


def test_fixture_resolution_is_repeatable_and_receipts_are_append_only(tmp_path: Path) -> None:
    candidate = build_calibration_pilot()
    resolver = FixtureContextResolver(admitted_store(tmp_path), ROOT)
    first = resolver.resolve(
        candidate,
        calibration_acceptance_record(candidate),
        calibration_source_manifest(),
        resolved_at=NOW,
    )
    second = resolver.resolve(
        candidate,
        calibration_acceptance_record(candidate),
        calibration_source_manifest(),
        resolved_at=NOW + timedelta(minutes=1),
    )
    assert first.context == second.context
    assert first.context.fixture_context_digest == candidate.fixture_context_digest
    assert first.receipt.receipt_digest != second.receipt.receipt_digest
    assert first.context.external_effects == "disabled"
    assert first.context.supra_agent_enabled is False


def test_fixture_context_denies_labels_and_undeclared_resources(tmp_path: Path) -> None:
    candidate = build_calibration_pilot()
    resolved = FixtureContextResolver(admitted_store(tmp_path), ROOT).resolve(
        candidate,
        calibration_acceptance_record(candidate),
        calibration_source_manifest(),
        resolved_at=NOW,
    )
    context = resolved.context
    assert "data/fixtures/synthetic/thesis-day4/labels.parquet" in (
        context.sources.denied_references
    )
    assert not context.allows_capability("capability:risk:undeclared@1.0.0")
    assert not context.allows_dataset("dataset:risk:future-outcomes@1.0.0")


def test_resolved_context_and_each_receipt_survive_restart(tmp_path: Path) -> None:
    candidate = build_calibration_pilot()
    resolver = FixtureContextResolver(admitted_store(tmp_path), ROOT)
    first = resolver.resolve(
        candidate,
        calibration_acceptance_record(candidate),
        calibration_source_manifest(),
        resolved_at=NOW,
    )
    second = resolver.resolve(
        candidate,
        calibration_acceptance_record(candidate),
        calibration_source_manifest(),
        resolved_at=NOW + timedelta(minutes=1),
    )
    root = tmp_path / "fixture-contexts"
    LocalFixtureContextStore(root).save(first)
    LocalFixtureContextStore(root).save(second)
    reopened = LocalFixtureContextStore(root)
    assert reopened.get(candidate.fixture_context_digest) == first.context
    assert {item.receipt_digest for item in reopened.receipts(candidate.fixture_context_digest)} == {
        first.receipt.receipt_digest,
        second.receipt.receipt_digest,
    }


def test_fixture_resolution_detects_source_tampering(tmp_path: Path) -> None:
    candidate = build_calibration_pilot()
    manifest_payload = calibration_source_manifest().model_dump(mode="json")
    manifest_payload["bindings"][0]["content_digest"] = "sha256:" + "0" * 64
    manifest_payload["manifest_digest"] = None
    tampered = FixtureSourceManifest.model_validate(manifest_payload)
    with pytest.raises(ValueError, match="source digest mismatch"):
        FixtureContextResolver(admitted_store(tmp_path), ROOT).resolve(
            candidate,
            calibration_acceptance_record(candidate),
            tampered,
            resolved_at=NOW,
        )


def test_acceptance_tampering_is_rejected() -> None:
    payload = calibration_acceptance_record().model_dump(mode="json")
    payload["rationale"] = "Changed after review."
    with pytest.raises(ValidationError, match="acceptance_digest"):
        calibration_acceptance_record().model_validate(payload)
