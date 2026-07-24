"""Final deterministic journey for the Day 2–3 Phase 1 local data plane."""

from __future__ import annotations

import hashlib
import inspect
import json
import socket
from pathlib import Path

import duckdb
import pyarrow.parquet as pq
import pytest
from risk_data import ResearchDataPlane, fixed_query_manifests

from scripts.day23.run_phase1_demo import (
    ARTIFACT_NAMES,
    REQUIRED_CURATED_VIEWS,
    execute_phase1_journey,
    write_phase1_artifacts,
)


def test_d23_phase1_data_plane_journey(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "external-local-research-data"

    def prohibit_network(*args: object, **kwargs: object) -> object:
        raise AssertionError("external network access attempted")

    monkeypatch.setattr(socket, "socket", prohibit_network)
    result = execute_phase1_journey(data_root)
    paths = write_phase1_artifacts(result)

    assert result["effects"] == ()
    assert set(paths) == set(ARTIFACT_NAMES)
    assert all(path.parent == data_root / "day23-phase1" for path in paths.values())
    assert all(path.is_file() for path in paths.values())

    payloads = {
        key: json.loads(path.read_text(encoding="utf-8"))
        for key, path in paths.items()
    }
    assert all(payload["effects"] == [] for payload in payloads.values())

    previews = payloads["import_previews"]["previews"]
    assert [item["dataset_kind"] for item in previews] == [
        "daily_market",
        "fundamentals_annual",
        "identifier_crosswalk",
    ]
    assert all(item["accepted_row_count"] == item["row_count"] for item in previews)
    assert all(item["network_enabled"] is False for item in previews)
    assert payloads["import_confirmations"]["confirmation_count"] == 3
    assert all(
        item["created"]
        for item in payloads["import_confirmations"]["explicit_confirmations"]
    )

    snapshots = payloads["dataset_snapshots"]
    assert snapshots["immutable"] is True
    assert len(snapshots["snapshots"]) == 3
    assert REQUIRED_CURATED_VIEWS <= set(snapshots["latest_curated_views"])
    for relative in snapshots["normalized_parquet_paths"]:
        path = data_root / "day23-phase1" / relative
        assert path.suffix == ".parquet" and path.is_file()
        assert pq.read_table(path).num_rows > 0
    for relative in snapshots["curated_duckdb_paths"]:
        path = data_root / "day23-phase1" / relative
        assert path.suffix == ".duckdb" and path.is_file()
    latest_curated = data_root / "day23-phase1" / snapshots["latest_curated_path"]
    with duckdb.connect(str(latest_curated), read_only=True) as connection:
        views = {
            row[0]
            for row in connection.execute(
                "SELECT table_name FROM information_schema.views WHERE table_schema = 'main'"
            ).fetchall()
        }
    assert REQUIRED_CURATED_VIEWS <= views

    quality = payloads["quality_reports"]
    assert quality["all_non_blocking"] is True
    assert {report["dataset_id"] for report in quality["reports"]} == {
        "synthetic-crsp-like-daily",
        "synthetic-compustat-like-annual",
        "synthetic-crsp-compustat-link",
    }

    crosswalk = payloads["identifier_crosswalk"]
    assert crosswalk["ticker_matching_used"] is False
    assert crosswalk["guessed_matches"] == []
    assert crosswalk["crosswalk"]["records"]
    for record in crosswalk["crosswalk"]["records"]:
        assert record["source_identifier"]["identifier_type"] == "gvkey"
        assert record["target_identifier"]["identifier_type"] == "permno"
        assert record["effective_from"]
        assert record["open_ended"] is (record["effective_to"] is None)

    queries = payloads["fixed_query_results"]
    expected_manifest_ids = {item.manifest_id for item in fixed_query_manifests()}
    assert {item["manifest_id"] for item in queries["results"]} == expected_manifest_ids
    assert queries["arbitrary_sql_available"] is False
    assert len(queries["arbitrary_sql_rejections"]) == 2
    assert not hasattr(ResearchDataPlane, "execute_sql")
    assert "execute_sql" not in inspect.getsource(ResearchDataPlane)

    point_in_time = payloads["point_in_time_proof"]
    assert point_in_time["rule"] == "available_at <= as_of"
    assert point_in_time["no_look_ahead"] is True
    assert [row["gvkey"] for row in point_in_time["before"]["rows"]] == ["990001"]
    assert [row["gvkey"] for row in point_in_time["after"]["rows"]] == [
        "990001",
        "990002",
    ]
    assert point_in_time["excluded_before_as_of"]["gvkey"] == "990002"

    register = payloads["provider_register"]
    assert register["external_network_providers_disabled"] is True
    external = {
        item["provider_id"]: item
        for item in register["providers"]
        if item["provider_id"] in register["external_provider_ids"]
    }
    assert set(external) == {"wrds", "crsp", "compustat", "ravenpack", "accern", "bloomberg"}
    assert all(
        not item["enabled"] and item["access_state"] == "unavailable"
        for item in external.values()
    )

    manifest = payloads["evidence_manifest"]
    assert {item["path"] for item in manifest["artifacts"]} == {
        name for key, name in ARTIFACT_NAMES.items() if key != "evidence_manifest"
    }
    for item in manifest["artifacts"]:
        artifact = paths["evidence_manifest"].parent / item["path"]
        assert item["digest"] == "sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest()

    first_run = {key: path.read_bytes() for key, path in paths.items()}
    repeated = write_phase1_artifacts(execute_phase1_journey(data_root))
    assert {key: path.read_bytes() for key, path in repeated.items()} == first_run
