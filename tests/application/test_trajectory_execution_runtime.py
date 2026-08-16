from datetime import datetime, timezone
from types import SimpleNamespace

from risk_artifacts import DataTruthClass, LocalArtifactRepository, RightsState

import trajectory_execution_runtime as runtime


NOW = datetime(2015, 8, 25, 9, 0, tzinfo=timezone.utc)


def _trajectory():
    receipt = SimpleNamespace(
        processing_wall_ms=12.5,
        replay_triggered_at=NOW,
        replay_paused_at=NOW,
        replay_resumed_at=NOW,
    )
    cycle = SimpleNamespace(
        context=SimpleNamespace(
            cycle_id="cycle-one", replay_at=NOW,
            trigger=SimpleNamespace(kind="event_available"),
            eligible_observations=(SimpleNamespace(observation_id="event-one", kind="event"),),
        ),
        result=SimpleNamespace(
            architecture_output=None, status="abstained",
            reason="No new material evidence.", capability_calls=0, model_calls=0,
        ),
        processing_receipt=receipt,
    )
    return SimpleNamespace(
        trajectory_id="trajectory-one", run_id="run-one", matrix_id="matrix-one",
        cell_id="cell-one", case_id="case-one", status="completed_with_abstentions",
        cycles=(cycle,), completed_at=NOW,
        trajectory_digest="sha256:" + "a" * 64,
    )


def test_presentation_artifact_is_idempotent_and_excluded_from_evaluation(
    tmp_path, monkeypatch,
) -> None:
    store = LocalArtifactRepository(tmp_path / "artifacts")
    monkeypatch.setattr(runtime, "artifact_store", lambda: store)
    monkeypatch.setattr(
        runtime, "matched_run_store",
        lambda: SimpleNamespace(get=lambda _matrix_id: SimpleNamespace(experiment_id="experiment-one")),
    )
    trajectory = _trajectory()

    first = runtime._ensure_presentation_artifact(trajectory, "A1")
    second = runtime._ensure_presentation_artifact(trajectory, "A1")
    record = store.get(first)
    timeline = runtime._trajectory_timeline(trajectory, "A1")

    assert first == second
    assert record.manifest.data_truth == DataTruthClass.LICENSED_REAL
    assert record.manifest.rights == RightsState.LICENSED_RESTRICTED
    assert "excluded_from_evaluation" in record.manifest.restrictions
    assert record.manifest.entry_file == runtime.PRESENTATION_FILE
    assert timeline["presentation_excluded_from_evaluation"] is True
    assert timeline["gold_reference_visible"] is False
    assert timeline["cycles"][0]["simulated_time_frozen"] is True
