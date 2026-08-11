from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import date, timedelta

import pytest


ROOT = Path(__file__).resolve().parents[2]
LABS_ROOT = ROOT / "apps" / "portfolio-risk-workbench" / "labs"
sys.path.insert(0, str(LABS_ROOT))

import agent_studio  # noqa: E402
import duckdb_server  # noqa: E402


def test_live_llm_requests_are_pinned_to_lowest_cost_model() -> None:
    assert agent_studio.COST_OPTIMIZED_LLM_MODEL == "gpt-5.6-luna"
    plan = agent_studio.BlueprintPlanRequest(
        description="Design a governed portfolio risk agent."
    )
    blueprint = agent_studio.AgentBlueprint.model_validate(
        agent_studio.risk_agent_templates()[0]["blueprint"]
    )
    run = agent_studio.RunRequest(blueprint=blueprint)

    assert plan.model == "gpt-5.6-luna"
    assert run.execution_model == "gpt-5.6-luna"
    assert [item["id"] for item in agent_studio.runtime_status()["models"]] == [
        "gpt-5.6-luna"
    ]

    for disallowed_model in ("gpt-5.5", "gpt-5.4"):
        with pytest.raises(ValueError):
            agent_studio.BlueprintPlanRequest(
                description="Design a governed portfolio risk agent.",
                model=disallowed_model,
            )


def test_experimental_interpretation_schema_collects_evaluation_semantics() -> None:
    schema = agent_studio.experimental_interpretation_schema("specialist_node")
    required = set(schema["required"])
    assert {"assessment_state", "material_findings", "decision", "confidence_method"} <= required
    finding = schema["properties"]["material_findings"]["items"]
    assert {"severity", "materiality", "confidence", "evidence_ids"} <= set(finding["required"])

    byproducts = agent_studio._evaluation_byproducts_from_interpretation(
        {
            "assessment_state": "alert",
            "risk_interpretation": "Concentration amplifies the observed downside channel.",
            "expectations": "Loss sensitivity remains elevated while concentration persists.",
            "confidence": 0.7,
            "confidence_kind": "ordinal_judgement",
            "confidence_method": "Model judgement grounded in the supplied exposure receipt.",
            "material_findings": [{
                "claim": "The largest issuer concentration is material.",
                "risk_type": "concentration", "affected_asset": "Issuer A",
                "direction": "negative", "materiality": 0.8, "severity": 2,
                "confidence": 0.75, "confidence_method": "Exposure result comparison.",
                "evidence_ids": ["evidence-exposure-1"],
            }],
            "decision": {
                "monitoring_action": "increase_monitoring", "portfolio_action": "none",
                "rationale_finding_indexes": [0],
                "alternatives_considered": ["continue_monitoring"],
            },
            "warnings": [], "limitations": [], "missing_information": [], "assumptions": [],
        },
        experimental_role="specialist_node",
    )
    assert byproducts["decision"]["decision_scope"] == "node_advisory"
    assert byproducts["decision"]["rationale_finding_ids"] == (
        byproducts["findings"][0]["finding_id"],
    )


def test_blueprint_planning_reports_an_incomplete_server_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_runtime(_request: object) -> dict[str, object]:
        error = ModuleNotFoundError("No module named 'openai'")
        error.name = "openai"
        raise error

    monkeypatch.setattr(duckdb_server, "plan_blueprint", missing_runtime)
    request = agent_studio.BlueprintPlanRequest(
        description="Design a governed portfolio risk agent."
    )

    with pytest.raises(duckdb_server.HTTPException) as caught:
        duckdb_server.create_agent_blueprint(request)

    assert caught.value.status_code == 503
    assert "start_live_data.sh" in caught.value.detail


def test_run_report_uses_only_existing_evidence_and_has_no_effects() -> None:
    result = {
        "run_id": "run-20260803T090000Z-1234abcd",
        "presentation": {
            "title": "Daily review",
            "outcome_sought": "Review portfolio risk",
            "as_of": "2026-08-03",
            "executive_conclusion": "Concentration requires review.",
            "observations": [],
            "findings": ["Concentration requires review."],
            "limitations": [],
            "next_steps": [],
            "review_boundary": "No effect was created.",
        },
        "input_context": {
            "portfolio_capability_input": {"evidence_id": "evidence:portfolio-1"},
        },
        "final_state": {
            "capability_results": [
                {"receipt": {"evidence_ids": ["evidence:capability-1"]}}
            ],
            "model_output": {
                "material_findings": [
                    {"claim": "Concentration requires review.", "evidence_ids": ["evidence:portfolio-1"]}
                ]
            },
        },
    }
    report, validation = agent_studio._compose_run_report(result)
    assert report["effects"] == []
    assert "evidence:portfolio-1" in report["sections"][1]["evidence_ids"]
    assert validation["evidence_coverage"] == 1
    assert "<script" not in report["rendered_html"]


