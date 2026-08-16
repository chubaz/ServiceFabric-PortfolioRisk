"""Bounded, read-only inputs for retrospective case-context preparation.

The query returns provider-neutral, minimally derived rows for one exact
security and one exact review window.  It never guesses availability, performs
fuzzy matching, labels evidence, or writes to the licensed database.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Literal

import duckdb
from pydantic import Field, field_validator, model_validator

from risk_domain.digests import sha256_digest

from .research_contracts import ResearchContract


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("context timestamps must be timezone-aware")
    return value.astimezone(UTC)


def _timestamp(value: datetime | str) -> datetime:
    """Parse DuckDB timestamps without requiring its optional ``pytz`` adapter."""

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    return _utc(parsed)


class EventContextInput(ResearchContract):
    source_record_id: str = Field(min_length=1, max_length=240)
    canonical_security_id: str = Field(min_length=1, max_length=120)
    observed_at: datetime
    available_at: datetime
    event_type: str = Field(min_length=1, max_length=160)
    topic: str = Field(min_length=1, max_length=240)
    category: str = Field(min_length=1, max_length=240)
    entity_name: str = Field(min_length=1, max_length=240)
    relevance: Decimal | None = Field(default=None, ge=0, le=1)
    novelty: Decimal | None = Field(default=None, ge=0, le=1)
    sentiment: Decimal | None = Field(default=None, ge=-1, le=1)
    duplicate_record_count: int = Field(ge=1)
    quality_flags: tuple[str, ...] = ()

    _times = field_validator("observed_at", "available_at")(_utc)

    @model_validator(mode="after")
    def temporal_integrity(self) -> "EventContextInput":
        if self.available_at < self.observed_at:
            raise ValueError("event availability cannot precede event time")
        return self


class FundamentalContextInput(ResearchContract):
    source_record_id: str = Field(min_length=1, max_length=240)
    canonical_security_id: str = Field(min_length=1, max_length=120)
    canonical_issuer_id: str = Field(min_length=1, max_length=120)
    observed_at: datetime
    available_at: datetime
    currency: str = Field(min_length=1, max_length=24)
    total_assets: Decimal | None = None
    total_liabilities: Decimal | None = None
    common_equity: Decimal | None = None
    revenue: Decimal | None = None
    net_income: Decimal | None = None
    quality_flags: tuple[str, ...] = ()

    _times = field_validator("observed_at", "available_at")(_utc)

    @model_validator(mode="after")
    def temporal_integrity(self) -> "FundamentalContextInput":
        if self.available_at < self.observed_at:
            raise ValueError("fundamental availability cannot precede observation time")
        return self


class ContextInputBatch(ResearchContract):
    canonical_security_id: str = Field(min_length=1, max_length=120)
    manifestation_time: datetime
    retrospective_cutoff: datetime
    event_window_start: date
    event_window_end: date
    fundamental_window_start: date
    event_rows: tuple[EventContextInput, ...]
    fundamental_rows: tuple[FundamentalContextInput, ...]
    excluded_missing_availability: int = Field(ge=0)
    excluded_temporal_violations: int = Field(ge=0)
    excluded_after_cutoff: int = Field(ge=0)
    source_revisions: tuple[str, ...]
    query_receipts: tuple[Literal[
        "ravenpack-selected-context-v1",
        "compustat-selected-context-v1",
        "context-exclusion-counts-v1",
    ], ...]
    batch_digest: str | None = None

    _times = field_validator("manifestation_time", "retrospective_cutoff")(_utc)

    @model_validator(mode="after")
    def ordered_and_reconciled(self) -> "ContextInputBatch":
        if self.event_window_end < self.event_window_start:
            raise ValueError("event window end cannot precede its start")
        if self.retrospective_cutoff < self.manifestation_time:
            raise ValueError("retrospective cutoff cannot precede manifestation")
        if self.source_revisions != tuple(sorted(set(self.source_revisions))):
            raise ValueError("source revisions must be unique and sorted")
        if self.query_receipts != tuple(dict.fromkeys(self.query_receipts)):
            raise ValueError("query receipts must be unique")
        expected = sha256_digest(self.model_dump(mode="json", exclude={"batch_digest"}))
        if self.batch_digest is not None and self.batch_digest != expected:
            raise ValueError("context input digest does not match canonical content")
        object.__setattr__(self, "batch_digest", expected)
        return self


def query_selected_case_context(
    connection: duckdb.DuckDBPyConnection,
    *,
    permno: int,
    manifestation_time: datetime,
    retrospective_cutoff: datetime,
    event_days_before: int,
    event_days_after: int,
    fundamental_lookback_quarters: int,
) -> ContextInputBatch:
    """Read only the bounded rows needed to prepare one review proposal."""

    if permno <= 0:
        raise ValueError("a positive PERMNO is required")
    manifestation_time = _utc(manifestation_time)
    retrospective_cutoff = _utc(retrospective_cutoff)
    if retrospective_cutoff < manifestation_time:
        raise ValueError("retrospective cutoff cannot precede manifestation")
    event_start = manifestation_time.date() - timedelta(days=event_days_before)
    event_end = min(
        manifestation_time.date() + timedelta(days=event_days_after),
        retrospective_cutoff.date(),
    )
    fundamental_start = manifestation_time.date() - timedelta(days=92 * fundamental_lookback_quarters)

    event_values = connection.execute(
        """
        SELECT coalesce(source_event_id, local_event_id) AS source_record_id,
               min(event_time)::VARCHAR AS observed_at,
               min(available_at)::VARCHAR AS available_at,
               coalesce(nullif(min(event_type), ''), 'Unclassified event') AS event_type,
               coalesce(nullif(min(topic), ''), 'No topic supplied') AS topic,
               coalesce(nullif(min(category), ''), 'Unclassified') AS category,
               coalesce(nullif(min(provider_entity_name), ''), nullif(min(position_name), ''), 'Mapped issuer') AS entity_name,
               max(relevance) AS relevance,
               avg(novelty) AS novelty,
               avg(sentiment) AS sentiment,
               count(*) AS duplicate_record_count,
               min(dataset_revision) AS dataset_revision
        FROM ravenpack_events_linked
        WHERE permno = ?
          AND event_time::DATE BETWEEN ? AND ?
          AND event_time IS NOT NULL
          AND available_at IS NOT NULL
          AND available_at >= event_time
          AND available_at <= ?
        GROUP BY coalesce(source_event_id, local_event_id)
        ORDER BY observed_at, source_record_id
        """,
        [permno, event_start, event_end, retrospective_cutoff],
    ).fetchall()

    fundamental_values = connection.execute(
        """
        SELECT concat(q.gvkey, ':', q.observed_at::VARCHAR, ':', coalesce(q.source_revision, 'unknown')),
               q.gvkey,
               q.observed_at,
               q.available_at::VARCHAR,
               coalesce(nullif(q.currency, ''), 'Unknown'),
               q.total_assets, q.total_liabilities, q.common_equity,
               q.revenue, q.net_income, coalesce(q.source_revision, 'unknown')
        FROM ccm_links l
        JOIN compustat_quarterly q USING (gvkey)
        WHERE l.permno = ?
          AND q.observed_at BETWEEN ? AND ?
          AND q.available_at IS NOT NULL
          AND q.available_at::DATE >= q.observed_at
          AND q.available_at <= ?
          AND l.link_start <= q.observed_at
          AND (l.link_end IS NULL OR l.link_end >= q.observed_at)
        ORDER BY q.available_at, q.gvkey, q.observed_at
        """,
        [permno, fundamental_start, manifestation_time.date(), retrospective_cutoff],
    ).fetchall()

    exclusions = connection.execute(
        """
        WITH source_rows AS (
          SELECT event_time AS observed_at, available_at
          FROM ravenpack_events_linked
          WHERE permno = ? AND event_time::DATE BETWEEN ? AND ?
          UNION ALL
          SELECT q.observed_at::TIMESTAMPTZ, q.available_at
          FROM ccm_links l JOIN compustat_quarterly q USING (gvkey)
          WHERE l.permno = ? AND q.observed_at BETWEEN ? AND ?
            AND l.link_start <= q.observed_at
            AND (l.link_end IS NULL OR l.link_end >= q.observed_at)
        )
        SELECT count(*) FILTER (WHERE available_at IS NULL),
               count(*) FILTER (WHERE available_at IS NOT NULL AND available_at < observed_at),
               count(*) FILTER (WHERE available_at > ?)
        FROM source_rows
        """,
        [permno, event_start, event_end, permno, fundamental_start, manifestation_time.date(), retrospective_cutoff],
    ).fetchone()

    event_rows = tuple(
        EventContextInput(
            source_record_id=str(row[0]), canonical_security_id=f"permno:{permno}",
            observed_at=_timestamp(row[1]), available_at=_timestamp(row[2]), event_type=str(row[3]),
            topic=str(row[4]), category=str(row[5]), entity_name=str(row[6]),
            relevance=None if row[7] is None else Decimal(str(row[7])),
            novelty=None if row[8] is None else Decimal(str(row[8])),
            sentiment=None if row[9] is None else Decimal(str(row[9])),
            duplicate_record_count=int(row[10]),
            quality_flags=tuple(sorted({
                "provider_lifecycle_unverified",
                *("duplicate_provider_records" for _ in [0] if int(row[10]) > 1),
            })),
        )
        for row in event_values
    )
    fundamental_rows = tuple(
        FundamentalContextInput(
            source_record_id=str(row[0]), canonical_security_id=f"permno:{permno}",
            canonical_issuer_id=f"gvkey:{row[1]}",
            observed_at=datetime.combine(row[2], datetime.min.time(), tzinfo=UTC),
            available_at=_timestamp(row[3]), currency=str(row[4]), total_assets=row[5],
            total_liabilities=row[6], common_equity=row[7], revenue=row[8],
            net_income=row[9], quality_flags=(),
        )
        for row in fundamental_values
    )
    revisions = tuple(sorted({
        *(str(row[11]) for row in event_values if row[11]),
        *(str(row[10]) for row in fundamental_values if row[10]),
    }))
    raw = dict(
        canonical_security_id=f"permno:{permno}", manifestation_time=manifestation_time,
        retrospective_cutoff=retrospective_cutoff, event_window_start=event_start,
        event_window_end=event_end, fundamental_window_start=fundamental_start,
        event_rows=event_rows, fundamental_rows=fundamental_rows,
        excluded_missing_availability=int(exclusions[0]),
        excluded_temporal_violations=int(exclusions[1]),
        excluded_after_cutoff=int(exclusions[2]), source_revisions=revisions,
        query_receipts=("ravenpack-selected-context-v1", "compustat-selected-context-v1", "context-exclusion-counts-v1"),
    )
    return ContextInputBatch(**raw)
