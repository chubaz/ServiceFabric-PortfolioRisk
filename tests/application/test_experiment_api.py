from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
LABS_ROOT = ROOT / "apps" / "portfolio-risk-workbench" / "labs"
sys.path.insert(0, str(LABS_ROOT))

import duckdb_server  # noqa: E402
from risk_experiments import DataTruth, PresentationMode  # noqa: E402
from risk_registry import AssetKind  # noqa: E402


def workflow_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PORTFOLIO_RISK_REGISTRY_ROOT", str(tmp_path / "registry"))
    projection = next(
        item
        for item in duckdb_server.discover_registry_projections()
        if item.identity.kind == AssetKind.WORKFLOW
    )
    return duckdb_server.registry_store().index(
        projection, actor="test.reviewer"
    ).projection.identity


def synthetic_portfolio_option():
    return next(
        item
        for item in duckdb_server._experiment_options_payload()["portfolios"]
        if item["data_truth"] == "reviewed_synthetic"
    )


def test_draft_validate_ready_enqueue_and_resume_controls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_EXPERIMENT_ROOT", str(tmp_path / "experiments"))
    system_asset = workflow_identity(tmp_path, monkeypatch)
    portfolio = synthetic_portfolio_option()
    created = duckdb_server.draft_experiment(
        duckdb_server.ExperimentDraftRequest(
            experiment_id="api-experiment-alpha",
            name="Daily risk review",
            purpose="Prepare a bounded daily portfolio risk review.",
            hypothesis="The workflow produces evidence-grounded review material.",
            start_date=date(2024, 1, 2),
            end_date=date(2024, 1, 5),
            presentation_mode=PresentationMode.INTERACTIVE_FOREGROUND,
            data_truth=DataTruth.REVIEWED_SYNTHETIC,
            portfolio_reference=portfolio["reference"],
            snapshot_policy_reference="snapshot-policy:available-at@v1",
            mandate_reference="mandate:research-default@v1",
            data_revision_reference=portfolio["data_revision_reference"],
            system_asset=system_asset,
        )
    )
    assert created["state"] == "draft"
    validated = duckdb_server.transition_experiment(
        "api-experiment-alpha",
        duckdb_server.ExperimentTransitionRequest(
            to_state="validated",
            rationale="Canonical bindings and system definition were reviewed.",
            idempotency_key="validate-api-alpha",
            expected_revision=created["revision"],
        ),
    )
    ready = duckdb_server.transition_experiment(
        "api-experiment-alpha",
        duckdb_server.ExperimentTransitionRequest(
            to_state="ready",
            rationale="The experiment is ready for explicit admission.",
            idempotency_key="ready-api-alpha",
            expected_revision=validated["revision"],
        ),
    )
    queued = duckdb_server.enqueue_experiment(
        "api-experiment-alpha",
        duckdb_server.ExperimentEnqueueRequest(
            idempotency_key="enqueue-api-alpha", expected_revision=ready["revision"]
        ),
    )
    assert queued["queue"]["status"] == "queued"
    assert queued["queue"]["job_kind"] == "workflow_replay"
    running = duckdb_server.control_experiment_queue(
        queued["queue"]["queue_id"],
        duckdb_server.ExperimentQueueControlRequest(
            action="start", resume_token=queued["queue"]["resume_token"]
        ),
    )
    assert running["experiment"]["state"] == "running"
    catalogue = duckdb_server.experiment_catalogue()
    assert catalogue["runtime"]["automatic_scheduler"] is False
    assert catalogue["runtime"]["external_effects"] == "disabled"
    assert catalogue["summary"]["experiments"] == 1


def test_evaluation_mode_requires_evaluation_asset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_EXPERIMENT_ROOT", str(tmp_path / "evaluation"))
    system_asset = workflow_identity(tmp_path, monkeypatch)
    portfolio = synthetic_portfolio_option()
    with pytest.raises(duckdb_server.HTTPException) as denied:
        duckdb_server.draft_experiment(
            duckdb_server.ExperimentDraftRequest(
                experiment_id="invalid-evaluation",
                name="Invalid evaluation",
                purpose="Attempt an incompatible assignment.",
                hypothesis="This must be rejected before persistence.",
                start_date=date(2024, 1, 2),
                end_date=date(2024, 1, 5),
                presentation_mode=PresentationMode.EVALUATION_ONLY,
                data_truth=DataTruth.REVIEWED_SYNTHETIC,
                portfolio_reference=portfolio["reference"],
                snapshot_policy_reference="snapshot-policy:available-at@v1",
                mandate_reference="mandate:research-default@v1",
                data_revision_reference=portfolio["data_revision_reference"],
                system_asset=system_asset,
            )
        )
    assert denied.value.status_code == 409
    assert "requires a evaluation" in denied.value.detail


