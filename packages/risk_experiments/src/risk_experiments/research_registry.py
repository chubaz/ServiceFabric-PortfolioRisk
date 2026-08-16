"""Immutable classification contracts for thesis experiment runs and analyses.

The registry deliberately classifies one run; it does not schedule a batch.
That keeps the single-run surface and a future concurrent Experiment Lab on the
same scientific identity without duplicating orchestration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .models import DIGEST, IDENTIFIER, FrozenModel, canonical_digest


BASELINE_IDS = ("b0", "b1", "a1")


class ContextRevision(FrozenModel):
    """A closed context identity and, optionally, its immutable successor."""

    fixture_context_digest: str = Field(pattern=DIGEST)
    supersedes_context_digest: str | None = Field(default=None, pattern=DIGEST)
    changed_dimensions: tuple[
        Literal[
            "portfolio_mandate",
            "scenario",
            "data_boundary",
            "information_regime",
            "capability_environment",
            "architecture_contract",
            "evaluation_protocol",
        ],
        ...,
    ] = ()
    recorded_at: datetime
    revision_digest: str | None = Field(default=None, pattern=DIGEST)

    @field_validator("recorded_at")
    @classmethod
    def normalise_recorded_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_supersession(self) -> "ContextRevision":
        if self.supersedes_context_digest is None and self.changed_dimensions:
            raise ValueError("an initial context cannot declare changed dimensions")
        if self.supersedes_context_digest is not None:
            if self.supersedes_context_digest == self.fixture_context_digest:
                raise ValueError("a context revision must name a different successor digest")
            if not self.changed_dimensions:
                raise ValueError("a successor context must declare what changed")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"revision_digest"}))
        if self.revision_digest is not None and self.revision_digest != expected:
            raise ValueError("revision_digest does not match canonical content")
        object.__setattr__(self, "revision_digest", expected)
        return self


class RunClassification(FrozenModel):
    """The scientific bin of one execution, independent of its output quality."""

    study_id: str = Field(pattern=IDENTIFIER)
    experiment_id: str = Field(pattern=IDENTIFIER)
    fixture_context_digest: str = Field(pattern=DIGEST)
    case_id: str = Field(pattern=IDENTIFIER)
    baseline_id: Literal["b0", "b1", "a1"]
    architecture_reference: str = Field(min_length=8, max_length=1000)
    portfolio_mandate_reference: str = Field(min_length=8, max_length=1000)
    information_regime_reference: str = Field(min_length=8, max_length=1000)
    scenario_reference: str = Field(min_length=8, max_length=1000)
    evaluation_reference: str = Field(min_length=8, max_length=1000)
    repetition: int = Field(ge=1, le=100)
    market_regime_labels: tuple[str, ...] = ()
    run_id: str | None = Field(default=None, pattern=IDENTIFIER)
    classification_digest: str | None = Field(default=None, pattern=DIGEST)

    @field_validator("market_regime_labels")
    @classmethod
    def labels_are_sorted(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("market-regime labels must be unique and sorted")
        return value

    @property
    def cell_key(self) -> str:
        """The planned comparison cell; deliberately excludes run and outcome."""
        return canonical_digest({
            "study_id": self.study_id,
            "experiment_id": self.experiment_id,
            "fixture_context_digest": self.fixture_context_digest,
            "case_id": self.case_id,
            "baseline_id": self.baseline_id,
            "architecture_reference": self.architecture_reference,
            "portfolio_mandate_reference": self.portfolio_mandate_reference,
            "information_regime_reference": self.information_regime_reference,
            "scenario_reference": self.scenario_reference,
            "evaluation_reference": self.evaluation_reference,
            "repetition": self.repetition,
        })

    @model_validator(mode="after")
    def bind_digest(self) -> "RunClassification":
        expected = canonical_digest(self.model_dump(mode="json", exclude={"classification_digest"}))
        if self.classification_digest is not None and self.classification_digest != expected:
            raise ValueError("classification_digest does not match canonical content")
        object.__setattr__(self, "classification_digest", expected)
        return self


class RerunObligation(FrozenModel):
    source_context_digest: str = Field(pattern=DIGEST)
    target_context_digest: str = Field(pattern=DIGEST)
    cell_key: str = Field(pattern=DIGEST)
    reason: Literal["context_superseded", "architecture_changed", "capability_environment_changed"]
    status: Literal["required", "satisfied", "not_required"] = "required"


class AnalysisDefinition(FrozenModel):
    """A versioned, declarative request for a thesis comparison or model."""

    analysis_id: str = Field(pattern=IDENTIFIER)
    study_id: str = Field(pattern=IDENTIFIER)
    experiment_id: str = Field(pattern=IDENTIFIER)
    name: str = Field(min_length=3, max_length=200)
    analysis_kind: Literal["paired_comparison", "counterfactual", "regression", "coverage"]
    baseline_id: Literal["b0", "b1", "a1"]
    treatment_ids: tuple[Literal["b0", "b1", "a1"], ...] = Field(min_length=1)
    changed_dimensions: tuple[Literal["architecture", "information_regime", "capability_environment", "scenario"], ...]
    outcome_references: tuple[str, ...] = Field(min_length=1)
    missingness_rule: str = Field(min_length=10, max_length=600)
    analysis_digest: str | None = Field(default=None, pattern=DIGEST)

    @model_validator(mode="after")
    def validate_comparison(self) -> "AnalysisDefinition":
        if self.baseline_id in self.treatment_ids:
            raise ValueError("an analysis treatment cannot also be its baseline")
        if len(self.treatment_ids) != len(set(self.treatment_ids)):
            raise ValueError("analysis treatments must be unique")
        if len(self.changed_dimensions) != len(set(self.changed_dimensions)):
            raise ValueError("changed dimensions must be unique")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"analysis_digest"}))
        if self.analysis_digest is not None and self.analysis_digest != expected:
            raise ValueError("analysis_digest does not match canonical content")
        object.__setattr__(self, "analysis_digest", expected)
        return self


class AnalysisSnapshot(FrozenModel):
    analysis_digest: str = Field(pattern=DIGEST)
    fixture_context_digest: str = Field(pattern=DIGEST)
    run_ids: tuple[str, ...] = Field(min_length=1)
    evaluation_references: tuple[str, ...] = Field(min_length=1)
    status: Literal["complete", "partial", "blocked"]
    missing_cell_keys: tuple[str, ...] = ()
    snapshot_digest: str | None = Field(default=None, pattern=DIGEST)

    @model_validator(mode="after")
    def bind_snapshot(self) -> "AnalysisSnapshot":
        if len(self.run_ids) != len(set(self.run_ids)):
            raise ValueError("analysis snapshot run IDs must be unique")
        if self.status == "complete" and self.missing_cell_keys:
            raise ValueError("a complete analysis snapshot cannot have missing cells")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"snapshot_digest"}))
        if self.snapshot_digest is not None and self.snapshot_digest != expected:
            raise ValueError("snapshot_digest does not match canonical content")
        object.__setattr__(self, "snapshot_digest", expected)
        return self


def rerun_obligations(
    revision: ContextRevision, classifications: tuple[RunClassification, ...]
) -> tuple[RerunObligation, ...]:
    """Produce one obligation per old cell affected by a new context version."""
    if revision.supersedes_context_digest is None:
        return ()
    reason = (
        "architecture_changed" if revision.changed_dimensions == ("architecture_contract",)
        else "capability_environment_changed" if revision.changed_dimensions == ("capability_environment",)
        else "context_superseded"
    )
    return tuple(
        RerunObligation(
            source_context_digest=revision.supersedes_context_digest,
            target_context_digest=revision.fixture_context_digest,
            cell_key=item.cell_key,
            reason=reason,
        )
        for item in classifications
        if item.fixture_context_digest == revision.supersedes_context_digest
    )
