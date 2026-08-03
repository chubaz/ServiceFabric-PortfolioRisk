import socket
from datetime import UTC, datetime
from decimal import Decimal

from portfolio_risk_thesis.day3.contracts import (
    ArchitectureInputBundle,
    PositionExposure,
)
from portfolio_risk_thesis.day3.prompts import prompt_reference
from portfolio_risk_thesis.day3.providers import FixtureStructuredModelProvider
from portfolio_risk_thesis.day3.runner import run, validate_run, write_run
from portfolio_risk_thesis.day3.treatments import ROLES


def test_public_day3_vertical_slice_is_network_free_and_effect_free(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("network is prohibited in the public Day 3 journey")
        ),
    )
    context = ArchitectureInputBundle(
        portfolio_id="synthetic-diversified",
        as_of=datetime(2024, 1, 3, tzinfo=UTC),
        metrics={
            "daily_return": Decimal("-0.04"),
            "annualized_volatility": Decimal("0.20"),
            "maximum_drawdown": Decimal("0.10"),
            "historical_var_95": Decimal("0.02"),
            "historical_expected_shortfall_95": Decimal("0.03"),
        },
        deterministic_finding="REVIEW",
        review_item="Review deterministic threshold evidence.",
        decision_point="REVIEW",
        exposures=(
            PositionExposure(
                position_alias="position-001",
                weight=Decimal("1"),
                evidence_refs=("synthetic-evidence",),
            ),
        ),
        evidence_refs=("synthetic-evidence",),
        warnings=("event_source_curated",),
        limitations=("Synthetic public journey only.",),
    )
    valid = {
        "architecture_id": "A1",
        "status": "REVIEW",
        "severity": 1,
        "summary": "Synthetic fixture review output.",
        "human_review_required": True,
        "effects": [],
    }
    invalid = {
        "architecture_id": "B1",
        "status": "REVIEW",
        "severity": 1,
        "summary": "Synthetic fixture review output.",
        "affected_positions": ["position-999"],
        "human_review_required": True,
        "effects": [],
    }
    prompt_ids = {
        ROLES[0]: "a1-market-data",
        ROLES[1]: "a1-portfolio-exposure",
        ROLES[2]: "a1-news-sentiment",
        ROLES[3]: "a1-alert-synthesis",
    }
    responses = {
        (
            "B1",
            ROLES[-1],
            prompt_reference("b1-synthesizer").digest,
            context.context_digest,
        ): invalid,
        **{
            (
                "A1",
                role,
                prompt_reference(prompt_ids[role]).digest,
                context.context_digest,
            ): valid
            for role in ROLES
        },
    }
    provider = FixtureStructuredModelProvider(responses)
    comparison = run(context, provider)
    output = write_run(tmp_path.resolve(), context, comparison)
    validate_run(output)
    b0, b1, a1 = comparison.runs
    assert [len(item.receipts) for item in comparison.runs] == [0, 1, 4]
    assert b0.output.status == context.decision_point
    assert b1.output.status == "ABSTAINED_AGENT_OUTPUT"
    assert a1.output.status == "REVIEW"
    assert tuple(receipt.role_id for receipt in a1.receipts) == ROLES
    assert all(item.context_digest == context.context_digest for item in comparison.runs)
    assert all(item.output.human_review_required for item in comparison.runs)
    assert all(item.output.effects == () for item in comparison.runs)
    assert "permno" not in str(context.model_safe()).casefold()
    assert "outcome_label" not in str(context.model_safe()).casefold()
