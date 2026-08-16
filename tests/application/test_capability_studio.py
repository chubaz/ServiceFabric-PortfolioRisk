from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
LABS_ROOT = ROOT / "apps" / "portfolio-risk-workbench" / "labs"
for package in (
    "risk_domain",
    "risk_capabilities",
    "risk_analytics",
    "risk_registry",
    "risk_artifacts",
    "risk_experiments",
    "risk_reports",
    "risk_decisions",
):
    sys.path.insert(0, str(ROOT / "packages" / package / "src"))
sys.path.insert(0, str(LABS_ROOT))

import capability_studio as studio  # noqa: E402


@pytest.fixture
def isolated_studio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(studio, "CAPABILITY_STUDIO_ROOT", tmp_path)
    monkeypatch.setattr(studio, "PROPOSAL_ROOT", tmp_path / "proposals")
    monkeypatch.setattr(studio, "DESIGN_SESSION_ROOT", tmp_path / "design-sessions")
    monkeypatch.setattr(studio, "STUDIO_DESIGN_PROPOSAL_ROOT", tmp_path / "studio-design-proposals")
    monkeypatch.setattr(studio, "RUN_REPOSITORY", tmp_path / "runs")
    monkeypatch.setattr(studio, "CANONICAL_REGISTRY_ROOT", tmp_path / "canonical-registry")
    monkeypatch.setattr(studio, "_CANONICAL_SERVICE", None)
    studio._CANONICAL_DEFINITIONS.clear()
    studio._CANONICAL_OPERATIONS.clear()
    studio._CANONICAL_SCHEMAS.clear()
    return tmp_path


def test_catalogue_is_reuse_first_and_declares_effect_boundary() -> None:
    result = studio.capability_catalogue()

    assert {key: result["counts"][key] for key in ("capabilities", "available", "fixture_ready", "packages", "hosts")} == {
            "capabilities": 28,
            "available": 24,
            "fixture_ready": 24,
        "packages": 4,
        "hosts": 5,
    }
    assert 0 <= result["counts"]["validation_eligible"] <= result["counts"]["fixture_ready"]
    assert result["resolution_policy"] == "exact_first_explicit_compatible_substitution"
    assert result["effect_policy"] == {
        "available": ("observe", "system_object_write", "experiment_object_write"),
        "external": "placeholder_disabled",
        "licensed_source_database": "read_only",
    }
    assert all(item["effect_level"] == "observe" for item in result["capabilities"])
    by_id = {item["capability_id"]: item for item in result["capabilities"]}
    assert by_id["risk.var.historical"]["family"] == "analytics"
    assert "risk.report.render" not in by_id
    assert "monitoring.report.render" not in by_id
    assert by_id["risk.capability.news_sentiment"]["family"] == "interpretation"
    assert [item["test_id"] for item in by_id["risk.var.historical"]["validation_tests"]] == [
        "contract",
        "resolution",
        "fixed_tests",
        "effect_boundary",
    ]
    assert by_id["events.query.as_of"]["test_case_status"] == "ready"
    assert by_id["risk.capability.news_sentiment"]["test_case_status"] == "implementation_required"
    assert by_id["risk.returns.simple"]["description"]["script"]["available"] is True
    assert "def calculate_simple_returns" in by_id["risk.returns.simple"]["description"]["script"]["source"]
    assert by_id["risk.capability.news_sentiment"]["description"]["script"]["available"] is False
    assert by_id["risk.returns.simple"]["description"]["contract"]["agent_text"].startswith("Capability: risk.returns.simple")
    assert by_id["risk.var.historical"]["execution_profile"]["kind"] == "statistical"
    assert by_id["risk.var.historical"]["execution_profile"]["parameterisation"] == "a_priori"
    assert by_id["risk.scenario.evaluate"]["execution_profile"]["parameterisation"] == "agent_optional"
    assert by_id["risk.capability.news_sentiment"]["execution_profile"]["parameterisation"] == "agent_required"
    assert all(item["description"] and item["b0_role"] for item in result["packages"])
    assert by_id["events.query.as_of"]["validation_gate"]["validated"] is False
    assert all(item["host_id"] not in {"servicefabric.dashboard", "servicefabric.report"} for item in result["hosts"])
    assert any(item["write_boundary"].endswith("source databases remain read-only") for item in result["hosts"])
    assert all(item["description"] and item["capability_integration"] and item["effect_boundary"] for item in result["hosts"])


