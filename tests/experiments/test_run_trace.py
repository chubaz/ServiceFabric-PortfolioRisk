from datetime import datetime, timezone

from risk_experiments import build_calibration_pilot, calibration_acceptance_record, calibration_source_manifest
from risk_experiments.fixture_context import FixtureContext
from risk_experiments.run_trace import build_effect_free_trace


def test_effect_free_trace_uses_only_declared_context():
    candidate = build_calibration_pilot()
    context = FixtureContext(
        object_set=candidate,
        acceptance=calibration_acceptance_record(candidate),
        sources=calibration_source_manifest(),
        reachable_capability_references=tuple(item.reference for item in candidate.resource_envelope.capability_pack.capabilities),
        reachable_dataset_references=tuple(item.reference for item in candidate.world_context.data_manifest.datasets),
        fixture_context_digest=candidate.fixture_context_digest,
    )
    trace = build_effect_free_trace(context, created_at=datetime(2026, 8, 10, tzinfo=timezone.utc))
    assert trace.selected_capability_reference in context.reachable_capability_references
    assert trace.accessed_dataset_references == context.reachable_dataset_references
    assert trace.labels_accessed is False
    assert trace.metric_calculated is False
    assert trace.external_effects == "disabled"
