"""Pydantic v2 contracts for immutable Day 0 and Day 1 planning records."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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


class ImplementationStatus(str, Enum):
    PLANNED = "planned"
    PARTIAL = "partial"
    IMPLEMENTED = "implemented"


class Deadline(ImmutablePlanningModel):
    """A deterministic deadline measured from an explicitly supplied epoch."""

    anchor: Literal["T0", "T1"] = "T0"
    offset_minutes: int = Field(ge=0)

    def at(self, t0: datetime) -> datetime:
        """Resolve this deadline from an explicit epoch, preserving the Day 0 keyword."""
        if t0.tzinfo is None or t0.utcoffset() is None:
            raise ValueError(f"{self.anchor} must be timezone-aware")
        return t0.astimezone(UTC) + timedelta(minutes=self.offset_minutes)


class WorkItem(ImmutablePlanningModel):
    work_item_id: str = Field(pattern=r"^(?:[A-Z]{2,}-[0-9]{2}(?:-[A-Z0-9]+)*|D1-KP-0[1-5])$")
    title: str = Field(min_length=1, max_length=256)
    purpose: str = Field(min_length=1, max_length=2000)
    owner_lane: Literal["planning", "knowledge"] = "planning"
    status: ReviewState = ReviewState.DRAFT
    dependencies: tuple[str, ...] = ()


class SourceReferenceLink(ImmutablePlanningModel):
    reference_id: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]*$")
    title: str = Field(min_length=1, max_length=256)
    uri: str = Field(min_length=1, max_length=2048)
    relevance: str = Field(min_length=1, max_length=2000)


class ArtifactLink(ImmutablePlanningModel):
    artifact_id: str = Field(pattern=r"^(?:KP-0[0-5]|D1-KP-0[1-5])-A[0-9]+$")
    path: str = Field(min_length=1, max_length=2048)
    label: str = Field(min_length=1, max_length=256)
    purpose: str = Field(min_length=1, max_length=2000)


class ThesisTraceabilityEntry(ImmutablePlanningModel):
    entry_id: str = Field(pattern=r"^(?:KP-0[0-5]|D1-KP-0[1-5])-T[0-9]+$")
    thesis: str = Field(min_length=1, max_length=2000)
    evidence_reference_ids: tuple[str, ...] = Field(min_length=1)
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = Field(min_length=1)


class ReviewDecision(ImmutablePlanningModel):
    """An append-only review event; updates create a new knowledge product value."""

    decision_id: str = Field(pattern=r"^(?:KP-0[0-5]|D1-KP-0[1-5])-R[0-9]+$")
    state: ReviewState
    decided_by: str = Field(min_length=1, max_length=256)
    rationale: str = Field(min_length=1, max_length=2000)


class KnowledgeProduct(WorkItem):
    knowledge_product_id: str = Field(pattern=r"^(?:KP-0[0-5]|D1-KP-0[1-5])$")
    planning_day: Literal["day-0", "day-1"] = "day-0"
    draft_deadline: Deadline
    review_deadline: Deadline
    acceptance_criteria: tuple[str, ...] = Field(min_length=1)
    source_references: tuple[SourceReferenceLink, ...] = ()
    artifact_paths: tuple[str, ...] = Field(min_length=1)
    artifact_links: tuple[ArtifactLink, ...] = Field(min_length=1)
    thesis_traceability: tuple[ThesisTraceabilityEntry, ...] = ()
    implementation_status: ImplementationStatus
    implementation_summary: str = Field(min_length=1, max_length=2000)
    review_history: tuple[ReviewDecision, ...] = ()

    @model_validator(mode="after")
    def product_invariants(self) -> "KnowledgeProduct":
        if self.work_item_id != self.knowledge_product_id:
            raise ValueError("work_item_id must equal knowledge_product_id")
        is_day_1 = self.knowledge_product_id.startswith("D1-")
        expected_day = "day-1" if is_day_1 else "day-0"
        expected_anchor = "T1" if is_day_1 else "T0"
        expected_lane = "knowledge" if is_day_1 else "planning"
        if self.planning_day != expected_day:
            raise ValueError("planning_day must match the knowledge product epoch")
        if self.draft_deadline.anchor != expected_anchor or self.review_deadline.anchor != expected_anchor:
            raise ValueError("deadline anchors must match the knowledge product epoch")
        if self.owner_lane != expected_lane:
            raise ValueError("owner_lane must match the knowledge product epoch")
        if self.review_deadline.offset_minutes < self.draft_deadline.offset_minutes:
            raise ValueError("review deadline must not precede draft deadline")
        if len(self.dependencies) != len(set(self.dependencies)):
            raise ValueError("dependencies must be distinct")
        if len(self.source_references) != len({item.reference_id for item in self.source_references}):
            raise ValueError("source reference IDs must be distinct")
        if len(self.artifact_links) != len({item.artifact_id for item in self.artifact_links}):
            raise ValueError("artifact link IDs must be distinct")
        if {item.path for item in self.artifact_links} != set(self.artifact_paths):
            raise ValueError("artifact links must cover exactly the artifact paths")
        if len(self.thesis_traceability) != len({item.entry_id for item in self.thesis_traceability}):
            raise ValueError("thesis traceability IDs must be distinct")
        known_references = {item.reference_id for item in self.source_references}
        traceability_unknown = sorted({reference_id for entry in self.thesis_traceability for reference_id in entry.evidence_reference_ids if reference_id not in known_references})
        if traceability_unknown:
            raise ValueError(f"unknown thesis evidence references: {', '.join(traceability_unknown)}")
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

    def is_review_due(self, t0: datetime, as_of: datetime) -> bool:
        return as_of.astimezone(UTC) >= self.review_deadline.at(t0)

    def is_overdue(self, t0: datetime, as_of: datetime) -> bool:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        return self.status not in {ReviewState.APPROVED, ReviewState.SUPERSEDED} and as_of.astimezone(UTC) > self.review_deadline.at(t0)


class PlanningCatalog(ImmutablePlanningModel):
    knowledge_products: tuple[KnowledgeProduct, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def catalog_references_are_valid(self) -> "PlanningCatalog":
        identifiers = [item.knowledge_product_id for item in self.knowledge_products]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("knowledge product IDs must be unique")
        planning_days = {item.planning_day for item in self.knowledge_products}
        if len(planning_days) != 1:
            raise ValueError("knowledge products in a catalogue must share one planning epoch")
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

    def dependency_traversal(self, knowledge_product_id: str) -> tuple[KnowledgeProduct, ...]:
        """Return transitive dependencies in deterministic dependency-first order."""
        products_by_id = {item.knowledge_product_id: item for item in self.knowledge_products}
        if knowledge_product_id not in products_by_id:
            raise KeyError(knowledge_product_id)
        traversed: list[KnowledgeProduct] = []
        seen: set[str] = set()

        def visit(current_id: str) -> None:
            for dependency_id in sorted(products_by_id[current_id].dependencies):
                if dependency_id not in seen:
                    visit(dependency_id)
                    seen.add(dependency_id)
                    traversed.append(products_by_id[dependency_id])

        visit(knowledge_product_id)
        return tuple(traversed)

    def blocking_dependencies(self, knowledge_product_id: str) -> tuple[KnowledgeProduct, ...]:
        return tuple(item for item in self.dependency_traversal(knowledge_product_id) if item.status != ReviewState.APPROVED)

    def is_dependency_blocked(self, knowledge_product_id: str) -> bool:
        return bool(self.blocking_dependencies(knowledge_product_id))

    def review_queue(self) -> tuple[KnowledgeProduct, ...]:
        queued = (item for item in self.knowledge_products if item.status in {ReviewState.REVIEW_REQUESTED, ReviewState.CHANGES_REQUESTED})
        return tuple(sorted(queued, key=lambda item: (item.review_deadline.offset_minutes, item.knowledge_product_id)))

    def due_for_review(self, t0: datetime, as_of: datetime) -> tuple[KnowledgeProduct, ...]:
        return tuple(item for item in self.review_queue() if item.is_review_due(t0, as_of))

    def overdue(self, t0: datetime, as_of: datetime) -> tuple[KnowledgeProduct, ...]:
        return tuple(sorted((item for item in self.knowledge_products if item.is_overdue(t0, as_of)), key=lambda item: (item.review_deadline.offset_minutes, item.knowledge_product_id)))
