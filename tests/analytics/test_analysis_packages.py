from __future__ import annotations

import pytest

from risk_analytics import (
    CapabilityImplementationKind,
    DAILY_PORTFOLIO_DOWNSIDE_RISK_PACKAGE,
    RiskAnalysisPackageDefinition,
)


def test_daily_downside_package_preserves_the_approved_definition_boundaries() -> None:
    package = DAILY_PORTFOLIO_DOWNSIDE_RISK_PACKAGE
    assert package.authoring_mode == "risk_question_first"
    assert package.resolution_mode == "hybrid"
    assert package.output_boundary == "analysis_dossier"
    assert package.temporal_envelope.eligibility_field == "available_at"
    assert package.temporal_envelope.supplemental_queries_inherit_boundary is True
    assert package.stable_core_with_supplemental_expansion is True
    assert package.supplemental_work_may_mutate_published_core is False
    assert package.narrative_value_policy.admission_paths == (
        "decision_value",
        "research_value",
    )
    assert package.narrative_value_policy.empty_output_is_valid is True
    assert package.publication_validation.deterministic_validation_required is True
    assert package.publication_validation.representative_dossier_human_review_required is True


def test_daily_downside_package_reuses_registered_analytical_capabilities() -> None:
    package = DAILY_PORTFOLIO_DOWNSIDE_RISK_PACKAGE
    implementations = {
        role.default_implementation for role in package.capability_roles
    }
    assert {
        "portfolio.data_context.create",
        "risk.returns.simple",
        "risk.volatility.annualized",
        "risk.drawdown.maximum",
        "risk.var.historical",
        "risk.expected_shortfall.historical",
        "portfolio.exposure.summarize",
        "risk.contribution.summarize",
        "risk.scenario.evaluate",
        "risk.report.render",
        "risk.agent.alert_recommendation",
    } == implementations
    narrative = next(
        role
        for role in package.capability_roles
        if role.implementation_kind is CapabilityImplementationKind.AGENT_BACKED
    )
    assert narrative.role_id == "interpret_material_findings"
    assert all(section.may_be_empty for section in package.dossier_sections)


def test_dossier_sections_cannot_reference_unknown_capability_roles() -> None:
    source = DAILY_PORTFOLIO_DOWNSIDE_RISK_PACKAGE.model_dump(mode="python")
    source["dossier_sections"][0]["evidence_role_ids"] = ("unknown_role",)
    with pytest.raises(ValueError, match="unknown capability roles"):
        RiskAnalysisPackageDefinition.model_validate(source)
