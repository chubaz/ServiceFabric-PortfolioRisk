from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError
from risk_experiments import (
    BaselineDefinition,
    DataTruth,
    ExperimentDefinition,
    HypothesisDefinition,
    InformationRegimeDefinition,
    MetricDefinition,
    MetricDirection,
    PresentationMode,
    ResearchQuestionDefinition,
    RiskOutcomeDefinition,
    RiskOutcomeState,
    ScientificDesignPack,
    SourceBinding,
    TemporalWindow,
    canonical_digest,
)
from risk_registry import AssetKind, RegistryIdentity


def scientific_design_pack(*, baseline_step: str = "b0") -> ScientificDesignPack:
    question = ResearchQuestionDefinition(
        namespace="portfolio-risk.thesis",
        definition_id="information-value",
        version="1.0.0",
        name="Information value in portfolio-risk analysis",
        question="How does the reachable information regime affect forward portfolio-risk assessment quality?",
        population="Governed historical and reviewed synthetic portfolio-risk cases.",
        unit_of_analysis="One immutable portfolio-risk experiment run.",
        intervention="Change the predeclared information regime or analytical system.",
        comparator="The matching lower baseline-ladder treatment on the same world context.",
        estimand="Average change in the predeclared risk-quality metric across eligible cases.",
    )
    outcome = RiskOutcomeDefinition(
        namespace="portfolio-risk.thesis",
        definition_id="forward-risk-position",
        version="1.0.0",
        name="Forward risk-position outcome",
        unit_of_analysis="One portfolio at one decision time.",
        observation_horizon_seconds=1_728_000,
        states=(
            RiskOutcomeState(
                state_id="good",
                ordinal=0,
                label="Good",
                criterion="No material breach occurs and the position remains inside the governed risk envelope.",
            ),
            RiskOutcomeState(
                state_id="very_bad",
                ordinal=1,
                label="Very bad",
                criterion="A material breach occurs without timely mitigation.",
                is_breach=True,
            ),
        ),
        mitigation_rule="A risk is mitigated only when a retained decision precedes and reduces the defined adverse outcome.",
        censoring_rule="Cases without the complete twenty-day observation horizon remain censored, not successful.",
    )
    return ScientificDesignPack(
        namespace="portfolio-risk.thesis",
        pack_id=f"information-value-{baseline_step}",
        version="1.0.0",
        name=f"Information value design {baseline_step}",
        owner="local.researcher",
        research_question=question,
        hypothesis=HypothesisDefinition(
            namespace="portfolio-risk.thesis",
            definition_id=f"information-value-{baseline_step}",
            version="1.0.0",
            name="Information value hypothesis",
            research_question_reference=question.reference,
            statement="A richer governed information regime improves forward risk-position classification.",
            expected_direction="The treatment has a lower loss and breach error than its baseline.",
            falsification_condition="The confidence interval includes no improvement or the treatment performs worse.",
        ),
        baseline=BaselineDefinition(
            namespace="portfolio-risk.thesis",
            definition_id=f"baseline-{baseline_step}",
            version="1.0.0",
            name=f"Baseline ladder {baseline_step}",
            step_id=baseline_step,
            comparator_kind="deterministic" if baseline_step == "b0" else "single_agent",
            behaviour="Produce the bounded portfolio-risk assessment using only the declared resources.",
            resource_references=("capability:risk:exposure@1.0.0",),
        ),
        information_regime=InformationRegimeDefinition(
            namespace="portfolio-risk.thesis",
            definition_id="prices-holdings",
            version="1.0.0",
            name="Prices and holdings",
            evidence_categories=("holdings", "prices"),
            resource_references=("dataset:risk:portfolio-panel@2024-01-05",),
        ),
        risk_outcome=outcome,
        metric=MetricDefinition(
            namespace="portfolio-risk.thesis",
            definition_id="ordinal-risk-error",
            version="1.0.0",
            name="Ordinal forward-risk error",
            risk_outcome_reference=outcome.reference,
            estimand="Mean absolute ordinal error against the labelled forward risk-position state.",
            formula="mean(abs(predicted_state_ordinal - observed_state_ordinal))",
            aggregation="Calculate per case, then average within each experimental arm.",
            direction=MetricDirection.LOWER_IS_BETTER,
            missingness_rule="Exclude only predeclared censored cases and report their count separately.",
            uncertainty_rule="Report a confidence interval over independent eligible cases.",
        ),
    )