def test_historical_host_blueprint_remains_readable_but_active_assessment_blocks_it() -> None:
    requirement = (
        "Create a reusable operation that calculates a point-in-time portfolio "
        "return distribution and shows it as an interactive D3.js dashboard graph."
    )
    blueprint = studio._blueprint(requirement, ())

    assert blueprint.display_name == "Calculate Point-in-Time Portfolio Return Distribution"
    assert blueprint.capability_id.startswith("risk.proposed.calculate_point_in_time_portfolio_return_distribution")
    assert blueprint.renderer == "dashboard_component"
    assert blueprint.implementation_class == "typescript"
    assert blueprint.host_binding is not None
    assert blueprint.host_binding.host_id == "servicefabric.dashboard"
    assert blueprint.host_binding.framework == "D3.js"
    assert studio._design_target(requirement) == "capability"

    assessment = studio.assess_requirement(studio.RequirementAssessmentRequest(requirement=requirement))
    assert assessment.recommendation == "blocked"
    assert "ADR-0009" in assessment.rationale
    assert assessment.blueprint.display_name == "Calculate Point-in-Time Portfolio Return Distribution"


def test_semantic_title_removes_authoring_scaffolding() -> None:
    assert studio._semantic_title(
        "I would like you to create a capability that renders a mandate breach decision card using TypeScript."
    ) == "Render Mandate Breach Decision Card"


def test_assessment_finds_existing_capability_before_proposing_development() -> None:
    result = studio.assess_requirement(
        studio.RequirementAssessmentRequest(
            requirement="Calculate historical value at risk and explain the result"
        )
    )

    assert result.recommendation == "reuse"
    assert result.candidates[0]["capability_id"] == "risk.var.historical"
    assert result.compact_candidate_count <= 6
    assert result.total_library_count == 28
    assert result.model_receipt["provider"] == "none"
    assert result.blueprint.capability_id == "risk.var.historical"
    assert result.blueprint.effect_profile == "observe"
    assert result.discussion_status == "refining"
    assert result.intent == "clarify"
    assert result.quiz is not None
    assert len(result.quiz.options) == 4


def test_dashboard_requirement_is_routed_to_the_post_thesis_incubator() -> None:
    result = studio.assess_requirement(
        studio.RequirementAssessmentRequest(
            requirement=(
                "Create an interactive D3.js dashboard showing a point-in-time portfolio "
                "return distribution from any semantically sufficient upstream capability data."
            )
        )
    )
    assert result.recommendation == "blocked"
    assert "ADR-0009" in result.rationale
    assert "structured analytical output" in result.response


def test_design_sessions_are_resumable_idempotent_and_deletable(
    isolated_studio: Path,
) -> None:
    request = studio.RequirementAssessmentRequest(
        requirement="Render a point-in-time return distribution in an interactive dashboard."
    )
    assessment = studio.assess_requirement(request)
    first = studio.save_design_session(request, assessment)
    repeated = studio.save_design_session(request, assessment)

    assert first["session_id"] == assessment.session_id
    assert repeated["revision"] == 1
    assert studio.list_design_sessions()[0]["session_id"] == assessment.session_id
    assert studio.load_design_session(assessment.session_id)["dependency_map"]
    assert studio.delete_design_session(assessment.session_id) == {
        "deleted": True,
        "session_id": assessment.session_id,
        "recoverable": False,
    }
    assert studio.list_design_sessions() == []


def test_consensus_precedes_draft_and_approval_is_the_first_backlog_write(
    isolated_studio: Path,
) -> None:
    first_requirement = "Calculate historical value at risk for supplied portfolio returns"
    conversation = (
        studio.DesignMessage(role="user", content=first_requirement),
        studio.DesignMessage(role="assistant", content="Which exact input and output boundary should apply?"),
    )
    final_answer = "Use immutable point-in-time portfolio return data as input and return a typed result with a readable metric output."
    ready = studio.assess_requirement(
        studio.RequirementAssessmentRequest(
            requirement=final_answer,
            conversation=conversation,
        )
    )
    assert ready.discussion_status == "consensus_ready"
    assert ready.open_questions == ()

    concluded = studio.assess_requirement(
        studio.RequirementAssessmentRequest(
            requirement=final_answer,
            conversation=conversation,
            conclude=True,
        )
    )
    assert concluded.discussion_status == "concluded"
    request = studio.ProposalCreateRequest(assessment=concluded, decision="reuse")
    draft = studio.compile_blueprint(request)
    assert draft.capability_id == "risk.var.historical"
    assert studio.list_proposals() == []

    approved = studio.approve_blueprint(request)
    assert approved["status"] == "human_approved"
    assert len(studio.list_proposals()) == 1
    deletion = studio.delete_proposal(approved["proposal_id"])
    assert deletion == {"deleted": True, "proposal_id": approved["proposal_id"], "recoverable": False}
    assert studio.list_proposals() == []


