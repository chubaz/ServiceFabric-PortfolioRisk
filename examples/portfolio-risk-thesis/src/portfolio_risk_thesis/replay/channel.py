"""Connect the deterministic clock, point-in-time adapters and canonical builder."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..adapters import HistoricalEventDataAdapter, HistoricalMarketDataAdapter
from ..contracts import HistoricalStep, PortfolioDefinition, ReplaySpecification
from ..portfolio.snapshot_builder import SnapshotBuildResult, SnapshotBuilder
from .clock import ReplayClock


class ReplayStepResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    step: HistoricalStep
    snapshot: SnapshotBuildResult


class ReplayChannel:
    def __init__(
        self,
        market: HistoricalMarketDataAdapter,
        events: HistoricalEventDataAdapter,
        builder: SnapshotBuilder,
    ) -> None:
        self.market = market
        self.events = events
        self.builder = builder

    def replay(
        self,
        clock: ReplayClock,
        specification: ReplaySpecification,
        portfolio: PortfolioDefinition,
    ) -> tuple[ReplayStepResult, ...]:
        if clock.specification != specification:
            raise ValueError("clock specification must match replay specification")
        if portfolio.portfolio_id != specification.portfolio_id:
            raise ValueError("portfolio does not match replay specification")
        instrument_ids = tuple(item.instrument_id for item in portfolio.positions)
        results: list[ReplayStepResult] = []
        for tick in clock:
            newly_market = self.market.newly_available(tick.previous_as_of, tick.as_of, instrument_ids)
            newly_events = self.events.newly_available(tick.previous_as_of, tick.as_of, instrument_ids)
            latest = self.market.latest_observations_as_of(tick.as_of, instrument_ids)
            evidence = tuple(
                sorted(
                    {row.evidence_ref for row in newly_market}
                    | {row.evidence_ref for row in newly_events}
                    | {row.evidence_ref for row in latest}
                )
            )
            step = HistoricalStep(
                run_id=tick.run_id,
                ordinal=tick.ordinal,
                previous_as_of=tick.previous_as_of,
                as_of=tick.as_of,
                newly_eligible_market_records=newly_market,
                newly_eligible_event_records=newly_events,
                latest_eligible_market_records=latest,
                evidence_references=evidence,
            )
            snapshot = self.builder.build(portfolio, tick.as_of, latest, specification.dataset_revision)
            results.append(ReplayStepResult(step=step, snapshot=snapshot))
        return tuple(results)
