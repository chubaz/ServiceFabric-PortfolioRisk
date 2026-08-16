"""Fixed read-only retrospective CRSP path query for the label study."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal

import duckdb
from pydantic import Field, field_validator, model_validator

from risk_domain.digests import sha256_digest

from .research_contracts import ResearchContract


class LabelStudyMarketRow(ResearchContract):
    permno: int = Field(gt=0)
    observed_at: datetime
    available_at: datetime
    total_return: Decimal
    valuation_price: Decimal | None = Field(default=None, gt=0)

    @field_validator("observed_at", "available_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("label-study timestamps must be timezone-aware")
        return value.astimezone(UTC)


class LabelStudyMarketBatch(ResearchContract):
    dataset_snapshot_id: str = Field(min_length=1, max_length=256)
    requested_start: date
    requested_end: date
    retrospective_cutoff: datetime
    requested_permnos: tuple[int, ...] = Field(min_length=1)
    source_row_count: int = Field(ge=0)
    missing_return_count: int = Field(ge=0)
    rows: tuple[LabelStudyMarketRow, ...]
    batch_digest: str

    @field_validator("retrospective_cutoff")
    @classmethod
    def cutoff_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrospective cutoff must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def reconciles(self) -> "LabelStudyMarketBatch":
        if self.requested_end < self.requested_start:
            raise ValueError("label-study end cannot precede start")
        if self.source_row_count != len(self.rows) + self.missing_return_count:
            raise ValueError("label-study rows must reconcile")
        if any(max(item.observed_at, item.available_at) > self.retrospective_cutoff for item in self.rows):
            raise ValueError("label-study rows exceed the retrospective cutoff")
        expected = sha256_digest(self.model_dump(mode="python", exclude={"batch_digest"}))
        if self.batch_digest != expected:
            raise ValueError("label-study batch digest does not match its content")
        return self


def _utc(value: object) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, date):
        result = datetime.combine(value, time.min)
    else:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return result.replace(tzinfo=UTC) if result.tzinfo is None else result.astimezone(UTC)


def query_crsp_label_study_market(
    connection: duckdb.DuckDBPyConnection,
    *,
    dataset_snapshot_id: str,
    permnos: tuple[int, ...],
    start_date: date,
    end_date: date,
) -> LabelStudyMarketBatch:
    """Fetch a bounded retrospective path. Callers cannot inject SQL."""

    ordered = tuple(sorted(set(permnos)))
    if not ordered or any(value <= 0 for value in ordered):
        raise ValueError("at least one positive PERMNO is required")
    if end_date < start_date:
        raise ValueError("label-study end cannot precede start")
    markers = ",".join("?" for _ in ordered)
    raw = connection.execute(
        f"""
        SELECT observed_at::DATE, permno, total_return, valuation_price, available_at::VARCHAR
        FROM crsp_daily
        WHERE permno IN ({markers})
          AND observed_at::DATE BETWEEN ? AND ?
          AND observed_at::DATE <= ?
        ORDER BY observed_at, permno
        """,
        [*ordered, start_date, end_date, end_date],
    ).fetchall()
    rows = tuple(
        LabelStudyMarketRow(
            permno=int(permno), observed_at=_utc(observed), available_at=_utc(available),
            total_return=Decimal(str(total_return)),
            valuation_price=None if price is None else Decimal(str(abs(price))),
        )
        for observed, permno, total_return, price, available in raw
        if total_return is not None and available is not None
    )
    cutoff = max(
        datetime.combine(end_date, time.max, tzinfo=UTC),
        max((item.available_at for item in rows), default=datetime.combine(end_date, time.max, tzinfo=UTC)),
    )
    value = {
        "dataset_snapshot_id": dataset_snapshot_id, "requested_start": start_date,
        "requested_end": end_date, "retrospective_cutoff": cutoff,
        "requested_permnos": ordered, "source_row_count": len(raw),
        "missing_return_count": len(raw) - len(rows), "rows": rows,
    }
    return LabelStudyMarketBatch(**value, batch_digest=sha256_digest(value))
