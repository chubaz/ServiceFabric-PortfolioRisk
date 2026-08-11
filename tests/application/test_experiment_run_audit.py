from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from risk_artifacts import (
    ArtifactKind,
    ArtifactManifest,
    DataTruthClass,
    LocalArtifactRepository,
    PublicationState,
    RetentionClass,
    RightsState,
    file_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
LABS_ROOT = ROOT / "apps" / "portfolio-risk-workbench" / "labs"
sys.path.insert(0, str(LABS_ROOT))

import experiment_run_audit  # noqa: E402


NOW = datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc)


def _admit_run(repository: LocalArtifactRepository, artifact_id: str, run_id: str, agent: str) -> None:
    payloads = {
        "manifest.json": json.dumps(
            {
                "run_id": run_id,
                "comparison_id": "comparison-acceptance-001",
                "scenario": "concentration",
                "portfolio_id": "portfolio-001",
                "as_of": "2024-01-05",
                "output_contract": "RiskBrief",
                "execution_mode": "deterministic",
                "execution_model": None,
            },
            sort_keys=True,
        ).encode(),
        "blueprint.json": json.dumps({"agent": agent}, sort_keys=True).encode(),
        "input.json": b'{"portfolio":"portfolio-001"}',
        "input-provenance.json": b'{"regime":"prices-only"}',
    }
    roles = {
        "manifest.json": "legacy_manifest",
        "blueprint.json": "agent_blueprint_input",
        "input.json": "run_input",
        "input-provenance.json": "input_provenance",
    }
    files = tuple(
        sorted(
            (
                file_manifest(
                    path=path,
                    content=content,
                    media_type="application/json",
                    role=roles[path],
                )
                for path, content in payloads.items()
            ),
            key=lambda item: item.path,
        )
    )
    manifest = ArtifactManifest(
        artifact_id=artifact_id,
        title=f"Retained {agent}",
        kind=ArtifactKind.RETAINED_RUN,
        created_at=NOW,
        created_by="tests.runner",
        creation_method="tests.fixture",
        run_id=run_id,
        experiment_id="experiment-acceptance-001",
        data_truth=DataTruthClass.REVIEWED_SYNTHETIC,
        rights=RightsState.INTERNAL,
        rights_policy_id="internal.synthetic.research.v1",
        publication=PublicationState.RESTRICTED,
        retention=RetentionClass.EXPERIMENT_EVIDENCE,
        entry_file="manifest.json",
        files=files,
        total_size_bytes=sum(len(value) for value in payloads.values()),
    )
    repository.admit(manifest, payloads, actor="tests.reviewer", occurred_at=NOW)


def test_acceptance_records_form_an_immutable_revision_cycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "artifacts"
    monkeypatch.setenv("PORTFOLIO_RISK_ARTIFACT_ROOT", str(root))
    repository = LocalArtifactRepository(root)
    _admit_run(repository, "retained-run-audit-left", "run-audit-left", "baseline")
    _admit_run(repository, "retained-run-audit-right", "run-audit-right", "treatment")
    comparison_request = experiment_run_audit.RunComparisonRequest(
        left_artifact_id="retained-run-audit-left",
        right_artifact_id="retained-run-audit-right",
        planned_variable_dimensions=("agent_definition",),
    )
    comparison = experiment_run_audit.comparison_payload(comparison_request)
    assert comparison["pair_comparable"]
    assert not comparison["thesis_ready"]

    with pytest.raises(ValueError, match="thesis-ready"):
        experiment_run_audit.record_acceptance(
            experiment_run_audit.RunAcceptanceRequest(
                **comparison_request.model_dump(),
                expected_comparison_digest=comparison["comparison_digest"],
                verdict="accepted",
                actor="local.researcher",
                rationale="Premature acceptance must fail.",
            )
        )

    first = experiment_run_audit.record_acceptance(
        experiment_run_audit.RunAcceptanceRequest(
            **comparison_request.model_dump(),
            expected_comparison_digest=comparison["comparison_digest"],
            verdict="revision_required",
            actor="local.researcher",
            rationale="Add explicit thesis-design identities before evidence use.",
        )
    )
    assert first["acceptance"]["cycle"] == 1
    first_id = first["record"]["manifest"]["artifact_id"]
    second = experiment_run_audit.record_acceptance(
        experiment_run_audit.RunAcceptanceRequest(
            **comparison_request.model_dump(),
            expected_comparison_digest=comparison["comparison_digest"],
            verdict="revision_required",
            actor="local.researcher",
            rationale="The revised run pair still lacks the required identities.",
            prior_acceptance_artifact_id=first_id,
        )
    )
    assert second["acceptance"]["cycle"] == 2
    assert second["record"]["manifest"]["supersedes_artifact_id"] == first_id
    catalogue = experiment_run_audit.catalogue_payload()
    assert len(catalogue["retained_runs"]) == 2
    assert len(catalogue["acceptance_records"]) == 2
