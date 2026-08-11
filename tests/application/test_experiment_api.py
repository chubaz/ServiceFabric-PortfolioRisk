from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

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
        "run-input.json",
        "run-trace.json",
    }
    assert record.manifest.entry_file == "architecture-output.json"
    catalogue = duckdb_server.list_historical_replays()
    assert catalogue["runs"][0]["run_id"] == result["run_id"]
    loaded = duckdb_server.load_historical_replay(saved["artifact_id"])
    assert loaded["mandate"]["reference"] == result["mandate"]["reference"]
    assert loaded["saved"]["artifact_id"] == saved["artifact_id"]


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
