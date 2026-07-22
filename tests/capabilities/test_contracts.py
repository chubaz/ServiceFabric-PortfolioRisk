import pytest
from pydantic import ValidationError

from risk_capabilities import CAPABILITY_DESCRIPTORS, CapabilityInvocation


def test_capability_descriptors_are_bounded_and_deny_order_and_broker_effects() -> None:
    assert len({item.capability_id for item in CAPABILITY_DESCRIPTORS}) == len(CAPABILITY_DESCRIPTORS)
    for descriptor in CAPABILITY_DESCRIPTORS:
        assert "order_submission" in descriptor.denied_effects
        assert "broker_connectivity" in descriptor.denied_effects
        assert descriptor.requires_evidence is True
        assert {
            "order_submission",
            "broker_connectivity",
            "trade_execution",
            "automatic_rebalancing",
            "optimization",
            "hedge_execution",
            "provider_call",
            "external_llm_call",
        }.issubset(descriptor.denied_effects)


def test_contracts_reject_raw_secret_style_fields() -> None:
    fields = set(CapabilityInvocation.model_fields)
    assert not fields.intersection({"api_key", "password", "secret", "token"})


def test_invocation_rejects_credential_like_input_names_at_every_supported_depth() -> None:
    with pytest.raises(ValidationError, match="credential-like"):
        CapabilityInvocation(invocation_id="invoke-1", capability_id="risk.capability.news_sentiment", inputs={"api_key": "not-accepted"})
    with pytest.raises(ValidationError):
        CapabilityInvocation(invocation_id="invoke-1", capability_id="risk.capability.news_sentiment", inputs={"context": {"api_key": "not-accepted"}})


def test_invocation_inputs_are_immutable_and_canonically_ordered() -> None:
    invocation = CapabilityInvocation(invocation_id="invoke-1", capability_id="risk.capability.news_sentiment", inputs={"zeta": "two", "alpha": "one"})
    assert [item.name for item in invocation.inputs] == ["alpha", "zeta"]
    with pytest.raises(ValidationError):
        invocation.inputs[0].name = "changed"  # type: ignore[misc]


def test_invocation_is_strict_about_undeclared_fields() -> None:
    try:
        CapabilityInvocation(invocation_id="invoke-1", capability_id="risk.capability.news_sentiment", api_key="not-accepted")
    except ValidationError:
        pass
    else:
        raise AssertionError("raw provider material must not be accepted")
