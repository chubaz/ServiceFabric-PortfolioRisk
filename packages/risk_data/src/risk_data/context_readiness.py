"""Read-only qualification of sources needed by later case-context work.

This module deliberately does not retrieve event rows, calculate relationships, or
attach evidence to a label.  It answers the narrower question: are the governed
sources and point-in-time fields present enough for a later, separately authorised
association task?
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

import duckdb
from pydantic import Field, field_validator, model_validator

from risk_domain.digests import sha256_digest

from .research_contracts import ResearchContract


class SourceQualification(ResearchContract):
    source: Literal["ravenpack_events", "compustat_fundamentals"]
    state: Literal["ready", "partial", "blocked"]
    provider_id: str
    dataset_revision: str
    publication_restriction: str
    requested_security_count: int = Field(ge=0)
    covered_security_count: int = Field(ge=0)
    row_count: int = Field(ge=0)
    eligible_row_count: int = Field(ge=0)
    missing_observation_time_count: int = Field(ge=0)
    missing_available_at_count: int = Field(ge=0)
    temporal_order_violation_count: int = Field(ge=0)
    required_fields_present: tuple[str, ...]
    missing_semantics: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class ContextPreparationStep(ResearchContract):
    key: str
    label: str
    state: Literal["ready", "blocked", "deferred"]
    depends_on: tuple[str, ...] = ()
    reason: str


class ContextSourceReadiness(ResearchContract):
    batch_id: str
    portfolio_id: str
    period_start: date
    period_end: date
    retrospective_cutoff: datetime
    checked_at: datetime
    sources: tuple[SourceQualification, ...]
    preparation_steps: tuple[ContextPreparationStep, ...]
    association_execution: Literal["not_authorized"] = "not_authorized"
    association_count: Literal[0] = 0
    readiness: Literal["ready_for_authorisation", "not_ready"]
    digest: str

    @field_validator("retrospective_cutoff", "checked_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("context-readiness timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def proves_no_association(self) -> "ContextSourceReadiness":
        if self.association_count != 0 or self.association_execution != "not_authorized":
            raise ValueError("source qualification cannot perform associations")
        expected = sha256_digest(self.model_dump(mode="python", exclude={"digest"}))
        if self.digest != expected:
            raise ValueError("context-readiness digest does not match its content")
        return self


def _columns(connection: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    return {str(row[0]) for row in connection.execute(f"DESCRIBE {table}").fetchall()}


def qualify_case_context_sources(
    connection: duckdb.DuckDBPyConnection,
    *,
    batch_id: str,
    portfolio_id: str,
    permnos: tuple[int, ...],
    start_date: date,
    end_date: date,
    retrospective_cutoff: datetime,
    checked_at: datetime,
) -> ContextSourceReadiness:
    """Profile only counts, schemas and temporal integrity using fixed SQL."""

    ordered = tuple(sorted(set(permnos)))
    if not ordered or any(value <= 0 for value in ordered):
        raise ValueError("at least one positive PERMNO is required")
    if end_date < start_date:
        raise ValueError("context-readiness end cannot precede start")
    checked_at = checked_at.astimezone(UTC)
    retrospective_cutoff = retrospective_cutoff.astimezone(UTC)
    markers = ",".join("?" for _ in ordered)

    event_columns = _columns(connection, "ravenpack_events_linked")
    event_required = {"provider_id", "dataset_revision", "event_time", "available_at", "permno", "local_event_id"}
    event_row = connection.execute(
        f"""
        SELECT count(*),
               count(*) FILTER (WHERE available_at <= ?),
               count(DISTINCT permno),
               count(*) FILTER (WHERE event_time IS NULL),
               count(*) FILTER (WHERE available_at IS NULL),
               count(*) FILTER (WHERE event_time IS NOT NULL AND available_at IS NOT NULL AND available_at < event_time),
               coalesce(min(provider_id), 'ravenpack'),
               coalesce(min(dataset_revision), 'unknown')
        FROM ravenpack_events_linked
        WHERE permno IN ({markers})
          AND event_time::DATE BETWEEN ? AND ?
        """,
        [retrospective_cutoff, *ordered, start_date, end_date],
    ).fetchone()
    status = connection.execute(
        """SELECT publication_restriction FROM ravenpack_integration_status
           WHERE provider_id = 'ravenpack' LIMIT 1"""
    ).fetchone()
    event_missing_semantics = tuple(
        item for item in ("amendment_state", "supersedes_event_id", "retraction_state")
        if item not in event_columns
    )
    event_state: Literal["ready", "partial", "blocked"] = "ready"
    if not event_required.issubset(event_columns) or int(event_row[0]) == 0:
        event_state = "blocked"
    elif event_missing_semantics or int(event_row[4]) or int(event_row[5]):
        event_state = "partial"
    event = SourceQualification(
        source="ravenpack_events", state=event_state, provider_id=str(event_row[6]),
        dataset_revision=str(event_row[7]), publication_restriction=str(status[0] if status else "private_local"),
        requested_security_count=len(ordered), covered_security_count=int(event_row[2]),
        row_count=int(event_row[0]), eligible_row_count=int(event_row[1]),
        missing_observation_time_count=int(event_row[3]), missing_available_at_count=int(event_row[4]),
        temporal_order_violation_count=int(event_row[5]),
        required_fields_present=tuple(sorted(event_required & event_columns)),
        missing_semantics=event_missing_semantics,
        limitations=tuple(
            item for item in (
                "Event amendments and retractions require an explicit provider mapping before association."
                if event_missing_semantics else None,
                f"RavenPack has mapped coverage for {int(event_row[2])} of {len(ordered)} requested securities."
                if int(event_row[2]) < len(ordered) else None,
            ) if item is not None
        ),
    )

    fundamental_columns = _columns(connection, "compustat_quarterly")
    fundamental_required = {"gvkey", "observed_at", "available_at", "source_revision"}
    fundamental_row = connection.execute(
        f"""
        WITH linked AS (
          SELECT DISTINCT l.permno, l.gvkey
          FROM ccm_links l
          WHERE l.permno IN ({markers})
            AND l.link_start <= ?
            AND (l.link_end IS NULL OR l.link_end >= ?)
        )
        SELECT count(*),
               count(*) FILTER (WHERE q.available_at <= ?),
               count(DISTINCT linked.permno),
               count(*) FILTER (WHERE q.observed_at IS NULL),
               count(*) FILTER (WHERE q.available_at IS NULL),
               count(*) FILTER (WHERE q.observed_at IS NOT NULL AND q.available_at IS NOT NULL AND q.available_at::DATE < q.observed_at),
               coalesce(min(q.source_revision), 'unknown')
        FROM linked JOIN compustat_quarterly q USING (gvkey)
        WHERE q.observed_at BETWEEN ? AND ?
        """,
        [*ordered, end_date, start_date, retrospective_cutoff, start_date, end_date],
    ).fetchone()
    fundamental_state: Literal["ready", "partial", "blocked"] = "ready"
    if not fundamental_required.issubset(fundamental_columns) or int(fundamental_row[0]) == 0:
        fundamental_state = "blocked"
    elif int(fundamental_row[4]) or int(fundamental_row[5]):
        fundamental_state = "partial"
    fundamental = SourceQualification(
        source="compustat_fundamentals", state=fundamental_state, provider_id="compustat",
        dataset_revision=str(fundamental_row[6]), publication_restriction="private_local",
        requested_security_count=len(ordered), covered_security_count=int(fundamental_row[2]),
        row_count=int(fundamental_row[0]), eligible_row_count=int(fundamental_row[1]),
        missing_observation_time_count=int(fundamental_row[3]), missing_available_at_count=int(fundamental_row[4]),
        temporal_order_violation_count=int(fundamental_row[5]),
        required_fields_present=tuple(sorted(fundamental_required & fundamental_columns)),
        limitations=tuple(
            item for item in (
                f"Compustat has mapped coverage for {int(fundamental_row[2])} of {len(ordered)} requested securities."
                if int(fundamental_row[2]) < len(ordered) else None,
                f"{int(fundamental_row[4])} Compustat rows have no qualified availability timestamp."
                if int(fundamental_row[4]) else None,
            ) if item is not None
        ),
    )

    source_ready = all(item.state != "blocked" for item in (event, fundamental))
    steps = (
        ContextPreparationStep(key="qualify_sources", label="Qualify source contracts", state="ready" if source_ready else "blocked", reason="Schema, rights and bounded coverage are profiled without reading evidence content."),
        ContextPreparationStep(key="qualify_time", label="Qualify point-in-time fields", state="ready" if all(not item.missing_available_at_count and not item.temporal_order_violation_count for item in (event, fundamental)) else "blocked", depends_on=("qualify_sources",), reason="Observation and availability time remain separate."),
        ContextPreparationStep(key="map_entities", label="Qualify security mappings", state="ready" if all(item.covered_security_count > 0 for item in (event, fundamental)) else "blocked", depends_on=("qualify_sources",), reason="Coverage is counted; no record is attached to a signal."),
        ContextPreparationStep(key="retrieve_context", label="Retrieve bounded context", state="deferred", depends_on=("qualify_time", "map_entities"), reason="Requires a later explicit association authorisation."),
        ContextPreparationStep(key="propose_associations", label="Propose evidence associations", state="deferred", depends_on=("retrieve_context",), reason="Not run in this development slice."),
        ContextPreparationStep(key="build_controls", label="Prepare controls and counter-evidence", state="deferred", depends_on=("propose_associations",), reason="Not run until a case design requires it."),
    )
    raw = dict(batch_id=batch_id, portfolio_id=portfolio_id, period_start=start_date,
               period_end=end_date, retrospective_cutoff=retrospective_cutoff, checked_at=checked_at,
               sources=(event, fundamental), preparation_steps=steps,
               association_execution="not_authorized", association_count=0,
               readiness="ready_for_authorisation" if source_ready and all(step.state != "blocked" for step in steps[:3]) else "not_ready")
    return ContextSourceReadiness(**raw, digest=sha256_digest(raw))