def binding(role: str) -> SourceBinding:
    reference = f"canonical:{role}:alpha"
    return SourceBinding(
        role=role,
        reference=reference,
        revision="v1",
        digest=canonical_digest({"reference": reference, "revision": "v1"}),
    )


def test_pack_is_digest_bound_and_supplies_exact_s4_identities() -> None:
    pack = scientific_design_pack()
    assert pack.pack_digest.startswith("sha256:")
    assert pack.registry_identity.reference == (
        "scientific_design:portfolio-risk.thesis:information-value-b0@1.0.0"
    )
    identities = pack.comparison_identity()
    assert tuple(sorted(identities)) == (
        "baseline_step",
        "information_regime",
        "metric_definition",
        "research_question",
        "risk_outcome_definition",
    )
    assert all("#sha256:" in reference for reference in identities.values())


def test_pack_rejects_broken_scientific_links_and_tampering() -> None:
    pack = scientific_design_pack()
    payload = pack.model_dump(mode="json")
    payload["hypothesis"]["research_question_reference"] = "research_question:wrong"
    payload["hypothesis"]["definition_digest"] = None
    payload["pack_digest"] = None
    with pytest.raises(ValidationError, match="hypothesis must reference"):
        ScientificDesignPack.model_validate(payload)

    payload = pack.model_dump(mode="json")
    payload["name"] = "Changed after digest"
    with pytest.raises(ValidationError, match="pack_digest"):
        ScientificDesignPack.model_validate(payload)


def test_risk_outcome_requires_an_ordered_scale_and_breach_state() -> None:
    payload = scientific_design_pack().risk_outcome.model_dump(mode="json")
    payload["states"][1]["ordinal"] = 3
    payload["definition_digest"] = None
    with pytest.raises(ValidationError, match="contiguous"):
        RiskOutcomeDefinition.model_validate(payload)


def test_experiment_can_pin_only_a_scientific_design_registry_identity() -> None:
    pack = scientific_design_pack()
    experiment = ExperimentDefinition(
        experiment_id="experiment-scientific-design",
        version="1.0.0",
        name="Scientific identity binding",
        purpose="Verify that an experiment pins one exact scientific design pack.",
        hypothesis=pack.hypothesis.statement,
        owner="local.researcher",
        created_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        temporal=TemporalWindow(
            start_date=date(2024, 1, 2), end_date=date(2024, 1, 5)
        ),
        presentation_mode=PresentationMode.INTERACTIVE_FOREGROUND,
        data_truth=DataTruth.REVIEWED_SYNTHETIC,
        source_bindings=tuple(
            sorted(
                (
                    binding("portfolio"),
                    binding("snapshot_policy"),
                    binding("mandate"),
                    binding("data_revision"),
                ),
                key=lambda item: (item.role, item.reference, item.revision),
            )
        ),
        system_assets=(
            RegistryIdentity(
                kind=AssetKind.WORKFLOW,
                namespace="risk",
                asset_id="daily-review",
                version="1.0.0",
            ),
        ),
        scientific_design=pack.registry_identity,
    )
    assert experiment.scientific_design == pack.registry_identity

    payload = experiment.model_dump(mode="json")
    payload["scientific_design"] = payload["system_assets"][0]
    payload["definition_digest"] = None
    with pytest.raises(ValidationError, match="scientific-design pack"):
        ExperimentDefinition.model_validate(payload)
