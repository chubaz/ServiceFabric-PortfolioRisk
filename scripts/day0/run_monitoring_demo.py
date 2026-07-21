#!/usr/bin/env python3
"""Run the deterministic synthetic Day 0 monitoring journey headlessly."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from risk_agents import DeterministicMonitoringOrchestrator, MonitoringRunRequest
from risk_capabilities import (
    AlertReviewRequest,
    AnomalyDetectionRequest,
    CapabilityRegistry,
    DecisionPoint,
    EvidenceReference,
    ExposureSummaryRequest,
    NewsClassificationRequest,
    PortfolioSnapshotRequest,
    PositionSpecification,
    SyntheticNewsEvent,
)
from risk_data import NormalizedMarketRecord, ingest_synthetic
from risk_data.pipeline import resolve_data_root
from risk_domain import AgentRun, ArtifactReference, CashBalance, DatasetSnapshot
from risk_domain.digests import sha256_digest


AS_OF = datetime(2026, 7, 13, tzinfo=UTC)
RUN_AT = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
CONCENTRATION_LIMIT = Decimal("0.40")
OUTPUT_DIRECTORY = Path("day0-monitoring")
OUTPUT_NAMES = {
    "portfolio_snapshot": "portfolio-snapshot.json",
    "exposure_snapshot": "exposure-snapshot.json",
    "findings": "findings.json",
    "agent_runs": "agent-runs.json",
    "alert_draft": "alert-draft.json",
    "evidence_manifest": "evidence-manifest.json",
}


def _json_value(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")  # type: ignore[union-attr]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return value


def _encoded(value: object) -> bytes:
    return (json.dumps(_json_value(value), indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_stable(path: Path, value: object) -> Path:
    content = _encoded(value)
    if path.exists():
        if path.read_bytes() != content:
            raise FileExistsError(f"immutable Day 0 output differs from existing artifact: {path}")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _dataset_snapshot(root: Path) -> DatasetSnapshot:
    manifest = root / "manifests" / "dataset-snapshot.json"
    if not manifest.exists():
        return ingest_synthetic(root).snapshot
    snapshot = DatasetSnapshot.model_validate_json(manifest.read_text(encoding="utf-8"))
    root_resolved = root.resolve()
    for artifact in snapshot.files:
        path = (root / artifact.path).resolve()
        if root_resolved not in path.parents or not path.is_file():
            raise ValueError(f"dataset snapshot artifact is unavailable: {artifact.path}")
        if path.stat().st_size != artifact.size:
            raise ValueError(f"dataset snapshot artifact size differs: {artifact.path}")
        if _sha256_file(path) != artifact.digest:
            raise ValueError(f"dataset snapshot artifact digest differs: {artifact.path}")
    return snapshot


def _market_records(root: Path) -> tuple[NormalizedMarketRecord, ...]:
    rows = pq.read_table(root / "market" / "prices.parquet").to_pylist()
    return tuple(
        NormalizedMarketRecord(
            instrument_id=row["instrument_id"],
            identifier={
                "identifier_type": row["identifier_type"],
                "value": row["identifier_value"],
            },
            observed_at=row["observed_at"],
            price=Decimal(str(row["price"])),
            currency=row["currency"],
        )
        for row in rows
    )


def execute_monitoring_journey(output_root: Path | str | None = None) -> dict[str, Any]:
    """Execute the complete deterministic journey and return its typed records."""
    root = resolve_data_root(output_root)
    dataset_snapshot = _dataset_snapshot(root)
    observations = _market_records(root)
    portfolio_observations = tuple(
        observation for observation in observations if observation.observed_at <= AS_OF
    )
    evidence = (
        EvidenceReference(
            evidence_id=dataset_snapshot.snapshot_id,
            reference="manifests/dataset-snapshot.json",
            source_type="synthetic-dataset-snapshot",
        ),
    )
    domain_evidence = (
        ArtifactReference(
            artifact_id=dataset_snapshot.snapshot_id,
            digest=dataset_snapshot.digest or sha256_digest(dataset_snapshot),
            media_type="application/json",
            reference="manifests/dataset-snapshot.json",
        ),
    )

    registry = CapabilityRegistry()
    portfolio_result = registry.invoke(
        "portfolio.snapshot.create",
        PortfolioSnapshotRequest(
            snapshot_id="synthetic-day0-portfolio-20260713",
            as_of=AS_OF,
            positions=(
                PositionSpecification(instrument_id="instrument-alpha", quantity=Decimal("200")),
                PositionSpecification(instrument_id="instrument-beta", quantity=Decimal("200")),
                PositionSpecification(instrument_id="instrument-gamma", quantity=Decimal("25")),
            ),
            cash_balances=(CashBalance(currency="USD", amount=Decimal("5000.00")),),
            normalized_observations=portfolio_observations,
            evidence_references=evidence,
        ),
    )
    if portfolio_result.status != "succeeded" or portfolio_result.data is None:
        raise RuntimeError("portfolio snapshot creation failed")
    portfolio_snapshot = portfolio_result.data

    monitoring_request = MonitoringRunRequest(
        portfolio_snapshot=portfolio_snapshot,
        market_request=AnomalyDetectionRequest(
            normalized_observations=observations,
            percentage_threshold=Decimal("0.10"),
            evidence_references=evidence,
        ),
        news_event=SyntheticNewsEvent(
            event_id="synthetic-news-alpha-prototype-demo-20260717",
            instrument_id="instrument-alpha",
            headline="Synthetic test event: ALPHA prototype demonstration",
            sentiment="negative",
            relevance="high",
        ),
        evidence_references=evidence,
    )
    monitoring = DeterministicMonitoringOrchestrator(registry).run(monitoring_request)
    if monitoring.status != "succeeded" or monitoring.alert_draft is None:
        raise RuntimeError("monitoring orchestration failed")

    market_output, exposure_output, news_output, alert_output = monitoring.outputs
    exposure_snapshot = exposure_output.data
    if exposure_snapshot is None:
        raise RuntimeError("exposure summary did not produce a snapshot")
    findings = tuple(finding for output in monitoring.outputs for finding in output.findings)

    roles = (
        "risk.agent.market_data",
        "risk.agent.portfolio_exposure",
        "risk.agent.news_sentiment",
        "risk.agent.alert_recommendation",
    )
    agent_runs = tuple(
        AgentRun(
            run_id=f"day0-monitoring:{index}:{role}",
            agent_role=role,
            capability_invocations=(output.capability_id,),
            input_digest=sha256_digest(monitoring_request),
            output_digest=sha256_digest(output),
            evidence_references=domain_evidence,
            warnings=output.warnings,
            observed_at=RUN_AT,
        )
        for index, (role, output) in enumerate(zip(roles, monitoring.outputs, strict=True), start=1)
    )

    decision = DecisionPoint(
        decision_id="decision:day0-monitoring:request-changes",
        alert_id=monitoring.alert_draft.alert_id,
        decision="request_changes",
        rationale="Human review requests additional scenario context before any further analysis.",
        human_reviewer_id="day0-human-reviewer",
    )
    review = registry.invoke(
        "alert.draft.review",
        AlertReviewRequest(
            draft=monitoring.alert_draft,
            decision_point=decision,
            evidence_references=evidence,
        ),
    )
    if review.status != "succeeded":
        raise RuntimeError("human review record creation failed")

    return {
        "data_root": root,
        "dataset_snapshot": dataset_snapshot,
        "portfolio_snapshot": portfolio_snapshot,
        "exposure_snapshot": exposure_snapshot,
        "market_output": market_output,
        "exposure_output": exposure_output,
        "news_output": news_output,
        "alert_output": alert_output,
        "findings": findings,
        "agent_runs": agent_runs,
        "alert_draft": monitoring.alert_draft,
        "monitoring": monitoring,
        "decision_point": decision,
        "review": review,
        "concentration_limit": CONCENTRATION_LIMIT,
    }


def write_monitoring_artifacts(result: dict[str, Any]) -> dict[str, Path]:
    """Write the six required stable JSON artifacts beneath the data root."""
    root = Path(result["data_root"])
    output = root / OUTPUT_DIRECTORY
    paths = {
        key: output / name
        for key, name in OUTPUT_NAMES.items()
    }
    _write_stable(paths["portfolio_snapshot"], result["portfolio_snapshot"])
    _write_stable(paths["exposure_snapshot"], result["exposure_snapshot"])
    _write_stable(paths["findings"], {"findings": result["findings"]})
    _write_stable(
        paths["agent_runs"],
        {
            "agent_runs": result["agent_runs"],
            "capability_outputs": tuple(
                {
                    "agent_role": agent_run.agent_role,
                    "capability_id": output.capability_id,
                    "output_digest": sha256_digest(output),
                    "assumptions": output.assumptions,
                    "warnings": output.warnings,
                    "limitations": output.limitations,
                }
                for agent_run, output in zip(
                    result["agent_runs"], result["monitoring"].outputs, strict=True
                )
            ),
        },
    )
    _write_stable(paths["alert_draft"], result["alert_draft"])
    artifacts = tuple(
        {
            "path": path.relative_to(root).as_posix(),
            "digest": _sha256_file(path),
        }
        for key, path in paths.items()
        if key != "evidence_manifest"
    )
    manifest = {
        "manifest_type": "day0-synthetic-monitoring-evidence",
        "generated_at": RUN_AT,
        "synthetic": True,
        "synthetic_label": "synthetic",
        "dataset_snapshot_id": result["dataset_snapshot"].snapshot_id,
        "dataset_snapshot_digest": result["dataset_snapshot"].digest,
        "human_review_required": True,
        "effects": (),
        "human_review": {
            "decision_point": result["decision_point"],
            "review": result["review"],
        },
        "artifacts": artifacts,
    }
    _write_stable(paths["evidence_manifest"], manifest)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=os.environ.get("PORTFOLIO_RISK_DATA_ROOT"),
        help="External data root (defaults to PORTFOLIO_RISK_DATA_ROOT).",
    )
    args = parser.parse_args()
    result = execute_monitoring_journey(args.output_root)
    paths = write_monitoring_artifacts(result)
    print(json.dumps({key: str(value) for key, value in paths.items()}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
