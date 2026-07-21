"""Evidence-bundle tests for the deterministic synthetic Day 0 data flow."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from risk_data.evidence import build_evidence_bundle, export_evidence
from risk_data.pipeline import ingest_synthetic
from risk_domain.digests import sha256_digest


GENERATED_AT = datetime(2026, 7, 21, 14, 30, tzinfo=UTC)


def test_evidence_bundle_is_deterministic_complete_and_synthetic(tmp_path: Path) -> None:
    output_root = tmp_path / "evidence-data"
    ingest_synthetic(output_root)
    first = build_evidence_bundle(output_root, GENERATED_AT)
    second = build_evidence_bundle(output_root, GENERATED_AT)
    bundle_path = export_evidence(output_root, GENERATED_AT)
    persisted = json.loads(bundle_path.read_text(encoding="utf-8"))

    assert first == second
    assert first["digest"] == second["digest"] == persisted["digest"]
    assert persisted["digest"] == sha256_digest(persisted)
    assert persisted["generated_at"] == "2026-07-21T14:30:00.000000Z"
    assert persisted["query_specification_digest"].startswith("sha256:")
    assert persisted["query_specification_digest"] == sha256_digest(persisted["query_specification"])
    assert persisted["synthetic_disclosure"]["synthetic"] is True
    assert persisted["synthetic_disclosure"]["synthetic_label"] == "synthetic"
    assert persisted["anomaly"]["daily_return"] == "-0.12"
    assert persisted["anomaly"]["quality_flags"] == ["complete"]
    event = persisted["anomaly"]["news_events"][0]
    assert event["synthetic"] is True
    assert "Fictional scenario" in event["summary"]

    for source in persisted["source_file_digests"]:
        path = output_root / source["path"]
        assert path.is_file()
        assert source["digest"] == "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    serialized = json.dumps(persisted, sort_keys=True).lower()
    assert "credential" not in serialized
    assert "endpoint" not in serialized


def test_export_evidence_cli_uses_existing_external_ingestion_root(tmp_path: Path) -> None:
    output_root = tmp_path / "cli-evidence-data"
    ingest_synthetic(output_root)
    repository_root = Path(__file__).resolve().parents[2]
    environment = os.environ | {"PYTHONPATH": os.pathsep.join((str(repository_root), str(repository_root / "packages" / "risk_data" / "src"), str(repository_root / "packages" / "risk_domain" / "src")))}
    completed = subprocess.run([sys.executable, "-m", "risk_data.cli", "export-evidence", "--output", str(output_root), "--generated-at", "2026-07-21T14:30:00Z"], cwd=repository_root, env=environment, check=True, capture_output=True, text=True)

    assert completed.stdout.strip() == str(output_root / "manifests" / "evidence-bundle.json")
    assert (output_root / "manifests" / "evidence-bundle.json").is_file()
