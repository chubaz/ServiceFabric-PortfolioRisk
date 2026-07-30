"""Post-execution construction of the three frozen Day 4 label views.

This module deliberately depends only on label contracts.  Architecture
context and provider modules must never import it: callers invoke these
functions only after architecture execution has been sealed.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from decimal import Decimal

from .contracts import (
    Day4LabelPolicy,
    EventWindowLabel,
    HistoricalWindow,
    OutcomeLabel,
    PortfolioDayKey,
    PortfolioDayLabel,
)


def _decimal(value: object | None) -> Decimal | None:
    if value is None:
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _utc(value: object | None) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise TypeError("outcome realized_at must be a datetime")
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("outcome realized_at must be explicit UTC")
    return value.astimezone(UTC)


def _field(value: object, *names: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        for name in names:
            if name in value:
                return value[name]
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return default


def _threshold(policy: Day4LabelPolicy, *names: str) -> Decimal:
    value = _field(policy, *names)
    if value is None:
        raise ValueError(f"reviewed label policy is missing {names[0]}")
    return _decimal(value)  # type: ignore[return-value]


def _outcome_for(
    outcomes: Mapping[object, object],
    key: PortfolioDayKey,
) -> object:
    """Resolve a future-only observation without imposing a storage format."""

    candidates: tuple[object, ...] = (
        key.key_digest,
        (key.portfolio_id, key.window_id, key.as_of),
        (key.portfolio_id, key.as_of),
    )
    for candidate in candidates:
        if candidate in outcomes:
            return outcomes[candidate]
    raise ValueError(f"missing reviewed future outcome for {key.key_digest}")


def construct_event_window_label(
    key: PortfolioDayKey,
    window: HistoricalWindow,
    *,
    evidence_refs: Iterable[str] = (),
) -> EventWindowLabel:
    """Build the reviewed event label for one portfolio-day.

    A relevant stress window becomes positive only once its predeclared
    trigger was available.  Control windows and pre-trigger dates remain
    negative.
    """

    if key.window_id != window.window_id or key.as_of not in window.review_dates:
        raise ValueError("portfolio-day key does not belong to the reviewed window")
    relevant = key.portfolio_id in window.relevant_portfolios
    trigger = window.trigger_available_at
    positive = bool(
        window.kind == "stress"
        and relevant
        and trigger is not None
        and trigger <= key.as_of
    )
    rationale = (
        "Predeclared relevant stress window after reviewed trigger availability."
        if positive
        else "No reviewed event-window positive applies to this portfolio-day."
    )
    return EventWindowLabel(
        key=key,
        positive=positive,
        trigger_available_at=trigger if relevant and window.kind == "stress" else None,
        evidence_refs=tuple(sorted(set(evidence_refs))),
        rationale=rationale,
    )


def construct_outcome_label(
    key: PortfolioDayKey,
    future_observation: object,
    policy: Day4LabelPolicy,
) -> OutcomeLabel:
    """Apply only externally reviewed thresholds to a five-session outcome."""

    drawdown = _decimal(
        _field(future_observation, "portfolio_drawdown", "future_portfolio_drawdown")
    )
    volatility = _decimal(
        _field(future_observation, "realized_volatility", "future_realized_volatility")
    )
    worst_loss = _decimal(
        _field(future_observation, "worst_position_loss", "future_worst_position_loss")
    )
    material_event = bool(
        _field(future_observation, "material_event", default=False)
    )
    realized_at = _utc(
        _field(future_observation, "realized_at", "outcome_at")
    )
    evidence_refs = tuple(
        sorted(set(_field(future_observation, "evidence_refs", default=()) or ()))
    )
    sessions = _field(
        future_observation,
        "future_business_sessions",
        "business_session_count",
        default=policy.future_business_sessions,
    )
    if sessions != policy.future_business_sessions:
        raise ValueError("future outcome does not cover the reviewed five sessions")
    if realized_at is not None and realized_at <= key.as_of:
        raise ValueError("future outcome must be realized after the architecture as_of")

    drawdown_threshold = _threshold(
        policy,
        "portfolio_drawdown_threshold",
        "future_portfolio_drawdown_threshold",
    )
    volatility_threshold = _threshold(
        policy,
        "realized_volatility_threshold",
        "future_realized_volatility_threshold",
    )
    loss_threshold = _threshold(
        policy,
        "worst_position_loss_threshold",
        "future_worst_position_loss_threshold",
    )
    material_enabled = bool(
        _field(policy, "material_event_enabled", default=False)
    )

    # Drawdown and position loss may be represented as signed returns or as
    # positive magnitudes.  Contract thresholds are positive magnitudes.
    drawdown_breach = bool(
        drawdown is not None
        and (
            drawdown <= drawdown_threshold
            if drawdown_threshold < 0
            else abs(drawdown) >= drawdown_threshold
        )
    )
    loss_breach = bool(
        worst_loss is not None
        and (
            worst_loss <= loss_threshold
            if loss_threshold < 0
            else abs(min(worst_loss, Decimal("0"))) >= loss_threshold
        )
    )
    volatility_breach = bool(
        volatility is not None and volatility >= volatility_threshold
    )
    material_breach = material_enabled and material_event
    positive = drawdown_breach or volatility_breach or loss_breach or material_breach
    triggered = [
        name
        for name, breached in (
            ("portfolio_drawdown", drawdown_breach),
            ("realized_volatility", volatility_breach),
            ("worst_position_loss", loss_breach),
            ("material_event", material_breach),
        )
        if breached
    ]
    missing = [
        name
        for name, value in (
            ("portfolio_drawdown", drawdown),
            ("realized_volatility", volatility),
            ("worst_position_loss", worst_loss),
        )
        if value is None
    ]
    rationale = (
        "Reviewed five-business-session threshold(s): " + ", ".join(triggered) + "."
        if triggered
        else "No observed reviewed five-business-session threshold was reached."
    )
    if missing:
        rationale += " Missing observations: " + ", ".join(missing) + "."
    return OutcomeLabel(
        key=key,
        positive=positive,
        realized_at=realized_at,
        portfolio_drawdown=drawdown,
        realized_volatility=volatility,
        worst_position_loss=worst_loss,
        material_event=material_event,
        evidence_refs=evidence_refs,
        rationale=rationale,
    )


def construct_portfolio_day_label(
    key: PortfolioDayKey,
    window: HistoricalWindow,
    future_observation: object,
    policy: Day4LabelPolicy,
    *,
    event_evidence_refs: Iterable[str] = (),
) -> PortfolioDayLabel:
    """Build event, outcome and composite-OR views for one sealed context."""

    event = construct_event_window_label(
        key,
        window,
        evidence_refs=event_evidence_refs,
    )
    outcome = construct_outcome_label(key, future_observation, policy)
    return PortfolioDayLabel(
        key=key,
        event_window=event,
        outcome=outcome,
        composite=event.positive or outcome.positive,
    )


def construct_labels(
    keys: Iterable[PortfolioDayKey],
    windows: Iterable[HistoricalWindow],
    future_outcomes: Mapping[object, object],
    policy: Day4LabelPolicy,
    *,
    architecture_execution_sealed: bool,
    event_evidence_refs: Mapping[str, Iterable[str]] | None = None,
) -> tuple[PortfolioDayLabel, ...]:
    """Construct the complete immutable label panel after execution is sealed."""

    if architecture_execution_sealed is not True:
        raise ValueError("architecture execution must be sealed before labels are constructed")
    window_values = tuple(windows)
    window_by_id = {window.window_id: window for window in window_values}
    if len(window_by_id) != len(window_values):
        raise ValueError("reviewed window identifiers must be unique")
    labels: list[PortfolioDayLabel] = []
    seen: set[str] = set()
    for key in sorted(
        keys,
        key=lambda item: (item.window_id, item.portfolio_id, item.as_of),
    ):
        if key.key_digest in seen:
            raise ValueError("portfolio-day keys must be unique")
        seen.add(key.key_digest)
        if key.window_id not in window_by_id:
            raise ValueError(f"unknown reviewed window: {key.window_id}")
        labels.append(
            construct_portfolio_day_label(
                key,
                window_by_id[key.window_id],
                _outcome_for(future_outcomes, key),
                policy,
                event_evidence_refs=(
                    event_evidence_refs or {}
                ).get(key.key_digest, ()),
            )
        )
    return tuple(labels)


# Explicit alias used by orchestration code to emphasize the phase boundary.
construct_labels_after_sealed_execution = construct_labels
