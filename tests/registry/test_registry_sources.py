from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LABS_ROOT = ROOT / "apps" / "portfolio-risk-workbench" / "labs"
sys.path.insert(0, str(LABS_ROOT))

from registry_sources import discover_registry_projections  # noqa: E402


def test_discovery_surfaces_all_initial_asset_kinds_from_existing_sources() -> None:
    items = discover_registry_projections(
        discovered_at=datetime(2026, 8, 3, tzinfo=timezone.utc)
    )
    counts = Counter(item.identity.kind.value for item in items)
    assert set(counts) == {
        "agent",
        "capability",
        "evaluation",
        "report",
        "dashboard",
        "scenario",
        "workflow",
    }
    assert counts == {
        "agent": 4,
        "capability": 29,
        "evaluation": 1,
        "report": 3,
        "dashboard": 1,
        "scenario": 3,
        "workflow": 3,
    }
    assert len(items) == 44
    assert len(items) == len({item.identity.reference for item in items})


def test_every_projection_points_to_a_real_source_without_embedding_it() -> None:
    for item in discover_registry_projections():
        assert item.source.source_reference
        assert len(item.source.source_digest) == 64
        assert len(item.source.definition_digest) == 64
        assert len(item.source.adapter_digest) == 64
        assert item.provenance.repository_commit
        assert item.identity.namespace
        assert item.source_contract
        source_path = item.source.source_reference.split("#", 1)[0]
        assert (ROOT / source_path).is_file()
        assert not hasattr(item, "attributes")
        assert "Indexed metadata only" in item.provenance.notes[0]


def test_relationships_resolve_to_exact_registry_revisions() -> None:
    items = discover_registry_projections()
    references = {item.identity.reference for item in items}
    relationships = [edge for item in items for edge in item.relationships]
    assert relationships
    assert all(edge.resolution in {"resolved", "unavailable"} for edge in relationships)
    assert all(
        edge.target_reference in references
        for edge in relationships
        if edge.resolution == "resolved"
    )
    assert all(reference in references for item in items for reference in item.lineage)


def test_only_reviewed_role_and_capability_contracts_are_canonical() -> None:
    items = discover_registry_projections()
    canonical = {item.identity.kind.value for item in items if item.source.canonical}
    candidate = {item.identity.kind.value for item in items if not item.source.canonical}
    assert canonical == {"agent", "capability"}
    assert candidate == {"evaluation", "report", "dashboard", "scenario", "workflow"}
