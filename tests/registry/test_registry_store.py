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
            kind=AssetKind.AGENT,
            namespace="test.agent",
            asset_id="risk.agent.test",
            version=version,
        ),
        display_name="Test Agent",
        summary="A bounded test projection whose canonical definition remains elsewhere.",
        source=SourceReference(
            source_type="python_registry",
            source_reference="packages/example.py#AGENTS",
            source_digest="a" * 64,
            definition_digest="c" * 64,
            adapter_id="test-adapter/v1",
            adapter_digest="d" * 64,
        ),
        provenance=Provenance(
            discovered_by="test-adapter", discovered_at=observed_at
        ),
        compatibility=Compatibility(
            status="compatible",
            evaluated_source_digest="c" * 64,
            evaluator_revision="test-adapter/v1",
        ),
        source_contract="test.AgentDefinition",
        tags=("test",),
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
                adapter_id="test-adapter/v1",
                adapter_digest="d" * 64,
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


def test_document_reconstructs_when_aggregate_snapshot_is_missing(
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
    snapshot.unlink()

    assert store.get(identity) == expected
    event_files = sorted(store._events_path(identity).glob("*.json"))  # noqa: SLF001
    assert [path.name for path in event_files] == ["000001.json", "000002.json"]


def test_snapshot_replay_mismatch_fails_closed(tmp_path: Path) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    identity = projection().identity
    store.index(projection(), actor="tester")
    snapshot = store._path(identity)  # noqa: SLF001 - integrity test
    snapshot.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        store.get(identity)


def test_tampered_lifecycle_event_fails_closed(tmp_path: Path) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    identity = projection().identity
    store.index(projection(), actor="tester")
    store.transition(
        identity,
        LifecycleState.VALIDATED,
        actor="reviewer",
        rationale="Original validation receipt.",
    )
    event_path = store._events_path(identity) / "000002.json"  # noqa: SLF001
    event_path.chmod(0o600)
    value = json.loads(event_path.read_text(encoding="utf-8"))
    value["rationale"] = "Tampered after write."
    event_path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValidationError, match="digest verification failed"):
        LocalRegistryStore(store.root).get(identity)


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


def test_projection_rejects_arbitrary_or_nested_definition_payloads() -> None:
    value = projection().model_dump(mode="python")
    value["attributes"] = {"details": {"definition": {"full": "copy"}}}
    with pytest.raises(ValidationError, match="Extra inputs"):
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


def test_compare_rejects_unrelated_stable_identities(tmp_path: Path) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    first = store.index(projection(), actor="tester")
    unrelated_projection = projection(version="2.0.0").model_copy(
        update={
            "identity": RegistryIdentity(
                kind=AssetKind.CAPABILITY,
                namespace="test.capability",
                asset_id="risk.capability.unrelated",
                version="2.0.0",
            )
        }
    )
    second = store.index(unrelated_projection, actor="tester")
    with pytest.raises(RegistryConflict, match="same stable registry identity"):
        store.compare(first.projection.identity, second.projection.identity)


def test_symlink_record_is_refused(tmp_path: Path) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    store.records_root.mkdir(parents=True)
    record_path = store._path(projection().identity)  # noqa: SLF001 - safety test
    target = tmp_path / "outside.json"
    target.write_text(json.dumps({"unsafe": True}), encoding="utf-8")
    record_path.symlink_to(target)
    with pytest.raises((ValueError, RegistryConflict), match="symbolic link"):
        store.index(projection(), actor="tester")


def test_symlinked_parent_component_is_refused(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(outside, target_is_directory=True)
    store = LocalRegistryStore(alias / "registry")
    with pytest.raises(ValueError, match="path components"):
        store.index(projection(), actor="tester")


def test_symlinked_lock_file_is_refused(tmp_path: Path) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    store._ensure_safe_root()  # noqa: SLF001 - safety setup
    target = tmp_path / "outside-lock"
    target.write_text("outside", encoding="utf-8")
    (store.root / ".registry.lock").symlink_to(target)
    with pytest.raises(OSError):
        store.index(projection(), actor="tester")


def test_symlinked_event_directory_is_refused_before_projection_write(
    tmp_path: Path,
) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    store._ensure_safe_root()  # noqa: SLF001 - safety setup
    outside = tmp_path / "outside-events"
    outside.mkdir()
    events_path = store._events_path(projection().identity)  # noqa: SLF001
    events_path.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="events directory"):
        store.index(projection(), actor="tester")
    assert not store._projection_path(projection().identity).exists()  # noqa: SLF001


def test_bootstrap_conflict_prevents_every_new_write(tmp_path: Path) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    existing = projection()
    store.index(existing, actor="tester")
    conflicting = existing.model_copy(update={"summary": "Changed source observation."})
    new_projection = projection(version="2.0.0")

    indexed, conflicts = store.index_many(
        (conflicting, new_projection), actor="bootstrap-reviewer"
    )

    assert indexed == []
    assert len(conflicts) == 1
    assert len(store.list()) == 1
