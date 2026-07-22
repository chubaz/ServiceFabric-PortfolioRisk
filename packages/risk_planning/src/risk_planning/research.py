"""Immutable, non-executable research and notebook catalogue contracts."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, model_validator

from .models import ImmutablePlanningModel


class ResearchStatus(str, Enum):
    PROPOSED = "proposed"
    IN_REVIEW = "in_review"
    REVIEWED = "reviewed"
    DEFERRED = "deferred"


class OperatingProfile(str, Enum):
    RESEARCH = "research"
    PERSONAL_PORTFOLIO = "personal_portfolio"


class VisibilityState(str, Enum):
    PUBLIC = "public"
    PRIVATE_LOCAL = "private_local"


class EvidenceState(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    SYNTHETIC = "synthetic"


class MethodologyReference(ImmutablePlanningModel):
    methodology_id: str = Field(pattern=r"^METH-[A-Z0-9-]+$")
    title: str = Field(min_length=1, max_length=256)
    summary: str = Field(min_length=1, max_length=2000)
    reference_uri: str = Field(min_length=1, max_length=2048)


class EvidenceLink(ImmutablePlanningModel):
    evidence_id: str = Field(pattern=r"^EVID-[A-Z0-9-]+$")
    title: str = Field(min_length=1, max_length=256)
    uri: str = Field(min_length=1, max_length=2048)
    relevance: str = Field(min_length=1, max_length=2000)


class ResearchItem(ImmutablePlanningModel):
    research_id: str = Field(pattern=r"^D1-RES-[0-9]{2}$")
    title: str = Field(min_length=1, max_length=256)
    purpose: str = Field(min_length=1, max_length=2000)
    owner: str = Field(min_length=1, max_length=256)
    status: ResearchStatus
    methodology: MethodologyReference
    inputs: tuple[str, ...] = Field(min_length=1)
    evidence: tuple[EvidenceLink, ...] = Field(min_length=1)
    assumptions: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)
    artifact_links: tuple[str, ...] = Field(min_length=1)
    profiles: tuple[OperatingProfile, ...] = Field(min_length=1)
    visibility: VisibilityState
    evidence_state: EvidenceState

    @model_validator(mode="after")
    def item_references_are_distinct(self) -> "ResearchItem":
        if len(self.evidence) != len({item.evidence_id for item in self.evidence}):
            raise ValueError("evidence IDs must be distinct within a research item")
        if len(self.profiles) != len(set(self.profiles)):
            raise ValueError("profiles must be distinct")
        if self.evidence_state == EvidenceState.PRIVATE and self.visibility != VisibilityState.PRIVATE_LOCAL:
            raise ValueError("private evidence must have private_local visibility")
        return self


class ResearchCatalogue(ImmutablePlanningModel):
    items: tuple[ResearchItem, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def identifiers_are_unique(self) -> "ResearchCatalogue":
        if len(self.items) != len({item.research_id for item in self.items}):
            raise ValueError("research IDs must be unique")
        return self

    def ordered_items(self) -> tuple[ResearchItem, ...]:
        return tuple(sorted(self.items, key=lambda item: item.research_id))


class NotebookExecutionState(str, Enum):
    CATALOGUE_ONLY = "catalogue_only"
    NOT_AVAILABLE = "not_available"


class NotebookCatalogueItem(ImmutablePlanningModel):
    notebook_id: str = Field(pattern=r"^D1-NB-[0-9]{2}$")
    title: str = Field(min_length=1, max_length=256)
    purpose: str = Field(min_length=1, max_length=2000)
    owner: str = Field(min_length=1, max_length=256)
    methodology: MethodologyReference
    inputs: tuple[str, ...] = Field(min_length=1)
    evidence: tuple[EvidenceLink, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)
    artifact_links: tuple[str, ...] = Field(min_length=1)
    future_notebook_path: str | None = Field(default=None, max_length=2048)
    execution_state: NotebookExecutionState
    execution_disclosure: str = Field(min_length=1, max_length=1000)
    profiles: tuple[OperatingProfile, ...] = Field(min_length=1)
    visibility: VisibilityState
    evidence_state: EvidenceState

    @model_validator(mode="after")
    def notebook_is_catalogue_only(self) -> "NotebookCatalogueItem":
        if len(self.evidence) != len({item.evidence_id for item in self.evidence}):
            raise ValueError("evidence IDs must be distinct within a notebook item")
        if len(self.profiles) != len(set(self.profiles)):
            raise ValueError("profiles must be distinct")
        if "not run" not in self.execution_disclosure.lower():
            raise ValueError("execution disclosure must state that the notebook is not run")
        if self.evidence_state == EvidenceState.PRIVATE and self.visibility != VisibilityState.PRIVATE_LOCAL:
            raise ValueError("private evidence must have private_local visibility")
        return self


class NotebookCatalogue(ImmutablePlanningModel):
    items: tuple[NotebookCatalogueItem, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def identifiers_are_unique(self) -> "NotebookCatalogue":
        if len(self.items) != len({item.notebook_id for item in self.items}):
            raise ValueError("notebook IDs must be unique")
        return self

    def ordered_items(self) -> tuple[NotebookCatalogueItem, ...]:
        return tuple(sorted(self.items, key=lambda item: item.notebook_id))


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    payload: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain one YAML mapping")
    return payload


def load_research_catalogue(path: Path) -> ResearchCatalogue:
    return ResearchCatalogue.model_validate(_load_yaml_mapping(path))


def load_notebook_catalogue(path: Path) -> NotebookCatalogue:
    return NotebookCatalogue.model_validate(_load_yaml_mapping(path))
