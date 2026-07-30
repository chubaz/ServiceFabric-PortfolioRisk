"""Deterministic descriptive evaluation for the sealed Day 4 experiment."""
from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

from .contracts import (
    AlertOutcomeMatch,
    ArchitectureEvaluation,
    ArchitectureObservation,
    Day4LabelPolicy,
    PortfolioDayLabel,
    ProviderPricingSnapshot,
    RepeatabilityEvaluation,
)

EvaluationClass = Literal["alert", "no_alert", "abstention", "execution_failure"]
LABEL_VIEWS = ("event_window", "outcome", "composite")
PROVIDER_FAILURE_WARNINGS = frozenset({"provider_error", "invalid_structured_output"})
MATCHING_RULE = "closest_eligible_prior_unmatched_alert"


def _decimal(value: object) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _ratio(numerator: int | Decimal, denominator: int | Decimal) -> Decimal | None:
    return _decimal(numerator) / _decimal(denominator) if denominator else None


def _median(values: Sequence[int | Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(_decimal(value) for value in values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal("2")


def deterministic_p95(values: Iterable[int]) -> int | None:
    """Return the deterministic nearest-rank 95th percentile."""

    ordered = sorted(values)
    if not ordered:
        return None
    return ordered[max(0, math.ceil(Decimal("0.95") * len(ordered)) - 1)]


def jaccard_agreement(left: Iterable[str], right: Iterable[str]) -> Decimal:
    """Jaccard agreement with two empty sets treated as exact agreement."""

    left_set, right_set = set(left), set(right)
    union = left_set | right_set
    return (
        Decimal("1")
        if not union
        else Decimal(len(left_set & right_set)) / Decimal(len(union))
    )


def _receipt_warnings(observation: ArchitectureObservation) -> set[str]:
    warnings = set(observation.warnings)
    for receipt in observation.provider_receipts:
        warnings.update(receipt.warnings)
    return warnings


def classify_observation(observation: ArchitectureObservation) -> EvaluationClass:
    """Classify an observation, consulting provider receipts before status."""

    if (
        observation.execution_failure
        or observation.provider_error
        or _receipt_warnings(observation).intersection(PROVIDER_FAILURE_WARNINGS)
    ):
        return "execution_failure"
    if observation.status in {"REVIEW", "URGENT_REVIEW"}:
        return "alert"
    if observation.status == "NO_ISSUE":
        return "no_alert"
    if observation.status in {"ABSTAIN", "ABSTAINED_AGENT_OUTPUT"}:
        return "abstention"
    raise ValueError(f"unsupported architecture status: {observation.status}")


# Compatibility spelling used by some callers.
classify_architecture_observation = classify_observation


def _label_positive(label: PortfolioDayLabel, view: str) -> bool:
    if view == "event_window":
        return label.event_window.positive
    if view == "outcome":
        return label.outcome.positive
    if view == "composite":
        return label.composite
    raise ValueError(f"unsupported label view: {view}")


def _primary(observation: ArchitectureObservation) -> bool:
    return observation.repetition in (0, "primary")


def _business_days_between(start: datetime, end: datetime) -> int:
    """Count business dates after ``start`` through ``end``."""

    if end < start:
        raise ValueError("outcome cannot precede alert")
    current = start.date() + timedelta(days=1)
    final = end.date()
    count = 0
    while current <= final:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


def match_alerts_to_outcomes(
    observations: Iterable[ArchitectureObservation],
    labels: Iterable[PortfolioDayLabel],
    *,
    matching_lookback_business_days: int,
) -> tuple[AlertOutcomeMatch, ...]:
    """Match the closest prior unmatched alert to each positive outcome."""

    if matching_lookback_business_days < 1:
        raise ValueError("matching lookback must be positive")
    observation_values = tuple(observations)
    task_ids = [item.task_id for item in observation_values if _primary(item)]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("primary alert task identities must be unique")
    label_values = tuple(labels)
    labels_by_key = {item.key.key_digest: item for item in label_values}
    if len(labels_by_key) != len(label_values):
        raise ValueError("portfolio-day labels must be unique")
    alerts_by_architecture_portfolio: dict[
        tuple[str, str], list[ArchitectureObservation]
    ] = defaultdict(list)
    for observation in observation_values:
        if (
            _primary(observation)
            and classify_observation(observation) == "alert"
        ):
            alerts_by_architecture_portfolio[
                (observation.architecture_id, observation.key.portfolio_id)
            ].append(observation)
    for alerts in alerts_by_architecture_portfolio.values():
        alerts.sort(key=lambda item: (item.key.as_of, item.task_id))

    outcomes_by_portfolio: dict[str, list[PortfolioDayLabel]] = defaultdict(list)
    for label in label_values:
        if label.outcome.positive and label.outcome.realized_at is not None:
            outcomes_by_portfolio[label.key.portfolio_id].append(label)
    for outcomes in outcomes_by_portfolio.values():
        outcomes.sort(
            key=lambda item: (item.outcome.realized_at, item.label_digest)
        )

    matches: list[AlertOutcomeMatch] = []
    architectures = sorted(
        {observation.architecture_id for observation in observation_values}
    )
    for architecture_id in architectures:
        for portfolio_id, outcomes in sorted(outcomes_by_portfolio.items()):
            alerts = alerts_by_architecture_portfolio.get(
                (architecture_id, portfolio_id), []
            )
            used_alerts: set[str] = set()
            for outcome in outcomes:
                outcome_at = outcome.outcome.realized_at
                assert outcome_at is not None
                eligible = [
                    alert
                    for alert in alerts
                    if alert.task_id not in used_alerts
                    and alert.key.as_of <= outcome_at
                    and _business_days_between(alert.key.as_of, outcome_at)
                    <= matching_lookback_business_days
                ]
                if not eligible:
                    continue
                alert = max(eligible, key=lambda item: (item.key.as_of, item.task_id))
                used_alerts.add(alert.task_id)
                lead = _decimal((outcome_at - alert.key.as_of).total_seconds())
                evidence = tuple(
                    sorted(
                        set(alert.evidence_refs)
                        | set(outcome.outcome.evidence_refs)
                    )
                )
                matches.append(
                    AlertOutcomeMatch(
                        architecture_id=architecture_id,
                        portfolio_id=portfolio_id,
                        alert_task_id=alert.task_id,
                        outcome_label_digest=outcome.label_digest,
                        alert_at=alert.key.as_of,
                        outcome_at=outcome_at,
                        lead_time_seconds=int(lead),
                        matching_lookback_business_days=matching_lookback_business_days,
                        rule=MATCHING_RULE,
                        evidence_refs=evidence,
                    )
                )
    return tuple(
        sorted(
            matches,
            key=lambda item: (
                item.architecture_id,
                item.portfolio_id,
                item.outcome_at,
                item.alert_task_id,
            ),
        )
    )


def _event_delays(
    observations: Sequence[ArchitectureObservation],
    labels_by_key: Mapping[str, PortfolioDayLabel],
) -> list[Decimal]:
    first_alert_by_trigger: dict[datetime, datetime] = {}
    for observation in observations:
        if classify_observation(observation) != "alert":
            continue
        label = labels_by_key[observation.key.key_digest]
        trigger = label.event_window.trigger_available_at
        if not label.event_window.positive or trigger is None:
            continue
        if observation.key.as_of < trigger:
            continue
        current = first_alert_by_trigger.get(trigger)
        if current is None or observation.key.as_of < current:
            first_alert_by_trigger[trigger] = observation.key.as_of
    return [
        _decimal((alert_at - trigger).total_seconds())
        for trigger, alert_at in sorted(first_alert_by_trigger.items())
    ]


def _pricing_cost(
    observations: Sequence[ArchitectureObservation],
    pricing: ProviderPricingSnapshot | None,
) -> tuple[Decimal | None, tuple[str, ...]]:
    input_tokens = sum(item.input_tokens for item in observations)
    output_tokens = sum(item.output_tokens for item in observations)
    receipts = [
        receipt
        for observation in observations
        for receipt in observation.provider_receipts
    ]
    if not receipts and not input_tokens and not output_tokens:
        return Decimal("0"), ()
    if pricing is None:
        return None, ("pricing_unavailable",)
    applicable = all(
        receipt.provider_id == pricing.provider_id
        and receipt.model_id == pricing.model_snapshot
        for receipt in receipts
    )
    if receipts and not applicable:
        return None, ("pricing_unavailable",)
    million = Decimal("1000000")
    cost = (
        Decimal(input_tokens) * pricing.input_price_per_million_tokens / million
        + Decimal(output_tokens) * pricing.output_price_per_million_tokens / million
    )
    return cost, ()


def _legacy_unsupported(observation: ArchitectureObservation) -> bool:
    return bool(
        _receipt_warnings(observation).intersection(
            {"unsupported_claim", "unsupported_claims", "numeric_claim", "evidence"}
        )
    )


def evaluate_architectures(
    observations: Iterable[ArchitectureObservation],
    labels: Iterable[PortfolioDayLabel],
    policy: Day4LabelPolicy,
    *,
    pricing: ProviderPricingSnapshot | None = None,
    label_views: Iterable[str] = LABEL_VIEWS,
) -> tuple[ArchitectureEvaluation, ...]:
    """Evaluate every architecture/view/portfolio/window group descriptively."""

    observation_values = tuple(item for item in observations if _primary(item))
    label_values = tuple(labels)
    labels_by_key = {item.key.key_digest: item for item in label_values}
    if len(labels_by_key) != len(label_values):
        raise ValueError("portfolio-day labels must be unique")
    if any(item.key.key_digest not in labels_by_key for item in observation_values):
        raise ValueError("every primary architecture observation requires one label")
    views = tuple(label_views)
    if not views or set(views).difference(LABEL_VIEWS):
        raise ValueError("label views must use the frozen Day 4 catalogue")

    matches = match_alerts_to_outcomes(
        observation_values,
        label_values,
        matching_lookback_business_days=policy.matching_lookback_business_days,
    )
    matches_by_group: dict[tuple[str, str], list[AlertOutcomeMatch]] = defaultdict(list)
    for match in matches:
        outcome_label = next(
            label for label in label_values
            if label.label_digest == match.outcome_label_digest
        )
        matches_by_group[(match.architecture_id, outcome_label.key.window_id)].append(match)

    grouped: dict[
        tuple[str, str, str, str], list[ArchitectureObservation]
    ] = defaultdict(list)
    for observation in observation_values:
        for view in views:
            grouped[
                (
                    observation.architecture_id,
                    view,
                    observation.key.portfolio_id,
                    observation.key.window_id,
                )
            ].append(observation)

    evaluations: list[ArchitectureEvaluation] = []
    for (architecture_id, view, portfolio_id, window_id), group in sorted(grouped.items()):
        classifications = [classify_observation(item) for item in group]
        pairs = [
            (classification, _label_positive(labels_by_key[item.key.key_digest], view))
            for item, classification in zip(group, classifications, strict=True)
        ]
        tp = sum(category == "alert" and positive for category, positive in pairs)
        fp = sum(category == "alert" and not positive for category, positive in pairs)
        tn = sum(category == "no_alert" and not positive for category, positive in pairs)
        fn = sum(
            positive and category in {"no_alert", "abstention"}
            for category, positive in pairs
        )
        precision = _ratio(tp, tp + fp)
        recall = _ratio(tp, tp + fn)
        warnings: list[str] = []
        if precision is None:
            warnings.append("undefined_precision")
        if recall is None:
            warnings.append("undefined_recall")
        cost, pricing_warnings = _pricing_cost(group, pricing)
        warnings.extend(pricing_warnings)
        completed = [
            item
            for item, category in zip(group, classifications, strict=True)
            if category != "execution_failure"
        ]
        evidence_covered = sum(bool(item.evidence_refs) for item in completed)
        critic_denominator = len(completed)
        claim_count = sum(item.claim_count for item in completed)
        unsupported_claim_count = sum(
            item.unsupported_claim_count for item in completed
        )
        if claim_count:
            unsupported_claim_rate = _ratio(
                unsupported_claim_count, claim_count
            )
        else:
            legacy_unsupported_count = sum(
                _legacy_unsupported(item) for item in completed
            )
            unsupported_claim_rate = (
                _ratio(legacy_unsupported_count, critic_denominator)
                if legacy_unsupported_count
                else Decimal("0")
            )
            warnings.append("undefined_unsupported_claim_rate")
        if not critic_denominator:
            warnings.extend(
                (
                    "undefined_evidence_reference_coverage",
                    "undefined_critic_pass_rate",
                )
            )
        group_matches = [
            item
            for item in matches_by_group.get((architecture_id, window_id), ())
            if item.portfolio_id == portfolio_id
        ]
        delays = _event_delays(group, labels_by_key)
        evaluations.append(
            ArchitectureEvaluation(
                architecture_id=architecture_id,
                label_view=view,
                portfolio_id=portfolio_id,
                window_id=window_id,
                total_portfolio_days=len(group),
                alerts=classifications.count("alert"),
                abstentions=classifications.count("abstention"),
                execution_failures=classifications.count("execution_failure"),
                true_positives=tp,
                false_positives=fp,
                true_negatives=tn,
                false_negatives=fn,
                precision=precision,
                recall=recall,
                alerts_per_100_portfolio_days=(
                    Decimal(classifications.count("alert"))
                    * Decimal("100")
                    / Decimal(len(group))
                ),
                abstention_rate=_ratio(classifications.count("abstention"), len(group)),
                evaluated_coverage=_ratio(
                    classifications.count("alert") + classifications.count("no_alert"),
                    len(group),
                ),
                evidence_reference_coverage=_ratio(
                    evidence_covered, critic_denominator
                ) or Decimal("0"),
                unsupported_claim_rate=unsupported_claim_rate or Decimal("0"),
                critic_pass_rate=_ratio(
                    sum(item.critic_passed for item in completed), critic_denominator
                ) or Decimal("0"),
                median_event_detection_delay_seconds=_median(delays),
                median_outcome_lead_time_seconds=_median(
                    [item.lead_time_seconds for item in group_matches]
                ),
                median_latency_ms=_median([item.latency_ms for item in group]),
                p95_latency_ms=deterministic_p95(
                    item.latency_ms for item in group
                ),
                input_tokens=sum(item.input_tokens for item in group),
                output_tokens=sum(item.output_tokens for item in group),
                provider_cost=cost,
                currency=pricing.currency if cost is not None and pricing else None,
                warnings=tuple(sorted(set(warnings))),
            )
        )
    return tuple(evaluations)


def evaluate_repeatability(
    observations: Iterable[ArchitectureObservation],
) -> tuple[RepeatabilityEvaluation, ...]:
    """Measure exact and set agreement over the predeclared anchor panel."""

    values = tuple(observations)
    repeated_keys = {
        item.key.key_digest for item in values if item.repetition == 1
    }
    if not repeated_keys:
        raise ValueError("repeatability evaluation requires repeated anchor observations")
    grouped: dict[tuple[str, str], list[ArchitectureObservation]] = defaultdict(list)
    for observation in values:
        if observation.key.key_digest in repeated_keys:
            grouped[(observation.architecture_id, observation.key.key_digest)].append(
                observation
            )
    results: list[RepeatabilityEvaluation] = []
    architectures = {value.architecture_id for value in values}
    for architecture_id in (
        item for item in ("B0", "B1", "A1") if item in architectures
    ):
        status: list[Decimal] = []
        severity: list[Decimal] = []
        output_digest: list[Decimal] = []
        positions: list[Decimal] = []
        evidence: list[Decimal] = []
        anchor_count = 0
        for (candidate, _key_digest), group in sorted(grouped.items()):
            if candidate != architecture_id:
                continue
            ordered = sorted(group, key=lambda item: (item.repetition, item.task_id))
            if architecture_id == "B0":
                if len(ordered) != 1:
                    raise ValueError("B0 repeatability uses deterministic primary reuse only")
                left = right = ordered[0]
            else:
                if len(ordered) != 2:
                    raise ValueError("B1/A1 repeatability anchors require exactly two observations")
                left, right = ordered
            anchor_count += 1
            status.append(Decimal(left.status == right.status))
            severity.append(Decimal(left.severity == right.severity))
            output_digest.append(
                Decimal(left.semantic_output_digest == right.semantic_output_digest)
            )
            positions.append(
                jaccard_agreement(left.affected_positions, right.affected_positions)
            )
            evidence.append(
                jaccard_agreement(left.evidence_refs, right.evidence_refs)
            )
        if not anchor_count:
            continue
        results.append(
            RepeatabilityEvaluation(
                architecture_id=architecture_id,
                anchor_count=anchor_count,
                semantic_status_agreement=_ratio(sum(status), anchor_count),
                severity_agreement=_ratio(sum(severity), anchor_count),
                exact_output_digest_agreement=_ratio(
                    sum(output_digest), anchor_count
                ),
                affected_position_jaccard_agreement=_ratio(
                    sum(positions), anchor_count
                ),
                evidence_reference_jaccard_agreement=_ratio(
                    sum(evidence), anchor_count
                ),
                warnings=(),
                limitations=(
                    (
                        "B0 uses deterministic reuse."
                        if architecture_id == "B0"
                        else (
                            "Two observations per anchor are a preliminary "
                            "agreement check only."
                        )
                    ),
                ),
            )
        )
    return tuple(results)
