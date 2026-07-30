"""Reviewed point-in-time curated-event helpers; never a live-news connector."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from pydantic import ValidationError

from .contracts import EligibleAgentEvent, canonical, digest

EVENT_FIELDS = tuple(EligibleAgentEvent.model_fields)


def _load(path: Path) -> list[dict[str, object]]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    records = document.get("events", document) if isinstance(document, dict) else document
    if not isinstance(records, list):
        raise ValueError("event manifest must contain an events list")
    if any(
        any(
            marker in str(key).casefold()
            for marker in ("outcome", "retrospective", "future_label")
        )
        for record in records
        if isinstance(record, dict)
        for key in record
    ):
        raise ValueError("outcome and retrospective labels are prohibited from Day 3")
    return records


def validate_event_manifest(path: Path | str) -> tuple[EligibleAgentEvent, ...]:
    try:
        events = tuple(EligibleAgentEvent.model_validate(record) for record in _load(Path(path)))
    except (OSError, ValidationError, yaml.YAMLError, TypeError, ValueError) as error:
        raise ValueError(f"invalid reviewed event manifest: {error}") from error
    ids = [event.event_id for event in events]
    if len(ids) != len(set(ids)):
        raise ValueError("event IDs must be unique")
    return tuple(sorted(events, key=lambda event: (event.available_at, event.event_id)))


def materialize_events(manifest: Path | str, output: Path | str) -> Path:
    target = Path(output)
    if not target.is_absolute():
        raise ValueError("event dataset output must be an explicit absolute path")
    events = validate_event_manifest(manifest)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if target.exists():
        if read_events(target) == events:
            return target
        raise ValueError("immutable event dataset already exists with different content")
    payload = [canonical(event) for event in events]
    table = pa.Table.from_pylist(payload)
    descriptor, staging_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        dir=target.parent,
    )
    os.close(descriptor)
    staging = Path(staging_name)
    try:
        pq.write_table(table, staging, compression="zstd")
        staging.chmod(0o600)
        staging.rename(target)
    finally:
        if staging.exists():
            staging.unlink()
    return target


def read_events(dataset: Path | str) -> tuple[EligibleAgentEvent, ...]:
    rows = pq.read_table(dataset).to_pylist()
    return tuple(EligibleAgentEvent.model_validate(row) for row in rows)


def eligible_events(events: tuple[EligibleAgentEvent, ...], as_of: datetime) -> tuple[EligibleAgentEvent, ...]:
    return tuple(event for event in events if event.available_at <= as_of)


def initialize_event_template(output: Path | str) -> Path:
    target = Path(output)
    if not target.is_absolute():
        raise ValueError("event template output must be absolute")
    if target.exists():
        raise ValueError("event template already exists")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.write_text(
        yaml.safe_dump({"events": [{
            "event_id": "reviewed-event-001", "event_time": "2024-01-02T15:00:00Z",
            "available_at": "2024-01-02T15:00:00Z", "entity_alias": "entity-001",
            "instrument_aliases": ["position-001"], "title": "Short reviewed title",
            "short_summary": "Short human-authored reviewed summary.", "sentiment": "neutral",
            "relevance": "0.50", "source_reference": "reviewer-source-reference",
            "evidence_digest": digest("reviewed-event-001"), "profile": "private_curated",
            "publication_state": "reviewed", "limitations": ["No outcome labels."],
        }]}, sort_keys=False), encoding="utf-8")
    target.chmod(0o600)
    return target
