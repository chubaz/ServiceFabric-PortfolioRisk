from __future__ import annotations

from pathlib import Path

import pytest
from risk_experiments import ExperimentConflict, ExperimentSet, ExperimentState, LocalExperimentStore, PresentationMode

from .test_models import definition


def advance_ready(store: LocalExperimentStore, mode: PresentationMode = PresentationMode.INTERACTIVE_FOREGROUND):
    created = store.create(definition(mode=mode), actor="test.reviewer", idempotency_key="create-alpha")
    validated = store.transition(created.definition.experiment_id, ExperimentState.VALIDATED, actor="test.reviewer", rationale="Required bindings were reviewed.", idempotency_key="validate-alpha", expected_revision=created.revision)
    return store.transition(created.definition.experiment_id, ExperimentState.READY, actor="test.reviewer", rationale="Experiment is ready for queue admission.", idempotency_key="ready-alpha", expected_revision=validated.revision)


def test_store_is_restart_safe_and_queue_is_explicit(tmp_path: Path) -> None:
    store = LocalExperimentStore(tmp_path / "experiments")
    ready = advance_ready(store)
    queued, entry = store.enqueue(ready.definition.experiment_id, actor="test.reviewer", idempotency_key="enqueue-alpha", expected_revision=ready.revision)
    assert queued.state == ExperimentState.QUEUED
    assert entry.job_kind == "workflow_replay"
    restarted = LocalExperimentStore(tmp_path / "experiments")
    assert restarted.get("experiment-alpha").state == ExperimentState.QUEUED
    running, running_entry = restarted.update_queue(entry.queue_id, action="start", resume_token=entry.resume_token)
    assert running.state == ExperimentState.RUNNING
    repeated_running, repeated_entry = restarted.update_queue(entry.queue_id, action="start", resume_token=entry.resume_token)
    assert repeated_running.revision == running.revision
    assert repeated_entry == running_entry
    paused, _ = restarted.update_queue(entry.queue_id, action="pause", resume_token=entry.resume_token)
    assert paused.state == ExperimentState.PAUSED_FOR_DECISION


def test_evaluation_only_queue_cannot_request_workflow_execution(tmp_path: Path) -> None:
    store = LocalExperimentStore(tmp_path / "evaluation")
    ready = advance_ready(store, PresentationMode.EVALUATION_ONLY)
    _record, entry = store.enqueue(ready.definition.experiment_id, actor="test.reviewer", idempotency_key="enqueue-evaluation", expected_revision=ready.revision)
    assert entry.job_kind == "evaluate_existing_outputs"
    assert "agent and workflow execution are disabled" in entry.message


def test_optimistic_revision_and_idempotency_are_enforced(tmp_path: Path) -> None:
    store = LocalExperimentStore(tmp_path / "conflict")
    ready = advance_ready(store)
    with pytest.raises(ExperimentConflict, match="revision changed"):
        store.enqueue(ready.definition.experiment_id, actor="test.reviewer", idempotency_key="enqueue-alpha", expected_revision="sha256:" + "0" * 64)
    first, entry = store.enqueue(ready.definition.experiment_id, actor="test.reviewer", idempotency_key="enqueue-alpha", expected_revision=ready.revision)
    second, duplicate = store.enqueue(ready.definition.experiment_id, actor="test.reviewer", idempotency_key="enqueue-alpha", expected_revision=ready.revision)
    assert second.revision == first.revision
    assert duplicate == entry
