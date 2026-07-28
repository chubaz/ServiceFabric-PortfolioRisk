"""Read-only, manifest-validated historical market adapter."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pyarrow.parquet as pq

from ..contracts import DatasetMetadata, HistoricalMarketObservation, utc_datetime
from ..manifests import sha256_file


class HistoricalMarketDataAdapter:
    def __init__(self, metadata: DatasetMetadata) -> None:
        if len(metadata.source_paths) != 1:
            raise ValueError("Day 1 market adapter requires exactly one source")
        self._metadata = metadata
        self._path = Path(metadata.source_paths[0])
        if sha256_file(self._path) != metadata.source_digests[0]:
            raise ValueError(f"market source digest does not match metadata: {self._path}")
        schema = set(pq.read_schema(self._path).names)
        missing = set(metadata.required_columns) - schema
        if missing:
            raise ValueError(f"market source is missing required columns: {sorted(missing)}")
        self._rows = tuple(self._record(row) for row in pq.read_table(self._path).to_pylist())

    @staticmethod
    def _record(row: dict[str, object]) -> HistoricalMarketObservation:
        return HistoricalMarketObservation.model_validate(row)

    @staticmethod
    def _instrument_filter(instruments: tuple[str, ...] | list[str]) -> set[str]:
        selected = set(instruments)
        if not selected:
            raise ValueError("an explicit non-empty instrument selection is required")
        return selected

    def instruments(self) -> tuple[str, ...]:
        return tuple(sorted({row.instrument_id for row in self._rows}))

    def observations(
        self,
        start: datetime,
        end: datetime,
        instruments: tuple[str, ...] | list[str],
    ) -> tuple[HistoricalMarketObservation, ...]:
        start, end = utc_datetime(start), utc_datetime(end)
        if end < start:
            raise ValueError("end must not precede start")
        selected = self._instrument_filter(instruments)
        return tuple(
            sorted(
                (row for row in self._rows if row.instrument_id in selected and start <= row.timestamp <= end),
                key=lambda row: (row.timestamp, row.available_at, row.instrument_id),
            )
        )

    def observations_as_of(
        self,
        as_of: datetime,
        instruments: tuple[str, ...] | list[str],
        lookback: int,
    ) -> tuple[HistoricalMarketObservation, ...]:
        as_of = utc_datetime(as_of)
        if lookback < 1:
            raise ValueError("lookback must be positive")
        selected = self._instrument_filter(instruments)
        eligible = [row for row in self._rows if row.instrument_id in selected and row.available_at <= as_of]
        by_instrument: dict[str, list[HistoricalMarketObservation]] = {}
        for row in eligible:
            by_instrument.setdefault(row.instrument_id, []).append(row)
        retained: list[HistoricalMarketObservation] = []
        for instrument_id in sorted(by_instrument):
            ordered = sorted(by_instrument[instrument_id], key=lambda row: (row.timestamp, row.available_at))
            retained.extend(ordered[-lookback:])
        return tuple(sorted(retained, key=lambda row: (row.timestamp, row.available_at, row.instrument_id)))

    def latest_observations_as_of(
        self,
        as_of: datetime,
        instruments: tuple[str, ...] | list[str],
    ) -> tuple[HistoricalMarketObservation, ...]:
        as_of = utc_datetime(as_of)
        selected = self._instrument_filter(instruments)
        latest: dict[str, HistoricalMarketObservation] = {}
        for row in self._rows:
            if row.instrument_id not in selected or row.available_at > as_of:
                continue
            prior = latest.get(row.instrument_id)
            if prior is None or (row.timestamp, row.available_at) > (prior.timestamp, prior.available_at):
                latest[row.instrument_id] = row
        return tuple(latest[key] for key in sorted(latest))

    def newly_available(
        self,
        previous_as_of: datetime | None,
        as_of: datetime,
        instruments: tuple[str, ...] | list[str],
    ) -> tuple[HistoricalMarketObservation, ...]:
        as_of = utc_datetime(as_of)
        previous = utc_datetime(previous_as_of) if previous_as_of is not None else as_of - timedelta(microseconds=1)
        selected = self._instrument_filter(instruments)
        return tuple(
            sorted(
                (row for row in self._rows if row.instrument_id in selected and previous < row.available_at <= as_of),
                key=lambda row: (row.available_at, row.timestamp, row.instrument_id),
            )
        )

    def metadata(self) -> DatasetMetadata:
        return self._metadata
