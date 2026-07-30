import json
from types import SimpleNamespace

import pytest

from portfolio_risk_thesis.day3.contracts import ModelConfiguration
from portfolio_risk_thesis.day3.providers import (
    FixtureStructuredModelProvider,
    OpenAIResponsesProvider,
)
from portfolio_risk_thesis.day3.treatments import a1, b1

from day3_helpers import bundle, fixture_responses, model_configuration, output


def test_fixture_provider_is_deterministic_and_unknown_digest_fails():
    context = bundle()
    provider = FixtureStructuredModelProvider(fixture_responses(context))
    request_provider = FixtureStructuredModelProvider(fixture_responses(context))
    first = b1(context, provider)
    second = b1(context, request_provider)
    assert first.output == second.output
    assert first.receipts == second.receipts
    unknown = FixtureStructuredModelProvider({})
    with pytest.raises(ValueError, match="exact"):
        b1(context, unknown)


def test_b1_and_a1_use_one_fixture_model_identity():
    context = bundle()
    provider = FixtureStructuredModelProvider(fixture_responses(context))
    receipts = b1(context, provider).receipts + a1(context, provider).receipts
    assert {receipt.model_id for receipt in receipts} == {"fixture-structured-v1"}


def test_openai_request_is_strict_tool_free_unstored_and_contains_no_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-test-key")
    captured = {}

    class Responses:
        def create(self, **body):
            captured.update(body)
            return SimpleNamespace(
                output_text=json.dumps(output("B1")),
                usage=SimpleNamespace(input_tokens=10, output_tokens=5),
                id="response-001",
                model="gpt-4.1-mini-2025-04-14",
            )

    def factory(**kwargs):
        assert kwargs["api_key"] == "secret-test-key"
        assert kwargs["max_retries"] == 1
        return SimpleNamespace(responses=Responses())

    provider = OpenAIResponsesProvider(
        ModelConfiguration.model_validate(model_configuration("openai_responses")),
        client_factory=factory,
    )
    result = b1(bundle(), provider)
    encoded = json.dumps(captured, sort_keys=True)
    assert captured["store"] is False
    assert captured["tools"] == []
    assert captured["text"]["format"]["strict"] is True
    schema = captured["text"]["format"]["schema"]
    assert schema["properties"]["architecture_id"]["const"] == "B1"
    assert schema["properties"]["recommended_next_steps"]["items"]["enum"]
    assert schema["properties"]["effects"]["maxItems"] == 0
    assert (
        schema["$defs"]["StructuredClaim"]["properties"]["evidence_refs"]["minItems"]
        == 1
    )
    assert captured["temperature"] == 0
    assert "secret-test-key" not in encoded
    assert result.receipts[0].input_tokens == 10
    assert result.receipts[0].output_tokens == 5
    assert result.receipts[0].response_id == "response-001"


@pytest.mark.parametrize("mode", ("error", "invalid_json"))
def test_openai_timeout_or_invalid_output_abstains_without_fixture_fallback(
    monkeypatch,
    mode,
):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-test-key")

    if mode == "error":
        def factory(**kwargs):
            raise TimeoutError("synthetic timeout")
    else:
        class Responses:
            def create(self, **body):
                return SimpleNamespace(output_text="not-json")

        def factory(**kwargs):
            return SimpleNamespace(responses=Responses())

    provider = OpenAIResponsesProvider(
        ModelConfiguration.model_validate(model_configuration("openai_responses")),
        client_factory=factory,
    )
    result = b1(bundle(), provider)
    assert result.output.status == "ABSTAINED_AGENT_OUTPUT"
    assert result.receipts[0].provider_id == "openai_responses"
    assert result.receipts[0].warnings[0] in {
        "provider_error",
        "invalid_structured_output",
    }


def test_terminal_quota_error_is_sanitized_and_skips_later_calls(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-test-key")
    calls = 0

    class QuotaError(Exception):
        code = "insufficient_quota"
        status_code = 429

    class Responses:
        def create(self, **body):
            nonlocal calls
            calls += 1
            raise QuotaError("message must not be retained")

    def factory(**kwargs):
        return SimpleNamespace(responses=Responses())

    provider = OpenAIResponsesProvider(
        ModelConfiguration.model_validate(model_configuration("openai_responses")),
        client_factory=factory,
    )
    first = b1(bundle(), provider)
    second = a1(bundle(), provider)
    assert calls == 1
    assert first.receipts[0].warnings == (
        "provider_error",
        "provider_error:QuotaError:insufficient_quota:429",
    )
    assert all(
        receipt.warnings[1].startswith(
            "skipped_after_terminal_error:QuotaError:insufficient_quota"
        )
        for receipt in second.receipts
    )
    assert "message must not be retained" not in json.dumps(
        [first.model_dump(mode="json"), second.model_dump(mode="json")]
    )


def test_incomplete_response_preserves_usage_and_skips_later_calls(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-test-key")
    calls = 0

    class Responses:
        def create(self, **body):
            nonlocal calls
            calls += 1
            return SimpleNamespace(
                status="incomplete",
                incomplete_details=SimpleNamespace(reason="max_output_tokens"),
                output_text='{"architecture_id":"B1"',
                usage=SimpleNamespace(input_tokens=6000, output_tokens=1600),
                id="response-incomplete",
                model="gpt-5.4-2026-03-05",
            )

    def factory(**kwargs):
        return SimpleNamespace(responses=Responses())

    provider = OpenAIResponsesProvider(
        ModelConfiguration.model_validate(model_configuration("openai_responses")),
        client_factory=factory,
    )
    first = b1(bundle(), provider)
    second = a1(bundle(), provider)
    assert calls == 1
    receipt = first.receipts[0]
    assert receipt.warnings == (
        "invalid_structured_output",
        "invalid_structured_output:incomplete:max_output_tokens",
    )
    assert receipt.response_id == "response-incomplete"
    assert receipt.input_tokens == 6000
    assert receipt.output_tokens == 1600
    assert all(
        value.warnings[1].startswith("skipped_after_terminal_error:")
        for value in second.receipts
    )


def test_validation_error_names_field_safely_and_skips_later_calls(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-test-key")
    calls = 0
    invalid = output("B1")
    invalid["recommended_next_steps"] = ["model supplied unsafe text"]

    class Responses:
        def create(self, **body):
            nonlocal calls
            calls += 1
            return SimpleNamespace(
                status="completed",
                output_text=json.dumps(invalid),
                usage=SimpleNamespace(input_tokens=20, output_tokens=10),
                id="response-invalid",
                model="gpt-5.4-2026-03-05",
            )

    def factory(**kwargs):
        return SimpleNamespace(responses=Responses())

    provider = OpenAIResponsesProvider(
        ModelConfiguration.model_validate(model_configuration("openai_responses")),
        client_factory=factory,
    )
    first = b1(bundle(), provider)
    second = a1(bundle(), provider)
    assert calls == 1
    assert first.receipts[0].warnings == (
        "invalid_structured_output",
        "invalid_structured_output:ValidationError:"
        "recommended_next_steps:value_error",
    )
    assert all(
        value.warnings[1].startswith("skipped_after_terminal_error:")
        for value in second.receipts
    )
    encoded = json.dumps([first.model_dump(mode="json"), second.model_dump(mode="json")])
    assert "model supplied unsafe text" not in encoded
