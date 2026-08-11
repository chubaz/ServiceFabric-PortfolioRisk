"""Versioned definitions for composing reusable portfolio-risk analysis packages."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from risk_domain.common import ImmutableDomainModel, NonEmptyString


class CapabilityImplementationKind(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM_ASSISTED = "llm_assisted"
    AGENT_BACKED = "agent_backed"


class SemanticDataRole(ImmutableDomainModel):
    role_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    description: str = Field(min_length=3, max_length=1200)
    input_contract: NonEmptyString
    required: bool = True
    as_of_rule: Literal["package_as_of", "strictly_prior", "assignment_effective_at"]
    default_binding: NonEmptyString
    runtime_override_allowed: bool = True
    point_in_time_safe_required: bool = True


class CapabilityRole(ImmutableDomainModel):
    role_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    objective: str = Field(min_length=3, max_length=1200)
    implementation_kind: CapabilityImplementationKind
    input_contract: NonEmptyString
    output_contract: NonEmptyString
    default_implementation: NonEmptyString
    required: bool = True
    substitutable: bool = True
    stable_core: bool = True
    minimum_validation_state: Literal["candidate", "validated", "published"] = "validated"
    point_in_time_safe_required: bool = True


class TemporalEnvelope(ImmutableDomainModel):
    as_of_binding: NonEmptyString
    eligibility_field: Literal["available_at"] = "available_at"
    dataset_revision_policy: Literal["pinned"] = "pinned"
    mapping_policy: Literal["point_in_time"] = "point_in_time"
    supplemental_queries_inherit_boundary: Literal[True] = True
    component_overrides_may_only_be_stricter: Literal[True] = True


class NarrativeValuePolicy(ImmutableDomainModel):
    admission_paths: tuple[Literal["decision_value", "research_value"], ...]
    dimensions: tuple[
        Literal[
            "portfolio_materiality",
            "mandate_relevance",
            "decision_relevance",
            "novelty",
            "evidence_strength",
            "time_sensitivity",
            "uncertainty_reduction",
        ],
        ...,
    ]
    penalties: tuple[Literal["repetition", "unsupported_inference", "methodology_narration", "low_materiality"], ...]
    empty_output_is_valid: Literal[True] = True
    rejected_candidates_are_audit_only: Literal[True] = True

    @field_validator("admission_paths", "dimensions", "penalties")
    @classmethod
    def values_are_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("narrative policy values must be unique")
        return values


class ArchitectureOutputField(ImmutableDomainModel):
    section_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    title: NonEmptyString
    question: str = Field(min_length=3, max_length=1200)
    evidence_role_ids: tuple[str, ...]
    max_words: int = Field(ge=20, le=600)
    may_be_empty: Literal[True] = True
    format: Literal["markdown", "table", "visual_spec", "mixed"] = "markdown"

    @field_validator("evidence_role_ids")
    @classmethod
    def evidence_roles_are_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("section evidence roles must be unique")
        return values


class OutputValidationPolicy(ImmutableDomainModel):
    deterministic_validation_required: Literal[True] = True
    representative_output_human_review_required: Literal[True] = True
    fixture_cases: tuple[Literal["normal", "missing_data", "temporal_boundary", "adverse"], ...]
    exact_llm_wording_is_regression_target: Literal[False] = False
    required_agentic_checks: tuple[
        Literal[
            "admitted_findings_only",
            "evidence_citations",
            "numbers_reconcile",
            "no_unsupported_claims",
            "empty_sections_allowed",
            "output_schema_valid",
        ],
        ...,
    ]


class RiskAnalysisPackageDefinition(ImmutableDomainModel):
    package_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,159}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    display_name: NonEmptyString
    risk_question: str = Field(min_length=12, max_length=2000)
    authoring_mode: Literal["risk_question_first"] = "risk_question_first"
    resolution_mode: Literal["hybrid"] = "hybrid"
    data_roles: tuple[SemanticDataRole, ...]
    capability_roles: tuple[CapabilityRole, ...]
    output_fields: tuple[ArchitectureOutputField, ...]
    temporal_envelope: TemporalEnvelope
    narrative_value_policy: NarrativeValuePolicy
    output_validation: OutputValidationPolicy
    stable_core_with_supplemental_expansion: Literal[True] = True
    supplemental_work_may_mutate_published_core: Literal[False] = False
    output_boundary: Literal["architecture_output"] = "architecture_output"

    @model_validator(mode="after")
    def package_members_are_unique_and_resolvable(self) -> "RiskAnalysisPackageDefinition":
        for label, values in (
            ("data role", [item.role_id for item in self.data_roles]),
            ("capability role", [item.role_id for item in self.capability_roles]),
            ("output field", [item.section_id for item in self.output_fields]),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} identifiers must be unique")
        capability_ids = {item.role_id for item in self.capability_roles}
        for section in self.output_fields:
            unknown = set(section.evidence_role_ids) - capability_ids
            if unknown:
                raise ValueError(
                    f"output field {section.section_id} references unknown capability roles: {sorted(unknown)}"
                )
        if not any(item.implementation_kind is CapabilityImplementationKind.AGENT_BACKED for item in self.capability_roles):
            raise ValueError("an architecture output package requires a bounded agent-backed interpretation role")
        return self


DAILY_PORTFOLIO_DOWNSIDE_RISK_PACKAGE = RiskAnalysisPackageDefinition(
    package_id="risk.analysis.daily_portfolio_downside",
    version="0.1.0",
    display_name="Daily Portfolio Downside Risk",
    risk_question=(
        "Determine whether the portfolio's current volatility, drawdown, tail losses, "
        "concentration and reviewed downside scenarios reveal a material change in risk."
    ),
    data_roles=(
        SemanticDataRole(
            role_id="portfolio_snapshot",
            description="Immutable holdings, cash and valuation state selected at the package as-of time.",
            input_contract="PortfolioSnapshot",
            as_of_rule="package_as_of",
            default_binding="portfolio.snapshot.create",
        ),
        SemanticDataRole(
            role_id="point_in_time_market_series",
            description="Eligible market observations for current holdings, with explicit availability and revision lineage.",
            input_contract="PortfolioDataContext",
            as_of_rule="package_as_of",
            default_binding="portfolio.data_context.create",
        ),
        SemanticDataRole(
            role_id="mandate_context",
            description="Effective mandate rules and review thresholds supplied by the assignment boundary.",
            input_contract="MandateReference",
            as_of_rule="assignment_effective_at",
            default_binding="assignment.mandate_reference",
        ),
        SemanticDataRole(
            role_id="reviewed_scenarios",
            description="Published or validated scenarios eligible for the selected portfolio and as-of time.",
            input_contract="ScenarioDefinition[]",
            required=False,
            as_of_rule="package_as_of",
            default_binding="registry.scenario_definitions",
        ),
    ),
    capability_roles=(
        CapabilityRole(role_id="prepare_context", objective="Assemble a point-in-time portfolio data context.", implementation_kind="deterministic", input_contract="PortfolioDataContextRequest", output_contract="PortfolioDataContext", default_implementation="portfolio.data_context.create"),
        CapabilityRole(role_id="calculate_returns", objective="Calculate the reviewed daily return series.", implementation_kind="deterministic", input_contract="ReturnsRequest", output_contract="ReturnSeriesResult", default_implementation="risk.returns.simple"),
        CapabilityRole(role_id="estimate_volatility", objective="Estimate annualized sample volatility from reviewed returns.", implementation_kind="deterministic", input_contract="VolatilityRequest", output_contract="VolatilityResult", default_implementation="risk.volatility.annualized"),
        CapabilityRole(role_id="measure_drawdown", objective="Measure the maximum peak-to-trough loss path.", implementation_kind="deterministic", input_contract="DerivedReturnsRequest", output_contract="DrawdownResult", default_implementation="risk.drawdown.maximum"),
        CapabilityRole(role_id="estimate_var", objective="Estimate nearest-rank historical Value at Risk.", implementation_kind="deterministic", input_contract="HistoricalTailRiskRequest", output_contract="HistoricalTailRiskResult", default_implementation="risk.var.historical"),
        CapabilityRole(role_id="estimate_expected_shortfall", objective="Estimate the mean loss beyond historical VaR.", implementation_kind="deterministic", input_contract="HistoricalTailRiskRequest", output_contract="HistoricalTailRiskResult", default_implementation="risk.expected_shortfall.historical"),
        CapabilityRole(role_id="summarize_exposure", objective="Calculate weights and concentration from the immutable snapshot.", implementation_kind="deterministic", input_contract="ExposureSummaryRequest", output_contract="ExposureSnapshot", default_implementation="portfolio.exposure.summarize"),
        CapabilityRole(role_id="attribute_return", objective="Reconcile constituent weighted-return contributions.", implementation_kind="deterministic", input_contract="ContributionSummaryRequest", output_contract="ContributionSummary", default_implementation="risk.contribution.summarize"),
        CapabilityRole(role_id="evaluate_scenario", objective="Evaluate one reviewed effect-free downside scenario.", implementation_kind="deterministic", input_contract="ScenarioRequest", output_contract="ScenarioResult", default_implementation="risk.scenario.evaluate", required=False),
        CapabilityRole(role_id="interpret_material_findings", objective="Select only valuable findings and populate cited ArchitectureOutput fields.", implementation_kind="agent_backed", input_contract="ValidatedRiskEvidencePacket", output_contract="ArchitectureOutputContribution", default_implementation="risk.agent.alert_recommendation"),
    ),
    output_fields=(
        ArchitectureOutputField(section_id="material_signal", title="Material signal", question="What changed materially and why does it matter now?", evidence_role_ids=("estimate_volatility", "measure_drawdown", "estimate_var", "estimate_expected_shortfall"), max_words=90),
        ArchitectureOutputField(section_id="downside_profile", title="Downside profile", question="What does the joint loss distribution evidence reveal without repeating the signal?", evidence_role_ids=("estimate_volatility", "measure_drawdown", "estimate_var", "estimate_expected_shortfall"), max_words=150, format="mixed"),
        ArchitectureOutputField(section_id="drivers_and_exposure", title="Drivers and exposure", question="Which holdings or concentrations explain the material portfolio risk?", evidence_role_ids=("summarize_exposure", "attribute_return"), max_words=140, format="mixed"),
        ArchitectureOutputField(section_id="scenario_sensitivity", title="Scenario sensitivity", question="Does a reviewed downside scenario alter the risk interpretation?", evidence_role_ids=("evaluate_scenario",), max_words=120, format="mixed"),
        ArchitectureOutputField(section_id="uncertainty_and_review", title="Uncertainty and review", question="Which unresolved issue could change the conclusion or require human attention?", evidence_role_ids=("prepare_context",), max_words=100),
    ),
    temporal_envelope=TemporalEnvelope(as_of_binding="assignment.as_of"),
    narrative_value_policy=NarrativeValuePolicy(
        admission_paths=("decision_value", "research_value"),
        dimensions=("portfolio_materiality", "mandate_relevance", "decision_relevance", "novelty", "evidence_strength", "time_sensitivity", "uncertainty_reduction"),
        penalties=("repetition", "unsupported_inference", "methodology_narration", "low_materiality"),
    ),
    output_validation=OutputValidationPolicy(
        fixture_cases=("normal", "missing_data", "temporal_boundary", "adverse"),
        required_agentic_checks=("admitted_findings_only", "evidence_citations", "numbers_reconcile", "no_unsupported_claims", "empty_sections_allowed", "output_schema_valid"),
    ),
)


RISK_ANALYSIS_PACKAGES = (DAILY_PORTFOLIO_DOWNSIDE_RISK_PACKAGE,)