def test_new_agent_runs_persist_structured_output_without_presentation_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(agent_studio, "RUN_ROOT", tmp_path)
    result = {
        "run_id": "run-20260811T010000Z-1234abcd",
        "agent_name": "Structured risk agent",
        "assignment_summary": "Analyse the frozen portfolio context.",
        "output_contract": "ArchitectureOutput",
        "status": "completed",
        "data_mode": "reviewed_synthetic",
        "data_label": "Reviewed synthetic",
        "execution_mode": "deterministic",
        "execution_model": None,
        "scenario": "concentration",
        "portfolio_id": "portfolio-1",
        "as_of": "2026-08-11",
        "created_at": "2026-08-11T01:00:00Z",
        "elapsed_ms": 1,
        "operating_profile": "development",
        "authority_boundary": "findings_and_proposals_only",
        "external_effects": [],
        "persistence_class": "temporary_local_run",
        "input_context": {"portfolio_id": "portfolio-1"},
        "input_provenance": {"data_mode": "reviewed_synthetic"},
        "blueprint": {"name": "structured_risk_agent"},
        "activity": [],
        "interrupted": False,
        "auto_approved": False,
        "checkpoint_release": {"released": False},
        "final_state": {
            "narrative": "Concentration requires review.",
            "critique": "Evidence is limited.",
            "research_plan": {},
            "capability_results": [],
            "model_output": {"material_findings": []},
            "rationale_summary": [],
            "model_receipts": [],
            "semantic_verification": {"status": "passed"},
            "review": {"approved": False},
        },
    }

    manifest = agent_studio._persist_run(result)
    names = {item["name"] for item in manifest["files"]}
    assert "agent-output.json" in names
    assert "architecture-output.json" not in names
    assert "report.json" not in names
    assert "review-brief.md" not in names
    assert "review-brief.html" not in names
    output = json.loads((tmp_path / result["run_id"] / "output.json").read_text())
    assert "report" not in output
    assert "presentation" not in output
    headless = json.loads((tmp_path / result["run_id"] / "agent-output.json").read_text())
    assert headless["evaluation_status"] == "not_admitted_to_experiment"
    assert headless["presentation_artifacts"] == []
    file_roles = {item["name"]: item.get("evaluation_role") for item in manifest["files"]}
    assert file_roles["agent-output.json"] == "candidate_agent_output"
    assert file_roles["transcript.md"] == "technical_trace"


def test_agent_studio_architect_is_a_bounded_static_system_agent() -> None:
    template = agent_studio.agent_studio_architect_template()
    blueprint = agent_studio.AgentBlueprint.model_validate(template["blueprint"])

    assert template["id"] == "system-agent-agent-studio-architect"
    assert blueprint.agent_class == "static_system"
    assert blueprint.version == "0.1.0"
    assert blueprint.input_contract == "AgentBlueprintContext"
    assert blueprint.output_contract == "AgentBlueprintProposal"
    assert blueprint.static_system_scope is not None
    assert blueprint.static_system_scope.owning_studio == "agent"
    assert blueprint.static_system_scope.proposal_only is True
    assert blueprint.static_system_scope.skill_ids == ["build-servicefabric-agent"]
    assert set(blueprint.capabilities) == agent_studio.SYSTEM_CAPABILITY_IDS
    assert blueprint.governance.effects_allowed is False
    assert blueprint.governance.human_approval is True
    assert blueprint.experimental_role is None
    assert blueprint.experimental_wrapper is None


