from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from portfolio_risk_thesis.day3.contracts import (
    ArchitectureInputBundle,
    ArchitectureReviewOutput,
    ModelCallReceipt,
    ModelConfiguration,
    PositionExposure,
    digest,
)

from day3_helpers import bundle, model_configuration


def test_contracts_are_strict_immutable_digestible_and_private_neutral():
    context = bundle()
    assert context.context_digest.startswith("sha256:")
    assert "permno" not in str(context.model_safe()).casefold()
    with pytest.raises(ValidationError):
        ArchitectureInputBundle.model_validate(
            context.model_dump(mode="python") | {"unexpected": True}
        )
    with pytest.raises(ValidationError):
        PositionExposure(
            position_alias="permno-123",
            weight="1",
            evidence_refs=("evidence",),
        )
    with pytest.raises(ValidationError):
        context.portfolio_id = "changed"


def test_forbidden_output_fields_human_review_and_effects_are_rejected():
    base = {
        "architecture_id": "B1",
        "status": "REVIEW",
        "severity": 1,
        "summary": "Review.",
    }
    for invalid in (
        {"chain_of_thought": "hidden"},
        {"human_review_required": False},
        {"effects": ["trade"]},
        {"recommended_next_steps": ["buy_security"]},
    ):
        with pytest.raises(ValidationError):
            ArchitectureReviewOutput.model_validate(base | invalid)


def test_model_configuration_freezes_snapshot_sampling_and_tools():
    configuration = ModelConfiguration.model_validate(model_configuration("fixture"))
    assert configuration.model_id == configuration.model_snapshot
    assert configuration.tools == ()
    assert configuration.store is False
    for update in (
        {"model_snapshot": "different"},
        {"temperature": "0"},
        {"tools": ["web_search"]},
        {"store": True},
    ):
        with pytest.raises(ValidationError):
            ModelConfiguration.model_validate(
                configuration.model_dump(mode="python") | update
            )


def test_semantic_output_digest_excludes_receipt_latency_and_response_id():
    output = ArchitectureReviewOutput(
        architecture_id="B1",
        status="REVIEW",
        severity=1,
        summary="Review.",
    )
    common = {
        "provider_id": "fixture",
        "model_id": "fixture-structured-v1",
        "architecture_id": "B1",
        "role_id": "risk.agent.alert_recommendation",
        "prompt_digest": digest("prompt"),
        "request_digest": digest("request"),
        "raw_response_digest": digest("raw"),
        "parsed_output_digest": output.output_digest,
    }
    first = ModelCallReceipt(**common, elapsed_ms=1, response_id="one")
    second = ModelCallReceipt(**common, elapsed_ms=999, response_id="two")
    assert first != second
    assert output.output_digest == ArchitectureReviewOutput.model_validate(
        output.model_dump(mode="python")
    ).output_digest
