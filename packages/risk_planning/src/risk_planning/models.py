"""Pydantic v2 contracts for immutable Day 0 planning records."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ImmutablePlanningModel(BaseModel):
    """Strict, frozen base for persisted planning records."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class ReviewState(str, Enum):
    DRAFT = "draft"
    REVIEW_REQUESTED = "review_requested"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class Deadline(ImmutablePlanningModel):
    """A deterministic deadline measured from the shared Day 0 anchor."""

    anchor: Literal["T0"] = "T0"
    offset_minutes: int = Field(ge=0)


class WorkItem(ImmutablePlanningModel):
    work_item_id: str = Field(pattern=r"^[A-Z]{2,}-[0-9]{2}(?:-[A-Z0-9]+)*$")
    title: str = Field(min_length=1, max_length=256)
    purpose: str = Field(min_length=1, max_length=2000)
    owner_lane: Literal["planning"] = "planning"
    status: ReviewState = ReviewState.DRAFT
    dependencies: tuple[str, ...] = ()


class SourceReferenceLink(ImmutablePlanningModel):
    reference_id: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]*$")
    title: str = Field(min_length=1, max_length=256)
    uri: str = Field(min_length=1, max_length=2048)
    relevance: str = Field(min_length=1, max_length=2000)


class ReviewDecision(ImmutablePlanningModel):
    """An append-only review event; updates create a new knowledge product value."""

    decision_id: str = Field(pattern=r"^[A-Z]{2}-[0-9]{2}-R[0-9]+$")
    state: ReviewState
    decided_by: str = Field(min_length=1, max_length=256)
    rationale: str = Field(min_length=1, max_length=2000)


class KnowledgeProduct(WorkItem):
    knowledge_product_id: str = Field(pattern=r"^KP-[0-9]{2}$")
    draft_deadline: Deadline
    review_deadline: Deadline
    acceptance_criteria: tuple[str, ...] = Field(min_length=1)
    source_references: tuple[SourceReferenceLink, ...] = ()
    artifact_paths: tuple[str, ...] = Field(min_length=1)
    review_history: tuple[ReviewDecision, ...] = ()

    @model_validator(mode="after")
    def product_invariants(self) -> "KnowledgeProduct":
        if self.work_item_id != self.knowledge_product_id:
            raise ValueError("work_item_id must equal knowledge_product_id")
        if self.review_deadline.offset_minutes < self.draft_deadline.offset_minutes:
            raise ValueError("review deadline must not precede draft deadline")
        if len(self.dependencies) != len(set(self.dependencies)):
            raise ValueError("dependencies must be distinct")
        if len(self.source_references) != len({item.reference_id for item in self.source_references}):
            raise ValueError("source reference IDs must be distinct")
        if len(self.review_history) != len({item.decision_id for item in self.review_history}):
            raise ValueError("review decision IDs must be distinct")
        decision_prefix = f"{self.knowledge_product_id}-R"
        if any(not item.decision_id.startswith(decision_prefix) for item in self.review_history):
            raise ValueError("review decision IDs must belong to the knowledge product")
        return self

    def record_review_decision(self, decision: ReviewDecision) -> "KnowledgeProduct":
        """Return a revised value with an appended review decision, never mutating history."""
        payload = self.model_dump(mode="python")
        payload["status"] = decision.state
        payload["review_history"] = (*self.review_history, decision)
        return self.model_validate(payload)


class PlanningCatalog(ImmutablePlanningModel):
    knowledge_products: tuple[KnowledgeProduct, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def catalog_references_are_valid(self) -> "PlanningCatalog":
        identifiers = [item.knowledge_product_id for item in self.knowledge_products]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("knowledge product IDs must be unique")
        known = set(identifiers)
        unknown = sorted({dependency for item in self.knowledge_products for dependency in item.dependencies if dependency not in known})
        if unknown:
            raise ValueError(f"unknown knowledge product dependencies: {', '.join(unknown)}")
        dependencies_by_id = {item.knowledge_product_id: item.dependencies for item in self.knowledge_products}
        visited: set[str] = set()
        active: set[str] = set()

        def visit(knowledge_product_id: str) -> None:
            if knowledge_product_id in active:
                raise ValueError("knowledge product dependencies must be acyclic")
            if knowledge_product_id in visited:
                return
            active.add(knowledge_product_id)
            for dependency in dependencies_by_id[knowledge_product_id]:
                visit(dependency)
            active.remove(knowledge_product_id)
            visited.add(knowledge_product_id)

        for knowledge_product_id in sorted(dependencies_by_id):
            visit(knowledge_product_id)
        return self

    def sorted_by_draft_deadline(self) -> tuple[KnowledgeProduct, ...]:
        return tuple(sorted(self.knowledge_products, key=lambda item: (item.draft_deadline.offset_minutes, item.knowledge_product_id)))