def test_every_experimental_agent_is_created_with_the_headless_wrapper() -> None:
    templates = agent_studio.risk_agent_templates()

    for template in templates:
        blueprint = agent_studio.AgentBlueprint.model_validate(template["blueprint"])
        assert blueprint.experimental_wrapper is not None
        assert blueprint.experimental_wrapper.execution_mode == "headless"
        assert blueprint.experimental_wrapper.captures_runtime_behavior is True
        assert blueprint.experimental_wrapper.presentation_artifact_policy == "label_and_exclude"
        assert blueprint.experimental_wrapper.maps_to_architecture_output == (
            blueprint.experimental_role == "final_decision_agent"
        )

    assert templates[0]["blueprint"]["experimental_role"] == "final_decision_agent"
    assert templates[1]["blueprint"]["experimental_role"] == "specialist_node"
    assert templates[-1]["blueprint"]["experimental_role"] == "specialist_node"


def test_compiler_exposes_experimental_wrapper_as_a_release_check() -> None:
    blueprint = agent_studio.AgentBlueprint.model_validate(
        agent_studio.risk_agent_templates()[1]["blueprint"]
    )
    compilation = agent_studio.compile_blueprint(blueprint, persist=False)
    wrapper_check = next(
        item for item in compilation["checks"] if item["name"] == "Experimental wrapper"
    )

    assert wrapper_check["status"] == "passed"
    assert "specialist node" in wrapper_check["detail"]
    assert "Run headlessly" in blueprint.system_instructions
    assert "do not claim the architecture-final decision" in blueprint.system_instructions


def test_agent_classes_cannot_cross_context_or_capability_boundaries() -> None:
    static_payload = agent_studio.agent_studio_architect_template()["blueprint"]
    static_payload["capability_latches"][0]["capability_id"] = "portfolio_exposure"
    with pytest.raises(ValueError, match="experimental risk capabilities"):
        agent_studio.AgentBlueprint.model_validate(static_payload)

    experimental_payload = agent_studio.risk_agent_templates()[0]["blueprint"]
    experimental_payload["capability_latches"][0]["capability_id"] = (
        "registry_agent_search"
    )
    with pytest.raises(ValueError, match="Studio design capabilities"):
        agent_studio.AgentBlueprint.model_validate(experimental_payload)


def test_static_system_fixture_is_explicitly_synthetic_and_does_not_call_codex() -> None:
    fixture = agent_studio.static_system_agent_fixture()

    assert fixture["agent_class"] == "static_system"
    assert fixture["synthetic"] is True
    assert fixture["summary"] == {"passed": 3, "failed": 0, "total": 3}
    assert {item["case"] for item in fixture["checks"]} == {
        "representative",
        "failure_boundary",
        "adversarial",
    }
    assert fixture["studio_codex"]["state"] == "development_provider_ready"
    assert fixture["studio_codex"]["fixture_executes_codex"] is False


def test_agent_studio_surface_exposes_class_and_skill_boundaries() -> None:
    html = (LABS_ROOT / "index.html").read_text()
    javascript = (LABS_ROOT / "labs.js").read_text()
    skill = (ROOT / "codex" / "skills" / "build-servicefabric-agent" / "SKILL.md").read_text()

    assert 'data-agent-class="static_system"' in html
    assert 'data-agent-class="experimental_specialist"' in html
    assert "Agent Studio Architect" in html
    assert 'id="agent-studio-companion"' in html
    assert "Every refinement is a diff" in html
    assert "system-agent-agent-studio-architect" in javascript
    assert "Verify blueprint" in javascript
    assert "Edit advanced configuration" in javascript
    assert "Resolve material finding" in javascript
    assert "resolveAgentConfigurationReview" in javascript
    assert "live Studio runtime does not have both the OpenAI SDK" in javascript
    assert "/api/agents/blueprint/refine" in javascript
    assert 'id="agent-lifecycle-review"' not in html
    assert "reviewAgentConfiguration" in javascript
    assert "loadAgentDevelopmentHistory" in javascript
    assert "agentStudioCandidateValidated" in javascript
    assert "No Registry write, activation, portfolio effect" in javascript
    assert "Do not register, activate, publish, merge" in skill
    assert 'id="agent-run-label" maxlength="120"' in html
    assert "Assignment must be 120 characters or fewer" in javascript
    assert 'data-agent-data-mode="historically_calibrated_synthetic"' in html
    assert 'data-agent-execution-mode="compare"' in html
    assert 'id="retain-agent-run"' in html
    assert "/api/agents/compare" in javascript


