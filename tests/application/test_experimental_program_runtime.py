from pathlib import Path

import experimental_program_runtime
from risk_experiments import FixtureContext, LocalFixtureContextStore, build_calibration_pilot, calibration_acceptance_record, calibration_source_manifest


def test_program_projection_counts_real_fixture_cases(tmp_path, monkeypatch):
    candidate = build_calibration_pilot()
    context = FixtureContext(
        object_set=candidate, acceptance=calibration_acceptance_record(candidate), sources=calibration_source_manifest(),
        reachable_capability_references=tuple(item.reference for item in candidate.resource_envelope.capability_pack.capabilities),
        reachable_dataset_references=tuple(item.reference for item in candidate.world_context.data_manifest.datasets),
        fixture_context_digest=candidate.fixture_context_digest,
    )
    store = LocalFixtureContextStore(tmp_path / "fixture")
    store._ensure_root()
    key = context.fixture_context_digest.removeprefix("sha256:")
    store._write_once(store.contexts_root / f"{key}.json", (context.model_dump_json(indent=2) + "\n").encode())
    monkeypatch.setattr(experimental_program_runtime, "fixture_store", lambda: store)
    monkeypatch.setattr(experimental_program_runtime, "FIXTURE_DIGEST", context.fixture_context_digest)
    value = experimental_program_runtime.experimental_program_payload()
    assert len(value["arm_plan"]["cases"]) == 15
    assert value["arm_plan"]["expected_outputs"] == 30
    assert value["matrix"]["planned_observations"] == 60
    assert value["boundary"]["outputs_generated"] is False
