"""Application service for saving, reopening and verifying one comparison."""

from __future__ import annotations

import json
from typing import Any

from gold_case_runtime import gold_case_store
from matched_run_runtime import matched_run_store
from trajectory_evaluation_runtime import evaluate_matched_matrix, evaluation_store
from trajectory_execution_runtime import trajectory_store
from risk_experiments import (
    LocalReproducibilityStore, ReproducibilityConflict, build_bundle_manifest,
    canonical_digest, trajectory_semantic_digest,
)


def reproducibility_store() -> LocalReproducibilityStore:
    return LocalReproducibilityStore(gold_case_store().root)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, indent=2, sort_keys=True, default=str).encode("utf-8")


def _report(comparison: dict[str, Any]) -> str:
    lines = [
        "# Architecture comparison",
        "",
        f"**Status:** {comparison['status'].replace('_', ' ')}  ",
        f"**Data:** {comparison['data_truth']}  ",
        f"**Case:** `{comparison['case_id']}`",
        "",
        comparison["summary"],
        "",
        "## What the comparison shows",
        "",
    ]
    lines.extend(f"- {item}" for item in comparison["findings"])
    lines.extend(["", "## Architecture results", "", "| Method | Runs | Dimensions | Cost |", "|---|---:|---:|---:|"])
    for item in comparison["architectures"]:
        lines.append(
            f"| {item['architecture']} | {item['run_count']} | {item['measured_dimensions']}/9 | "
            f"${item['resources']['cost_usd']:.4f} |"
        )
    lines.extend(["", "## Limits", ""])
    lines.extend(f"- {item}" for item in comparison["limitations"])
    lines.extend([
        "", "## Reproducibility", "",
        "The saved manifest binds the exact Case, Gold reference, matrix, trajectories, evaluations, prompts, model route and evaluator version. Gold truth was joined only after execution.",
    ])
    return "\n".join(lines) + "\n"


def _release_diagnostics(plan: Any, trajectories: list[Any], comparison: dict[str, Any]) -> dict[str, Any]:
    cells = {item.cell_id: item for item in plan.cells}
    b0_groups: dict[tuple[str, str], list[Any]] = {}
    for trajectory in trajectories:
        cell = cells[trajectory.cell_id]
        if cell.treatment_id == "B0":
            b0_groups.setdefault((cell.capability_package_id, cell.perturbation_condition.value), []).append(trajectory)
    b0_repeat_identity = all(
        len({trajectory_semantic_digest(item) for item in group}) == 1
        for group in b0_groups.values() if len(group) > 1
    )
    run_checks = [check for run in comparison["runs"] for check in run["checks"]]
    checks = {
        "matrix_complete": len(trajectories) == len(plan.cells),
        "all_runtime_checks_pass": all(item["passed"] for item in run_checks),
        "gold_firewall": all(
            next(check for check in run["checks"] if check["id"] == "gold-firewall")["passed"]
            for run in comparison["runs"]
        ),
        "deterministic_repetitions_identical": b0_repeat_identity,
        "stability_measured": all(
            next(item for item in architecture["dimensions"] if item["dimension_id"] == "stability")["status"] != "not_measurable"
            for architecture in comparison["architectures"]
        ),
        "robustness_measured": all(
            next(item for item in architecture["dimensions"] if item["dimension_id"] == "robustness")["status"] != "not_measurable"
            for architecture in comparison["architectures"]
        ),
        "capability_receipts_complete": all(
            cycle.result.capability_calls == cycle.processing_receipt.capability_calls
            and (
                cycle.result.architecture_output is None
                or cycle.result.architecture_output.execution_summary is None
                or cycle.result.capability_calls
                == cycle.result.architecture_output.execution_summary.capability_calls
            )
            for trajectory in trajectories for cycle in trajectory.cycles
        ),
        "no_external_effects": all(
            cycle.result.architecture_output is None
            or (
                cycle.result.architecture_output.decision.portfolio_action in {"none", "review_exposure"}
                and (
                    cycle.result.architecture_output.decision.portfolio_action == "none"
                    or cycle.result.architecture_output.decision.human_review_required
                )
            )
            for trajectory in trajectories for cycle in trajectory.cycles
        ),
    }
    return {
        "release_ready": all(checks.values()),
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "matrix_id": plan.matrix_id,
        "matrix_digest": plan.matrix_digest,
        "technical_use": "Feed this document to Codex when diagnosing or reproducing the comparison.",
    }


