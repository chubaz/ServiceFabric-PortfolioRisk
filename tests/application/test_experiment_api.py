from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
LABS_ROOT = ROOT / "apps" / "portfolio-risk-workbench" / "labs"
sys.path.insert(0, str(LABS_ROOT))

import duckdb_server  # noqa: E402
import experiment_workspace  # noqa: E402
import historical_replay_runtime  # noqa: E402
from risk_experiments import (  # noqa: E402
    DataTruth,
    ExperimentDefinition,
    ExperimentSet,
    PresentationMode,
    SourceBinding,
    TemporalWindow,
    canonical_digest,
)
from risk_registry import (  # noqa: E402
    AssetKind,
    Provenance,
    RegistryIdentity,
    RegistryProjection,
    SourceReference,
)


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


def test_experiment_options_declare_real_data_without_synthetic_fallback() -> None:
    options = duckdb_server._experiment_options_payload()
    real = [item for item in options["portfolios"] if item["data_truth"] == "licensed_real"]

    assert options["licensed_data"]["available"] is bool(real)
    assert options["licensed_data"]["access"] == "read_only"
    assert options["licensed_data"]["synthetic_fallback"] is False
    assert all(item["position_count"] > 0 for item in real)
    assert all(item["base_currency"] for item in real)


def test_metadata_remains_available_without_private_licensed_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unavailable_plane = duckdb_server.LazyReadOnlyDataPlane()
    monkeypatch.setattr(duckdb_server, "data_plane", unavailable_plane)

    def unavailable_root(_start: Path) -> Path:
        raise RuntimeError("private test data is absent")

    monkeypatch.setattr(duckdb_server, "find_private_root", unavailable_root)

    options = duckdb_server._experiment_options_payload()
    assert options["licensed_data"] == {
        "available": False,
        "status": "unavailable",
        "unavailable_reason": "licensed data root is not configured",
        "source_snapshot_id": None,
        "selection_id": None,
        "access": "read_only",
        "synthetic_fallback": False,
    }
    assert not [
        item for item in options["portfolios"] if item["data_truth"] == "licensed_real"
    ]
    assert [
        item for item in options["portfolios"] if item["data_truth"] == "reviewed_synthetic"
    ]
    assert duckdb_server.platform_workspaces()["portfolios"] == []

    with pytest.raises(RuntimeError, match="private test data is absent"):
        duckdb_server.portfolios()


