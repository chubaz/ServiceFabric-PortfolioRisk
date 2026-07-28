"""A deterministic daily replay clock with no system-clock dependency."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, time, timedelta

from pydantic import BaseModel, ConfigDict

from ..contracts import ReplaySpecification, utc_datetime


class ReplayTick(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    ordinal: int
    previous_as_of: datetime
    as_of: datetime


class ReplayClock:
    """Produce inclusive reviewed daily instants without sleeping or reading now()."""

    def __init__(self, specification: ReplaySpecification, review_time: time | None = None) -> None:
        review_time = review_time or specification.review_time
        if review_time.tzinfo is None or review_time.utcoffset() is None:
            raise ValueError("review_time must be timezone-aware UTC")
        if review_time.utcoffset() != timedelta(0):
            raise ValueError("review_time must use UTC")
        if review_time != specification.review_time:
            raise ValueError("review_time must match the reviewed replay specification")
        self.specification = specification
        self.review_time = review_time
        identity = {
            "specification": specification.model_dump(mode="json"),
            "review_time": review_time.isoformat(),
        }
        payload = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.run_id = f"sha256:{hashlib.sha256(payload).hexdigest()}"

    def ticks(self) -> tuple[ReplayTick, ...]:
        current_date = self.specification.start.date()
        end_date = self.specification.end.date()
        values: list[ReplayTick] = []
        ordinal = 0
        previous_tick: datetime | None = None
        while current_date <= end_date:
            as_of = utc_datetime(datetime.combine(current_date, self.review_time).astimezone(UTC))
            if self.specification.start <= as_of <= self.specification.end:
                lower_bound = self.specification.start - timedelta(microseconds=1)
                previous_as_of = previous_tick or max(as_of - timedelta(days=1), lower_bound)
                values.append(
                    ReplayTick(
                        run_id=self.run_id,
                        ordinal=ordinal,
                        previous_as_of=previous_as_of,
                        as_of=as_of,
                    )
                )
                previous_tick = as_of
                ordinal += 1
            current_date += timedelta(days=1)
        if not values:
            raise ValueError("no reviewed daily tick falls within the declared replay interval")
        return tuple(values)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.ticks())
