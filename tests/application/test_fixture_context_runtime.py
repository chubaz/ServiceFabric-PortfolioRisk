from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fixture_context_runtime import (
    calibration_fixture_payload,
    resolve_calibration_fixture,
)
from risk_experiments import calibration_registry_projections
from risk_registry import LifecycleState, LocalRegistryStore


ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 10, tzinfo=timezone.utc)


def registry(tmp_path: Path, *, validate: bool) -> LocalRegistryStore:
    value = LocalRegistryStore(tmp_path / "registry")
    documents, conflicts = value.index_many(
        calibration_registry_projections(
            ROOT,
            discovered_at=NOW,
            repository_commit="b" * 40,
        ),
        actor="test.reviewer",
    )
    assert conflicts == []
    if validate:
        for document in documents:
            value.transition(
                document.projection.identity,
                LifecycleState.VALIDATED,
                actor="test.reviewer",
                rationale="Accepted for application-level calibration testing.",
                expected_revision=document.receipts[-1].receipt_digest,
                occurred_at=NOW,
            )
    return value


def test_fixture_payload_separates_reviewed_admitted_and_resolved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_FIXTURE_ROOT", str(tmp_path / "fixtures"))
    admitted = registry(tmp_path, validate=True)
    before = calibration_fixture_payload(admitted)
    assert before["status"] == "admitted"
    assert before["persisted"] is False
    assert before["prohibited_claims"]
    after = resolve_calibration_fixture(admitted)
    assert after["status"] == "resolved"
    assert after["persisted"] is True
    assert after["resolved_context_verified"] is True
    assert after["resolution_receipts"] == 1
    assert after["external_effects"] == "disabled"


def test_application_resolution_rejects_candidate_only_registry_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_FIXTURE_ROOT", str(tmp_path / "fixtures"))
    candidate_only = registry(tmp_path, validate=False)
    assert calibration_fixture_payload(candidate_only)["status"] == "reviewed"
    with pytest.raises(ValueError, match="validated or published"):
        resolve_calibration_fixture(candidate_only)