def scientific_design_projection(identity: RegistryIdentity) -> RegistryProjection:
    return RegistryProjection(
        identity=identity,
        display_name="Scientific comparison design",
        summary="Exact thesis question, hypothesis, baseline, information regime, risk outcome and metric.",
        source=SourceReference(
            source_type="scientific_design_pack",
            source_reference="tests:scientific-design-pack",
            source_digest="a" * 64,
            definition_digest="b" * 64,
            native_version=identity.version,
            adapter_id="tests.scientific-design",
            adapter_digest="c" * 64,
        ),
        provenance=Provenance(
            discovered_by="tests.fixture",
            discovered_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        ),
        source_contract="ScientificDesignPack",
        tags=("scientific-design",),
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


def test_catalogue_isolates_a_comparison_set_with_a_missing_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = ExperimentSet(
        experiment_set_id="set-with-missing-member",
        name="Recoverable comparison",
        research_question="Can valid workspace state remain visible after a definition is lost?",
        owner="local.researcher",
        experiment_ids=("missing-experiment",),
        created_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
    )

    class StoreWithOrphanedSet:
        def list(self):
            return ()

        def queue_entries(self):
            return ()

        def list_sets(self):
            return (definition,)

    monkeypatch.setattr(experiment_workspace, "experiment_store", StoreWithOrphanedSet)
    payload = experiment_workspace.catalogue_payload()

    assert payload["summary"]["issues"] == 1
    assert payload["sets"][0]["comparison_ready"] is False
    assert payload["sets"][0]["members"][0]["state"] == "missing"
    assert payload["issues"][0]["code"] == "missing_experiment_member"


def _counterfactual_run_result(workflow_id: str, repetition: int) -> dict:
    case_id = "case-portfolio-01-2020-01-01-2020-01-03"
    model_calls = 0 if workflow_id == "B0" else 1
    return {
        "run_id": f"run-{workflow_id.lower()}-{repetition}",
        "workflow": {"id": workflow_id},
        "hierarchy": {
            "case": {"case_id": case_id, "context_digest": "sha256:" + "a" * 64},
            "regimes": [{"dimension": "volatility", "value": "high"}],
        },
        "portfolio": {"id": "portfolio-01"},
        "mandate": {"reference": "mandate:portfolio-risk:01@1.0.0"},
        "period": {"start": "2020-01-01", "end": "2020-01-03"},
        "execution_regime": {
            "resource_usage": {
                "processing_wall_ms": 10.0,
                "model_calls": model_calls,
                "input_tokens": model_calls * 10,
                "output_tokens": model_calls * 2,
                "estimated_cost_usd": model_calls * 0.01,
            }
        },
        "evaluation": {
            "id": "thesis_evaluation_v1",
            "dimensions": [
                {
                    "id": dimension_id,
                    "status": "partial",
                    "summary": "Retained observation only.",
                    "metrics": {},
                }
                for dimension_id in (
                    "detection_quality",
                    "severity_understanding",
                    "timeliness",
                    "evidence_quality",
                    "confidence_calibration",
                    "decision_quality",
                    "robustness",
                    "stability",
                    "efficiency",
                )
            ],
        },
        "run_record": {
            "run_input": {"information_regime": "market-events", "repetition": repetition},
            "run_trace": {"wall_clock_ms": 10.0},
            "finding_episodes": [],
            "architecture_outputs": [
                {
                    "assessment_state": "clear",
                    "severity": 0,
                    "confidence": 0.5,
                    "findings": [],
                    "decision": {
                        "monitoring_action": "continue_monitoring",
                        "portfolio_action": "none",
                        "human_review_required": False,
                    },
                }
            ],
        },
    }


def test_counterfactual_studio_exposes_hierarchy_and_dimension_roles() -> None:
    payload = duckdb_server.counterfactual_dimensions()
    dimensions = {item["id"]: item for item in payload["dimensions"]}

    assert payload["hierarchy"] == ["study", "experiment", "case", "run"]
    assert payload["regime_role"] == "cross_cutting_case_classification"
    assert dimensions["architecture"]["execution_state"] == "available"
    assert dimensions["portfolio_action"]["kind"] == "financial_counterfactual"
    assert dimensions["regime"]["kind"] == "conditioning_variable"


def test_counterfactual_batch_executes_cells_and_returns_terminal_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def fake_run(_private_root, **kwargs):
        calls.append(kwargs)
        return _counterfactual_run_result(kwargs["workflow_id"], kwargs["repetition"])

    monkeypatch.setattr(duckdb_server, "find_private_root", lambda _root: tmp_path)
    monkeypatch.setattr(duckdb_server, "run_historical_replay", fake_run)
    monkeypatch.setattr(
        duckdb_server,
        "_save_historical_replay",
        lambda value: {
            "artifact_id": f"historical-replay:{value['run_id']}",
            "saved_at": "2026-08-11T00:00:00+00:00",
            "state": "active",
        },
    )
    monkeypatch.setattr(
        duckdb_server,
        "_save_counterfactual_analysis",
        lambda _definition, analysis: {
            "artifact_id": "counterfactual-analysis:experiment-01:test",
            "artifact_digest": analysis["analysis_digest"],
            "created_at": analysis["generated_at"],
            "state": "active",
        },
    )
    request = duckdb_server.CounterfactualBatchRequest(
        study_id="study-01",
        study_title="Portfolio risk architecture study",
        experiment_id="experiment-01",
        research_question="Does architecture change the same Case output?",
        hypothesis="The architecture treatments produce different retained observations.",
        portfolio_ids=("portfolio-01",),
        workflow_ids=("B0", "B1"),
        start_date=date(2020, 1, 1),
        end_date=date(2020, 1, 3),
        repetitions=2,
        max_concurrency=2,
        authorize_external_model_calls=True,
    )

    payload = duckdb_server.create_counterfactual_batch(request)

    assert len(calls) == 4
    assert {item["workflow_id"] for item in calls} == {"B0", "B1"}
    assert {item["repetition"] for item in calls} == {1, 2}
    assert payload["definition"]["regime_role"] == "cross_cutting_case_classification"
    assert payload["analysis"]["status"] == "complete"
    assert payload["analysis"]["matrix_coverage"]["completed"] == 4
    assert len(payload["analysis"]["contrasts"]) == 2
    assert len(payload["run_artifacts"]) == 4


def test_counterfactual_batch_requires_explicit_model_authorization() -> None:
    request = duckdb_server.CounterfactualBatchRequest(
        study_id="study-01",
        study_title="Portfolio risk architecture study",
        experiment_id="experiment-01",
        research_question="Does architecture change the same Case output?",
        hypothesis="The architecture treatments produce different retained observations.",
        portfolio_ids=("portfolio-01",),
        workflow_ids=("B0", "A1"),
        start_date=date(2020, 1, 1),
        end_date=date(2020, 1, 3),
    )

    with pytest.raises(duckdb_server.HTTPException) as denied:
        duckdb_server.create_counterfactual_batch(request)

    assert denied.value.status_code == 422
    assert "explicit authorization" in denied.value.detail


def test_counterfactual_terminal_analysis_is_retained_as_its_own_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    definition = {
        "study": {"study_id": "study-01", "title": "S" * 300},
        "experiment": {"experiment_id": "experiment-01"},
    }
    analysis = {
        "analysis_digest": canonical_digest({"experiment_id": "experiment-01"}),
        "study_id": "study-01",
        "experiment_id": "experiment-01",
        "status": "partial",
        "generated_at": "2026-08-11T00:00:00+00:00",
        "matrix_coverage": {"planned": 2, "completed": 0, "failed": 0, "missing": 2, "fraction": 0.0},
        "cells": [],
    }

    saved = duckdb_server._save_counterfactual_analysis(definition, analysis)
    record = duckdb_server.artifact_store().get(saved["artifact_id"])
    loaded = duckdb_server.load_counterfactual_batch(saved["artifact_id"])

    assert record.manifest.kind.value == "evidence_bundle"
    assert len(record.manifest.title) == 200
    assert record.manifest.parent_artifact_ids == ()
    assert {item.path for item in record.manifest.files} == {
        "batch-definition.json",
        "counterfactual-analysis.json",
        "experiment-assurance-report.md",
        "shortcomings.json",
    }
    assert loaded["definition"] == definition
    assert loaded["analysis"] == analysis
    assert duckdb_server.list_counterfactual_batches()["analyses"][0]["analysis_digest"] == analysis["analysis_digest"]


def test_research_catalogues_ignore_tombstoned_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class TombstonedStore:
        def list(self):
            return [
                SimpleNamespace(
                    manifest=SimpleNamespace(creation_method="deterministic_historical_replay"),
                    state=SimpleNamespace(value="tombstoned"),
                ),
                SimpleNamespace(
                    manifest=SimpleNamespace(creation_method="experiment-lab.counterfactual-terminal-analysis"),
                    state=SimpleNamespace(value="tombstoned"),
                ),
            ]

        def open_file(self, *_args, **_kwargs):
            raise AssertionError("tombstoned evidence must not be opened")

    monkeypatch.setattr(duckdb_server, "artifact_store", TombstonedStore)

    assert duckdb_server._saved_historical_replays() == []
    assert duckdb_server._counterfactual_analysis_artifacts() == []


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


def test_experiment_requires_its_scientific_design_pack_to_be_saved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_EXPERIMENT_ROOT", str(tmp_path / "experiments"))
    system_asset = workflow_identity(tmp_path, monkeypatch)
    design_identity = RegistryIdentity(
        kind=AssetKind.SCIENTIFIC_DESIGN,
        namespace="portfolio-risk.thesis",
        asset_id="information-value-b0",
        version="1.0.0",
    )
    object_set_identity = RegistryIdentity(
        kind=AssetKind.EXPERIMENT_OBJECT_SET,
        namespace="portfolio-risk.thesis",
        asset_id="pilot-object-set",
        version="1.0.0",
    )
    raw_bindings = {
        "portfolio": "portfolio-fixture:alpha@v1",
        "snapshot_policy": "snapshot-policy:available-at@v1",
        "mandate": "mandate:research-default@v1",
        "data_revision": "fixture:portfolio-risk-thesis@v1",
    }
    definition = ExperimentDefinition(
        experiment_id="experiment-scientific-design-api",
        version="1.0.0",
        name="Scientific design Registry gate",
        purpose="Require the complete scientific design pack before experiment admission.",
        hypothesis="The governed treatment improves the predeclared risk-quality metric.",
        owner="test.reviewer",
        created_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        temporal=TemporalWindow(
            start_date=date(2024, 1, 2), end_date=date(2024, 1, 5)
        ),
        presentation_mode=PresentationMode.INTERACTIVE_FOREGROUND,
        data_truth=DataTruth.REVIEWED_SYNTHETIC,
        source_bindings=tuple(
            SourceBinding(
                role=role,
                reference=reference,
                revision="v1",
                digest=canonical_digest({"role": role, "reference": reference}),
            )
            for role, reference in sorted(raw_bindings.items())
        ),
        system_assets=(system_asset,),
        scientific_design=design_identity,
        object_set=object_set_identity,
    )
    request = duckdb_server.ExperimentCreateRequest(
        definition=definition,
        actor="test.reviewer",
        idempotency_key="create-scientific-design-api",
    )
    with pytest.raises(duckdb_server.HTTPException) as denied:
        duckdb_server.create_experiment(request)
    assert denied.value.status_code == 409
    assert design_identity.reference in denied.value.detail
    assert object_set_identity.reference in denied.value.detail

    duckdb_server.registry_store().index(
        scientific_design_projection(design_identity), actor="test.reviewer"
    )
    with pytest.raises(duckdb_server.HTTPException) as object_set_denied:
        duckdb_server.create_experiment(request)
    assert object_set_identity.reference in object_set_denied.value.detail

    duckdb_server.registry_store().index(
        scientific_design_projection(object_set_identity), actor="test.reviewer"
    )
    created = duckdb_server.create_experiment(request)
    assert created["definition"]["scientific_design"] == design_identity.model_dump(
        mode="json"
    )
    assert created["definition"]["object_set"] == object_set_identity.model_dump(
        mode="json"
    )


def test_platform_workspace_projection_separates_definitions_and_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workflow_identity(tmp_path, monkeypatch)
    payload = duckdb_server.platform_workspaces()
    assert [zone["zone_id"] for zone in payload["zones"]] == ["system", "research"]
    assert [phase["phase_id"] for phase in payload["development_phases"]] == ["build", "apply"]
    studio_ids = {profile["studio_id"] for profile in payload["studio_profiles"]}
    assert studio_ids >= {"agent", "capability", "risk_analysis", "scenario", "workflow", "provider_connector"}
    assert studio_ids.isdisjoint({"dashboard", "report", "investment_thesis"})
    assert payload["terminology"]["artifact"].startswith("A run work product")
    assert "companion_capability" in payload["terminology"]
    assert payload["terminology"]["blueprint_draft"].startswith("The mutable Agent Blueprint")
    assert payload["terminology"]["material_finding"].startswith("An unresolved critical or high")
    assert "development_proposal" in payload["terminology"]
    assert "development_job" in payload["terminology"]
    assert "registry_admission" in payload["terminology"]
    assert payload["saved_counts"]["workflow"] == 1
    assert payload["saved_definitions"][0]["experiment_eligible"] is True
    assert {item["phase"] for item in payload["future_dependencies"]} >= {
        "PLATFORM-P7", "PLATFORM-P8", "PLATFORM-P9", "PLATFORM-P14", "PLATFORM-P15"
    }


def test_real_portfolio_mandates_are_explicit_and_cover_monitoring_rules() -> None:
    for portfolio_id in ("defensive_multi_asset", "diversified", "technology_concentrated"):
        rules = historical_replay_runtime._mandate_payload(portfolio_id)["rules"]
        assert {item["metric"] for item in rules} >= {
            "daily_return", "annualised_volatility", "drawdown", "cash_weight", "largest_issuer_weight"
        }


def test_historical_replay_can_be_saved_listed_and_reloaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    result = {
        "run_id": "replay-20171229T120000000000Z",
        "status": "completed",
        "workflow": {"id": "B0", "type": "Rules", "model_calls": 0},
        "hierarchy": {
            "study": {"study_id": "study-01", "title": "Portfolio risk study"},
            "experiment": {"experiment_id": "experiment-01"},
            "case": {"case_id": "case-01"},
            "run": {"run_id": "replay-20171229T120000000000Z"},
            "regimes": [],
        },
        "run_record": {
            "run_input": {"case_id": "case-01"},
            "architecture_output": {
                "output_id": "output-01",
                "assessment_state": "clear",
                "severity": 0,
                "confidence": 0.65,
                "confidence_method": "deterministic threshold distance",
                "risk_interpretation": "No mandate threshold was breached.",
                "decision": {"monitoring_action": "continue_monitoring", "portfolio_action": "none"},
            },
            "run_trace": {"model_calls": 0},
            "evaluation_record": {"evaluated_output_id": "output-01"},
        },
        "portfolio": {"id": "diversified", "holdings": []},
        "mandate": historical_replay_runtime._mandate_payload("diversified"),
        "period": {"start": "2017-12-01", "end": "2017-12-29"},
        "evaluation": {
            "dimensions": [{"label": "Detection quality", "status": "not_measurable", "summary": "Requires labels."}],
            "rule_summary": [{"label": "Daily loss", "passed": 10, "breached": 1, "unable_to_assess": 1}],
        },
        "clock": [],
        "methodology_note": "Fixed holdings counterfactual.",
    }
    saved = duckdb_server._save_historical_replay(result)
    assert saved["state"] == "active"
    record = duckdb_server.artifact_store().get(saved["artifact_id"])
    assert {item.path for item in record.manifest.files} == {
        "architecture-output.json",
        "architecture-outputs.json",
        "case.json",
        "decision-branches.json",
        "evaluation-record.json",
        "finding-episodes.json",
        "metric-specifications.json",
        "processing-receipts.json",
        "result.json",
        "run-assurance-report.md",
        "run-assurance.json",
        "run-diagnostics.json",
        "run-input.json",
        "run-manifest.json",
        "run-trace.json",
        "runtime-report.json",
    }
    assert record.manifest.entry_file == "architecture-output.json"
    manifest_bytes, _ = duckdb_server.artifact_store().open_file(
        saved["artifact_id"], "run-manifest.json"
    )
    run_manifest = json.loads(manifest_bytes)
    assert run_manifest["schema_version"] == "portfolio-risk.run-reproducibility-manifest/v1"
    assert run_manifest["run_id"] == result["run_id"]
    assert run_manifest["manifest_digest"].startswith("sha256:")
    catalogue = duckdb_server.list_historical_replays()
    assert catalogue["runs"][0]["run_id"] == result["run_id"]
    loaded = duckdb_server.load_historical_replay(saved["artifact_id"])
    assert loaded["mandate"]["reference"] == result["mandate"]["reference"]
    assert loaded["saved"]["artifact_id"] == saved["artifact_id"]


def _assurance_result(*, label_state: str = "admitted") -> dict:
    dimensions = [
        "detection_quality", "severity_understanding", "timeliness",
        "evidence_quality", "confidence_calibration", "decision_quality",
        "robustness", "stability", "efficiency",
    ]
    return {
        "run_id": "run-assurance-01",
        "status": "completed",
        "hierarchy": {
            "case": {"case_id": "case-01", "context_digest": "sha256:" + "a" * 64},
        },
        "run_record": {
            "run_input": {
                "case_id": "case-01",
                "capability_configurations": [
                    {
                        "capability_id": "historical-replay-context",
                        "evaluation_roles": ["architecture_input", "measurement"],
                    },
                    {
                        "capability_id": "portfolio-risk-metric-pack",
                        "evaluation_roles": ["architecture_input", "measurement"],
                    },
                    {
                        "capability_id": "event-relevance-classifier",
                        "evaluation_roles": ["architecture_input"],
                    },
                    {
                        "capability_id": "fundamental-state-classifier",
                        "evaluation_roles": ["architecture_input"],
                    },
                    {
                        "capability_id": "mandate-policy-evaluator",
                        "evaluation_roles": ["architecture_input", "measurement"],
                    },
                    {
                        "capability_id": "mandate-rule-reference-label",
                        "evaluation_roles": ["reference_label"],
                    },
                    {
                        "capability_id": "daily-session-timeliness",
                        "evaluation_roles": ["measurement"],
                    },
                    {
                        "capability_id": "evidence-structural-audit",
                        "evaluation_roles": ["measurement"],
                    },
                    {
                        "capability_id": "execution-telemetry-collector",
                        "evaluation_roles": ["measurement"],
                    },
                ],
            },
            "architecture_output": {"output_id": "output-01"},
            "architecture_outputs": [
                {
                    "output_id": "output-01",
                    "execution_summary": {
                        "errors": [],
                        "schema_validation_failures": 0,
                        "semantic_verification_failures": 0,
                    },
                }
            ],
            "processing_receipts": [{"processing_wall_ms": 12.0}],
        },
        "workflow": {"id": "B0"},
        "execution_regime": {"resource_usage": {"processing_wall_ms": 12.0}},
        "diagnostics": {"counts": {}, "shortcomings": [], "codex_handoff": {}},
        "evaluation": {
            "trading_days": 1,
            "workflow_failures": 0,
            "reference_treatment": {
                "scope": "deterministic_mandate_breaches",
                "label_state": label_state,
                "label_set_digest": "sha256:" + "b" * 64 if label_state == "admitted" else None,
                "cycles": 1,
            },
            "dimensions": [
                {"id": dimension, "status": "measured"} for dimension in dimensions
            ],
        },
    }


def test_single_run_assurance_uses_canonical_attributes_without_reexecution() -> None:
    assurance = duckdb_server._single_run_assurance(
        _assurance_result(), retention_requested=True
    )

    assert assurance["engine_ready"] is True
    assert assurance["archive_ready"] is True
    assert assurance["computation"] == {
        "strategy": "canonical_attribute_inspection",
        "database_queries": 0,
        "model_calls": 0,
        "capability_reexecutions": 0,
    }
    assert next(
        item for item in assurance["checks"] if item["check_id"] == "capability-readiness"
    )["status"] == "pass"
    assert next(
        item for item in assurance["checks"] if item["check_id"] == "label-scope"
    )["status"] == "warning"


def test_single_run_assurance_fails_when_reference_labels_are_not_admitted() -> None:
    assurance = duckdb_server._single_run_assurance(
        _assurance_result(label_state="not_admitted"), retention_requested=True
    )

    label_check = next(
        item for item in assurance["checks"] if item["check_id"] == "label-readiness"
    )
    assert label_check["status"] == "fail"
    assert label_check["required_for_valid_run"] is True
    assert assurance["engine_ready"] is False
    assert assurance["archive_ready"] is False


def test_professor_demo_definition_pins_one_case_and_all_demo_capabilities() -> None:
    definition = historical_replay_runtime.professor_demo_definition()

    assert definition["demo_id"] == "professor-demo-v0.1"
    assert definition["case"]["portfolio_id"] == "defensive_multi_asset"
    assert definition["case"]["start_date"] == definition["case"]["end_date"] == "2016-03-07"
    assert definition["architectures"] == ["B0", "B1", "A1"]
    assert set(definition["capabilities"]) == {
        item.capability_id for item in historical_replay_runtime.PRECONFIGURED_CAPABILITIES
    }
    assert definition["effects"] == []


def test_professor_demo_endpoint_exposes_preflight_without_model_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {"demo_ready": True, "status": "ready_with_limitations"}
    monkeypatch.setattr(duckdb_server, "find_private_root", lambda _root: Path("/licensed"))
    monkeypatch.setattr(duckdb_server, "professor_demo_preflight", lambda _root: expected)

    assert duckdb_server.professor_demo() == expected


def test_professor_demo_run_compiles_the_frozen_three_cell_matrix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}
    monkeypatch.setattr(duckdb_server, "find_private_root", lambda _root: Path("/licensed"))
    monkeypatch.setattr(
        duckdb_server,
        "professor_demo_preflight",
        lambda _root: {"demo_ready": True, "checks": []},
    )

    def execute(request):
        captured["request"] = request
        return {"analysis": {"status": "complete"}}

    monkeypatch.setattr(duckdb_server, "create_counterfactual_batch", execute)
    result = duckdb_server.run_professor_demo(
        duckdb_server.ProfessorDemoRunRequest(authorize_external_model_calls=True)
    )

    request = captured["request"]
    assert request.portfolio_ids == ("defensive_multi_asset",)
    assert request.workflow_ids == ("B0", "B1", "A1")
    assert request.start_date == request.end_date == date(2016, 3, 7)
    assert request.authorize_external_model_calls is True
    assert result["analysis"]["status"] == "complete"


