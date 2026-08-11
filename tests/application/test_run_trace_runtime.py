from datetime import datetime, timezone
from pathlib import Path

import fixture_context_runtime
import run_trace_runtime
from risk_experiments import build_calibration_pilot, calibration_acceptance_record, calibration_registry_projections
from risk_experiments.fixture_context import FixtureContextResolver, LocalFixtureContextStore
from risk_registry import LifecycleState, LocalRegistryStore


def test_run_trace_requires_resolved_fixture_and_retains_artifact(tmp_path, monkeypatch):
    registry = LocalRegistryStore(tmp_path / "registry")
    candidate = build_calibration_pilot()
    documents, conflicts = registry.index_many(calibration_registry_projections(Path(__file__).parents[2], discovered_at=datetime(2026, 8, 10, tzinfo=timezone.utc), repository_commit=None), actor="local.researcher")
    assert not conflicts
    for document in documents:
        registry.transition(document.projection.identity, to_state=LifecycleState.VALIDATED, actor="local.researcher", rationale="P8 test", expected_revision=document.receipts[-1].receipt_digest)
    resolved = FixtureContextResolver(registry, Path(__file__).parents[2]).resolve(candidate, calibration_acceptance_record(candidate), fixture_context_runtime.calibration_source_manifest(), resolved_at=candidate.world_context.data_manifest.as_of)
    store = LocalFixtureContextStore(tmp_path / "fixtures")
    store.save(resolved)
    monkeypatch.setattr(fixture_context_runtime, "fixture_store", lambda: store)
    monkeypatch.setattr(run_trace_runtime, "fixture_store", lambda: store)
    monkeypatch.setattr(run_trace_runtime, "FIXTURE_DIGEST", candidate.fixture_context_digest)
    from risk_artifacts import LocalArtifactRepository
    monkeypatch.setattr(run_trace_runtime, "artifact_store", lambda: LocalArtifactRepository(tmp_path / "artifacts"))
    value = run_trace_runtime.create_calibration_run_trace(actor="local.researcher")
    assert value["trace"]["labels_accessed"] is False
    assert value["manifest"]["kind"] == "retained_run"
