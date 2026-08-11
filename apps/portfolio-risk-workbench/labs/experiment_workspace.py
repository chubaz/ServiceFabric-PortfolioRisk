"""Application projection for the external experiment workspace."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from risk_experiments import ExperimentRecord, ExperimentSet, LocalExperimentStore


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def experiment_store() -> LocalExperimentStore:
    configured = os.getenv("PORTFOLIO_RISK_EXPERIMENT_ROOT")
    root = (
        Path(configured).expanduser().absolute()
        if configured
        else Path.home() / ".servicefabric-portfolio-risk" / "experiments-v1"
    )
    if root == REPOSITORY_ROOT or root.is_relative_to(REPOSITORY_ROOT):
        raise ValueError("PORTFOLIO_RISK_EXPERIMENT_ROOT must remain outside Git")
    return LocalExperimentStore(root)


def record_payload(record: ExperimentRecord) -> dict[str, Any]:
    return {
        "definition": record.definition.model_dump(mode="json"),
        "state": record.state.value,
        "revision": record.revision,
        "receipts": [item.model_dump(mode="json") for item in record.receipts],
    }


def set_payload(
    definition: ExperimentSet,
    store: LocalExperimentStore,
    *,
    records: dict[str, ExperimentRecord] | None = None,
    queue: list[Any] | None = None,
) -> dict[str, Any]:
    records = (
        records
        if records is not None
        else {item.definition.experiment_id: item for item in store.list()}
    )
    queue = queue if queue is not None else store.queue_entries()
    queue_by_experiment: dict[str, list[str]] = {}
    for item in queue:
        queue_by_experiment.setdefault(item.experiment_id, []).append(item.status)
    members = []
    issues = []
    for experiment_id in definition.experiment_ids:
        record = records.get(experiment_id)
        if record is None:
            issues.append(
                {
                    "code": "missing_experiment_member",
                    "set_id": definition.experiment_set_id,
                    "experiment_id": experiment_id,
                    "message": (
                        f"Comparison set {definition.experiment_set_id} references missing experiment "
                        f"{experiment_id}. Recreate the definition or replace the set."
                    ),
                }
            )
            members.append(
                {
                    "experiment_id": experiment_id,
                    "name": "Unavailable experiment",
                    "mode": "unavailable",
                    "data_truth": "unavailable",
                    "state": "missing",
                    "queue_states": queue_by_experiment.get(experiment_id, []),
                    "definition_digest": None,
                }
            )
            continue
        members.append(
            {
                "experiment_id": experiment_id,
                "name": record.definition.name,
                "mode": record.definition.presentation_mode.value,
                "data_truth": record.definition.data_truth.value,
                "state": record.state.value,
                "queue_states": queue_by_experiment.get(experiment_id, []),
                "definition_digest": record.definition.definition_digest,
            }
        )
    planned_runs = len(definition.experiment_ids) * len(definition.seeds) * definition.repeat_count
    return {
        "definition": definition.model_dump(mode="json"),
        "members": members,
        "planned_runs": planned_runs,
        "comparison_ready": not issues
        and all(item["state"] in {"completed", "reviewed", "archived"} for item in members),
        "issues": issues,
    }


def catalogue_payload() -> dict[str, Any]:
    store = experiment_store()
    records = store.list()
    queue = store.queue_entries()
    sets = store.list_sets()
    records_by_id = {item.definition.experiment_id: item for item in records}
    set_projections = [
        set_payload(item, store, records=records_by_id, queue=queue) for item in sets
    ]
    issues = [issue for item in set_projections for issue in item["issues"]]
    for entry in queue:
        if entry.experiment_id not in records_by_id:
            issues.append(
                {
                    "code": "orphaned_queue_entry",
                    "queue_id": entry.queue_id,
                    "experiment_id": entry.experiment_id,
                    "message": (
                        f"Queue entry {entry.queue_id} references missing experiment "
                        f"{entry.experiment_id}. It cannot be controlled from this workspace."
                    ),
                }
            )
    return {
        "runtime": {
            "storage": "external_local_metadata",
            "worker": "explicit_local_controller_only",
            "automatic_scheduler": False,
            "external_effects": "disabled",
            "resumable": True,
        },
        "summary": {
            "experiments": len(records),
            "ready_or_active": sum(item.state.value in {"ready", "queued", "running", "paused_for_decision"} for item in records),
            "queued_jobs": sum(item.status in {"queued", "running", "paused"} for item in queue),
            "experiment_sets": len(sets),
            "issues": len(issues),
        },
        "records": [record_payload(item) for item in records],
        "queue": [item.model_dump(mode="json") for item in queue],
        "sets": set_projections,
        "issues": issues,
    }