def test_mature_object_discussion_creates_non_final_studio_handoff(
    isolated_studio: Path,
) -> None:
    assessment = studio.assess_requirement(
        studio.RequirementAssessmentRequest(
            requirement="Design a workflow using immutable portfolio context inputs and a typed report output with human review.",
            conversation=(studio.DesignMessage(role="user", content="I need a composable risk workflow."),),
            conclude=True,
        )
    )
    assert assessment.discussion_status == "concluded"
    assert assessment.design_target == "workflow"
    handoff = studio.create_studio_design_proposal(
        studio.StudioDesignProposalRequest(assessment=assessment)
    )
    assert handoff["target_studio"] == "workflow"
    assert handoff["status"] == "proposed"
    assert "does not create" in handoff["limitations"][0]


def test_strict_design_schema_requires_every_property_and_removes_defaults() -> None:
    schema = studio._strict_schema(studio._Advice)

    def assert_strict(value: object) -> None:
        if isinstance(value, dict):
            assert "default" not in value
            properties = value.get("properties")
            if isinstance(properties, dict):
                assert value["additionalProperties"] is False
                assert value["required"] == list(properties)
            for child in value.values():
                assert_strict(child)
        elif isinstance(value, list):
            for child in value:
                assert_strict(child)

    assert_strict(schema)


def test_llm_failure_retains_deterministic_assessment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(studio, "_live_design_advice", fail)
    result = studio.assess_requirement(
        studio.RequirementAssessmentRequest(
            requirement="Calculate historical value at risk for supplied returns",
            use_llm=True,
        )
    )

    assert result.recommendation == "reuse"
    assert result.blueprint.capability_id == "risk.var.historical"
    assert result.model_receipt["status"] == "failed"
    assert result.model_receipt["error_type"] == "RuntimeError"
    assert "deterministic blueprint is shown instead" in result.response


def test_proposal_requires_human_approval_before_codex_handoff(
    isolated_studio: Path,
) -> None:
    assessment = studio.assess_requirement(
        studio.RequirementAssessmentRequest(
            requirement="Calculate historical expected shortfall for supplied returns"
        )
    )
    proposal = studio.create_proposal(
        studio.ProposalCreateRequest(assessment=assessment, decision="reuse")
    )

    assert proposal["status"] == "identified"
    assert proposal["studio_codex"]["eligible"] is False
    assert proposal["design_session_id"] == assessment.session_id
    assert proposal["dependency_map"]
    revised = studio.transition_proposal(
        proposal["proposal_id"],
        studio.ProposalTransitionRequest(action="return_to_design"),
    )
    assert revised["status"] == "identified"
    assert revised["events"][-1]["action"] == "return_to_design"
    assert revised["studio_codex"]["eligible"] is False
    with pytest.raises(ValueError, match="invalid capability proposal transition"):
        studio.transition_proposal(
            proposal["proposal_id"],
            studio.ProposalTransitionRequest(action="prepare_codex"),
        )

    approved = studio.transition_proposal(
        proposal["proposal_id"], studio.ProposalTransitionRequest(action="approve")
    )
    ready = studio.transition_proposal(
        proposal["proposal_id"],
        studio.ProposalTransitionRequest(action="prepare_codex"),
    )
    assert approved["status"] == "human_approved"
    assert ready["status"] == "ready_for_studio_codex"
    assert ready["studio_codex"]["eligible"] is True
    assert "Do not edit vendor/servicefabric" in ready["studio_codex"]["build_brief"]
    assert "write licensed/source databases" in ready["studio_codex"]["build_brief"]
    assert "Dependency:" in ready["studio_codex"]["build_brief"]


