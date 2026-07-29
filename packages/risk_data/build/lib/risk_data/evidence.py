"""Deterministic evidence bundles for synthetic ingestion and anomaly review."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from risk_domain.digests import sha256_digest

from .contracts import FIXTURE_SEED, QuerySpec, SYNTHETIC_LABEL, _utc
from .pipeline import FIXTURE_CREATED_AT, resolve_data_root
from .serialization import manifest_json


EVIDENCE_BUNDLE_PATH = Path("manifests/evidence-bundle.json")


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _generated_at(value: datetime | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return _utc(value)


def _load_artifact(root: Path, relative_path: str) -> dict[str, Any]:
    path = root / relative_path
    if not path.is_file():
        raise FileNotFoundError(f"required ingestion artifact is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _alpha_anomaly_input(root: Path) -> dict[str, Any]:
    prices_path = root / "market" / "prices.parquet"
    if not prices_path.is_file():
        raise FileNotFoundError(f"required market dataset is missing: {prices_path}")
    alpha = sorted((row for row in pq.read_table(prices_path).to_pylist() if row["symbol"] == "ALPHA"), key=lambda row: row["observed_at"])[-2:]
    if len(alpha) != 2:
        raise ValueError("ALPHA anomaly evidence requires two observations")
    observations = [{"instrument_id": row["instrument_id"], "symbol": row["symbol"], "observed_at": row["observed_at"], "price": row["price"], "currency": row["currency"], "synthetic": row["synthetic"], "synthetic_label": row["synthetic_label"], "quality_flags": row["quality_flags"]} for row in alpha]
    daily_return = Decimal(alpha[-1]["price"]) / Decimal(alpha[-2]["price"]) - Decimal("1")
    return {"anomaly_id": "synthetic-alpha-daily-return-20260717", "instrument_id": "instrument-alpha", "anomaly_type": "daily_return", "daily_return": daily_return, "input_observations": observations, "quality_flags": ["complete"], "news_events": [{"event_id": "synthetic-news-alpha-prototype-demo-20260717", "instrument_id": "instrument-alpha", "occurred_at": datetime(2026, 7, 17, 9, 0, tzinfo=UTC), "headline": "Synthetic test event: ALPHA prototype demonstration", "summary": "Fictional scenario created solely for Day 0 evidence tests; it is not a news article or market report.", "synthetic": True, "synthetic_label": SYNTHETIC_LABEL, "fixture_seed": FIXTURE_SEED}]}


def build_evidence_bundle(output_root: Path | str | None, generated_at: datetime | str) -> dict[str, Any]:
    """Build, without writing, a deterministic evidence object for reviewed inputs."""
    root = resolve_data_root(output_root)
    ingestion_run = _load_artifact(root, "manifests/ingestion-run.json")
    dataset_snapshot = _load_artifact(root, "manifests/dataset-snapshot.json")
    source_files = []
    for file_entry in dataset_snapshot["files"]:
        path = root / file_entry["path"]
        if not path.is_file():
            raise FileNotFoundError(f"snapshot source file is missing: {path}")
        actual_digest = _sha256_file(path)
        if actual_digest != file_entry["digest"]:
            raise ValueError(f"snapshot source digest does not verify: {file_entry['path']}")
        source_files.append({"path": file_entry["path"], "digest": actual_digest, "exists": True})
    query = QuerySpec(dataset="market", instrument_ids=("instrument-alpha",), start_at=datetime(2026, 7, 16, tzinfo=UTC), end_at=datetime(2026, 7, 17, tzinfo=UTC), include_duplicate_candidates=False)
    bundle: dict[str, Any] = {"bundle_type": "synthetic-ingestion-anomaly-evidence", "generated_at": _generated_at(generated_at), "synthetic_disclosure": {"synthetic": True, "synthetic_label": SYNTHETIC_LABEL, "fixture_seed": FIXTURE_SEED, "statement": "All observations and the associated ALPHA event are fictional synthetic test data, not provider, market, or news data."}, "query_specification": query, "query_specification_digest": sha256_digest(query), "ingestion_run": ingestion_run, "dataset_snapshot": dataset_snapshot, "source_file_digests": source_files, "validation_summary": ingestion_run["evidence"], "anomaly": _alpha_anomaly_input(root)}
    bundle["digest"] = sha256_digest(bundle)
    return bundle


def export_evidence(output_root: Path | str | None, generated_at: datetime | str) -> Path:
    """Write one immutable evidence bundle beneath the existing external data root."""
    root = resolve_data_root(output_root)
    output_path = root / EVIDENCE_BUNDLE_PATH
    if output_path.exists():
        raise FileExistsError(f"immutable evidence bundle already exists: {output_path}")
    bundle = build_evidence_bundle(root, generated_at)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(manifest_json(bundle), encoding="utf-8")
    return output_path
