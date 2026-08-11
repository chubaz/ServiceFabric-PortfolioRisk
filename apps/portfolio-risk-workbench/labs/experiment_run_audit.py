"""Experiment Workspace adapter for retained-run comparison and acceptance."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator
from risk_artifacts import (
    ArtifactKind,
    ArtifactManifest,
    DataTruthClass,
    PreviewMode,
    PublicationState,
    RetentionClass,
    RightsState,
    SourceRevision,
    VARIABLE_DIMENSIONS,
    compare_retained_runs,
    file_manifest,
)

from artifact_repository import artifact_store, record_payload


IDENTIFIER_PATTERN = r"^[a-z0-9][a-z0-9._:-]{2,159}$"
DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"
ACCEPTANCE_ROLE = "experiment_acceptance_record"
ACCEPTANCE_FILE = "acceptance-record.json"


class RunComparisonRequest(BaseModel):
    left_artifact_id: str = Field(pattern=IDENTIFIER_PATTERN)
    right_artifact_id: str = Field(pattern=IDENTIFIER_PATTERN)
    planned_variable_dimensions: tuple[str, ...] = Field(default=(), max_length=9)

    @field_validator("planned_variable_dimensions")
    @classmethod
    def valid_variables(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("planned variable dimensions must be unique and sorted")
        unknown = sorted(set(value) - set(VARIABLE_DIMENSIONS))
        if unknown:
            raise ValueError("unknown planned variable dimensions: " + ", ".join(unknown))
        return value


class RunAcceptanceRequest(RunComparisonRequest):
    expected_comparison_digest: str = Field(pattern=DIGEST_PATTERN)
    verdict: Literal["accepted", "revision_required", "rejected"]
    actor: str = Field(pattern=IDENTIFIER_PATTERN)
    rationale: str = Field(min_length=3, max_length=1200)
    prior_acceptance_artifact_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)


def _comparison(request: RunComparisonRequest):  # type: ignore[no-untyped-def]
    return compare_retained_runs(
        artifact_store(),
        request.left_artifact_id,
        request.right_artifact_id,
        planned_variable_dimensions=request.planned_variable_dimensions,
    )


def comparison_payload(request: RunComparisonRequest) -> dict[str, Any]:
    return _comparison(request).model_dump(mode="json")


def catalogue_payload() -> dict[str, Any]:
    store = artifact_store()
    records = store.list()
    runs = [
        {
            "artifact_id": record.manifest.artifact_id,
            "artifact_digest": record.manifest.artifact_digest,
            "run_id": record.manifest.run_id,
            "experiment_id": record.manifest.experiment_id,
            "title": record.manifest.title,
            "data_truth": record.manifest.data_truth.value,
            "state": record.state.value,
            "file_count": len(record.manifest.files),
        }
        for record in records
        if record.manifest.kind == ArtifactKind.RETAINED_RUN
    ]
    acceptances = []
    for record in records:
        item = next((item for item in record.manifest.files if item.role == ACCEPTANCE_ROLE), None)
        if item is None:
            continue
        content, _media_type = store.read_file_for_audit(record.manifest.artifact_id, item.path)
        value = json.loads(content)
        acceptances.append({
            "artifact_id": record.manifest.artifact_id,
            "title": record.manifest.title,
            "created_at": record.manifest.created_at.isoformat(),
            "supersedes_artifact_id": record.manifest.supersedes_artifact_id,
            "parent_artifact_ids": list(record.manifest.parent_artifact_ids),
            "state": record.state.value,
            "cycle": value.get("cycle"),
            "verdict": value.get("verdict"),
            "left_artifact_id": value.get("left_artifact_id"),
            "right_artifact_id": value.get("right_artifact_id"),
            "comparison_digest": value.get("comparison_digest"),
        })
    return {
        "retained_runs": runs,
        "acceptance_records": acceptances,
        "variable_dimensions": list(VARIABLE_DIMENSIONS),
        "boundary": {
            "source": "governed_artifact_repository_only",
            "complete_file_integrity_required": True,
            "automatic_metric_interpretation": False,
            "automatic_object_repair": False,
            "external_effects": "disabled",
        },
    }


def _acceptance_content(record, request: RunAcceptanceRequest, *, acceptance_id: str, cycle: int) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return {
        "schema_version": "portfolio-risk.experiment-run-acceptance/v1",
        "acceptance_id": acceptance_id,
        "cycle": cycle,
        "comparison_digest": record.comparison_digest,
        "left_artifact_id": record.left.artifact_id,
        "right_artifact_id": record.right.artifact_id,
        "planned_variable_dimensions": list(record.planned_variable_dimensions),
        "pair_comparable": record.pair_comparable,
        "thesis_ready": record.thesis_ready,
        "verdict": request.verdict,
        "rationale": request.rationale,
        "blockers": list(record.blockers),
        "warnings": list(record.warnings),
        "next_revision_requirements": list(record.next_revision_requirements),
        "prior_acceptance_artifact_id": request.prior_acceptance_artifact_id,
        "reviewed_by": request.actor,
        "reviewed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def _prior_cycle(artifact_id: str | None, pair: set[str]) -> int:
    if artifact_id is None:
        return 0
    store = artifact_store()
    prior = store.get(artifact_id)
    item = next((item for item in prior.manifest.files if item.role == ACCEPTANCE_ROLE), None)
    if item is None:
        raise ValueError("prior acceptance artifact does not contain an acceptance record")
    content, _media_type = store.read_file_for_audit(artifact_id, item.path)
    value = json.loads(content)
    prior_pair = {value.get("left_artifact_id"), value.get("right_artifact_id")}
    if prior_pair != pair:
        raise ValueError("prior acceptance record belongs to another run pair")
    cycle = value.get("cycle")
    if not isinstance(cycle, int) or cycle < 1:
        raise ValueError("prior acceptance cycle is invalid")
    return cycle


def _combined_truth(left: DataTruthClass, right: DataTruthClass) -> DataTruthClass:
    return left if left == right else DataTruthClass.MIXED


def _combined_rights(left: RightsState, right: RightsState) -> RightsState:
    if RightsState.LICENSED_RESTRICTED in {left, right}:
        return RightsState.LICENSED_RESTRICTED
    if RightsState.INTERNAL in {left, right}:
        return RightsState.INTERNAL
    return RightsState.PUBLIC


def record_acceptance(request: RunAcceptanceRequest) -> dict[str, Any]:
    comparison = _comparison(request)
    if comparison.comparison_digest != request.expected_comparison_digest:
        raise ValueError("comparison changed; review the current gate before recording acceptance")
    if request.verdict == "accepted" and not comparison.thesis_ready:
        raise ValueError("accepted is allowed only for a thesis-ready comparison")
    if request.verdict == "revision_required" and not comparison.pair_comparable:
        raise ValueError("a confounded or damaged pair must be rejected, not revision-required")
    store = artifact_store()
    left = store.get(request.left_artifact_id)
    right = store.get(request.right_artifact_id)
    pair = {request.left_artifact_id, request.right_artifact_id}
    cycle = _prior_cycle(request.prior_acceptance_artifact_id, pair) + 1
    identity_seed = "|".join(
        (
            comparison.comparison_digest or "",
            str(cycle),
            request.verdict,
            request.actor,
            datetime.now(timezone.utc).isoformat(),
        )
    )
    acceptance_id = "experiment-acceptance-" + hashlib.sha256(identity_seed.encode()).hexdigest()[:24]
    content = _acceptance_content(
        comparison, request, acceptance_id=acceptance_id, cycle=cycle
    )
    raw = (json.dumps(content, indent=2, sort_keys=True) + "\n").encode("utf-8")
    file = file_manifest(
        path=ACCEPTANCE_FILE,
        content=raw,
        media_type="application/json",
        role=ACCEPTANCE_ROLE,
        preview_mode=PreviewMode.ESCAPED_TEXT,
        download_allowed=False,
        sensitive=False,
    )
    parents = tuple(
        sorted(
            {
                request.left_artifact_id,
                request.right_artifact_id,
                *([request.prior_acceptance_artifact_id] if request.prior_acceptance_artifact_id else []),
            }
        )
    )
    restrictions = set(left.manifest.restrictions) | set(right.manifest.restrictions)
    restrictions.add("review_required_before_thesis_use")
    manifest = ArtifactManifest(
        artifact_id=acceptance_id,
        title=f"Experiment run acceptance · cycle {cycle}",
        kind=ArtifactKind.EVIDENCE_BUNDLE,
        created_at=datetime.now(timezone.utc),
        created_by=request.actor,
        creation_method="experiment-workspace.run-comparison-acceptance",
        experiment_id=(
            left.manifest.experiment_id
            if left.manifest.experiment_id == right.manifest.experiment_id
            else None
        ),
        data_truth=_combined_truth(left.manifest.data_truth, right.manifest.data_truth),
        rights=_combined_rights(left.manifest.rights, right.manifest.rights),
        rights_policy_id=(
            left.manifest.rights_policy_id
            if left.manifest.rights_policy_id == right.manifest.rights_policy_id
            else "mixed.research.evidence.v1"
        ),
        publication=PublicationState.RESTRICTED,
        retention=RetentionClass.EXPERIMENT_EVIDENCE,
        entry_file=ACCEPTANCE_FILE,
        files=(file,),
        total_size_bytes=len(raw),
        source_revisions=tuple(
            sorted(
                (
                    SourceRevision(
                        kind="retained_run_artifact",
                        source_id=item.manifest.artifact_id,
                        revision=item.revision,
                        digest=item.manifest.artifact_digest or "",
                    )
                    for item in (left, right)
                ),
                key=lambda item: (item.kind, item.source_id, item.revision, item.digest),
            )
        ),
        parent_artifact_ids=parents,
        supersedes_artifact_id=request.prior_acceptance_artifact_id,
        restrictions=tuple(sorted(restrictions)),
    )
    admitted = store.admit(
        manifest,
        {ACCEPTANCE_FILE: raw},
        actor=request.actor,
        rationale="Record the reviewed experiment-run comparison gate.",
    )
    verification = store.verify(admitted.manifest.artifact_id)
    if not verification.valid:
        raise ValueError("acceptance artifact failed repository integrity verification")
    return {
        "record": record_payload(admitted),
        "acceptance": content,
        "comparison": comparison.model_dump(mode="json"),
    }
