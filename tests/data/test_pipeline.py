"""Integration tests for the filesystem-backed deterministic synthetic pipeline."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import duckdb
import pyarrow.parquet as pq
import pytest

from risk_data.pipeline import ingest_synthetic


def test_pipeline_materializes_parquet_duckdb_views_and_immutable_manifests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output_root = tmp_path / "portfolio-risk-data"
    monkeypatch.setenv("PORTFOLIO_RISK_DATA_ROOT", str(output_root))
    result = ingest_synthetic()

    market_path = output_root / "market" / "prices.parquet"
    fundamentals_path = output_root / "fundamentals" / "fundamentals.parquet"
    catalog_path = output_root / "catalog" / "day0.duckdb"
    assert {path.relative_to(output_root).as_posix() for path in output_root.rglob("*") if path.is_file()} == {"market/prices.parquet", "fundamentals/fundamentals.parquet", "catalog/day0.duckdb", "manifests/ingestion-run.json", "manifests/dataset-snapshot.json"}

    market = pq.read_table(market_path).to_pylist()
    fundamentals = pq.read_table(fundamentals_path).to_pylist()
    assert len(market) == 15
    assert len(fundamentals) == 6
    assert {row["symbol"] for row in market} == {"ALPHA", "BETA", "GAMMA"}
    assert all(row["synthetic"] and row["synthetic_label"] == "synthetic" for row in market + fundamentals)
    alpha = sorted((row for row in market if row["symbol"] == "ALPHA"), key=lambda row: row["observed_at"])
    assert Decimal(alpha[-1]["price"]) / Decimal(alpha[-2]["price"]) - Decimal("1") == Decimal("-0.12")

    with duckdb.connect(str(catalog_path), read_only=True) as connection:
        assert connection.execute("SELECT count(*) FROM market_prices").fetchone() == (15,)
        assert connection.execute("SELECT count(*) FROM fundamentals").fetchone() == (6,)
        assert connection.execute("SELECT count(*) FROM latest_market_prices").fetchone() == (3,)
        assert connection.execute("SELECT count(*) FROM latest_fundamentals").fetchone() == (6,)

    run_manifest = json.loads(result.ingestion_manifest.read_text(encoding="utf-8"))
    snapshot_manifest = json.loads(result.snapshot_manifest.read_text(encoding="utf-8"))
    assert run_manifest["evidence"].items() >= {"input_row_count": 25, "accepted_row_count": 21, "rejected_row_count": 4, "duplicates": 1, "missing_identifiers": 1, "stale_observations": 1, "missing_values": 1}.items()
    assert run_manifest["evidence"]["minimum_date"].startswith("2026-07-13T")
    assert run_manifest["evidence"]["maximum_date"].startswith("2026-07-17T")
    assert all(value.startswith("sha256:") for value in run_manifest["evidence"]["content_digests"].values())
    assert snapshot_manifest["provenance"] == {"synthetic": True, "synthetic_label": "synthetic", "synthetic_seed": 20260721, "sources": [{"reference": "fixture://day0/20260721", "retrieved_at": "2026-07-21T12:00:00.000000Z", "source_id": "synthetic-fixture", "source_type": "fixture"}]}
    assert result.snapshot.digest.startswith("sha256:")

    with pytest.raises(FileExistsError, match="immutable ingestion artifacts"):
        ingest_synthetic(output_root)


def test_cli_writes_only_to_requested_external_root(tmp_path: Path) -> None:
    output_root = tmp_path / "cli-output"
    repository_root = Path(__file__).resolve().parents[2]
    environment = os.environ | {"PYTHONPATH": os.pathsep.join((str(repository_root), str(repository_root / "packages" / "risk_data" / "src"), str(repository_root / "packages" / "risk_domain" / "src"))), "PORTFOLIO_RISK_DATA_ROOT": str(output_root)}
    completed = subprocess.run([sys.executable, "-m", "risk_data.cli", "ingest-synthetic", "--output", str(output_root)], cwd=repository_root, env=environment, check=True, capture_output=True, text=True)

    assert completed.stdout.strip() == str(output_root / "manifests" / "dataset-snapshot.json")
    assert (output_root / "catalog" / "day0.duckdb").exists()