def test_professor_demo_run_requires_explicit_model_authorization() -> None:
    with pytest.raises(duckdb_server.HTTPException) as denied:
        duckdb_server.run_professor_demo(duckdb_server.ProfessorDemoRunRequest())

    assert denied.value.status_code == 422


def test_functional_evaluator_does_not_award_vacuous_or_proxy_scores() -> None:
    dimensions = historical_replay_runtime._evaluate_architecture_outputs(
        (), (),
        position_observation_completeness=1.0,
        wall_clock_ms=12.0,
        query_receipts=("query-01",),
        repetitions=1,
        label_state="not_admitted",
    )
    by_id = {item["id"]: item for item in dimensions}

    assert by_id["evidence_quality"]["status"] == "not_applicable"
    assert by_id["evidence_quality"]["score"] is None
    assert by_id["decision_quality"]["status"] == "not_measurable"
    assert by_id["decision_quality"]["score"] is None
    assert by_id["robustness"]["status"] == "not_measurable"
    assert by_id["robustness"]["score"] is None
    assert by_id["stability"]["status"] == "partial"


def test_evaluator_calculates_admitted_mandate_reference_metrics() -> None:
    first = datetime(2017, 12, 1, 21, tzinfo=timezone.utc)
    second = datetime(2017, 12, 4, 21, tzinfo=timezone.utc)
    finding = SimpleNamespace(
        metric_id="cash-weight", severity=2, risk_type="liquidity",
        evidence_ids=("metric:cash",),
    )
    outputs = (
        SimpleNamespace(
            cycle_id="cycle-2017-12-01", findings=(finding,),
            architecture_type="single_agent", as_of=first, trigger_available_at=first,
            execution_summary=None, supporting_evidence_ids=("metric:cash",),
            conflicting_evidence_ids=(), confidence_kind="ordinal_judgement",
            confidence=0.8, assessment_state="watch",
            decision=SimpleNamespace(
                monitoring_action="increase_monitoring", portfolio_action="review_exposure",
            ),
        ),
        SimpleNamespace(
            cycle_id="cycle-2017-12-04", findings=(),
            architecture_type="single_agent", as_of=second, trigger_available_at=second,
            execution_summary=None, supporting_evidence_ids=(), conflicting_evidence_ids=(),
            confidence_kind="ordinal_judgement", confidence=0.8, assessment_state="clear",
            decision=SimpleNamespace(
                monitoring_action="continue_monitoring", portfolio_action="none",
            ),
        ),
    )
    references = (
        {
            "cycle_id": "cycle-2017-12-01", "available_at": first,
            "findings": ({
                "key": "cycle-2017-12-01:cash-weight", "metric_id": "cash-weight",
                "risk_type": "liquidity", "severity": 3, "available_at": first,
            },),
            "monitoring_action": "urgent_human_review", "portfolio_action": "review_exposure",
        },
        {
            "cycle_id": "cycle-2017-12-04", "available_at": second, "findings": (),
            "monitoring_action": "continue_monitoring", "portfolio_action": "none",
        },
    )
    dimensions = historical_replay_runtime._evaluate_architecture_outputs(
        outputs, (), position_observation_completeness=1.0, wall_clock_ms=20.0,
        query_receipts=("query-01",), repetitions=1, label_state="admitted",
        reference_cycles=references,
    )
    by_id = {item["id"]: item for item in dimensions}

    assert by_id["detection_quality"]["score"] == 1.0
    assert by_id["detection_quality"]["metrics"]["cycle_classification_accuracy"] == 1.0
    assert by_id["severity_understanding"]["metrics"]["severity_mae"] == 1.0
    assert by_id["severity_understanding"]["score"] == pytest.approx(2 / 3)
    assert by_id["timeliness"]["score"] == 1.0
    assert by_id["evidence_quality"]["score"] == 1.0
    assert by_id["decision_quality"]["metrics"]["monitoring_action_agreement"] == 0.5
    assert by_id["decision_quality"]["score"] == 0.75
    assert by_id["confidence_calibration"]["status"] == "not_measurable"
    assert by_id["robustness"]["score"] is None


