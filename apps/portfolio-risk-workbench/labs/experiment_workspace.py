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


def set_payload(definition: ExperimentSet, store: LocalExperimentStore) -> dict[str, Any]:
    records = {item.definition.experiment_id: item for item in store.list()}
    queue = store.queue_entries()
    queue_by_experiment: dict[str, list[str]] = {}
    for item in queue:
        queue_by_experiment.setdefault(item.experiment_id, []).append(item.status)
    members = []
    for experiment_id in definition.experiment_ids:
        record = records[experiment_id]
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
        "comparison_ready": all(item["state"] in {"completed", "reviewed", "archived"} for item in members),
    }


def catalogue_payload() -> dict[str, Any]:
    store = experiment_store()
    records = store.list()
    queue = store.queue_entries()
    sets = store.list_sets()
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
        },
        "records": [record_payload(item) for item in records],
        "queue": [item.model_dump(mode="json") for item in queue],
        "sets": [set_payload(item, store) for item in sets],
    }