def test_fixture_uses_canonical_invocation_and_persists_three_level_review(
    isolated_studio: Path,
) -> None:
    result = studio.execute_fixture(
        studio.FixtureRunRequest(capability_id="risk.var.historical")
    )
    manifest = result["manifest"]
    contents = result["contents"]

    assert manifest["status"] == "completed"
    assert manifest["data_truth"] == "reviewed_synthetic"
    assert manifest["canonical_servicefabric_invocation"] is True
    assert manifest["human_review_required"] is True
    assert manifest["effects"] == []
    assert Path(manifest["folder"]).parent == isolated_studio / "runs"

    assert contents["resolution.json"]["policy"] == "exact_first_explicit_compatible_substitution"
    assert contents["resolution.json"]["resolved_capability_id"] == "risk.var.historical"
    assert contents["resolution.json"]["canonical_servicefabric_invocation"] is True
    assert contents["effect-review.json"]["licensed_source_database"] == "read_only"
    assert contents["effect-review.json"]["external_effects"] == "disabled_placeholder"
    assert contents["effect-review.json"]["executed"] == []
    assert [item["sequence"] for item in contents["stages.json"]] == list(range(1, 8))
    assert contents["presentation.json"]["renderer"] == "metric"
    assert {item["label"] for item in contents["presentation.json"]["metrics"]} == {
        "Historical VaR",
        "Expected Shortfall",
        "Confidence",
    }

    after_run = studio.capability_catalogue()
    tested = next(item for item in after_run["capabilities"] if item["capability_id"] == "risk.var.historical")
    assert tested["validation_gate"] == {
        "status": "ready_for_review",
        "passed": 4,
        "required": 4,
        "validated": False,
    }

    loaded = studio.load_fixture_run(manifest["run_id"])
    assert loaded["manifest"]["run_id"] == manifest["run_id"]
    assert studio.list_fixture_runs()[0]["run_id"] == manifest["run_id"]
    deletion = studio.delete_fixture_run(manifest["run_id"])
    assert deletion == {
        "deleted": True,
        "run_id": manifest["run_id"],
        "recoverable": False,
    }
    assert studio.list_fixture_runs() == []


def test_every_active_local_capability_has_executable_fixed_tests(
    isolated_studio: Path,
) -> None:
    expected = {
        item.capability_id
        for item in studio.CAPABILITY_DESCRIPTORS
        if item.capability_id not in studio.INCUBATOR_CAPABILITY_IDS
        and item.capability_id in studio.DEFAULT_CAPABILITY_REGISTRY.capability_ids
    }

    assert studio._fixture_capability_ids() == expected
    for capability_id in sorted(expected):
        result = studio.execute_fixture(
            studio.FixtureRunRequest(capability_id=capability_id)
        )
        assert result["manifest"]["status"] == "completed"
        assert result["contents"]["validation.json"]["valid"] is True
        assert result["contents"]["validation.json"]["passed"] == 5
        assert len(result["contents"]["fixed-tests.json"]) == 5
        assert result["contents"]["effect-review.json"]["executed"] == []


def test_canonical_bridge_is_idempotent_across_process_restart(
    isolated_studio: Path,
) -> None:
    first = studio.execute_fixture(
        studio.FixtureRunRequest(capability_id="risk.var.historical")
    )
    studio._CANONICAL_SERVICE = None
    studio._CANONICAL_DEFINITIONS.clear()
    studio._CANONICAL_OPERATIONS.clear()
    studio._CANONICAL_SCHEMAS.clear()

    second = studio.execute_fixture(
        studio.FixtureRunRequest(capability_id="risk.var.historical")
    )

    assert first["contents"]["resolution.json"]["canonical_servicefabric_invocation"] is True
    assert second["contents"]["resolution.json"]["canonical_servicefabric_invocation"] is True
    assert second["contents"]["resolution.json"]["resolved_capability_id"] == "risk.var.historical"


def test_fixture_repository_and_effect_boundary_reject_unsafe_requests(
    isolated_studio: Path,
) -> None:
    with pytest.raises(ValueError, match="invalid capability run identifier"):
        studio.load_fixture_run("../../outside")
    with pytest.raises(ValueError, match="no executable implementation"):
        studio.execute_fixture(
            studio.FixtureRunRequest(capability_id="risk.capability.news_sentiment")
        )

    blocked = studio.assess_requirement(
        studio.RequirementAssessmentRequest(
            requirement="Write changes directly into the external licensed market database"
        )
    )
    assert blocked.recommendation == "blocked"
    assert blocked.blueprint.effect_profile == "external_placeholder"
