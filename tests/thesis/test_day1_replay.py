from __future__ import annotations

from datetime import UTC, datetime, time
from pathlib import Path

import pytest
import yaml

from portfolio_risk_thesis.adapters import HistoricalEventDataAdapter, HistoricalMarketDataAdapter
from portfolio_risk_thesis.cli import replay_results
from portfolio_risk_thesis.manifests import load_dataset_manifest, load_experiment, load_portfolio
from portfolio_risk_thesis.portfolio import SnapshotBuilder
from portfolio_risk_thesis.replay import ReplayChannel, ReplayClock


def replay(example_root: Path):  # type: ignore[no-untyped-def]
    market_metadata, event_metadata = load_dataset_manifest(example_root / "data" / "dataset_manifest.yaml")
    portfolio = load_portfolio(example_root / "portfolios" / "diversified.yaml")
    specification = load_experiment(example_root / "experiments" / "day1_smoke.yaml", portfolio.portfolio_id)
    clock = ReplayClock(specification, specification.review_time)
    channel = ReplayChannel(
        HistoricalMarketDataAdapter(market_metadata),
        HistoricalEventDataAdapter(event_metadata),
        SnapshotBuilder(),
    )
    return clock, channel.replay(clock, specification, portfolio)


def test_clock_is_inclusive_and_run_identity_is_deterministic(example_root: Path) -> None:
    first_clock, first = replay(example_root)
    second_clock, second = replay(example_root)
    assert len(first) == 5
    assert first_clock.run_id == second_clock.run_id
    assert first == second
    assert [item.step.ordinal for item in first] == list(range(5))


def test_replay_has_no_look_ahead_and_uses_new_availability_interval(example_root: Path) -> None:
    _, results = replay(example_root)
    for result in results:
        step = result.step
        assert all(step.previous_as_of < row.available_at <= step.as_of for row in step.newly_eligible_market_records)
        assert all(step.previous_as_of < row.available_at <= step.as_of for row in step.newly_eligible_event_records)
        assert all(row.available_at <= step.as_of for row in step.latest_eligible_market_records)
    june_27 = results[3].step
    june_28 = results[4].step
    assert "fictional-event-021" not in {row.event_id for row in june_27.newly_eligible_event_records}
    assert "fictional-event-021" in {row.event_id for row in june_28.newly_eligible_event_records}


def test_manifest_review_time_controls_ticks_and_run_identity(example_root: Path, tmp_path: Path) -> None:
    path = example_root / "experiments" / "day1_smoke.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["review_time"] = "17:00:00Z"
    alternate_path = tmp_path / "alternate-smoke.yaml"
    alternate_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    standard = load_experiment(path, "diversified")
    alternate = load_experiment(alternate_path, "diversified")
    standard_clock = ReplayClock(standard, standard.review_time)
    alternate_clock = ReplayClock(alternate, alternate.review_time)
    assert {tick.as_of.hour for tick in alternate_clock} == {17}
    assert standard_clock.run_id != alternate_clock.run_id
    public_results = replay_results(experiment_manifest=alternate_path)
    assert all(
        step.step.as_of.hour == 17
        for steps in public_results.values()
        for step in steps
    )
    with pytest.raises(ValueError, match="must match"):
        ReplayClock(alternate, time(18, 0, tzinfo=UTC))


def test_clock_emits_only_ticks_inside_partial_day_interval(example_root: Path) -> None:
    specification = load_experiment(
        example_root / "experiments" / "day1_smoke.yaml", "diversified"
    )
    bounded = specification.model_copy(
        update={
            "start": datetime(2024, 6, 24, 20, tzinfo=UTC),
            "end": datetime(2024, 6, 26, 17, tzinfo=UTC),
        }
    )
    ticks = ReplayClock(bounded, bounded.review_time).ticks()
    assert [tick.as_of for tick in ticks] == [datetime(2024, 6, 25, 18, tzinfo=UTC)]
    assert all(bounded.start <= tick.as_of <= bounded.end for tick in ticks)

    incompatible = bounded.model_copy(
        update={
            "start": datetime(2024, 6, 24, 20, tzinfo=UTC),
            "end": datetime(2024, 6, 25, 17, tzinfo=UTC),
        }
    )
    with pytest.raises(ValueError, match="no reviewed daily tick"):
        ReplayClock(incompatible, incompatible.review_time).ticks()
