from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError
from risk_experiments import (
    AuthorityEnvelope,
    AutonomyPolicy,
    CapabilityPack,
    ContextGraphSnapshot,
    DashboardPackageDefinition,
    DataSnapshotManifest,
    DatasetAccessGrant,
    DatasetRevisionBinding,
    EffectPolicy,
    EvaluationSuiteDefinition,
    EvaluationThreshold,
    ExperimentObjectSet,
    GovernanceRoute,
    MandateCapabilityRequirement,
    MandateConstraint,
    MandateSource,
    MandateVersion,
    MarketEnvironmentSnapshot,
    ModelRoutePolicy,
    OutputEvaluationPack,
    PortfolioEnvironmentView,
    PortfolioGovernancePack,
    PortfolioVersion,
    ProcessingDefinition,
    ReportTemplateDefinition,
    ResourceEnvelope,
    RiskPolicyRule,
    RiskPolicySet,
    ScenarioDefinition,
    SupraAgentPolicy,
    WorldContextPack,
)
from risk_registry import AssetKind, RegistryIdentity

from .test_scientific_design import scientific_design_pack


NOW = datetime(2024, 1, 5, 21, 0, tzinfo=timezone.utc)


def experiment_object_set() -> ExperimentObjectSet:
    scientific = scientific_design_pack()
    portfolio = PortfolioVersion(
        namespace="portfolio-risk.thesis",
        object_id="portfolio-alpha",
        version="1.0.0",
        name="Portfolio alpha",
        snapshot_reference="portfolio-snapshot:alpha@2024-01-05",
        snapshot_digest="sha256:" + "1" * 64,
        as_of=NOW,
        base_currency="USD",
        data_truth="reviewed_synthetic",
    )
    mandate = MandateVersion(
        namespace="portfolio-risk.thesis",
        object_id="research-mandate",
        version="1.0.0",
        name="Research mandate",
        objective="Preserve capital while maintaining a diversified research portfolio.",
        horizon_seconds=31_557_600,
        eligible_universe_reference="universe:reviewed-research-securities@1.0.0",
        constraints=(
            MandateConstraint(
                constraint_id="concentration",
                category="concentration",
                statement="No single position may exceed the declared concentration limit.",
                source_clause_reference="research-design#concentration",
            ),
        ),
        sources=(
            MandateSource(
                source_id="research-design",
                title="Reviewed synthetic research design",
                source_kind="synthetic_design",
                reference="fixture://mandates/research-design",
                note="Synthetic research-only mandate source.",
            ),
        ),
        capability_requirements=(
            MandateCapabilityRequirement(
                capability_reference="capability:risk:exposure@1.0.0",
                purpose="evaluate_compliance",
                constraint_ids=("concentration",),
            ),
        ),
        effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    policy = RiskPolicySet(
        namespace="portfolio-risk.thesis",
        object_id="research-risk-policy",
        version="1.0.0",
        name="Research risk policy",
        mandate_reference=mandate.reference,
        rules=(
            RiskPolicyRule(
                rule_id="position-concentration",
                mandate_constraint_id="concentration",
                system_treatment="compliance_test",
                capability_reference="capability:risk:exposure@1.0.0",
                metric_reference="metric:risk:largest-position-weight@1.0.0",
                operator="lte",
                threshold=Decimal("0.20"),
                unit="portfolio_weight",
                denominator="portfolio_nav",
                evaluation_basis="current",
                severity="breach",
                escalation="decision_required",
                governance_route=GovernanceRoute(
                    outcome="require_decision",
                    governance_level="human_reviewer",
                    decision_policy_reference="decision-policy:risk:human-review@1.0.0",
                ),
            ),
        ),
    )
    governance = PortfolioGovernancePack(
        namespace="portfolio-risk.thesis",
        object_id="portfolio-alpha-governance",
        version="1.0.0",
        name="Portfolio alpha governance",
        portfolio=portfolio,
        mandate=mandate,
        risk_policy=policy,
    )
    prices = DatasetRevisionBinding(
        dataset_id="prices",
        reference="dataset:risk:prices@2024-01-05",
        revision="2024-01-05",
        content_digest="sha256:" + "2" * 64,
        data_truth="reviewed_synthetic",
        rights_policy_reference="rights:internal-synthetic@1.0.0",
        available_at=NOW,
    )
    data = DataSnapshotManifest(
        namespace="portfolio-risk.thesis",
        object_id="daily-data",
        version="1.0.0",
        name="Daily eligible data",
        as_of=NOW,
        datasets=(prices,),
    )
    environment = MarketEnvironmentSnapshot(
        namespace="portfolio-risk.thesis",
        object_id="daily-environment",
        version="1.0.0",
        name="Daily market environment",
        as_of=NOW,
        data_manifest_reference=data.reference,
        observation_roles=("prices",),
    )
    scenario = ScenarioDefinition(
        namespace="portfolio-risk.thesis",
        object_id="observed-base",
        version="1.0.0",
        name="Observed base scenario",
        scenario_kind="observed",
        base_environment_reference=environment.reference,
        transformation="Use the eligible observed environment without transformation.",
    )
    view = PortfolioEnvironmentView(
        namespace="portfolio-risk.thesis",
        object_id="portfolio-alpha-observed-view",
        version="1.0.0",
        name="Portfolio alpha observed view",
        portfolio_reference=portfolio.reference,
        environment_reference=environment.reference,
        scenario_reference=scenario.reference,
        resolver_version="1.0.0",
    )
    graph = ContextGraphSnapshot(
        namespace="portfolio-risk.thesis",
        object_id="daily-context-graph",
        version="1.0.0",
        name="Daily context graph",
        as_of=NOW,
        node_references=tuple(sorted((environment.reference, portfolio.reference))),
    )
    world = WorldContextPack(
        namespace="portfolio-risk.thesis",
        object_id="portfolio-alpha-world",
        version="1.0.0",
        name="Portfolio alpha world",
        data_manifest=data,
        environment=environment,
        scenario=scenario,
        portfolio_view=view,
        context_graph=graph,
    )
    exposure = RegistryIdentity(
        kind=AssetKind.CAPABILITY,
        namespace="risk",
        asset_id="exposure",
        version="1.0.0",
    )
    capability_pack = CapabilityPack(
        namespace="portfolio-risk.thesis",
        object_id="basic-risk-capabilities",
        version="1.0.0",
        name="Basic risk capabilities",
        capabilities=(exposure,),
    )
    resources = ResourceEnvelope(
        namespace="portfolio-risk.thesis",
        object_id="pilot-resources",
        version="1.0.0",
        name="Pilot resource envelope",
        capability_pack=capability_pack,
        dataset_access_grants=(
            DatasetAccessGrant(
                grant_id="exposure-prices",
                capability_reference=exposure.reference,
                dataset_reference=prices.reference,
                allowed_operations=("read",),
            ),
        ),
        model_route=ModelRoutePolicy(
            namespace="portfolio-risk.thesis",
            object_id="deterministic-route",
            version="1.0.0",
            name="Deterministic route",
            route_references=("model-route:deterministic-fixture@1.0.0",),
            fallback_rule="fail_closed",
            max_calls=0,
        ),
    )
    authority = AuthorityEnvelope(
        namespace="portfolio-risk.thesis",
        object_id="human-reviewed-authority",
        version="1.0.0",
        name="Human reviewed authority",
        mandate_reference=mandate.reference,
        risk_policy_reference=policy.reference,
        processing=ProcessingDefinition(
            namespace="portfolio-risk.thesis",
            object_id="single-agent-workflow",
            version="1.0.0",
            name="Single agent processing",
            agent=RegistryIdentity(
                kind=AssetKind.AGENT,
                namespace="risk",
                asset_id="risk-analyst",
                version="1.0.0",
            ),
            graph=RegistryIdentity(
                kind=AssetKind.AGENT_GRAPH,
                namespace="risk",
                asset_id="single-agent-graph",
                version="1.0.0",
            ),
            workflow=RegistryIdentity(
                kind=AssetKind.WORKFLOW,
                namespace="risk",
                asset_id="daily-review",
                version="1.0.0",
            ),
            stop_rule="Stop after validated output or a mandatory human checkpoint.",
        ),
        autonomy=AutonomyPolicy(
            namespace="portfolio-risk.thesis",
            object_id="human-only",
            version="1.0.0",
            name="Human-only resolution",
            mode="human_only",
            proposal_actor_types=("agent", "human"),
            resolution_actor_types=("human",),
        ),
        supra_agent=SupraAgentPolicy(
            namespace="portfolio-risk.thesis",
            object_id="supra-disabled",
            version="1.0.0",
            name="Supra-agent disabled",
        ),
        effects=EffectPolicy(
            namespace="portfolio-risk.thesis",
            object_id="effects-disabled",
            version="1.0.0",
            name="Effects disabled",
            prohibited_effects=("broker_order", "external_message", "live_trade"),
        ),
    )
    output = OutputEvaluationPack(
        namespace="portfolio-risk.thesis",
        object_id="pilot-output-evaluation",
        version="1.0.0",
        name="Pilot output and evaluation",
        evaluation_suite=EvaluationSuiteDefinition(
            namespace="portfolio-risk.thesis",
            object_id="pilot-evaluation",
            version="1.0.0",
            name="Pilot evaluation suite",
            scientific_design_reference=scientific.reference,
            case_set_reference="case-set:reviewed-synthetic-pilot@1.0.0",
            seeds=(11, 29),
            repeat_count=2,
            thresholds=(
                EvaluationThreshold(
                    metric_reference=scientific.metric.reference,
                    operator="lte",
                    value=Decimal("0.25"),
                ),
            ),
        ),
        report_template=ReportTemplateDefinition(
            namespace="portfolio-risk.thesis",
            object_id="risk-review-report",
            version="1.0.0",
            name="Risk review report",
            sections=("Evidence", "Findings", "Uncertainty"),
            required_evidence_roles=("capability_receipts", "source_provenance"),
        ),
        dashboard=DashboardPackageDefinition(
            namespace="portfolio-risk.thesis",
            object_id="risk-evidence-dashboard",
            version="1.0.0",
            name="Risk evidence dashboard",
            views=("Outcome comparison",),
            metric_references=(scientific.metric.reference,),
        ),
    )
    return ExperimentObjectSet(
        namespace="portfolio-risk.thesis",
        object_set_id="pilot-object-set",
        version="1.0.0",
        scientific_design=scientific,
        portfolio_governance=governance,
        world_context=world,
        resource_envelope=resources,
        authority_envelope=authority,
        output_evaluation=output,
        resolver_version="1.0.0",
    )


def test_complete_object_set_has_four_component_digests_and_one_fixture_digest() -> None:
    value = experiment_object_set()
    assert value.registry_identity.kind is AssetKind.EXPERIMENT_OBJECT_SET
    assert all(
        getattr(value, field).startswith("sha256:")
        for field in (
            "world_context_digest",
            "resource_envelope_digest",
            "authority_envelope_digest",
            "evaluation_envelope_digest",
            "fixture_context_digest",
        )
    )
    assert ExperimentObjectSet.model_validate_json(value.model_dump_json()) == value


def test_agent_choice_is_dynamic_only_inside_the_frozen_resource_envelope() -> None:
    value = experiment_object_set()
    capability = value.resource_envelope.capability_pack.capabilities[0].reference
    dataset = value.world_context.data_manifest.datasets[0].reference
    fixture_digest = value.fixture_context_digest
    assert value.resource_envelope.allows_capability(capability)
    assert value.resource_envelope.allows_dataset(capability, dataset)
    assert not value.resource_envelope.allows_capability(
        "capability:risk:undeclared@1.0.0"
    )
    assert value.fixture_context_digest == fixture_digest


def test_declared_world_change_changes_only_world_and_fixture_digests() -> None:
    original = experiment_object_set()
    scenario_payload = original.world_context.scenario.model_dump(mode="json")
    scenario_payload["transformation"] = "Apply the separately declared stress transformation."
    scenario_payload["object_digest"] = None
    changed_scenario = ScenarioDefinition.model_validate(scenario_payload)

    world_payload = original.world_context.model_dump(mode="json")
    world_payload["scenario"] = changed_scenario.model_dump(mode="json")
    world_payload["portfolio_view"]["scenario_reference"] = changed_scenario.reference
    world_payload["portfolio_view"]["object_digest"] = None
    world_payload["object_digest"] = None
    changed_world = WorldContextPack.model_validate(world_payload)

    object_set_payload = original.model_dump(mode="json")
    object_set_payload["world_context"] = changed_world.model_dump(mode="json")
    for field in (
        "world_context_digest",
        "resource_envelope_digest",
        "authority_envelope_digest",
        "evaluation_envelope_digest",
        "fixture_context_digest",
    ):
        object_set_payload[field] = None
    changed = ExperimentObjectSet.model_validate(object_set_payload)

    assert changed.world_context_digest != original.world_context_digest
    assert changed.fixture_context_digest != original.fixture_context_digest
    assert changed.resource_envelope_digest == original.resource_envelope_digest
    assert changed.authority_envelope_digest == original.authority_envelope_digest
    assert changed.evaluation_envelope_digest == original.evaluation_envelope_digest


def test_post_as_of_data_and_undeclared_dataset_grants_fail_closed() -> None:
    value = experiment_object_set()
    data_payload = value.world_context.data_manifest.model_dump(mode="json")
    data_payload["datasets"][0]["available_at"] = "2024-01-06T00:00:00Z"
    data_payload["object_digest"] = None
    with pytest.raises(ValidationError, match="after the manifest"):
        DataSnapshotManifest.model_validate(data_payload)

    payload = value.model_dump(mode="json")
    payload["resource_envelope"]["dataset_access_grants"][0][
        "dataset_reference"
    ] = "dataset:risk:undeclared@1.0.0"
    payload["resource_envelope"]["object_digest"] = None
    for field in (
        "world_context_digest",
        "resource_envelope_digest",
        "authority_envelope_digest",
        "evaluation_envelope_digest",
        "fixture_context_digest",
    ):
        payload[field] = None
    with pytest.raises(ValidationError, match="world data manifest"):
        ExperimentObjectSet.model_validate(payload)


def test_supra_agent_authority_is_explicit_and_disabled_by_default() -> None:
    value = experiment_object_set()
    assert value.authority_envelope.autonomy.mode == "human_only"
    assert not value.authority_envelope.supra_agent.enabled
    payload = value.authority_envelope.model_dump(mode="json")
    payload["supra_agent"]["enabled"] = True
    payload["supra_agent"]["agent_reference"] = "agent:risk:supra@1.0.0"
    payload["supra_agent"]["allowed_decision_classes"] = ["risk_position"]
    payload["supra_agent"]["max_resolutions_per_run"] = 1
    payload["supra_agent"]["object_digest"] = None
    payload["object_digest"] = None
    with pytest.raises(ValidationError, match="autonomy mode"):
        AuthorityEnvelope.model_validate(payload)


def test_presentation_objects_cannot_hide_calculations() -> None:
    value = experiment_object_set()
    payload = value.output_evaluation.dashboard.model_dump(mode="json")
    payload["hidden_calculations"] = True
    payload["object_digest"] = None
    with pytest.raises(ValidationError):
        DashboardPackageDefinition.model_validate(payload)