def test_blueprint_refinement_applies_only_the_declared_diff() -> None:
    blueprint = agent_studio.AgentBlueprint.model_validate(
        agent_studio.risk_agent_templates()[0]["blueprint"]
    )
    before = blueprint.model_dump(mode="json")
    document = agent_studio.BlueprintDiffDocument(
        summary="Tighten the observable outcome without touching implementation policy.",
        changes=[
            agent_studio.BlueprintDiffChange(
                path="purpose",
                rationale="The outcome needs an explicit review artifact.",
                replacement_json='"Prepare a concise, cited portfolio risk review for a human decision maker."',
            )
        ],
        acceptance_criteria=["The purpose names a reviewable artifact."],
    )

    refined, applied, normalizations = agent_studio.apply_blueprint_diff(blueprint, document)
    after = refined.model_dump(mode="json")

    assert after["purpose"] != before["purpose"]
    assert applied[0]["path"] == "purpose"
    assert normalizations == []
    for field, value in before.items():
        if field != "purpose":
            assert after[field] == value


def test_invalid_blueprint_diff_reports_the_failing_field() -> None:
    blueprint = agent_studio.AgentBlueprint.model_validate(
        agent_studio.risk_agent_templates()[0]["blueprint"]
    )
    document = agent_studio.BlueprintDiffDocument(
        summary="Deliberately invalid reliability value for a diagnostic test.",
        changes=[
            agent_studio.BlueprintDiffChange(
                path="timeout_seconds",
                rationale="Exercise field-level validation diagnostics.",
                replacement_json="999",
            )
        ],
        acceptance_criteria=["Validation rejects the invalid timeout."],
    )

    with pytest.raises(ValueError, match="timeout_seconds"):
        agent_studio.apply_blueprint_diff(blueprint, document)


def test_blueprint_refinement_bounds_generated_nested_text_and_records_it() -> None:
    blueprint = agent_studio.AgentBlueprint.model_validate(
        agent_studio.risk_agent_templates()[0]["blueprint"]
    )
    prompt_template = blueprint.prompt_template.model_dump(mode="json")
    prompt_template["output_format_instruction"] = "material risk finding " * 100
    document = agent_studio.BlueprintDiffDocument(
        summary="Refine the prompt template while preserving its canonical field bounds.",
        changes=[
            agent_studio.BlueprintDiffChange(
                path="prompt_template",
                rationale="Make the output instruction more specific without invalidating the blueprint.",
                replacement_json=json.dumps(prompt_template),
            )
        ],
        acceptance_criteria=["The nested output instruction respects its field contract."],
    )

    refined, _, normalizations = agent_studio.apply_blueprint_diff(blueprint, document)

    assert len(refined.prompt_template.output_format_instruction) <= 1200
    assert normalizations == [
        {
            "path": "prompt_template.output_format_instruction",
            "reason": "Generated text exceeded the canonical field contract.",
            "original_length": 2200,
            "final_length": 1200,
            "max_length": 1200,
        }
    ]


def test_object_interaction_review_exposes_missing_capability_dependency() -> None:
    blueprint = agent_studio.AgentBlueprint.model_validate(
        agent_studio.risk_agent_templates()[0]["blueprint"]
    ).model_copy(
        update={
            "purpose": (
                "Analyse portfolio risk and modify the monitoring dashboard with the "
                "most material evidence for human review."
            )
        }
    )

    dependencies = agent_studio.blueprint_object_capability_dependencies(blueprint)
    dashboard = next(item for item in dependencies if item["object_kind"] == "dashboard")
    ledger = agent_studio.blueprint_requirement_ledger(blueprint)
    requirement = next(
        item
        for item in ledger
        if item["requirement_id"] == "system-object-dashboard-capability"
    )

    assert dashboard["status"] == "missing_capability"
    assert requirement["status"] == "partial"
    assert requirement["source"] == "system_object_binding"
    assert "Studio-Codex" in requirement["proposed_correction"]


