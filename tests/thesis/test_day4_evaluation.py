from datetime import UTC, datetime, timedelta
from decimal import Decimal

from portfolio_risk_thesis.day3.contracts import ModelCallReceipt, digest
from portfolio_risk_thesis.day4.contracts import (
    ArchitectureObservation,
    Day4LabelPolicy,
    EventWindowLabel,
    OutcomeLabel,
    PortfolioDayKey,
    PortfolioDayLabel,
    ProviderPricingSnapshot,
)
from portfolio_risk_thesis.day4.evaluation import (
    classify_observation,
    deterministic_p95,
    evaluate_architectures,
    evaluate_repeatability,
    jaccard_agreement,
    match_alerts_to_outcomes,
)


BASE = datetime(2024, 1, 8, 21, tzinfo=UTC)
DIGEST = digest("test")


def _key(day: int, portfolio: str = "portfolio-a") -> PortfolioDayKey:
    return PortfolioDayKey(
        portfolio_id=portfolio,
        window_id="stress_a",
        as_of=BASE + timedelta(days=day),
    )


def _label(
    key: PortfolioDayKey,
    *,
    event: bool,
    outcome: bool = False,
    realized_days: int = 2,
) -> PortfolioDayLabel:
    trigger = BASE if event else None
    return PortfolioDayLabel(
        key=key,
        event_window=EventWindowLabel(
            key=key,
            positive=event,
            trigger_available_at=trigger,
            rationale="Reviewed synthetic event label.",
        ),
        outcome=OutcomeLabel(
            key=key,
            positive=outcome,
            realized_at=key.as_of + timedelta(days=realized_days),
            portfolio_drawdown=Decimal("0.10") if outcome else Decimal("0.01"),
            realized_volatility=Decimal("0.20"),
            worst_position_loss=Decimal("-0.02"),
            rationale="Reviewed synthetic outcome label.",
            evidence_refs=("outcome-evidence",),
        ),
    )


def _receipt(*warnings: str, input_tokens: int = 100, output_tokens: int = 50):
    return ModelCallReceipt(
        provider_id="fixture",
        model_id="fixture-structured-v1",
        architecture_id="B1",
        role_id="risk.agent.alert_recommendation",
        prompt_digest=DIGEST,
        request_digest=DIGEST,
        raw_response_digest=DIGEST,
        parsed_output_digest=DIGEST,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        elapsed_ms=10,
        warnings=warnings,
    )


def _observation(
    key: PortfolioDayKey,
    status: str,
    *,
    architecture: str = "B0",
    repetition: int = 0,
    severity: int | None = None,
    evidence_refs: tuple[str, ...] = ("evidence",),
    affected_positions: tuple[str, ...] = (),
    output_digest: str = DIGEST,
    receipts: tuple[ModelCallReceipt, ...] | None = None,
    claim_count: int = 0,
    unsupported_claim_count: int = 0,
) -> ArchitectureObservation:
    if receipts is None:
        receipts = () if architecture == "B0" else (_receipt(),)
    if severity is None:
        severity = {"NO_ISSUE": 0, "REVIEW": 1, "URGENT_REVIEW": 3}.get(status, 0)
    return ArchitectureObservation(
        task_id=digest(
            (key.key_digest, architecture, repetition, status, output_digest, receipts)
        ),
        key=key,
        architecture_id=architecture,
        repetition=repetition,
        context_digest=DIGEST,
        semantic_output_digest=output_digest,
        status=status,
        severity=severity,
        critic_passed=status != "ABSTAINED_AGENT_OUTPUT",
        claim_count=claim_count,
        unsupported_claim_count=unsupported_claim_count,
        evidence_refs=evidence_refs,
        affected_positions=affected_positions,
        provider_receipts=receipts,
        latency_ms=sum(receipt.elapsed_ms for receipt in receipts),
        input_tokens=sum(receipt.input_tokens for receipt in receipts),
        output_tokens=sum(receipt.output_tokens for receipt in receipts),
    )


def _policy() -> Day4LabelPolicy:
    return Day4LabelPolicy(
        future_portfolio_drawdown_threshold=Decimal("0.08"),
        future_realized_volatility_threshold=Decimal("0.30"),
        worst_position_loss_threshold=Decimal("0.10"),
        material_event_enabled=True,
        matching_lookback_business_days=5,
    )


def test_classification_and_receipt_provider_failure_precedence():
    key = _key(0)
    assert classify_observation(_observation(key, "REVIEW")) == "alert"
    assert classify_observation(_observation(key, "NO_ISSUE")) == "no_alert"
    assert classify_observation(_observation(key, "ABSTAIN")) == "abstention"
    provider_failure = _observation(
        key,
        "ABSTAINED_AGENT_OUTPUT",
        architecture="B1",
        receipts=(_receipt("invalid_structured_output"),),
    )
    assert classify_observation(provider_failure) == "execution_failure"