def test_live_agent_replay_requires_explicit_external_context_authorization() -> None:
    request = duckdb_server.HistoricalReplayRequest(
        workflow_id="B1",
        portfolio_id="diversified",
        start_date=date(2017, 12, 1),
        end_date=date(2017, 12, 1),
        save_result=False,
    )
    with pytest.raises(duckdb_server.HTTPException, match="explicit authorization") as captured:
        duckdb_server.create_historical_replay(request)
    assert captured.value.status_code == 422


def test_agent_output_mapping_contract_keeps_artifact_flexible_and_evaluation_common() -> None:
    payload = duckdb_server.architecture_output_projection_contract()

    assert payload["flow"] == [
        "headless_agent_or_graph_wrapper",
        "evaluation_byproducts_and_observed_behavior",
        "deterministic_mapping",
        "architecture_output",
        "evaluation",
    ]
    assert payload["agent_writes_architecture_output"] is False
    assert payload["primary_artifact_is_rewritten"] is False
    assert "point_in_time_evidence_eligibility" in payload["checks"]
    assert payload["output_schema"]["title"] == "AgentStructuredOutput"
    assert payload["single_agent_wrapper_schema"]["title"] == "AgentExecutionEnvelope"
    assert payload["graph_wrapper_schema"]["title"] == "GraphExecutionEnvelope"


def test_matched_evaluation_endpoint_returns_only_salient_projection(monkeypatch) -> None:
    expected = {
        "matrix_id": "matrix-one",
        "status": "valid_with_limitations",
        "archivable": True,
        "coverage": {"completed": 3, "planned": 3},
        "runs": [],
    }
    monkeypatch.setattr(
        duckdb_server, "evaluate_matched_matrix",
        lambda matrix_id: expected if matrix_id == "matrix-one" else None,
    )

    assert duckdb_server.experiment_evaluate_matched_run_plan("matrix-one") == expected