def test_configuration_review_compiles_and_routes_codex_without_an_llm_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blueprint = agent_studio.AgentBlueprint.model_validate(
        agent_studio.risk_agent_templates()[0]["blueprint"]
    )
    monkeypatch.setattr(agent_studio, "AGENT_DEVELOPMENT_ROOT", tmp_path / "development")
    monkeypatch.setattr(agent_studio, "RUN_ROOT", tmp_path / "runs")
    result = agent_studio.review_blueprint_configuration(
        agent_studio.BlueprintReviewRequest(
            candidate=blueprint,
            baseline=blueprint,
            include_luna=False,
            persist=True,
        )
    )

    assert result["compile"]["persisted"] is False
    assert result["compile"]["checks"]
    assert result["complexity"]["score"] > 0
    assert result["codex"] == {
        "required": True,
        "model": "gpt-5.6-terra",
        "reasoning_effort": "high",
        "phase": "read_only_review",
        "automatic_after_job_authorization": True,
        "permission_requests_require_human_approval": True,
    }
    assert result["luna"]["status"] == "not_requested"
    history = agent_studio.agent_development_history(blueprint.name, blueprint.version)
    assert history["counts"] == {"reviews": 1, "runs": 0}
    assert history["memory_policy"]["archived"].startswith("Complete run files")


def test_user_requirement_identity_is_stable_across_review_order() -> None:
    blueprint = agent_studio.AgentBlueprint.model_validate(
        agent_studio.risk_agent_templates()[0]["blueprint"]
    )
    statements = [
        "Preserve the point-in-time evidence boundary.",
        "Return a concise Markdown review for human approval.",
    ]

    first = {
        item["statement"]: item["requirement_id"]
        for item in agent_studio.blueprint_requirement_ledger(blueprint, statements)
        if item["source"] == "user"
    }
    second = {
        item["statement"]: item["requirement_id"]
        for item in agent_studio.blueprint_requirement_ledger(
            blueprint, list(reversed(statements))
        )
        if item["source"] == "user"
    }

    assert first == second
    assert all(value.startswith("user-") and len(value) == 17 for value in first.values())


def test_later_user_refinement_supersedes_older_open_wording() -> None:
    blueprint = agent_studio.AgentBlueprint.model_validate(
        agent_studio.risk_agent_templates()[0]["blueprint"]
    )

    review = agent_studio.review_blueprint_configuration(
        agent_studio.BlueprintReviewRequest(
            candidate=blueprint,
            user_requirements=[
                "Add a concrete Markdown renderer before this candidate can be saved.",
                "Preserve the candidate and resolve the Markdown renderer by a bounded diff.",
            ],
            include_luna=False,
            persist=False,
        )
    )

    user_requirements = [
        item for item in review["requirements"] if item["source"] == "user"
    ]
    assert user_requirements[0]["status"] == "not_applicable"
    assert "Superseded by a later user refinement" in user_requirements[0]["evidence"]
    assert user_requirements[1]["status"] == "unproven"
    open_user_requirements = [
        item
        for item in review["requirements"]
        if item["source"] == "user"
        and item["status"] in {"partial", "conflict", "unproven"}
        and item["materiality"] in {"critical", "high"}
    ]
    assert len(open_user_requirements) == 1


def test_concentration_monitor_v020_compiles_a_strict_markdown_review() -> None:
    blueprint = agent_studio.concentration_and_mandate_monitor_blueprint()
    compilation = agent_studio.compile_blueprint(blueprint, persist=False)
    assessment = agent_studio.blueprint_complexity_assessment(blueprint, compilation)
    draft = agent_studio.build_concentration_review_draft(
        {
            "as_of_date": "2008-09-15",
            "largest_weight": 0.31,
            "applicable_mandate_limit": 0.25,
            "cash_weight": 0.05,
            "evidence_state": "complete",
        },
        [
            {
                "canonical_capability_id": "portfolio.exposure.summarize",
                "status": "succeeded",
                "result": {
                    "largest_position": {"instrument_id": "instrument-a", "weight": 0.31},
                    "cash_weight": 0.05,
                },
                "receipt": {"evidence_ids": ["evidence:portfolio-1"]},
            }
        ],
    )

    markdown = agent_studio.render_concentration_review_markdown(draft)

    assert blueprint.name == "concentration_and_mandate_monitor"
    assert blueprint.version == "0.2.0"
    assert blueprint.structured_output.rendering_target == "markdown_document"
    assert assessment["codex_route"] == "read_only_review"
    assert draft["mandate_comparison"]["comparison_status"] == "exceeds_limit"
    assert [line for line in markdown.splitlines() if line.startswith("## ")] == [
        "## One-sentence conclusion",
        "## Largest exposures",
        "## Largest exposure versus applicable mandate limit",
        "## Why the concentration matters",
        "## Evidence references",
        "## Missing information and uncertainty",
        "## Suggested human review actions",
    ]
    assert "<script" not in markdown
    assert '"revise": "draft", "continue": "human_review"' in compilation["source"]


