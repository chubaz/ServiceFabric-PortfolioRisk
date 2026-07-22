from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from risk_planning import KnowledgeProduct, PlanningCatalog, ReviewDecision, load_day1_seed_catalog, load_seed_catalog


ROOT = Path(__file__).resolve().parents[2]
T0 = datetime(2026, 7, 21, 9, 0, tzinfo=UTC)
T1 = datetime(2026, 7, 22, 9, 0, tzinfo=UTC)


def day1_catalog() -> PlanningCatalog:
    return load_day1_seed_catalog(ROOT)


def test_day0_seed_loader_remains_scoped_to_all_six_day0_products() -> None:
    loaded = load_seed_catalog(ROOT)
    assert [item.knowledge_product_id for item in loaded.knowledge_products] == [f"KP-{number:02d}" for number in range(6)]
    assert all(item.planning_day == "day-0" and item.draft_deadline.anchor == "T0" for item in loaded.knowledge_products)


def test_day0_deadline_resolution_preserves_t0_keyword_compatibility() -> None:
    deadline = load_seed_catalog(ROOT).knowledge_products[0].draft_deadline
    assert deadline.at(t0=T0) == datetime(2026, 7, 21, 10, 30, tzinfo=UTC)


def test_all_day1_products_load_with_exact_t1_deadlines() -> None:
    loaded = day1_catalog()
    assert [item.knowledge_product_id for item in loaded.knowledge_products] == [f"D1-KP-{number:02d}" for number in range(1, 6)]
    assert [(item.draft_deadline.offset_minutes, item.review_deadline.offset_minutes) for item in loaded.knowledge_products] == [
        (120, 240),
        (240, 360),
        (360, 480),
        (600, 720),
        (1080, 1320),
    ]
    assert all(item.planning_day == "day-1" and item.draft_deadline.anchor == "T1" for item in loaded.knowledge_products)
    assert loaded.knowledge_products[-1].review_deadline.at(T1) == datetime(2026, 7, 23, 7, 0, tzinfo=UTC)


def test_day1_dependencies_are_acyclic_and_deterministic() -> None:
    loaded = day1_catalog()
    assert [item.knowledge_product_id for item in loaded.dependency_traversal("D1-KP-05")] == [
        "D1-KP-01",
        "D1-KP-02",
        "D1-KP-03",
        "D1-KP-04",
    ]
    reversed_catalog = PlanningCatalog(knowledge_products=tuple(reversed(loaded.knowledge_products)))
    assert [item.knowledge_product_id for item in reversed_catalog.sorted_by_draft_deadline()] == [f"D1-KP-{number:02d}" for number in range(1, 6)]


def test_catalogues_reject_mixed_t0_and_t1_products() -> None:
    day0_product = load_seed_catalog(ROOT).knowledge_products[0]
    day1_product = day1_catalog().knowledge_products[0]
    with pytest.raises(ValidationError, match="must share one planning epoch"):
        PlanningCatalog(knowledge_products=(day0_product, day1_product))


def test_day1_review_history_is_immutable_and_rejects_cross_product_decisions() -> None:
    original = day1_catalog().knowledge_products[0]
    decision = ReviewDecision(
        decision_id="D1-KP-01-R2",
        state="approved",
        decided_by="knowledge-supervisor",
        rationale="Reviewed with evidence and limitations retained.",
    )
    revised = original.record_review_decision(decision)
    assert original.status == "review_requested"
    assert len(original.review_history) == 1
    assert revised.review_history == (*original.review_history, decision)
    unrelated = ReviewDecision(
        decision_id="D1-KP-02-R2",
        state="changes_requested",
        decided_by="knowledge-supervisor",
        rationale="This decision belongs to another product.",
    )
    with pytest.raises(ValidationError, match="must belong to the knowledge product"):
        original.record_review_decision(unrelated)


def test_identifier_and_epoch_rules_do_not_weaken_day0_validation() -> None:
    payload = load_seed_catalog(ROOT).knowledge_products[0].model_dump(mode="python")
    payload["work_item_id"] = "KP-06"
    payload["knowledge_product_id"] = "KP-06"
    with pytest.raises(ValidationError):
        KnowledgeProduct.model_validate(payload)
    payload = day1_catalog().knowledge_products[0].model_dump(mode="python")
    payload["draft_deadline"]["anchor"] = "T0"
    with pytest.raises(ValidationError, match="deadline anchors must match"):
        KnowledgeProduct.model_validate(payload)
