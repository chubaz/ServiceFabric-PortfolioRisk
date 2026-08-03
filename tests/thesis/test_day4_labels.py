from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from portfolio_risk_thesis.day4.contracts import (
    Day4LabelPolicy,
    HistoricalWindow,
    PortfolioDayKey,
)
from portfolio_risk_thesis.day4.labels import (
    construct_event_window_label,
    construct_labels,
    construct_outcome_label,
    construct_portfolio_day_label,
)


BASE = datetime(2024, 1, 8, 21, tzinfo=UTC)


def _window(window_id: str = "stress_a") -> HistoricalWindow:
    control = window_id == "control"
    return HistoricalWindow(
        window_id=window_id,
        kind="control" if control else "stress",
        rationale="Reviewed synthetic window.",
        review_dates=tuple(BASE + timedelta(days=index) for index in range(5)),
        trigger_available_at=None if control else BASE + timedelta(days=1),
        relevant_portfolios=() if control else ("portfolio-a",),
    )


def _policy() -> Day4LabelPolicy:
    return Day4LabelPolicy(
        future_portfolio_drawdown_threshold=Decimal("0.08"),
        future_realized_volatility_threshold=Decimal("0.30"),
        worst_position_loss_threshold=Decimal("0.10"),
        material_event_enabled=True,
        matching_lookback_business_days=5,
    )


def _future(key: PortfolioDayKey, **updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "realized_at": key.as_of + timedelta(days=7),
        "portfolio_drawdown": Decimal("0.02"),
        "realized_volatility": Decimal("0.15"),
        "worst_position_loss": Decimal("-0.03"),
        "material_event": False,
        "evidence_refs": ("future-evidence",),
    }
    value.update(updates)
    return value


def test_event_window_label_requires_relevance_and_reviewed_trigger_availability():
    window = _window()
    before = PortfolioDayKey(
        portfolio_id="portfolio-a", window_id="stress_a", as_of=BASE
    )
    after = PortfolioDayKey(
        portfolio_id="portfolio-a",
        window_id="stress_a",
        as_of=BASE + timedelta(days=1),
    )
    irrelevant = PortfolioDayKey(
        portfolio_id="portfolio-b",
        window_id="stress_a",
        as_of=BASE + timedelta(days=1),
    )

    assert not construct_event_window_label(before, window).positive
    assert construct_event_window_label(after, window).positive
    assert not construct_event_window_label(irrelevant, window).positive
    assert not construct_event_window_label(
        PortfolioDayKey(portfolio_id="portfolio-a", window_id="control", as_of=BASE),
        _window("control"),
    ).positive


@pytest.mark.parametrize(
    ("update", "positive"),
    [
        ({"portfolio_drawdown": Decimal("0.09")}, True),
        ({"realized_volatility": Decimal("0.31")}, True),
        ({"worst_position_loss": Decimal("-0.11")}, True),
        ({"material_event": True}, True),
        ({}, False),
    ],
)
def test_outcome_label_uses_only_explicit_reviewed_thresholds(update, positive):
    key = PortfolioDayKey(
        portfolio_id="portfolio-a", window_id="stress_a", as_of=BASE
    )
    label = construct_outcome_label(key, _future(key, **update), _policy())
    assert label.positive is positive
    assert label.realized_at > key.as_of


def test_composite_is_event_window_or_outcome():
    window = _window()
    key = PortfolioDayKey(
        portfolio_id="portfolio-a",
        window_id="stress_a",
        as_of=BASE + timedelta(days=1),
    )
    label = construct_portfolio_day_label(key, window, _future(key), _policy())
    assert label.event_window.positive
    assert not label.outcome.positive
    assert label.composite


def test_outcome_rejects_a_non_five_session_horizon():
    key = PortfolioDayKey(
        portfolio_id="portfolio-a", window_id="stress_a", as_of=BASE
    )
    with pytest.raises(ValueError, match="five sessions"):
        construct_outcome_label(
            key,
            _future(key, future_business_sessions=4),
            _policy(),
        )


def test_labels_cannot_be_constructed_until_architecture_execution_is_sealed():
    window = _window()
    key = PortfolioDayKey(
        portfolio_id="portfolio-a",
        window_id="stress_a",
        as_of=BASE + timedelta(days=1),
    )
    outcomes = {key.key_digest: _future(key)}
    with pytest.raises(ValueError, match="sealed"):
        construct_labels(
            (key,),
            (window,),
            outcomes,
            _policy(),
            architecture_execution_sealed=False,
        )
    assert len(
        construct_labels(
            (key,),
            (window,),
            outcomes,
            _policy(),
            architecture_execution_sealed=True,
        )
    ) == 1