def test_concentration_monitor_abstains_when_mandate_evidence_is_stale() -> None:
    draft = agent_studio.build_concentration_review_draft(
        {
            "as_of_date": "2008-09-15",
            "largest_weight": 0.31,
            "applicable_mandate_limit": 0.25,
            "evidence_state": "stale",
        },
        [],
    )

    markdown = agent_studio.render_concentration_review_markdown(draft)

    assert draft["mandate_comparison"]["comparison_status"] == "comparison_unavailable"
    assert "compliance" not in draft["conclusion"].casefold()
    assert "breach" not in draft["conclusion"].casefold()
    assert "comparison_unavailable" in markdown
    assert draft["missing_information_uncertainty"][0]["handling"].startswith("Abstain")


def test_concentration_monitor_rejects_adversarial_markdown_and_bounds_revisions() -> None:
    draft = agent_studio.build_concentration_review_draft(
        {"as_of_date": "2008-09-15", "evidence_state": "missing"}, []
    )
    draft["suggested_human_review_actions"] = ["Sell the largest position now."]
    draft["unexpected_section"] = "<script>alert(1)</script>"

    validation = agent_studio.validate_concentration_review_draft(draft)

    assert validation["status"] == "failed"
    assert {item["field"] for item in validation["conflicts"]} >= {
        "fields",
        "suggested_human_review_actions",
    }
    with pytest.raises(ValueError, match="strict concentration review validation failed"):
        agent_studio.render_concentration_review_markdown(draft)

    source = agent_studio.compile_blueprint(
        agent_studio.concentration_and_mandate_monitor_blueprint(), persist=False
    )["source"]
    assert 'state.get("iteration", 0) < BLUEPRINT["max_iterations"]' in source
    assert '"critique_requires_revision": bool(' in source


def test_generated_agent_binds_semantic_context_and_capability_results() -> None:
    payload = agent_studio.risk_agent_templates()[1]["blueprint"]
    payload["prompt_template"]["template"] = (
        "Portfolio context: {portfolio_context}\n"
        "Capability evidence: {capability_results}"
    )
    payload["prompt_template"]["variables"] = [
        "portfolio_context",
        "capability_results",
    ]
    payload["prompt_template"]["missing_variable_policy"] = "fail"
    blueprint = agent_studio.AgentBlueprint.model_validate(payload)
    namespace: dict[str, object] = {}
    exec(agent_studio._module_source(blueprint), namespace)

    rendered = namespace["render_prompt"](
        {
            "overall_context": {
                "portfolio_name": "Synthetic test portfolio",
                "largest_weight": 0.31,
                "mandate_status": "concentration review required",
            },
            "capability_results": [
                {
                    "capability": "portfolio_exposure",
                    "canonical_capability_id": "portfolio.exposure.summarize",
                    "status": "succeeded",
                    "detail": "Largest position is 31.0%.",
                    "result": {"largest_position": {"weight": 0.31}},
                    "receipt": {"evidence_ids": ["evidence:portfolio"]},
                }
            ],
        }
    )

    assert "Synthetic test portfolio" in rendered
    assert "portfolio.exposure.summarize" in rendered
    assert "evidence:portfolio" in rendered


def test_generated_live_node_uses_validated_runtime_model(monkeypatch: pytest.MonkeyPatch) -> None:
    blueprint = agent_studio.AgentBlueprint.model_validate(
        agent_studio.risk_agent_templates()[1]["blueprint"]
    )
    namespace: dict[str, object] = {}
    exec(agent_studio._module_source(blueprint), namespace)
    observed: dict[str, object] = {}

    def fake_live_interpretation(**kwargs: object) -> dict[str, object]:
        observed.update(kwargs)
        return {
            "interpretation": {
                "narrative": "Concentration requires human review.",
                "rationale_summary": ["Largest position exceeds the supplied limit."],
            },
            "receipt": {"provider": "test", "model": kwargs["model"]},
        }

    monkeypatch.setattr(
        agent_studio, "execute_live_interpretation", fake_live_interpretation
    )
    result = namespace["draft"](
        {
            "context": {
                "_agent_execution_mode": "live_llm",
                "_agent_execution_model": "gpt-5.6-luna",
                "as_of_date": "2008-09-15",
                "portfolio_name": "Synthetic test portfolio",
                "mandate_status": "concentration review required",
                "evidence_state": "complete",
            },
            "capability_results": [],
            "model_receipts": [],
            "trace": [],
        }
    )

    assert observed["model"] == "gpt-5.6-luna"
    assert result["narrative"] == "Concentration requires human review."
    assert result["model_receipts"][0]["model"] == "gpt-5.6-luna"


