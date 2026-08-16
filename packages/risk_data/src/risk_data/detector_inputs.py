"""Fixed, read-only CRSP input query for registered statistical detectors."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal

import duckdb
from pydantic import Field, field_validator, model_validator

from risk_domain.digests import sha256_digest

from .research_contracts import ResearchContract


class DetectorMarketRow(ResearchContract):
    permno: int = Field(gt=0)
    observed_at: datetime
    available_at: datetime
    total_return: Decimal

    @field_validator("observed_at", "available_at")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("detector market timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def availability_is_not_before_observation(self) -> "DetectorMarketRow":
        if self.available_at < self.observed_at:
            raise ValueError("detector market availability cannot precede observation")
        if not self.total_return.is_finite():
            raise ValueError("detector total return must be finite")
        return self


class DetectorMarketBatch(ResearchContract):
    dataset_snapshot_id: str = Field(min_length=1, max_length=256)
    requested_start: date
    requested_end: date
    as_of: datetime
    requested_permnos: tuple[int, ...] = Field(min_length=1)
    source_row_count: int = Field(ge=0)
    missing_return_count: int = Field(ge=0)
    rows: tuple[DetectorMarketRow, ...] = ()
    batch_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")

    @field_validator("as_of")
    @classmethod
    def as_of_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("detector batch as_of must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("requested_permnos")
    @classmethod
    def permnos_are_unique_and_ordered(cls, values: tuple[int, ...]) -> tuple[int, ...]:
        if any(item <= 0 for item in values) or len(values) != len(set(values)):
            raise ValueError("requested PERMNO values must be positive and unique")
        return tuple(sorted(values))

    @model_validator(mode="after")
    def batch_is_consistent(self) -> "DetectorMarketBatch":
        if self.requested_end < self.requested_start:
            raise ValueError("detector batch end cannot precede start")
        if self.source_row_count != len(self.rows) + self.missing_return_count:
            raise ValueError("complete and missing rows must reconcile to source_row_count")
        if any(item.available_at > self.as_of for item in self.rows):
            raise ValueError("detector market batch cannot contain future information")
        if tuple(self.rows) != tuple(sorted(self.rows, key=lambda item: (item.observed_at, item.permno))):
            raise ValueError("detector market rows must be ordered by observation time and PERMNO")
        expected = sha256_digest(self.model_dump(mode="python", exclude={"batch_digest"}))
        if self.batch_digest != expected:
            raise ValueError("batch_digest must equal the canonical detector input digest")
        return self


def _utc(value: object) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, date):
        result = datetime.combine(value, time.min)
    else:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def query_crsp_detector_market(
    connection: duckdb.DuckDBPyConnection,
    *,
    dataset_snapshot_id: str,
    permnos: tuple[int, ...],
    start_date: date,
    end_date: date,
) -> DetectorMarketBatch:
    """Execute one fixed point-in-time query; callers cannot supply SQL."""

    ordered_permnos = tuple(sorted(set(permnos)))
    if not ordered_permnos or any(item <= 0 for item in ordered_permnos):
        raise ValueError("at least one positive PERMNO is required")
    if end_date < start_date:
        raise ValueError("detector query end cannot precede start")
    placeholders = ",".join("?" for _ in ordered_permnos)
    as_of_value = connection.execute(
        f"""
        SELECT max(available_at)::VARCHAR
        FROM crsp_daily
        WHERE permno IN ({placeholders})
          AND observed_at::DATE <= ?
          AND available_at IS NOT NULL
        """,
        [*ordered_permnos, end_date],
    ).fetchone()[0]
    if as_of_value is None:
        raise ValueError("no point-in-time CRSP cutoff exists for the requested period")
    as_of = _utc(as_of_value)
    raw_rows = connection.execute(
        f"""
        SELECT observed_at::DATE, permno, total_return, available_at::VARCHAR
        FROM crsp_daily
        WHERE permno IN ({placeholders})
          AND observed_at::DATE BETWEEN ? AND ?
          AND available_at <= ?
        ORDER BY observed_at, permno
        """,
        [*ordered_permnos, start_date, end_date, as_of],
    ).fetchall()
    rows = tuple(
        DetectorMarketRow(
            permno=int(permno),
            observed_at=_utc(observed_at),
            available_at=_utc(available_at),
            total_return=Decimal(str(total_return)),
        )
        for observed_at, permno, total_return, available_at in raw_rows
        if total_return is not None and available_at is not None
    )
    value = {
        "dataset_snapshot_id": dataset_snapshot_id,
        "requested_start": start_date,
        "requested_end": end_date,
        "as_of": as_of,
        "requested_permnos": ordered_permnos,
        "source_row_count": len(raw_rows),
        "missing_return_count": len(raw_rows) - len(rows),
        "rows": rows,
    }
    return DetectorMarketBatch(**value, batch_digest=sha256_digest(value))
