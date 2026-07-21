from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from risk_planning import NotebookCatalogue, NotebookCatalogueItem, ResearchCatalogue, ResearchItem, load_notebook_catalogue, load_research_catalogue


ROOT = Path(__file__).resolve().parents[2]


def research_catalogue() -> ResearchCatalogue:
    return load_research_catalogue(ROOT / "docs" / "research" / "catalog.yaml")


def notebook_catalogue() -> NotebookCatalogue:
    return load_notebook_catalogue(ROOT / "notebooks" / "catalog" / "catalog.yaml")


def test_reviewed_research_catalogue_loads_and_orders_deterministically() -> None:
    loaded = research_catalogue()
    assert [item.research_id for item in loaded.items] == ["D1-RES-01", "D1-RES-02", "D1-RES-03"]
    assert all(item.status == "reviewed" for item in loaded.items)
    reversed_catalogue = ResearchCatalogue(items=tuple(reversed(loaded.items)))
    assert [item.research_id for item in reversed_catalogue.ordered_items()] == ["D1-RES-01", "D1-RES-02", "D1-RES-03"]


def test_research_items_require_evidence_assumptions_limitations_and_artifacts() -> None:
    payload = research_catalogue().items[0].model_dump(mode="python")
    for field in ("evidence", "assumptions", "limitations", "artifact_links"):
        broken = dict(payload)
        broken[field] = ()
        with pytest.raises(ValidationError):
            ResearchItem.model_validate(broken)


def test_profile_visibility_and_public_private_synthetic_states_are_explicit() -> None:
    loaded = research_catalogue()
    assert [(item.profiles[0].value, item.visibility.value, item.evidence_state.value) for item in loaded.items] == [
        ("research", "public", "public"),
        ("research", "public", "synthetic"),
        ("personal_portfolio", "private_local", "private"),
    ]
    payload = loaded.items[-1].model_dump(mode="python")
    payload["visibility"] = "public"
    with pytest.raises(ValidationError, match="private evidence must have private_local visibility"):
        ResearchItem.model_validate(payload)


def test_notebook_catalogue_is_metadata_only_and_deterministic() -> None:
    loaded = notebook_catalogue()
    assert {item.execution_state.value for item in loaded.items} == {"catalogue_only", "not_available"}
    assert all("not run" in item.execution_disclosure.lower() for item in loaded.items)
    reversed_catalogue = NotebookCatalogue(items=tuple(reversed(loaded.items)))
    assert [item.notebook_id for item in reversed_catalogue.ordered_items()] == ["D1-NB-01", "D1-NB-02", "D1-NB-03"]


def test_notebook_contract_exposes_no_execution_path_or_command_fields() -> None:
    public_methods = {name for name in dir(NotebookCatalogueItem) if not name.startswith("_")}
    assert not public_methods.intersection({"execute", "run", "run_notebook", "shell", "kernel", "query"})
    serialized_keys = set().union(*(item.model_dump().keys() for item in notebook_catalogue().items))
    assert not serialized_keys.intersection({"command", "shell", "python", "sql", "kernel", "code"})
    payload = notebook_catalogue().items[0].model_dump(mode="python")
    payload["command"] = "python future.ipynb"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        NotebookCatalogueItem.model_validate(payload)


def test_notebook_evidence_limitations_and_not_run_disclosure_are_required() -> None:
    payload = notebook_catalogue().items[0].model_dump(mode="python")
    for field in ("evidence", "limitations"):
        broken = dict(payload)
        broken[field] = ()
        with pytest.raises(ValidationError):
            NotebookCatalogueItem.model_validate(broken)
    payload["execution_disclosure"] = "Future catalogue entry."
    with pytest.raises(ValidationError, match="must state that the notebook is not run"):
        NotebookCatalogueItem.model_validate(payload)
