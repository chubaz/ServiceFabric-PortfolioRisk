from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from risk_registry import (
    AssetKind,
    Compatibility,
    LifecycleState,
    LocalRegistryStore,
    Provenance,
    RegistryConflict,
    RegistryIdentity,
    RegistryProjection,
    SourceReference,
)


NOW = datetime(2026, 8, 3, tzinfo=timezone.utc)


def projection(*, version: str = "1.0.0", observed_at: datetime = NOW) -> RegistryProjection:
    return RegistryProjection(
        identity=RegistryIdentity(
            kind=AssetKind.AGENT, asset_id="risk.agent.test", version=version
        ),
        display_name="Test Agent",
        summary="A bounded test projection whose canonical definition remains elsewhere.",
        source=SourceReference(
            source_type="python_registry",
            source_reference="packages/example.py#AGENTS",
            source_digest="a" * 64,
            definition_digest="c" * 64,
        ),
        provenance=Provenance(
            discovered_by="test-adapter", discovered_at=observed_at
        ),
        compatibility=Compatibility(status="compatible"),
        tags=("test",),
        attributes={"input_contract": "TestInput"},
    )


def test_index_is_idempotent_across_fresh_discovery_timestamps(tmp_path: Path) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    first = store.index(projection(), actor="tester")
    second = store.index(
        projection(observed_at=NOW + timedelta(minutes=5)), actor="tester"
    )
    assert second == first
    assert len(list((tmp_path / "registry" / "records").glob("*.json"))) == 1
    assert first.state is LifecycleState.CANDIDATE


def test_changed_source_observation_conflicts_instead_of_overwriting(tmp_path: Path) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    store.index(projection(), actor="tester")
    changed = projection().model_copy(
        update={
            "source": SourceReference(
                source_type="python_registry",
                source_reference="packages/example.py#AGENTS",
                source_digest="b" * 64,
                definition_digest="d" * 64,
            )
        }
    )
    with pytest.raises(RegistryConflict, match="different source observation"):
        store.index(changed, actor="tester")


def test_raw_file_change_with_same_definition_digest_is_idempotent(tmp_path: Path) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    first = store.index(projection(), actor="tester")
    value = projection().model_dump(mode="python")
    value["source"] = {**value["source"], "source_digest": "b" * 64}
    rescanned = RegistryProjection.model_validate(value)
    assert store.index(rescanned, actor="tester") == first


def test_lifecycle_is_validated_and_receipts_are_append_only(tmp_path: Path) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    identity = projection().identity
    store.index(projection(), actor="tester")
    with pytest.raises(RegistryConflict, match="candidate -> published"):
        store.transition(
            identity,
            LifecycleState.PUBLISHED,
            actor="tester",
            rationale="Invalid shortcut",
        )
    validated = store.transition(
        identity,
        LifecycleState.VALIDATED,
        actor="reviewer",
        rationale="Contract and source checks passed.",
    )
    published = store.transition(
        identity,
        LifecycleState.PUBLISHED,
        actor="publisher",
        rationale="Approved for the local development catalogue.",
    )
    assert [receipt.to_state for receipt in published.receipts] == [
        LifecycleState.CANDIDATE,
        LifecycleState.VALIDATED,
        LifecycleState.PUBLISHED,
    ]
    assert validated.projection == published.projection


def test_document_reconstructs_from_immutable_projection_and_events(
    tmp_path: Path,
) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    identity = projection().identity
    store.index(projection(), actor="tester")
    expected = store.transition(
        identity,
        LifecycleState.VALIDATED,
        actor="reviewer",
        rationale="Contract and source checks passed.",
    )

    snapshot = store._path(identity)  # noqa: SLF001 - recovery test
    snapshot.write_text("{}\n", encoding="utf-8")

    assert store.get(identity) == expected
    event_files = sorted(store._events_path(identity).glob("*.json"))  # noqa: SLF001
    assert [path.name for path in event_files] == ["000001.json", "000002.json"]


def test_deprecation_requires_replacement_reference(tmp_path: Path) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    identity = projection().identity
    store.index(projection(), actor="tester")
    store.transition(identity, LifecycleState.VALIDATED, actor="tester", rationale="validated")
    store.transition(identity, LifecycleState.PUBLISHED, actor="tester", rationale="published")
    with pytest.raises(ValidationError, match="replacement reference"):
        store.transition(
            identity,
            LifecycleState.DEPRECATED,
            actor="tester",
            rationale="Superseded",
        )


def test_projection_rejects_embedded_definition_payload() -> None:
    value = projection().model_dump(mode="python")
    value["attributes"] = {"manifest": {"full": "copy"}}
    with pytest.raises(ValidationError, match="may not embed"):
        RegistryProjection.model_validate(value)


def test_compare_reports_metadata_differences(tmp_path: Path) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    first = store.index(projection(version="1.0.0"), actor="tester")
    second_projection = projection(version="2.0.0").model_copy(
        update={"summary": "A changed source-compatible summary for version two."}
    )
    second = store.index(second_projection, actor="tester")
    comparison = store.compare(
        first.projection.identity, second.projection.identity
    )
    assert comparison["same_asset"] is True
    assert {item["field"] for item in comparison["differences"]} >= {
        "identity",
        "summary",
    }


def test_symlink_record_is_refused(tmp_path: Path) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    store.records_root.mkdir(parents=True)
    record_path = store._path(projection().identity)  # noqa: SLF001 - safety test
    target = tmp_path / "outside.json"
    target.write_text(json.dumps({"unsafe": True}), encoding="utf-8")
    record_path.symlink_to(target)
    with pytest.raises((ValueError, RegistryConflict), match="symbolic link"):
        store.index(projection(), actor="tester")
