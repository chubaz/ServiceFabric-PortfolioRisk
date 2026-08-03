from datetime import timedelta

import pytest
from pydantic import ValidationError

from portfolio_risk_thesis.day3 import ArchitectureReviewOutput, abstain, critic
from portfolio_risk_thesis.day3.contracts import ArchitectureInputBundle

from day3_helpers import EVIDENCE, bundle


def review_output(**updates: object) -> ArchitectureReviewOutput:
    value = {
        "architecture_id": "B1",
        "status": "REVIEW",
        "severity": 1,
        "summary": "Governed review.",
        "human_review_required": True,
        "effects": [],
    }
    value.update(updates)
    return ArchitectureReviewOutput.model_validate(value)


@pytest.mark.parametrize(
    ("updates", "code"),
    (
        ({"architecture_id": "A1"}, "architecture"),
        ({"affected_positions": ["position-999"]}, "position"),
        ({"metric_refs": ["unknown_metric"]}, "metric"),
        ({"event_refs": ["future-event"]}, "event"),
        ({"evidence_refs": ["unknown-evidence"]}, "evidence"),
        ({"status": "URGENT_REVIEW", "severity": 1}, "severity"),
        ({"summary": "Daily movement was 4%."}, "numeric_claim"),
        ({"summary": "Buy the affected position."}, "effect"),
        ({"summary": "Evidence at /Users/private/source.csv."}, "privacy"),
    ),
)
def test_critic_rejects_frozen_boundary_violations(updates, code):
    report = critic(review_output(**updates), bundle(), "B1")
    assert not report.passed
    assert code in {violation.code for violation in report.violations}


def test_metric_claim_requires_exact_authoritative_value_and_evidence():
    wrong = review_output(
        summary="Daily movement was 5%.",
        supporting_claims=(
            {
                "claim_id": "claim-001",
                "statement": "Daily movement was 5%.",
                "claim_type": "metric",
                "metric_ref": "daily_return",
                "reported_metric_value": "-0.05",
                "evidence_refs": [EVIDENCE],
            },
        ),
    )
    report = critic(wrong, bundle(), "B1")
    assert not report.passed
    assert "metric" in {violation.code for violation in report.violations}


def test_effect_free_safety_disclosure_is_not_a_transaction_instruction():
    report = critic(
        review_output(
            uncertainties=(
                "No network, broker, order, trade, rebalance or portfolio mutation effect.",
            )
        ),
        bundle(),
        "B1",
    )
    assert report.passed


def test_critic_failure_becomes_deterministic_abstention_and_preserves_digest():
    original = review_output(affected_positions=["position-999"])
    report = critic(original, bundle(), "B1")
    final = abstain(original, report)
    assert final.status == "ABSTAINED_AGENT_OUTPUT"
    assert final.severity == 0
    assert report.original_output_digest == original.output_digest
    assert original.output_digest in final.uncertainties[0]
    assert final.effects == ()
    assert final.human_review_required


def test_future_event_cannot_enter_the_authoritative_context():
    context = bundle()
    document = context.model_dump(mode="python")
    document["events"][0]["available_at"] = context.as_of + timedelta(seconds=1)
    with pytest.raises(ValidationError):
        ArchitectureInputBundle.model_validate(document)