def test_experiment_storage_inside_git_is_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_EXPERIMENT_ROOT", str(ROOT / "unsafe-experiments"))
    with pytest.raises(duckdb_server.HTTPException) as denied:
        duckdb_server.experiment_catalogue()
    assert denied.value.status_code == 409
    assert "outside Git" in denied.value.detail


def test_draft_rejects_portfolio_truth_misclassification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_EXPERIMENT_ROOT", str(tmp_path / "truth"))
    system_asset = workflow_identity(tmp_path, monkeypatch)
    synthetic = synthetic_portfolio_option()
    with pytest.raises(duckdb_server.HTTPException) as denied:
        duckdb_server.draft_experiment(
            duckdb_server.ExperimentDraftRequest(
                experiment_id="misclassified-source",
                name="Misclassified source",
                purpose="Attempt to misclassify a reviewed source.",
                hypothesis="The compiler must reject this mismatch.",
                start_date=date(2024, 1, 2),
                end_date=date(2024, 1, 5),
                presentation_mode=PresentationMode.INTERACTIVE_FOREGROUND,
                data_truth=DataTruth.LICENSED_REAL,
                portfolio_reference=synthetic["reference"],
                snapshot_policy_reference="snapshot-policy:available-at@v1",
                mandate_reference="mandate:research-default@v1",
                data_revision_reference=synthetic["data_revision_reference"],
                system_asset=system_asset,
            )
        )
    assert denied.value.status_code == 409
    assert "data-truth class" in denied.value.detail


def test_experiment_rejects_discovered_but_unsaved_system_asset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_REGISTRY_ROOT", str(tmp_path / "empty-registry"))
    monkeypatch.setenv("PORTFOLIO_RISK_EXPERIMENT_ROOT", str(tmp_path / "experiments"))
    portfolio = synthetic_portfolio_option()
    unsaved = next(
        item.identity
        for item in duckdb_server.discover_registry_projections()
        if item.identity.kind == AssetKind.WORKFLOW
    )
    with pytest.raises(duckdb_server.HTTPException) as denied:
        duckdb_server.draft_experiment(
            duckdb_server.ExperimentDraftRequest(
                experiment_id="unsaved-system-asset",
                name="Unsaved system asset",
                purpose="Verify the Registry admission boundary.",
                hypothesis="Source discovery alone must not authorize experimental use.",
                start_date=date(2024, 1, 2),
                end_date=date(2024, 1, 5),
                presentation_mode=PresentationMode.INTERACTIVE_FOREGROUND,
                data_truth=DataTruth.REVIEWED_SYNTHETIC,
                portfolio_reference=portfolio["reference"],
                snapshot_policy_reference="snapshot-policy:available-at@v1",
                mandate_reference="mandate:research-default@v1",
                data_revision_reference=portfolio["data_revision_reference"],
                system_asset=unsaved,
            )
        )
    assert denied.value.status_code == 409
    assert "must be saved in the Registry" in denied.value.detail


def test_platform_workspace_projection_separates_definitions_and_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workflow_identity(tmp_path, monkeypatch)
    payload = duckdb_server.platform_workspaces()
    assert [zone["zone_id"] for zone in payload["zones"]] == [
        "system", "application", "research"
    ]
    assert payload["terminology"]["artifact"].startswith("A run work product")
    assert payload["saved_counts"]["workflow"] == 1
    assert payload["saved_definitions"][0]["experiment_eligible"] is True
    assert {item["phase"] for item in payload["future_dependencies"]} >= {
        "PLATFORM-P7", "PLATFORM-P8", "PLATFORM-P9", "PLATFORM-P14", "PLATFORM-P15"
    }