def test_semantic_context_normalizes_aliases_and_detects_availability_conflicts() -> None:
    context = agent_studio._scenario_context("concentration")
    capability_results = [
        {
            "canonical_capability_id": "portfolio.exposure.summarize",
            "status": "succeeded",
            "result": {
                "coverage_status": "complete",
                "total_position_count": 4,
                "priced_position_count": 4,
                "excluded_positions": [],
                "weight_basis": "complete valued portfolio plus cash",
                "largest_position": {"instrument_id": "instrument-a", "weight": 0.31},
                "cash_weight": 0.05,
                "gross_exposure": 0.95,
                "net_exposure": 0.95,
            },
            "receipt": {"evidence_ids": ["evidence:synthetic"]},
        }
    ]
    normalized, facts = agent_studio.assemble_semantic_context(
        context, capability_results
    )
    assert normalized["maximum_drawdown"] == pytest.approx(0.026)
    assert normalized["valuation_coverage"]["status"] == "complete"
    assert normalized["concentration_excess"] == pytest.approx(0.06)

    verification = agent_studio.verify_interpretation_semantics(
        normalized,
        {
            "uncertainties": [
                "Valuation coverage is unavailable and maximum drawdown was not calculated."
            ]
        },
        "The largest position is 31.00% against a 25.00% concentration limit.",
        facts,
    )
    assert verification["status"] == "failed"
    assert {item["fact_id"] for item in verification["conflicts"]} >= {
        "portfolio.valuation_coverage",
        "risk.maximum_drawdown",
    }


def test_historically_calibrated_synthetic_reserves_oos_and_retains_no_rows() -> None:
    start = date(2000, 1, 1)
    values = []
    portfolio_value = 100.0
    for index in range(80):
        portfolio_value *= 1 + (0.001 if index % 2 else -0.0005)
        values.append(
            {
                "observed_at": (start + timedelta(days=index)).isoformat(),
                "portfolio_value": portfolio_value,
            }
        )
    context, provenance = agent_studio.historically_calibrated_synthetic_context(
        scenario="concentration",
        historical_values=values,
        portfolio_id="private-portfolio",
        as_of="2001-01-31",
    )
    assert context["data_truth"] == "historically_calibrated_synthetic"
    assert context["metric_pack_input"]["synthetic"] is True
    assert provenance["licensed_data_used_for_calibration"] is True
    assert provenance["licensed_rows_retained"] is False
    assert provenance["reserved_oos_window"]["used_for_generation"] is False
    serialized = str(context)
    assert "private-portfolio" not in serialized


def test_comparison_runner_freezes_one_input_for_both_methods(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blueprint = agent_studio.AgentBlueprint.model_validate(
        agent_studio.risk_agent_templates()[1]["blueprint"]
    )
    frozen_context = agent_studio._scenario_context("concentration")
    observed: list[agent_studio.RunRequest] = []

    monkeypatch.setattr(
        duckdb_server,
        "prepare_agent_input",
        lambda _request: (frozen_context, {"data_mode": "synthetic_behavior_sample"}),
    )

    def fake_run(request: agent_studio.RunRequest) -> dict[str, object]:
        observed.append(request)
        return {
            "elapsed_ms": 1.0,
            "final_state": {
                "semantic_verification": {"status": "passed"},
                "model_receipts": (
                    [{"total_tokens": 10}] if request.execution_mode == "live_llm" else []
                ),
            },
        }

    monkeypatch.setattr(duckdb_server, "run_blueprint", fake_run)
    result = duckdb_server.compare_agent_execution(
        agent_studio.RunRequest(blueprint=blueprint, persist_run=True)
    )

    assert [item.execution_mode for item in observed] == ["deterministic", "live_llm"]
    assert observed[0].input_context == observed[1].input_context == frozen_context
    assert observed[0].comparison_id == observed[1].comparison_id == result["comparison_id"]
    assert result["same_frozen_input"] is True
    assert result["summary"]["model_tokens"] == 10
