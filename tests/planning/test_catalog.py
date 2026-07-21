from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from risk_planning import KnowledgeProduct, PlanningCatalog, ReviewDecision, SourceReferenceLink, load_seed_catalog


ROOT = Path(__file__).resolve().parents[2]
T0 = datetime(2026, 7, 21, 9, 0, tzinfo=UTC)


def catalog() -> PlanningCatalog:
    return load_seed_catalog(ROOT)


def test_loads_all_deterministic_seed_objects() -> None:
    loaded = catalog()
    assert [item.knowledge_product_id for item in loaded.knowledge_products] == [f"KP-{number:02d}" for number in range(6)]
    assert all(item.draft_deadline.anchor == "T0" for item in loaded.knowledge_products)


def test_duplicate_ids_are_rejected() -> None:
    loaded = catalog()
    with pytest.raises(ValidationError, match="must be unique"):
        PlanningCatalog(knowledge_products=(loaded.knowledge_products[0], loaded.knowledge_products[0]))


def test_invalid_review_state_is_rejected() -> None:
    payload = catalog().knowledge_products[0].model_dump(mode="python")
    payload["status"] = "published"
    with pytest.raises(ValidationError):
        KnowledgeProduct.model_validate(payload)


def test_dependency_references_are_validated() -> None:
    loaded = catalog()
    broken = loaded.knowledge_products[1].model_copy(update={"dependencies": ("KP-99",)})
    with pytest.raises(ValidationError, match="unknown knowledge product dependencies: KP-99"):
        PlanningCatalog(knowledge_products=(loaded.knowledge_products[0], broken))


def test_cyclic_dependency_references_are_rejected() -> None:
    loaded = catalog()
    first = loaded.knowledge_products[0].model_copy(update={"dependencies": ("KP-01",)})
    second = loaded.knowledge_products[1].model_copy(update={"dependencies": ("KP-00",)})
    with pytest.raises(ValidationError, match="dependencies must be acyclic"):
        PlanningCatalog(knowledge_products=(first, second))


def test_deadlines_sort_deterministically() -> None:
    loaded = catalog()
    reversed_catalog = PlanningCatalog(knowledge_products=tuple(reversed(loaded.knowledge_products)))
    assert [item.knowledge_product_id for item in reversed_catalog.sorted_by_draft_deadline()] == [f"KP-{number:02d}" for number in range(6)]


def test_review_queue_and_due_computation_use_supplied_t0() -> None:
    loaded = catalog()
    first = loaded.knowledge_products[0].record_review_decision(
        ReviewDecision(decision_id="KP-00-R1", state="review_requested", decided_by="planning-supervisor", rationale="Ready for review.")
    )
    second = loaded.knowledge_products[1].record_review_decision(
        ReviewDecision(decision_id="KP-01-R1", state="changes_requested", decided_by="planning-supervisor", rationale="Clarify the adapter boundary.")
    )
    queued = PlanningCatalog(knowledge_products=(first, second))
    assert [item.knowledge_product_id for item in queued.review_queue()] == ["KP-00", "KP-01"]
    assert [item.knowledge_product_id for item in queued.due_for_review(T0, datetime(2026, 7, 21, 12, 0, tzinfo=UTC))] == ["KP-00"]


def test_overdue_computation_excludes_approved_products() -> None:
    first = catalog().knowledge_products[0].record_review_decision(
        ReviewDecision(decision_id="KP-00-R1", state="review_requested", decided_by="planning-supervisor", rationale="Ready for review.")
    )
    overdue_catalog = PlanningCatalog(knowledge_products=(first,))
    assert [item.knowledge_product_id for item in overdue_catalog.overdue(T0, datetime(2026, 7, 21, 12, 1, tzinfo=UTC))] == ["KP-00"]
    approved = first.record_review_decision(
        ReviewDecision(decision_id="KP-00-R2", state="approved", decided_by="planning-supervisor", rationale="Approved after review.")
    )
    assert PlanningCatalog(knowledge_products=(approved,)).overdue(T0, datetime(2026, 7, 21, 12, 1, tzinfo=UTC)) == ()


def test_dependency_traversal_and_blocking_are_deterministic() -> None:
    loaded = catalog()
    assert [item.knowledge_product_id for item in loaded.dependency_traversal("KP-05")] == ["KP-00", "KP-01", "KP-02", "KP-03", "KP-04"]
    assert loaded.is_dependency_blocked("KP-01")
    approved = loaded.knowledge_products[0].record_review_decision(
        ReviewDecision(decision_id="KP-00-R1", state="approved", decided_by="planning-supervisor", rationale="Approved prerequisite.")
    )
    unblocked = PlanningCatalog(knowledge_products=(approved, loaded.knowledge_products[1]))
    assert unblocked.blocking_dependencies("KP-01") == ()


def test_review_decisions_are_recorded_immutably() -> None:
    product = catalog().knowledge_products[0]
    decision = ReviewDecision(decision_id="KP-00-R1", state="review_requested", decided_by="planning-supervisor", rationale="Ready for bounded review.")
    revised = product.record_review_decision(decision)
    assert product.status == "draft"
    assert product.review_history == ()
    assert revised.status == "review_requested"
    assert revised.review_history == (decision,)
    with pytest.raises(ValidationError):
        revised.review_history = ()  # type: ignore[misc]


def test_review_decision_must_belong_to_its_knowledge_product() -> None:
    product = catalog().knowledge_products[1]
    unrelated = ReviewDecision(decision_id="KP-00-R1", state="review_requested", decided_by="planning-supervisor", rationale="Incorrectly attributed review.")
    with pytest.raises(ValidationError, match="must belong to the knowledge product"):
        product.record_review_decision(unrelated)


def test_source_references_are_preserved() -> None:
    product = catalog().knowledge_products[2]
    reference = product.source_references[0]
    assert reference == SourceReferenceLink(
        reference_id="ADR-0002",
        title="Day 0 runtime and storage conventions",
        uri="docs/architecture/adr/0002-day0-runtime-and-storage.md",
        relevance="Supplies immutable, UTC, Decimal, and synthetic-data conventions.",
    )


def test_artifact_links_traceability_and_implementation_status_are_preserved() -> None:
    product = catalog().knowledge_products[2]
    assert product.artifact_links[0].path == product.artifact_paths[0]
    assert product.implementation_status == "implemented"
    assert product.thesis_traceability[0].evidence_reference_ids == ("ADR-0002",)
    payload = product.model_dump(mode="python")
    payload["thesis_traceability"][0]["evidence_reference_ids"] = ("MISSING-REF",)
    with pytest.raises(ValidationError, match="unknown thesis evidence references"):
        KnowledgeProduct.model_validate(payload)
