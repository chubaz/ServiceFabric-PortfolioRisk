from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from risk_experiments import (
    MandateCapabilityRequirement,
    RiskPolicySet,
    load_synthetic_mandate_fixture,
    validate_mandate_policy_binding,
)
from risk_registry import AssetKind


FIXTURES = Path("data/fixtures/synthetic/mandates")


@pytest.mark.parametrize(
    "filename",
    (
        "european-corporate-bond-income.json",
        "institutional-diversified-growth.json",
        "liability-aware-pension.json",
    ),
)
def test_reference_mandates_compile_to_exact_policy_bindings(filename: str) -> None:
    mandate, policy = load_synthetic_mandate_fixture(FIXTURES / filename)

    assert policy.mandate_reference == mandate.reference
    assert mandate.registry_identity.kind is AssetKind.MANDATE
    assert policy.registry_identity.kind is AssetKind.RISK_POLICY
    assert all(source.authority_effect == "reference_only" for source in mandate.sources)
    assert all(rule.portfolio_effects == () for rule in (item.governance_route for item in policy.rules))
    assert all(rule.external_effects == () for rule in (item.governance_route for item in policy.rules))
    assert all(
        isinstance(rule.threshold, Decimal)
        for rule in policy.rules
        if rule.operator not in {"in", "not_in"}
    )


def test_categorical_universe_rule_is_distinct_from_numeric_compliance() -> None:
    mandate, policy = load_synthetic_mandate_fixture(
        FIXTURES / "european-corporate-bond-income.json"
    )
    credit_rule = next(item for item in policy.rules if item.rule_id == "credit-quality")

    assert credit_rule.system_treatment == "universe_filter"
    assert credit_rule.threshold is None
    assert "BBB-" in credit_rule.allowed_values
    assert credit_rule.evaluation_basis == "proposed_state"
    validate_mandate_policy_binding(mandate, policy)


def test_private_mandate_inputs_declare_roles_without_embedding_values() -> None:
    mandate, _ = load_synthetic_mandate_fixture(
        FIXTURES / "liability-aware-pension.json"
    )

    assert len(mandate.constraints) == 7
    assert tuple(item.data_role for item in mandate.data_requirements) == tuple(
        sorted(item.data_role for item in mandate.data_requirements)
    )
    benefit = next(
        item for item in mandate.data_requirements
        if item.data_role == "benefit_outflow_forecast"
    )
    assert benefit.confidentiality == "restricted"
    assert benefit.binding_scope == "experiment_assignment"
    assert not hasattr(benefit, "value")


def test_policy_cannot_use_an_undeclared_capability() -> None:
    mandate, policy = load_synthetic_mandate_fixture(
        FIXTURES / "institutional-diversified-growth.json"
    )
    rule = policy.rules[0].model_copy(
        update={"capability_reference": "capability:risk:undeclared@1.0.0"}
    )
    altered = policy.model_copy(update={"rules": (rule,) + policy.rules[1:]})

    with pytest.raises(ValueError, match="capability must be declared"):
        validate_mandate_policy_binding(mandate, altered)


def test_capability_requirements_may_only_name_mandate_constraints() -> None:
    mandate, _ = load_synthetic_mandate_fixture(
        FIXTURES / "institutional-diversified-growth.json"
    )
    invalid = mandate.model_dump(mode="python", exclude={"object_digest"})
    invalid["capability_requirements"] = (
        MandateCapabilityRequirement(
            capability_reference="capability:risk:portfolio.exposure.summarize@1.0.0",
            purpose="evaluate_compliance",
            constraint_ids=("unknown-constraint",),
        ),
    )

    with pytest.raises(ValidationError, match="only declared constraints"):
        mandate.__class__.model_validate(invalid)
