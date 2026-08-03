"""Run treatments and write a complete, immutable external evidence bundle."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

from .contracts import (
    ArchitectureComparison,
    ArchitectureInputBundle,
    Day3RunManifest,
    bytes_digest,
    canonical,
    contains_private_material,
    digest,
)
from .treatments import a1, b0, b1, definitions


def run(bundle: ArchitectureInputBundle, provider: object) -> ArchitectureComparison:
    return ArchitectureComparison(context_digest=bundle.context_digest, runs=(b0(bundle), b1(bundle, provider), a1(bundle, provider)))


def _bytes(value: object) -> bytes:
    return (json.dumps(canonical(value), sort_keys=True, indent=2) + "\n").encode("utf-8")


def comparison_summary(
    bundle: ArchitectureInputBundle,
    comparison: ArchitectureComparison,
) -> dict[str, object]:
    available_evidence = set(bundle.evidence_refs) | {
        event.evidence_digest for event in bundle.events
    }
    architectures = []
    for run_value in comparison.runs:
        cited = set(run_value.output.evidence_refs)
        claims = run_value.output.supporting_claims + run_value.output.contradictory_claims
        cited.update(reference for claim in claims for reference in claim.evidence_refs)
        coverage = (
            Decimal(len(cited.intersection(available_evidence)))
            / Decimal(len(available_evidence))
            if available_evidence
            else Decimal("1")
        )
        architectures.append(
            {
                "architecture_id": run_value.architecture_id,
                "status": run_value.output.status,
                "severity": run_value.output.severity,
                "critic_passed": run_value.critic.passed,
                "unsupported_claim_count": sum(
                    violation.code in {"evidence", "numeric_claim"}
                    for violation in run_value.critic.violations
                ),
                "evidence_reference_coverage": format(coverage, "f"),
                "model_calls": len(run_value.receipts),
                "input_tokens": sum(item.input_tokens for item in run_value.receipts),
                "output_tokens": sum(item.output_tokens for item in run_value.receipts),
                "latency_ms": sum(item.elapsed_ms for item in run_value.receipts),
                "provider_reported_models": sorted(
                    {item.model_id for item in run_value.receipts}
                ),
                "abstained": run_value.output.status
                in {"ABSTAIN", "ABSTAINED_AGENT_OUTPUT"},
                "semantic_output_digest": run_value.output.output_digest,
                "effects": 0,
            }
        )
    return {
        "context_digest": comparison.context_digest,
        "architectures": architectures,
        "effects": 0,
    }


def write_run(output_root: Path | str, bundle: ArchitectureInputBundle, comparison: ArchitectureComparison) -> Path:
    root = Path(output_root)
    if not root.is_absolute():
        raise ValueError("Day 3 output root must be explicit and absolute")
    run_id = "day3_" + digest(comparison).removeprefix("sha256:")[:24]
    target = root / run_id
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    runs = {item.architecture_id: item for item in comparison.runs}
    a1_receipts = runs["A1"].receipts
    a1_specialists = {
        item.role_id: item.output for item in runs["A1"].specialist_outputs
    }
    artifacts: dict[str, bytes] = {
        "architecture-input.json": _bytes(bundle),
        "treatment-definitions.json": _bytes(definitions()),
        "b0-output.json": _bytes(runs["B0"].output),
        "b1-output.json": _bytes(runs["B1"].output),
        "a1-market-output.json": _bytes(a1_specialists["risk.agent.market_data"]),
        "a1-exposure-output.json": _bytes(a1_specialists["risk.agent.portfolio_exposure"]),
        "a1-news-output.json": _bytes(a1_specialists["risk.agent.news_sentiment"]),
        "a1-synthesis-output.json": _bytes(runs["A1"].output),
        "critic-reports.json": _bytes({key: value.critic for key, value in runs.items()}),
        "model-call-receipts.json": _bytes({key: value.receipts for key, value in runs.items()}),
        "agent-timeline.json": _bytes(
            [
                {
                    "sequence": sequence,
                    "architecture_id": receipt.architecture_id,
                    "role_id": receipt.role_id,
                    "prompt_digest": receipt.prompt_digest,
                    "receipt": receipt,
                    "effects": [],
                }
                for sequence, receipt in enumerate(a1_receipts, start=1)
            ]
        ),
        "architecture-results.json": _bytes(comparison),
        "architecture-comparison.json": _bytes(
            comparison_summary(bundle, comparison)
        ),
    }
    artifacts["run-manifest.json"] = _bytes(
        Day3RunManifest(
            run_id=run_id,
            context_digest=bundle.context_digest,
            artifacts={
                name: bytes_digest(value) for name, value in artifacts.items()
            },
        )
    )
    artifacts["evidence-manifest.json"] = _bytes(
        {name: bytes_digest(value) for name, value in artifacts.items()}
    )
    if target.exists():
        actual_names = {path.name for path in target.iterdir() if path.is_file()}
        if actual_names != set(artifacts) or any(
            (target / name).read_bytes() != value
            for name, value in artifacts.items()
        ):
            raise ValueError("immutable Day 3 run already exists with different content")
        return target
    staging = Path(tempfile.mkdtemp(prefix=f".{run_id}.", dir=target.parent))
    try:
        os.chmod(staging, 0o700)
        for name, value in artifacts.items():
            path = staging / name
            path.write_bytes(value)
            path.chmod(0o600)
        staging.rename(target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return target


def validate_run(
    run_directory: Path | str,
    *,
    require_successful_provider: bool = False,
) -> ArchitectureComparison:
    target = Path(run_directory)
    if not target.is_absolute() or not target.is_dir():
        raise ValueError("Day 3 run directory must be an existing absolute directory")
    evidence = json.loads(
        (target / "evidence-manifest.json").read_text(encoding="utf-8")
    )
    if not isinstance(evidence, dict):
        raise ValueError("Day 3 evidence manifest must be an object")
    siblings = {
        path.name for path in target.iterdir()
        if path.is_file() and path.name != "evidence-manifest.json"
    }
    if siblings != set(evidence):
        raise ValueError("Day 3 evidence manifest does not cover every sibling artifact")
    for name, expected in evidence.items():
        if bytes_digest((target / name).read_bytes()) != expected:
            raise ValueError(f"Day 3 artifact digest mismatch: {name}")
    comparison = ArchitectureComparison.model_validate_json(
        (target / "architecture-results.json").read_text(encoding="utf-8")
    )
    if contains_private_material(comparison):
        raise ValueError("Day 3 model evidence contains private material")
    if require_successful_provider and any(
        warning in {"provider_error", "invalid_structured_output"}
        for run_value in comparison.runs[1:]
        for receipt in run_value.receipts
        for warning in receipt.warnings
    ):
        details = sorted({
            warning
            for run_value in comparison.runs[1:]
            for receipt in run_value.receipts
            for warning in receipt.warnings
            if warning not in {"provider_error", "invalid_structured_output"}
        })
        suffix = f": {', '.join(details)}" if details else ""
        raise ValueError(
            "real provider failure or invalid structured output" + suffix
        )
    return comparison
