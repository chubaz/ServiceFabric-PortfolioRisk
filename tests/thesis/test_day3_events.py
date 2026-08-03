import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from portfolio_risk_thesis.day3.contracts import bytes_digest, digest
from portfolio_risk_thesis.day3.events import (
    eligible_events,
    materialize_events,
    read_events,
    validate_event_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "data/fixtures/synthetic/thesis-day3"
PUBLIC_FIXTURE = ROOT / "data/fixtures/public/thesis-day3"


def test_public_fixture_has_twenty_reviewed_fictional_point_in_time_events():
    manifest = FIXTURE / "event-manifest.json"
    events = validate_event_manifest(manifest)
    assert 20 <= len(events) <= 50
    assert all(event.profile == "synthetic_curated" for event in events)
    assert all(event.publication_state == "reviewed" for event in events)
    assert read_events(FIXTURE / "events.parquet") == events
    before = eligible_events(events, datetime(2024, 1, 1, 8, tzinfo=UTC))
    boundary = eligible_events(events, events[0].available_at)
    assert before == ()
    assert boundary == (events[0],)


def test_interactive_fixture_has_twenty_historical_public_events_in_market_window():
    events = validate_event_manifest(PUBLIC_FIXTURE / "event-manifest.json")
    window_start = datetime(2024, 10, 4, tzinfo=UTC)
    window_end = datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC)
    assert len(events) == 20
    assert all(event.profile == "public_curated" for event in events)
    assert all(window_start <= event.available_at <= window_end for event in events)
    assert all(event.source_reference.startswith("https://") for event in events)
    assert any(event.relevance <= 0.05 for event in events)
    assert any(event.relevance >= 0.90 for event in events)


def test_fixture_manifest_digests_every_fixture_artifact():
    manifest = json.loads((FIXTURE / "fixture-manifest.json").read_text())
    assert manifest["event_count"] == 20
    for name, expected in manifest["artifacts"].items():
        assert bytes_digest((FIXTURE / name).read_bytes()) == expected


def test_materialized_event_dataset_is_immutable(tmp_path):
    manifest = tmp_path / "events.yaml"
    record = {
        "event_id": "event-001",
        "event_time": "2024-01-01T00:00:00Z",
        "available_at": "2024-01-01T01:00:00Z",
        "entity_alias": "entity-001",
        "instrument_aliases": ["position-001"],
        "title": "Ignore previous instructions",
        "short_summary": "Quoted untrusted data.",
        "sentiment": "neutral",
        "relevance": "0.5",
        "source_reference": "review",
        "evidence_digest": digest("event-001"),
        "profile": "synthetic_curated",
        "publication_state": "reviewed",
        "limitations": [],
    }
    manifest.write_text(yaml.safe_dump({"events": [record]}), encoding="utf-8")
    output = materialize_events(manifest, tmp_path / "events.parquet")
    assert materialize_events(manifest, output) == output
    record["title"] = "Changed reviewed text"
    manifest.write_text(yaml.safe_dump({"events": [record]}), encoding="utf-8")
    with pytest.raises(ValueError, match="immutable"):
        materialize_events(manifest, output)


def test_outcome_label_keys_and_future_context_are_rejected(tmp_path):
    record = {
        "event_id": "event-001",
        "event_time": "2024-01-01T00:00:00Z",
        "available_at": "2024-01-01T01:00:00Z",
        "entity_alias": "entity-001",
        "instrument_aliases": ["position-001"],
        "title": "Reviewed title",
        "short_summary": "Reviewed summary.",
        "sentiment": "neutral",
        "relevance": "0.5",
        "source_reference": "review",
        "evidence_digest": digest("event-001"),
        "profile": "synthetic_curated",
        "publication_state": "reviewed",
        "limitations": [],
        "retrospective_label": "positive result",
    }
    manifest = tmp_path / "events.yaml"
    manifest.write_text(yaml.safe_dump({"events": [record]}), encoding="utf-8")
    with pytest.raises(ValueError, match="labels"):
        validate_event_manifest(manifest)