def test_confusion_abstention_null_metrics_coverage_grounding_and_pricing():
    keys = (_key(0), _key(1), _key(2), _key(3))
    labels = (
        _label(keys[0], event=True),
        _label(keys[1], event=True),
        _label(keys[2], event=False),
        _label(keys[3], event=False),
    )
    observations = (
        _observation(keys[0], "REVIEW", architecture="B1"),
        _observation(
            keys[1],
            "ABSTAIN",
            architecture="B1",
            claim_count=2,
            unsupported_claim_count=1,
        ),
        _observation(keys[2], "REVIEW", architecture="B1"),
        _observation(keys[3], "ABSTAIN", architecture="B1", evidence_refs=()),
    )
    pricing = ProviderPricingSnapshot(
        provider_id="fixture",
        model_snapshot="fixture-structured-v1",
        currency="usd",
        input_price_per_million_tokens=Decimal("2"),
        output_price_per_million_tokens=Decimal("4"),
        effective_at=BASE,
        source_reference="reviewed synthetic pricing",
        reviewer="reviewer",
    )
    evaluation = evaluate_architectures(
        observations, labels, _policy(), pricing=pricing, label_views=("event_window",)
    )[0]
    assert (evaluation.true_positives, evaluation.false_positives) == (1, 1)
    assert (evaluation.true_negatives, evaluation.false_negatives) == (0, 1)
    assert evaluation.precision == Decimal("0.5")
    assert evaluation.recall == Decimal("0.5")
    assert evaluation.evaluated_coverage == Decimal("0.5")
    assert evaluation.evidence_reference_coverage == Decimal("0.75")
    assert evaluation.unsupported_claim_rate == Decimal("0.5")
    assert evaluation.provider_cost == Decimal("0.0016")
    assert evaluation.median_event_detection_delay_seconds == 0

    no_positive = evaluate_architectures(
        (_observation(keys[2], "NO_ISSUE"),),
        (labels[2],),
        _policy(),
        label_views=("event_window",),
    )[0]
    assert no_positive.precision is None and no_positive.recall is None
    assert {"undefined_precision", "undefined_recall"}.issubset(no_positive.warnings)


def test_provider_error_is_failure_not_abstention_and_missing_pricing_is_explicit():
    key = _key(0)
    label = _label(key, event=False)
    failure = _observation(
        key,
        "ABSTAINED_AGENT_OUTPUT",
        architecture="B1",
        receipts=(_receipt("provider_error"),),
    )
    result = evaluate_architectures(
        (failure,), (label,), _policy(), label_views=("event_window",)
    )[0]
    assert result.execution_failures == 1
    assert result.abstentions == 0
    assert result.evaluated_coverage == 0
    assert (
        result.true_positives,
        result.false_positives,
        result.true_negatives,
        result.false_negatives,
    ) == (0, 0, 0, 0)
    assert result.provider_cost is None
    assert "pricing_unavailable" in result.warnings


def test_one_to_one_same_portfolio_matching_uses_closest_prior_alert():
    first, closest = _key(0), _key(1)
    outcome_key = _key(2)
    outcome = _label(outcome_key, event=False, outcome=True, realized_days=1)
    other = _key(1, portfolio="portfolio-b")
    matches = match_alerts_to_outcomes(
        (
            _observation(first, "REVIEW"),
            _observation(closest, "REVIEW"),
            _observation(other, "REVIEW"),
        ),
        (outcome,),
        matching_lookback_business_days=5,
    )
    assert len(matches) == 1
    assert matches[0].alert_at == closest.as_of
    assert matches[0].portfolio_id == "portfolio-a"
    assert matches[0].lead_time_seconds == 2 * 86400


def test_repeatability_status_severity_digest_and_jaccard_agreements():
    anchor = _key(0)
    primary = _observation(
        anchor,
        "REVIEW",
        architecture="B1",
        affected_positions=("position-a", "position-b"),
        evidence_refs=("evidence-a",),
    )
    repeated = _observation(
        anchor,
        "URGENT_REVIEW",
        architecture="B1",
        repetition=1,
        affected_positions=("position-b",),
        evidence_refs=("evidence-a", "evidence-b"),
        output_digest=digest("different"),
    )
    deterministic = _observation(anchor, "REVIEW")
    results = {
        item.architecture_id: item
        for item in evaluate_repeatability((deterministic, primary, repeated))
    }
    assert results["B0"].semantic_status_agreement == 1
    assert results["B0"].severity_agreement == 1
    assert results["B0"].exact_output_digest_agreement == 1
    result = results["B1"]
    assert result.semantic_status_agreement == 0
    assert result.severity_agreement == 0
    assert result.exact_output_digest_agreement == 0
    assert result.affected_position_jaccard_agreement == Decimal("0.5")
    assert result.evidence_reference_jaccard_agreement == Decimal("0.5")
    assert "preliminary" in result.limitations[0]


def test_nearest_rank_p95_and_empty_set_jaccard_are_deterministic():
    assert deterministic_p95(range(1, 101)) == Decimal("95")
    assert deterministic_p95((10,)) == Decimal("10")
    assert deterministic_p95(()) is None
    assert jaccard_agreement((), ()) == Decimal("1")
