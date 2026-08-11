"""Fail-closed comparison of complete retained-run evidence bundles."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import ArtifactKind, ArtifactRecord
from .store import ArtifactConflict, LocalArtifactRepository


THESIS_DIMENSIONS = (
    "baseline_step",
    "information_regime",
    "metric_definition",
    "research_question",
    "risk_outcome_definition",
)
CONTROL_DIMENSIONS = (
    "metric_definition",
    "output_contract",
    "research_question",
    "risk_outcome_definition",
    "run_group",
)
PAIR_REQUIRED_CONTROLS = ("output_contract", "run_group")
PAIR_REQUIRED_DIMENSIONS = (
    "agent_definition",
    "data_truth",
    "execution",
    "information_regime",
    "input",
    "output_contract",
    "run_group",
    "scenario",
)
VARIABLE_DIMENSIONS = (
    "agent_definition",
    "as_of",
    "baseline_step",
    "data_truth",
    "execution",
    "information_regime",
    "input",
    "portfolio",
    "scenario",
)


def _digest(value: object) -> str:
    content = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FileComparisonStatus(StrEnum):
    SAME = "same"
    CHANGED = "changed"
    LEFT_ONLY = "left_only"
    RIGHT_ONLY = "right_only"


class RunDimension(FrozenModel):
    name: str
    value: str | None = None
    source: Literal[
        "explicit",
        "artifact_manifest",
        "legacy_manifest",
        "derived_file_digest",
        "missing",
    ]


class RunFileAudit(FrozenModel):
    path: str
    role: str
    content_digest: str
    size_bytes: int


class RetainedRunAudit(FrozenModel):
    artifact_id: str
    artifact_digest: str
    run_id: str | None
    experiment_id: str | None
    integrity_valid: bool
    files: tuple[RunFileAudit, ...]
    dimensions: tuple[RunDimension, ...]
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def dimension_map(self) -> dict[str, RunDimension]:
        return {item.name: item for item in self.dimensions}


class RunFileComparison(FrozenModel):
    path: str
    status: FileComparisonStatus
    left_role: str | None = None
    right_role: str | None = None
    left_digest: str | None = None
    right_digest: str | None = None


class RetainedRunComparison(FrozenModel):
    schema_version: Literal["portfolio-risk.retained-run-comparison/v1"] = (
        "portfolio-risk.retained-run-comparison/v1"
    )
    comparison_digest: str | None = None
    left: RetainedRunAudit
    right: RetainedRunAudit
    planned_variable_dimensions: tuple[str, ...] = ()
    observed_variable_dimensions: tuple[str, ...] = ()
    uncontrolled_differences: tuple[str, ...] = ()
    missing_thesis_dimensions: tuple[str, ...] = ()
    file_comparisons: tuple[RunFileComparison, ...]
    pair_comparable: bool
    thesis_ready: bool
    suggested_verdict: Literal["accepted", "revision_required", "rejected"]
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    next_revision_requirements: tuple[str, ...] = ()

    @model_validator(mode="after")
    def bind_digest(self) -> "RetainedRunComparison":
        payload = self.model_dump(mode="json", exclude={"comparison_digest"})
        expected = _digest(payload)
        if self.comparison_digest is not None and self.comparison_digest != expected:
            raise ValueError("comparison_digest does not match canonical comparison content")
        object.__setattr__(self, "comparison_digest", expected)
        return self


def _file_by_role(record: ArtifactRecord, role: str) -> str | None:
    matches = [item.path for item in record.manifest.files if item.role == role]
    return matches[0] if len(matches) == 1 else None


def _file_digest(record: ArtifactRecord, role: str) -> str | None:
    matches = [item.content_digest for item in record.manifest.files if item.role == role]
    return matches[0] if len(matches) == 1 else None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _explicit_design(source: dict[str, Any]) -> dict[str, Any]:
    design = source.get("experiment_design")
    return design if isinstance(design, dict) else {}


def audit_retained_run(
    repository: LocalArtifactRepository, artifact_id: str
) -> RetainedRunAudit:
    record = repository.get(artifact_id)
    blockers: list[str] = []
    warnings: list[str] = []
    if record.manifest.kind != ArtifactKind.RETAINED_RUN:
        blockers.append("artifact_is_not_a_retained_run")
    verification = repository.verify(artifact_id)
    if not verification.valid:
        blockers.append("artifact_integrity_verification_failed")
    manifest_path = _file_by_role(record, "legacy_manifest") or (
        "manifest.json" if any(item.path == "manifest.json" for item in record.manifest.files) else None
    )
    source: dict[str, Any] = {}
    if manifest_path is None:
        blockers.append("run_manifest_missing")
    else:
        try:
            raw, _media_type = repository.read_file_for_audit(artifact_id, manifest_path)
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("run manifest must be a JSON object")
            source = parsed
        except (ArtifactConflict, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            blockers.append("run_manifest_invalid")
    design = _explicit_design(source)

    def explicit(name: str) -> RunDimension:
        value = _text(design.get(name))
        return RunDimension(
            name=name,
            value=value,
            source="explicit" if value is not None else "missing",
        )

    information = explicit("information_regime")
    if information.value is None:
        provenance_digest = _file_digest(record, "input_provenance")
        information = RunDimension(
            name="information_regime",
            value=provenance_digest,
            source="derived_file_digest" if provenance_digest else "missing",
        )
    agent_definition = _file_digest(record, "agent_blueprint_input")
    input_digest = _file_digest(record, "run_input")
    execution = {
        "mode": source.get("execution_mode"),
        "model": source.get("execution_model"),
    }
    dimensions = (
        RunDimension(name="agent_definition", value=agent_definition, source="derived_file_digest" if agent_definition else "missing"),
        RunDimension(name="as_of", value=_text(source.get("as_of")), source="legacy_manifest" if source.get("as_of") is not None else "missing"),
        explicit("baseline_step"),
        RunDimension(name="data_truth", value=record.manifest.data_truth.value, source="artifact_manifest"),
        RunDimension(name="execution", value=_text(execution), source="legacy_manifest"),
        information,
        RunDimension(name="input", value=input_digest, source="derived_file_digest" if input_digest else "missing"),
        explicit("metric_definition"),
        RunDimension(name="output_contract", value=_text(source.get("output_contract")), source="legacy_manifest" if source.get("output_contract") is not None else "missing"),
        RunDimension(name="portfolio", value=_text(source.get("portfolio_id")), source="legacy_manifest" if source.get("portfolio_id") is not None else "missing"),
        explicit("research_question"),
        RunDimension(name="risk_outcome_definition", value=_text(design.get("risk_outcome_definition")), source="explicit" if design.get("risk_outcome_definition") is not None else "missing"),
        RunDimension(name="run_group", value=_text(source.get("comparison_id")), source="legacy_manifest" if source.get("comparison_id") is not None else "missing"),
        RunDimension(name="scenario", value=_text(source.get("scenario")), source="legacy_manifest" if source.get("scenario") is not None else "missing"),
    )
    if source.get("comparison_id") is None:
        warnings.append("run_group_is_not_declared")
    files = tuple(
        RunFileAudit(
            path=item.path,
            role=item.role,
            content_digest=item.content_digest,
            size_bytes=item.size_bytes,
        )
        for item in record.manifest.files
    )
    return RetainedRunAudit(
        artifact_id=artifact_id,
        artifact_digest=record.manifest.artifact_digest or "",
        run_id=record.manifest.run_id,
        experiment_id=record.manifest.experiment_id,
        integrity_valid=verification.valid,
        files=files,
        dimensions=tuple(sorted(dimensions, key=lambda item: item.name)),
        blockers=tuple(sorted(set(blockers))),
        warnings=tuple(sorted(set(warnings))),
    )


def compare_retained_runs(
    repository: LocalArtifactRepository,
    left_artifact_id: str,
    right_artifact_id: str,
    *,
    planned_variable_dimensions: tuple[str, ...] = (),
) -> RetainedRunComparison:
    if left_artifact_id == right_artifact_id:
        raise ValueError("comparison requires two different retained runs")
    planned = tuple(sorted(set(planned_variable_dimensions)))
    unknown = sorted(set(planned) - set(VARIABLE_DIMENSIONS))
    if unknown:
        raise ValueError("unknown planned variable dimensions: " + ", ".join(unknown))
    left = audit_retained_run(repository, left_artifact_id)
    right = audit_retained_run(repository, right_artifact_id)
    left_dimensions = left.dimension_map()
    right_dimensions = right.dimension_map()
    observed = tuple(
        name
        for name in sorted(left_dimensions)
        if left_dimensions[name].value != right_dimensions[name].value
    )
    uncontrolled = tuple(name for name in observed if name not in planned)
    blockers = [*left.blockers, *right.blockers]
    for name in PAIR_REQUIRED_DIMENSIONS:
        if left_dimensions[name].value is None or right_dimensions[name].value is None:
            blockers.append(f"required_comparison_dimension_missing:{name}")
    for name in CONTROL_DIMENSIONS:
        left_value = left_dimensions[name].value
        right_value = right_dimensions[name].value
        if name in PAIR_REQUIRED_CONTROLS and (left_value is None or right_value is None):
            blockers.append(f"required_control_missing:{name}")
        elif (left_value is None) != (right_value is None):
            blockers.append(f"required_control_missing_on_one_run:{name}")
        elif left_value != right_value:
            blockers.append(f"required_control_changed:{name}")
    if uncontrolled:
        blockers.extend(f"unplanned_dimension_changed:{name}" for name in uncontrolled)
    if not observed:
        blockers.append("no_counterfactual_dimension_changed")
    unobserved_plans = tuple(name for name in planned if name not in observed)
    warnings = [*left.warnings, *right.warnings]
    blockers.extend(f"planned_dimension_did_not_change:{name}" for name in unobserved_plans)

    left_files = {item.path: item for item in left.files}
    right_files = {item.path: item for item in right.files}
    file_comparisons = []
    for path in sorted(set(left_files) | set(right_files)):
        left_file = left_files.get(path)
        right_file = right_files.get(path)
        status = (
            FileComparisonStatus.LEFT_ONLY
            if right_file is None
            else FileComparisonStatus.RIGHT_ONLY
            if left_file is None
            else FileComparisonStatus.SAME
            if left_file.content_digest == right_file.content_digest and left_file.role == right_file.role
            else FileComparisonStatus.CHANGED
        )
        file_comparisons.append(
            RunFileComparison(
                path=path,
                status=status,
                left_role=left_file.role if left_file else None,
                right_role=right_file.role if right_file else None,
                left_digest=left_file.content_digest if left_file else None,
                right_digest=right_file.content_digest if right_file else None,
            )
        )

    missing_thesis = tuple(
        name
        for name in THESIS_DIMENSIONS
        if left_dimensions[name].source != "explicit"
        or right_dimensions[name].source != "explicit"
    )
    pair_comparable = not blockers
    thesis_ready = pair_comparable and not missing_thesis
    next_revisions = []
    if missing_thesis:
        next_revisions.append(
            "Declare immutable experiment-design identities for: " + ", ".join(missing_thesis)
        )
    if uncontrolled:
        next_revisions.append(
            "Hold constant or explicitly redesign the comparison for: " + ", ".join(uncontrolled)
        )
    if left.blockers or right.blockers:
        next_revisions.append("Repair and re-retain every run bundle that failed integrity or type checks.")
    if not observed:
        next_revisions.append("Create a counterfactual run with at least one predeclared treatment change.")
    suggested = "accepted" if thesis_ready else "rejected" if not pair_comparable else "revision_required"
    return RetainedRunComparison(
        left=left,
        right=right,
        planned_variable_dimensions=planned,
        observed_variable_dimensions=observed,
        uncontrolled_differences=uncontrolled,
        missing_thesis_dimensions=missing_thesis,
        file_comparisons=tuple(file_comparisons),
        pair_comparable=pair_comparable,
        thesis_ready=thesis_ready,
        suggested_verdict=suggested,
        blockers=tuple(sorted(set(blockers))),
        warnings=tuple(sorted(set(warnings))),
        next_revision_requirements=tuple(next_revisions),
    )