def create_reproducibility_bundle(matrix_id: str) -> dict[str, Any]:
    plan = matched_run_store().get(matrix_id)
    comparison = evaluate_matched_matrix(matrix_id)
    if not comparison["archivable"]:
        raise ReproducibilityConflict("only a complete, valid comparison can be saved")
    trajectories = sorted(
        (item for item in trajectory_store().list() if item.matrix_id == matrix_id),
        key=lambda item: item.cell_id,
    )
    references = [item for item in gold_case_store().list() if item.compiled_case_id == plan.case_id]
    if len(references) != 1:
        raise ReproducibilityConflict("the comparison must resolve exactly one Gold reference")
    gold = references[0]
    case = gold_case_store().get_case(plan.case_id)
    evaluations = [evaluation_store().get(run["evaluation_id"]) for run in comparison["runs"]]
    diagnostics = _release_diagnostics(plan, trajectories, comparison)
    files: dict[str, tuple[bytes, str, str]] = {
        "comparison.json": (_json_bytes(comparison), "application/json", "system"),
        "supervisor-report.md": (_report(comparison).encode(), "text/markdown", "supervisor"),
        "diagnostics.json": (_json_bytes(diagnostics), "application/json", "developer"),
        "records/matrix.json": (_json_bytes(plan.model_dump(mode="json")), "application/json", "system"),
        "records/case.json": (_json_bytes(case.model_dump(mode="json")), "application/json", "system"),
        "records/gold-reference.json": (_json_bytes(gold.model_dump(mode="json")), "application/json", "developer"),
    }
    for item in trajectories:
        files[f"records/trajectories/{item.trajectory_id}.json"] = (
            _json_bytes(item.model_dump(mode="json")), "application/json", "system",
        )
    for item in evaluations:
        files[f"records/evaluations/{item.evaluation_id}.json"] = (
            _json_bytes(item.model_dump(mode="json")), "application/json", "system",
        )
    versions = {
        "matrix_schema": plan.schema_version,
        "evaluator": comparison["technical_receipt"]["evaluator"],
        "model_routes": ",".join(sorted({item.model_reference or "none" for item in plan.cells})),
        "prompt_references": ",".join(sorted({item.prompt_reference or "none" for item in plan.cells})),
        "capability_package_digests": ",".join(sorted({item.capability_package_digest for item in plan.cells})),
    }
    created_at = max(item.completed_at for item in trajectories)
    manifest = build_bundle_manifest(
        matrix_id=matrix_id, case_id=plan.case_id, comparison=comparison,
        files=files, exact_versions=versions, created_at=created_at,
    )
    projection = reproducibility_store().save(manifest, {name: value[0] for name, value in files.items()})
    return _projection_payload(projection, comparison=comparison, diagnostics=diagnostics)


def _projection_payload(projection: Any, *, comparison: dict[str, Any] | None = None, diagnostics: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = projection.manifest
    return {
        "bundle_id": manifest.bundle_id, "matrix_id": manifest.matrix_id,
        "case_id": manifest.case_id, "state": projection.state,
        "verified": projection.verified, "verification_errors": list(projection.verification_errors),
        "created_at": manifest.created_at.isoformat(), "bundle_digest": manifest.bundle_digest,
        "comparison": comparison, "diagnostics": diagnostics,
    }


def list_reproducibility_bundles() -> dict[str, Any]:
    return {"bundles": [_projection_payload(item) for item in reproducibility_store().list()]}


def open_reproducibility_bundle(bundle_id: str) -> dict[str, Any]:
    projection = reproducibility_store().get(bundle_id)
    comparison = json.loads(reproducibility_store().read(bundle_id, "comparison.json"))
    diagnostics = json.loads(reproducibility_store().read(bundle_id, "diagnostics.json"))
    return _projection_payload(projection, comparison=comparison, diagnostics=diagnostics)


def verify_reproducibility_bundle(bundle_id: str) -> dict[str, Any]:
    projection = reproducibility_store().get(bundle_id)
    comparison = json.loads(reproducibility_store().read(bundle_id, "comparison.json"))
    current = evaluate_matched_matrix(projection.manifest.matrix_id)
    reproduction_matches = canonical_digest(current) == projection.manifest.comparison_digest
    payload = _projection_payload(projection, comparison=comparison)
    payload["reproduction_matches"] = reproduction_matches
    payload["verified"] = projection.verified and reproduction_matches
    return payload


def archive_reproducibility_bundle(bundle_id: str) -> dict[str, Any]:
    return _projection_payload(reproducibility_store().archive(bundle_id))


def restore_reproducibility_bundle(bundle_id: str) -> dict[str, Any]:
    return _projection_payload(reproducibility_store().restore(bundle_id))


def remove_reproducibility_bundle(bundle_id: str, confirmation: str) -> dict[str, Any]:
    return _projection_payload(reproducibility_store().remove(bundle_id, confirmation=confirmation))
