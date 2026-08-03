from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq
import pytest
import yaml

from portfolio_risk_thesis.adapters import HistoricalEventDataAdapter, HistoricalMarketDataAdapter
from portfolio_risk_thesis.cli import _external_output_root
from portfolio_risk_thesis.manifests import ManifestError, load_dataset_manifest, load_yaml


def adapters(example_root: Path):  # type: ignore[no-untyped-def]
    market, events = load_dataset_manifest(example_root / "data" / "dataset_manifest.yaml")
    return HistoricalMarketDataAdapter(market), HistoricalEventDataAdapter(events)


def test_manifest_digest_validation_and_metadata(example_root: Path, tmp_path: Path) -> None:
    manifest_path = example_root / "data" / "dataset_manifest.yaml"
    market, events = load_dataset_manifest(manifest_path)
    assert market.synthetic and events.synthetic
    assert market.row_counts == (1040,)
    broken = load_yaml(manifest_path)
    broken["market"]["file"] = str(Path(market.source_paths[0]))
    broken["events"]["file"] = str(Path(events.source_paths[0]))
    broken["market"]["digest"] = "sha256:" + "0" * 64
    broken_path = tmp_path / "dataset.yaml"
    broken_path.write_text(yaml.safe_dump(broken), encoding="utf-8")
    with pytest.raises(ManifestError, match="digest mismatch"):
        load_dataset_manifest(broken_path)


def test_fixture_shape_content_and_reproducibility(example_root: Path, fixture_root: Path, tmp_path: Path) -> None:
    market = pq.read_table(fixture_root / "market.parquet").to_pylist()
    events = pq.read_table(fixture_root / "events.parquet").to_pylist()
    assert len({row["instrument_id"] for row in market}) == 8
    assert {row["instrument_id"]: 0 for row in market}
    counts = {instrument_id: sum(row["instrument_id"] == instrument_id for row in market) for instrument_id in {row["instrument_id"] for row in market}}
    assert set(counts.values()) == {130}
    assert len(events) == 24
    for row in market + events:
        assert row["fixture_revision"] == "2026-07-28.2"
        assert row["content_digest"].startswith("sha256:")
        assert row["units"]
        assert row["quality_state"] in {"complete", "warning"}
        assert row["limitations"]
    forbidden = {"apple", "microsoft", "amazon", "tesla", "nvidia", "google", "meta", "jpmorgan"}
    payload = json.dumps(market + events, default=str).lower()
    assert not any(name in payload for name in forbidden)
    subprocess.run(
        [
            str(Path(__import__("sys").executable)),
            str(example_root / "scripts" / "generate_fixture.py"),
            "--output",
            str(tmp_path / "regenerated"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    for name in ("market.parquet", "events.parquet", "fixture-manifest.json"):
        assert (tmp_path / "regenerated" / name).read_bytes() == (fixture_root / name).read_bytes()


def test_market_filtering_latest_and_available_at_boundary(example_root: Path) -> None:
    market, _ = adapters(example_root)
    instrument = ("instrument-aurora-tech",)
    boundary = datetime(2024, 1, 2, 16, 30, tzinfo=UTC)
    assert market.latest_observations_as_of(boundary, instrument)[0].available_at == boundary
    assert market.latest_observations_as_of(datetime(2024, 1, 2, 16, 29, tzinfo=UTC), instrument) == ()
    rows = market.observations(
        datetime(2024, 1, 2, 0, tzinfo=UTC),
        datetime(2024, 1, 3, 23, tzinfo=UTC),
        instrument,
    )
    assert len(rows) == 2
    assert rows == tuple(sorted(rows, key=lambda row: (row.timestamp, row.available_at, row.instrument_id)))


def test_event_exact_filtering_future_exclusion_and_order(example_root: Path) -> None:
    _, events = adapters(example_root)
    selected = ("instrument-pantry-staples",)
    before = events.events_as_of(datetime(2024, 6, 27, 18, tzinfo=UTC), selected)
    after = events.events_as_of(datetime(2024, 6, 28, 18, tzinfo=UTC), selected)
    assert "fictional-event-021" not in {row.event_id for row in before}
    assert "fictional-event-021" in {row.event_id for row in after}
    assert after == tuple(sorted(after, key=lambda row: (row.available_at, row.event_time, row.event_id)))


def test_generated_outputs_must_be_beneath_configured_thesis_root(
    example_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = tmp_path / "thesis-data"
    monkeypatch.setenv("THESIS_DATA_ROOT", str(configured))
    assert _external_output_root(str(configured)) == configured
    assert _external_output_root(str(configured / "replays")) == configured / "replays"
    with pytest.raises(argparse.ArgumentTypeError, match="beneath THESIS_DATA_ROOT"):
        _external_output_root(str(tmp_path / "unrelated"))

    monkeypatch.setenv("THESIS_DATA_ROOT", str(example_root / "generated"))
    with pytest.raises(argparse.ArgumentTypeError, match="outside Git"):
        _external_output_root(str(example_root / "generated"))


def test_output_write_requires_thesis_data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("THESIS_DATA_ROOT", raising=False)
    with pytest.raises(argparse.ArgumentTypeError, match="must be configured"):
        _external_output_root(str(tmp_path / "replay"))
