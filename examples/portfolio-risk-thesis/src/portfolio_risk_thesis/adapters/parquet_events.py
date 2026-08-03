"""Read-only, exact-ID historical event adapter."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pyarrow.parquet as pq

from ..contracts import DatasetMetadata, HistoricalEventObservation, utc_datetime
from ..manifests import sha256_file


class HistoricalEventDataAdapter:
    def __init__(self, metadata: DatasetMetadata) -> None:
        if metadata.profile != "synthetic_local":
            raise ValueError(
                "licensed_local event data is not admitted by the CRSP/Compustat bridge"
            )
        if len(metadata.source_paths) != 1:
            raise ValueError("Day 1 event adapter requires exactly one source")
        self._metadata = metadata
        self._path = Path(metadata.source_paths[0])
        if sha256_file(self._path) != metadata.source_digests[0]:
            raise ValueError(f"event source digest does not match metadata: {self._path}")
        schema = set(pq.read_schema(self._path).names)
        missing = set(metadata.required_columns) - schema
        if missing:
            raise ValueError(f"event source is missing required columns: {sorted(missing)}")
        self._rows = tuple(HistoricalEventObservation.model_validate(row) for row in pq.read_table(self._path).to_pylist())

    @staticmethod
    def _selected(instruments: tuple[str, ...] | list[str]) -> set[str]:
        selected = set(instruments)
        if not selected:
            raise ValueError("an explicit non-empty instrument selection is required")
        return selected

    @staticmethod
    def _matches(row: HistoricalEventObservation, selected: set[str]) -> bool:
        return bool(selected.intersection(row.instrument_ids))

    @staticmethod
    def _ordered(rows: list[HistoricalEventObservation]) -> tuple[HistoricalEventObservation, ...]:
        return tuple(sorted(rows, key=lambda row: (row.available_at, row.event_time, row.event_id)))

    def events(self, start: datetime, end: datetime, instruments: tuple[str, ...] | list[str]) -> tuple[HistoricalEventObservation, ...]:
        start, end = utc_datetime(start), utc_datetime(end)
        if end < start:
            raise ValueError("end must not precede start")
        selected = self._selected(instruments)
        return self._ordered([row for row in self._rows if start <= row.event_time <= end and self._matches(row, selected)])

    def events_as_of(self, as_of: datetime, instruments: tuple[str, ...] | list[str]) -> tuple[HistoricalEventObservation, ...]:
        as_of = utc_datetime(as_of)
        selected = self._selected(instruments)
        return self._ordered([row for row in self._rows if row.available_at <= as_of and self._matches(row, selected)])

    def newly_available(
        self,
        previous_as_of: datetime | None,
        as_of: datetime,
        instruments: tuple[str, ...] | list[str],
    ) -> tuple[HistoricalEventObservation, ...]:
        as_of = utc_datetime(as_of)
        previous = utc_datetime(previous_as_of) if previous_as_of is not None else as_of - timedelta(microseconds=1)
        selected = self._selected(instruments)
        return self._ordered([row for row in self._rows if previous < row.available_at <= as_of and self._matches(row, selected)])

    def metadata(self) -> DatasetMetadata:
        return self._metadata
