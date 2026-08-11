"""One reviewed-synthetic calibration candidate admitted for Fixture development."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from risk_registry import (
    AssetKind,
    Compatibility,
    Provenance,
    RegistryIdentity,
    RegistryProjection,
    RegistryRelationship,
    SourceReference,
)

from .experiment_objects import (
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
from .scientific_design import (
    BaselineDefinition,
    HypothesisDefinition,
    InformationRegimeDefinition,
    MetricDefinition,
    MetricDirection,
    ResearchQuestionDefinition,
    RiskOutcomeDefinition,
    RiskOutcomeState,
    ScientificDesignPack,
)
from .fixture_context import (
    FixtureSourceBinding,
    FixtureSourceManifest,
    MethodologyAcceptanceRecord,
)
from .models import canonical_digest


NAMESPACE = "portfolio-risk.thesis"
VERSION = "1.0.0"
FIXTURE_AVAILABLE_AT = datetime(2026, 7, 30, tzinfo=timezone.utc)
PORTFOLIO_AS_OF = datetime(2024, 6, 14, 17, 0, tzinfo=timezone.utc)


def _scientific_design() -> ScientificDesignPack:
    question = ResearchQuestionDefinition(
        namespace=NAMESPACE,
        definition_id="calibration-agent-vs-b0",
        version=VERSION,
        name="Structured assessment calibration question",
        question=(
            "Across the reviewed-synthetic portfolio-date cases, does a structured "
            "single-agent assessment using the same holdings and prices reduce "
            "five-session forward risk-position ordinal error relative to the "
            "deterministic concentration-policy baseline?"
        ),
        population=(
            "The 45 reviewed-synthetic portfolio-date cases declared by the Thesis "
            "Day 4 fixture across three fictional portfolios and three windows."
        ),
        unit_of_analysis=(
            "One paired portfolio-date case evaluated under B0 and the structured "
            "single-agent treatment."
        ),
        intervention=(
            "A deterministic structured-agent fixture assessment with the declared "
            "resource envelope and evidence duties."
        ),
        comparator=(
            "B0 applies the predeclared largest-position concentration policy to the "
            "same portfolio, prices, window and as-of boundary."
        ),
        estimand=(
            "The paired mean difference in absolute ordinal error, treatment minus "
            "B0, over all eligible portfolio-date cases."
        ),
    )
    outcome = RiskOutcomeDefinition(
        namespace=NAMESPACE,
        definition_id="five-session-concentration-position",
        version=VERSION,
        name="Five-session concentration risk position",
        unit_of_analysis="One portfolio at one predeclared review time.",
        observation_horizon_seconds=604_800,
        states=(
            RiskOutcomeState(
                state_id="optimal",
                ordinal=0,
                label="Optimal",
                criterion=(
                    "No concentration breach occurs over the next five eligible "
                    "business sessions and minimum policy headroom is at least ten "
                    "percentage points."
                ),
            ),
            RiskOutcomeState(
                state_id="good",
                ordinal=1,
                label="Good",
                criterion=(
                    "No concentration breach occurs, but minimum policy headroom is "
                    "less than ten percentage points."
                ),
            ),
            RiskOutcomeState(
                state_id="bad",
                ordinal=2,
                label="Bad",
                criterion=(
                    "A concentration breach occurs for at most two eligible sessions "
                    "and maximum threshold excess is no more than five percentage points."
                ),
                is_breach=True,
            ),
            RiskOutcomeState(
                state_id="very_bad",
                ordinal=3,
                label="Very bad",
                criterion=(
                    "A concentration breach lasts more than two eligible sessions or "
                    "maximum threshold excess is greater than five percentage points."
                ),
                is_breach=True,
            ),
        ),
        mitigation_rule=(
            "This effect-free calibration cannot claim risk mitigation or avoidance. "
            "Those labels require a separately predeclared simulated-intervention "
            "counterfactual whose decision precedes the changed outcome."
        ),
        censoring_rule=(
            "A case without all five eligible forward sessions, a complete portfolio "
            "path or a calculable concentration metric is censored and reported."
        ),
    )
    return ScientificDesignPack(
        namespace=NAMESPACE,
        pack_id="calibration-agent-vs-b0",
        version=VERSION,
        name="Calibration pilot: structured agent versus B0",
        owner="local.researcher",
        research_question=question,
        hypothesis=HypothesisDefinition(
            namespace=NAMESPACE,
            definition_id="calibration-agent-vs-b0",
            version=VERSION,
            name="Structured assessment calibration hypothesis",
            research_question_reference=question.reference,
            statement=(
                "The structured-agent fixture has lower mean absolute ordinal error "
                "than B0 on the paired calibration cases."
            ),
            expected_direction=(
                "The paired treatment-minus-B0 mean absolute ordinal-error difference "
                "is below zero."
            ),
            falsification_condition=(
                "The paired interval includes zero, the point estimate is zero or "
                "positive, or differential censoring prevents the paired comparison."
            ),
        ),
        baseline=BaselineDefinition(
            namespace=NAMESPACE,
            definition_id="concentration-policy-b0",
            version=VERSION,
            name="B0 deterministic concentration policy",
            step_id="b0",
            comparator_kind="deterministic",
            behaviour=(
                "Calculate largest-position weight, compare it with the exact 35% "
                "policy limit, and map the declared headroom to the four-state scale."
            ),
            resource_references=("capability:risk:exposure@1.0.0",),
        ),
        information_regime=InformationRegimeDefinition(
            namespace=NAMESPACE,
            definition_id="holdings-prices-window",
            version=VERSION,
            name="Holdings, prices and declared window",
            evidence_categories=("holdings", "prices", "window_context"),
            resource_references=(
                "dataset:portfolio-risk.thesis:day4-pricing@2026-07-30.1",
                "dataset:portfolio-risk.thesis:day4-windows@2026-07-30.1",
            ),
        ),
        risk_outcome=outcome,
        metric=MetricDefinition(
            namespace=NAMESPACE,
            definition_id="paired-ordinal-risk-error",
            version=VERSION,
            name="Paired ordinal risk-position error",
            risk_outcome_reference=outcome.reference,
            estimand=(
                "Paired mean treatment-minus-B0 difference in absolute ordinal error."
            ),
            formula=(
                "mean(abs(treatment_ordinal - observed_ordinal) - "
                "abs(b0_ordinal - observed_ordinal))"
            ),
            aggregation=(
                "Calculate one paired difference per eligible portfolio-date, then "
                "average equally; also report results by portfolio and window."
            ),
            direction=MetricDirection.LOWER_IS_BETTER,
            missingness_rule=(
                "Use complete paired cases only, report censored and missing counts by "
                "arm and reason, and block inference under differential missingness."
            ),
            uncertainty_rule=(
                "Report a paired percentile bootstrap interval over portfolio-window "
                "clusters; treat it as descriptive during apparatus calibration."
            ),
        ),
    )


def build_calibration_pilot() -> ExperimentObjectSet:
    """Build the exact human-reviewed, effect-free P7 calibration candidate."""

    scientific = _scientific_design()
    portfolio = PortfolioVersion(
        namespace=NAMESPACE,
        object_id="diversified-synthetic",
        version=VERSION,
        name="Fictional diversified portfolio",
        snapshot_reference=(
            "examples/portfolio-risk-thesis/portfolios/diversified.yaml"
        ),
        snapshot_digest=(
            "sha256:af218b1573c16b1b7b25b33789970e3775fcf87dd430f4bc4b99e9927b33b2aa"
        ),
        as_of=PORTFOLIO_AS_OF,
        base_currency="USD",
        data_truth="reviewed_synthetic",
    )
    mandate = MandateVersion(
        namespace=NAMESPACE,
        object_id="calibration-mandate",
        version=VERSION,
        name="Calibration pilot mandate",
        objective=(
            "Preserve capital in a fictional diversified portfolio while testing "
            "effect-free concentration-risk assessment."
        ),
        horizon_seconds=31_557_600,
        eligible_universe_reference="universe:reviewed-synthetic-securities@1.0.0",
        constraints=(
            MandateConstraint(
                constraint_id="largest-position",
                category="concentration",
                statement="Largest position weight must not exceed 35%.",
                clause_type="hard_constraint",
                system_treatment="compliance_test",
                source_clause_reference="calibration-design#largest-position",
            ),
        ),
        sources=(
            MandateSource(
                source_id="calibration-design",
                title="Reviewed calibration-pilot design",
                source_kind="synthetic_design",
                reference="docs/thesis/methodology-acceptance-calibration-pilot.md",
                note="Research-only mandate language created for apparatus calibration.",
            ),
        ),
        capability_requirements=(
            MandateCapabilityRequirement(
                capability_reference="capability:risk:exposure@1.0.0",
                purpose="evaluate_compliance",
                constraint_ids=("largest-position",),
            ),
        ),
        applicable_law_notes=(
            "No legal or regulatory statement has operative effect in this calibration mandate.",
        ),
        effective_from=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )
    policy = RiskPolicySet(
        namespace=NAMESPACE,
        object_id="calibration-risk-policy",
        version=VERSION,
        name="Calibration concentration policy",
        mandate_reference=mandate.reference,
        rules=(
            RiskPolicyRule(
                rule_id="largest-position",
                mandate_constraint_id="largest-position",
                system_treatment="compliance_test",
                capability_reference="capability:risk:exposure@1.0.0",
                metric_reference="metric:risk:largest-position-weight@1.0.0",
                operator="lte",
                threshold=Decimal("0.35"),
                unit="portfolio_weight",
                denominator="portfolio_nav",
                evaluation_basis="current",
                severity="breach",
                escalation="human_review",
                governance_route=GovernanceRoute(
                    outcome="request_review",
                    governance_level="human_reviewer",
                    decision_policy_reference="decision-policy:calibration-human-review@1.0.0",
                ),
            ),
        ),
    )
    governance = PortfolioGovernancePack(
        namespace=NAMESPACE,
        object_id="calibration-governance",
        version=VERSION,
        name="Calibration portfolio governance",
        portfolio=portfolio,
        mandate=mandate,
        risk_policy=policy,
    )
    datasets = (
        DatasetRevisionBinding(
            dataset_id="pricing",
            reference="dataset:portfolio-risk.thesis:day4-pricing@2026-07-30.1",
            revision="2026-07-30.1",
            content_digest=(
                "sha256:857ff016286afaaf03a4b5887ba98713b1e839670aa19bc1129e9726cb3d318a"
            ),
            data_truth="reviewed_synthetic",
            rights_policy_reference="rights:repository-reviewed-synthetic@1.0.0",
            available_at=FIXTURE_AVAILABLE_AT,
        ),
        DatasetRevisionBinding(
            dataset_id="windows",
            reference="dataset:portfolio-risk.thesis:day4-windows@2026-07-30.1",
            revision="2026-07-30.1",
            content_digest=(
                "sha256:30c9784b77e3664aa4cdbcfda87301f394675bc605d725b06124a9321f1b8b32"
            ),
            data_truth="reviewed_synthetic",
            rights_policy_reference="rights:repository-reviewed-synthetic@1.0.0",
            available_at=FIXTURE_AVAILABLE_AT,
        ),
    )
    data_manifest = DataSnapshotManifest(
        namespace=NAMESPACE,
        object_id="calibration-inputs",
        version=VERSION,
        name="Calibration input manifest",
        as_of=FIXTURE_AVAILABLE_AT,
        datasets=datasets,
    )
    environment = MarketEnvironmentSnapshot(
        namespace=NAMESPACE,
        object_id="calibration-environment",
        version=VERSION,
        name="Calibration synthetic environment",
        as_of=FIXTURE_AVAILABLE_AT,
        data_manifest_reference=data_manifest.reference,
        observation_roles=("holdings", "prices", "window_context"),
    )
    scenario = ScenarioDefinition(
        namespace=NAMESPACE,
        object_id="declared-calibration-windows",
        version=VERSION,
        name="Declared synthetic stress and control windows",
        scenario_kind="synthetic",
        base_environment_reference=environment.reference,
        transformation=(
            "Use only the predeclared fictional stress_a, stress_b and control windows."
        ),
        calibration_reference=(
            "data/fixtures/synthetic/thesis-day4/fixture-manifest.json"
        ),
        seed=2_026_0730,
    )
    view = PortfolioEnvironmentView(
        namespace=NAMESPACE,
        object_id="diversified-calibration-view",
        version=VERSION,
        name="Diversified calibration view",
        portfolio_reference=portfolio.reference,
        environment_reference=environment.reference,
        scenario_reference=scenario.reference,
        resolver_version="1.0.0",
    )
    graph = ContextGraphSnapshot(
        namespace=NAMESPACE,
        object_id="calibration-context-graph",
        version=VERSION,
        name="Calibration context graph",
        as_of=FIXTURE_AVAILABLE_AT,
        node_references=tuple(sorted((environment.reference, portfolio.reference))),
    )
    world = WorldContextPack(
        namespace=NAMESPACE,
        object_id="calibration-world",
        version=VERSION,
        name="Calibration world context",
        data_manifest=data_manifest,
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
    resources = ResourceEnvelope(
        namespace=NAMESPACE,
        object_id="calibration-resources",
        version=VERSION,
        name="Calibration resource envelope",
        capability_pack=CapabilityPack(
            namespace=NAMESPACE,
            object_id="calibration-capabilities",
            version=VERSION,
            name="Calibration capability pack",
            capabilities=(exposure,),
        ),
        dataset_access_grants=(
            DatasetAccessGrant(
                grant_id="exposure-pricing",
                capability_reference=exposure.reference,
                dataset_reference=datasets[0].reference,
                allowed_operations=("aggregate", "filter", "read"),
            ),
            DatasetAccessGrant(
                grant_id="exposure-windows",
                capability_reference=exposure.reference,
                dataset_reference=datasets[1].reference,
                allowed_operations=("filter", "read"),
            ),
        ),
        model_route=ModelRoutePolicy(
            namespace=NAMESPACE,
            object_id="fixture-only-route",
            version=VERSION,
            name="Deterministic fixture-only route",
            route_references=("model-route:fixture-structured-v1@1.0.0",),
            fallback_rule="deterministic_fixture_only",
            max_calls=0,
        ),
    )
    authority = AuthorityEnvelope(
        namespace=NAMESPACE,
        object_id="calibration-authority",
        version=VERSION,
        name="Calibration human-only authority",
        mandate_reference=mandate.reference,
        risk_policy_reference=policy.reference,
        processing=ProcessingDefinition(
            namespace=NAMESPACE,
            object_id="calibration-processing",
            version=VERSION,
            name="Calibration structured-agent processing",
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
            stop_rule=(
                "Stop after one schema-valid assessment or a mandatory human checkpoint."
            ),
        ),
        autonomy=AutonomyPolicy(
            namespace=NAMESPACE,
            object_id="calibration-human-only",
            version=VERSION,
            name="Calibration human-only resolution",
            mode="human_only",
            proposal_actor_types=("agent", "human"),
            resolution_actor_types=("human",),
        ),
        supra_agent=SupraAgentPolicy(
            namespace=NAMESPACE,
            object_id="calibration-supra-disabled",
            version=VERSION,
            name="Calibration supra-agent disabled",
        ),
        effects=EffectPolicy(
            namespace=NAMESPACE,
            object_id="calibration-effects-disabled",
            version=VERSION,
            name="Calibration effects disabled",
            prohibited_effects=("broker_order", "external_message", "live_trade"),
        ),
    )
    output = OutputEvaluationPack(
        namespace=NAMESPACE,
        object_id="calibration-output-evaluation",
        version=VERSION,
        name="Calibration output and evaluation",
        evaluation_suite=EvaluationSuiteDefinition(
            namespace=NAMESPACE,
            object_id="calibration-evaluation",
            version=VERSION,
            name="Calibration evaluation suite",
            scientific_design_reference=scientific.reference,
            case_set_reference=(
                "case-set:portfolio-risk.thesis:day4-45-reviewed-synthetic@1.0.0"
            ),
            seeds=(11, 29),
            repeat_count=2,
            thresholds=(
                EvaluationThreshold(
                    metric_reference=scientific.metric.reference,
                    operator="lte",
                    value=Decimal("1.0"),
                ),
            ),
        ),
        report_template=ReportTemplateDefinition(
            namespace=NAMESPACE,
            object_id="calibration-report",
            version=VERSION,
            name="Calibration evidence report",
            sections=(
                "Question and design",
                "Input integrity",
                "Predictions and outcomes",
                "Paired comparison",
                "Missingness and limitations",
            ),
            required_evidence_roles=("capability_receipts", "source_provenance"),
        ),
        dashboard=DashboardPackageDefinition(
            namespace=NAMESPACE,
            object_id="calibration-dashboard",
            version=VERSION,
            name="Calibration evidence dashboard",
            views=("Paired ordinal error", "Outcome distribution", "Censoring"),
            metric_references=(scientific.metric.reference,),
        ),
    )
    return ExperimentObjectSet(
        namespace=NAMESPACE,
        object_set_id="calibration-agent-vs-b0",
        version=VERSION,
        scientific_design=scientific,
        portfolio_governance=governance,
        world_context=world,
        resource_envelope=resources,
        authority_envelope=authority,
        output_evaluation=output,
        resolver_version="1.0.0",
    )


def calibration_acceptance_record(
    object_set: ExperimentObjectSet | None = None,
) -> MethodologyAcceptanceRecord:
    """Return the delegated review decision for the exact calibration candidate."""

    candidate = object_set or build_calibration_pilot()
    return MethodologyAcceptanceRecord(
        namespace=NAMESPACE,
        record_id="calibration-agent-vs-b0",
        version=VERSION,
        decision="accepted_for_apparatus_calibration",
        reviewer="codex.delegated-methodology-review",
        authorized_by="User instruction in the active Codex development task.",
        reviewed_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        scientific_design_identity=candidate.scientific_design.registry_identity,
        experiment_object_set_identity=candidate.registry_identity,
        scientific_design_digest=candidate.scientific_design.pack_digest,
        fixture_context_digest=candidate.fixture_context_digest,
        approved_uses=("apparatus_calibration", "fixture_context_development"),
        prohibited_claims=(
            "causal_effect",
            "predictive_superiority",
            "risk_avoidance",
            "risk_mitigation",
            "thesis_inference",
        ),
        required_revisions=(
            "Create and independently review the four-state forward outcome labels.",
            "Run power and dependence analysis before fixing the inferential sample size.",
            "Add at least one historical point-in-time case family before external validity claims.",
            "Predeclare secondary breach, calibration and abstention metrics with multiplicity handling.",
            "Qualify any non-deterministic model route before replacing the fixture provider.",
        ),
        rationale=(
            "The question, paired comparator, information boundary, outcome protocol, "
            "primary metric, missingness rule, human authority and effect boundary are "
            "specific enough to exercise Fixture Context deterministically. The existing "
            "synthetic labels and two repeats are insufficient for thesis inference, so "
            "acceptance is limited to apparatus calibration and P7 development."
        ),
    )


def calibration_source_manifest() -> FixtureSourceManifest:
    """Bind the exact repository files reachable by the calibration Fixture."""

    candidate = build_calibration_pilot()
    datasets = candidate.world_context.data_manifest.datasets
    return FixtureSourceManifest(
        bindings=(
            FixtureSourceBinding(
                reference=datasets[0].reference,
                repository_relative_path=(
                    "data/fixtures/synthetic/thesis-day4/pricing-manifest.yaml"
                ),
                content_digest=datasets[0].content_digest,
            ),
            FixtureSourceBinding(
                reference=datasets[1].reference,
                repository_relative_path="data/fixtures/synthetic/thesis-day4/windows.json",
                content_digest=datasets[1].content_digest,
            ),
            FixtureSourceBinding(
                reference=candidate.portfolio_governance.portfolio.snapshot_reference,
                repository_relative_path=(
                    "examples/portfolio-risk-thesis/portfolios/diversified.yaml"
                ),
                content_digest=candidate.portfolio_governance.portfolio.snapshot_digest,
            ),
        ),
        denied_references=("data/fixtures/synthetic/thesis-day4/labels.parquet",),
    )


def calibration_registry_projections(
    repository_root: str | Path,
    *,
    discovered_at: datetime,
    repository_commit: str | None,
) -> tuple[RegistryProjection, RegistryProjection]:
    """Project the exact accepted definitions into the bounded local Registry."""

    root = Path(repository_root).resolve()
    source_path = Path(__file__).resolve()
    source_digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    candidate = build_calibration_pilot()
    acceptance = calibration_acceptance_record(candidate)
    definitions = (
        (
            candidate.scientific_design.registry_identity,
            "Calibration pilot scientific design",
            (
                "Paired B0 versus deterministic structured-agent calibration design; "
                "accepted for apparatus calibration only."
            ),
            candidate.scientific_design.pack_digest.removeprefix("sha256:"),
            "portfolio-risk.scientific-design-pack/v1",
            (),
        ),
        (
            candidate.registry_identity,
            "Calibration pilot experiment-object set",
            (
                "Closed reviewed-synthetic object set for deterministic Fixture Context "
                "development; no thesis inference or external effects."
            ),
            canonical_digest(candidate.model_dump(mode="json")).removeprefix("sha256:"),
            "portfolio-risk.experiment-object-set/v1",
            (
                RegistryRelationship(
                    relationship="uses_scientific_design",
                    target_native_id=candidate.scientific_design.registry_identity.asset_id,
                    target_reference=candidate.scientific_design.registry_identity.reference,
                    resolution="resolved",
                ),
            ),
        ),
    )
    projections = []
    for identity, display_name, summary, definition_digest, contract, relationships in definitions:
        projections.append(
            RegistryProjection(
                identity=identity,
                display_name=display_name,
                summary=summary,
                source=SourceReference(
                    source_type="python_factory",
                    source_reference=(
                        "packages/risk_experiments/src/risk_experiments/"
                        "pilot.py#build_calibration_pilot"
                    ),
                    source_digest=source_digest,
                    definition_digest=definition_digest,
                    native_version=VERSION,
                    canonical=True,
                    adapter_id="portfolio-risk.calibration-pilot-adapter/v1",
                    adapter_digest=source_digest,
                ),
                provenance=Provenance(
                    discovered_by="portfolio-risk.calibration-pilot-adapter/v1",
                    discovered_at=discovered_at,
                    repository_commit=repository_commit,
                    notes=(
                        "Delegated methodology acceptance is calibration-only.",
                        f"Acceptance: {acceptance.reference}",
                        f"Repository root at admission: {root.name}",
                    ),
                ),
                compatibility=Compatibility(
                    status="compatible",
                    api_versions=(contract,),
                    evaluated_source_digest=definition_digest,
                    evaluator_revision="fixture-context-resolver/1.0.0",
                    notes=("Validated by the aggregate S5/P7 calibration gate.",),
                ),
                source_contract=contract,
                relationships=relationships,
                tags=(
                    "apparatus-calibration",
                    "effect-free",
                    "human-only",
                    "reviewed-synthetic",
                ),
            )
        )
    return tuple(projections)  # type: ignore[return-value]
