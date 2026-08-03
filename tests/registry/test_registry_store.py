from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from risk_registry import (
    AssetKind,
    Compatibility,
    LifecycleReceipt,
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


def test_recomputed_lifecycle_event_cannot_replace_anchored_receipt(
    tmp_path: Path,
) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    identity = projection().identity
    store.index(projection(), actor="tester")
    current = store.transition(
        identity,
        LifecycleState.VALIDATED,
        actor="reviewer",
        rationale="Original validation receipt.",
    )
    original = current.receipts[-1]
    replacement = LifecycleReceipt.create(
        registry_reference=original.registry_reference,
        sequence=original.sequence,
        from_state=original.from_state,
        to_state=original.to_state,
        actor=original.actor,
        rationale="A validly recomputed but unauthorized replacement.",
        occurred_at=original.occurred_at,
        prior_receipt_digest=original.prior_receipt_digest,
    )
    event_path = store._events_path(identity) / "000002.json"  # noqa: SLF001
    event_path.chmod(0o600)
    event_path.write_text(replacement.model_dump_json(indent=2) + "\n", encoding="utf-8")
    store._path(identity).unlink()  # noqa: SLF001 - prove snapshot is not the anchor

    with pytest.raises(RegistryConflict, match="integrity anchor mismatch"):
        LocalRegistryStore(store.root).get(identity)


def test_lifecycle_event_filename_gaps_fail_closed(tmp_path: Path) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    identity = projection().identity
    store.index(projection(), actor="tester")
    store.transition(
        identity,
        LifecycleState.VALIDATED,
        actor="reviewer",
        rationale="Contract and source checks passed.",
    )
    events_path = store._events_path(identity)  # noqa: SLF001
    (events_path / "000002.json").rename(events_path / "000003.json")

    with pytest.raises(RegistryConflict, match="contiguous sequence"):
        LocalRegistryStore(store.root).get(identity)


def test_missing_committed_event_stream_cannot_fall_back_to_snapshot(
    tmp_path: Path,
) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    identity = projection().identity
    store.index(projection(), actor="tester")
    events_path = store._events_path(identity)  # noqa: SLF001
    events_path.rename(store.root / "removed-events")

    with pytest.raises(RegistryConflict, match="event stream is missing"):
        LocalRegistryStore(store.root).get(identity)


def test_valid_replacement_projection_cannot_escape_catalogue_anchor(
    tmp_path: Path,
) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    identity = projection().identity
    store.index(projection(), actor="tester")
    store.transition(
        identity,
        LifecycleState.VALIDATED,
        actor="reviewer",
        rationale="Contract and source checks passed.",
    )
    changed_source = projection().source.model_copy(
        update={"definition_digest": "e" * 64}
    )
    changed_compatibility = projection().compatibility.model_copy(
        update={"evaluated_source_digest": "e" * 64}
    )
    replacement = projection().model_copy(
        update={
            "summary": "A validly encoded but unauthorized replacement projection.",
            "source": changed_source,
            "compatibility": changed_compatibility,
        }
    )
    projection_path = store._projection_path(identity)  # noqa: SLF001
    projection_path.chmod(0o600)
    projection_path.write_text(
        replacement.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    store._path(identity).unlink()  # noqa: SLF001 - remove derived snapshot only

    with pytest.raises(RegistryConflict, match="projection.*catalogue anchor"):
        LocalRegistryStore(store.root).get(identity)


def test_interrupted_transition_remains_available_and_exact_retry_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    identity = projection().identity
    store.index(projection(), actor="tester")

    def fail_catalog_commit(entries: dict[str, dict[str, str]]) -> None:
        raise OSError("injected catalogue commit failure")

    monkeypatch.setattr(store, "_write_catalog", fail_catalog_commit)
    with pytest.raises(OSError, match="injected catalogue commit failure"):
        store.transition(
            identity,
            LifecycleState.VALIDATED,
            actor="reviewer",
            rationale="Contract and source checks passed.",
        )

    restarted = LocalRegistryStore(store.root)
    assert restarted.get(identity).state is LifecycleState.CANDIDATE
    assert restarted.list()[0].state is LifecycleState.CANDIDATE
    assert restarted.index(projection(), actor="bootstrap-reviewer").state is (
        LifecycleState.CANDIDATE
    )
    with pytest.raises(RegistryConflict, match="retried exactly"):
        restarted.transition(
            identity,
            LifecycleState.VALIDATED,
            actor="different-reviewer",
            rationale="Contract and source checks passed.",
        )

    recovered = restarted.transition(
        identity,
        LifecycleState.VALIDATED,
        actor="reviewer",
        rationale="Contract and source checks passed.",
    )
    assert recovered.state is LifecycleState.VALIDATED
    assert len(recovered.receipts) == 2


def test_transition_retry_is_idempotent_when_catalogue_commit_completed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    identity = projection().identity
    store.index(projection(), actor="tester")
    original_write_catalog = store._write_catalog  # noqa: SLF001 - fault injection

    def commit_then_report_failure(entries: dict[str, dict[str, str]]) -> None:
        original_write_catalog(entries)
        raise OSError("injected post-commit reporting failure")

    monkeypatch.setattr(store, "_write_catalog", commit_then_report_failure)
    with pytest.raises(OSError, match="post-commit reporting failure"):
        store.transition(
            identity,
            LifecycleState.VALIDATED,
            actor="reviewer",
            rationale="Contract and source checks passed.",
        )

    restarted = LocalRegistryStore(store.root)
    recovered = restarted.transition(
        identity,
        LifecycleState.VALIDATED,
        actor="reviewer",
        rationale="Contract and source checks passed.",
    )
    assert recovered.state is LifecycleState.VALIDATED
    assert len(recovered.receipts) == 2


def test_transition_recovers_when_event_is_durable_before_its_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    identity = projection().identity
    store.index(projection(), actor="tester")

    def fail_anchor_write(path: Path, value: str) -> None:
        raise OSError("injected anchor write failure")

    monkeypatch.setattr(store, "_write_immutable_text", fail_anchor_write)
    with pytest.raises(OSError, match="anchor write failure"):
        store.transition(
            identity,
            LifecycleState.VALIDATED,
            actor="reviewer",
            rationale="Contract and source checks passed.",
        )

    restarted = LocalRegistryStore(store.root)
    assert restarted.get(identity).state is LifecycleState.CANDIDATE
    recovered = restarted.transition(
        identity,
        LifecycleState.VALIDATED,
        actor="reviewer",
        rationale="Contract and source checks passed.",
    )
    assert recovered.state is LifecycleState.VALIDATED
    assert len(recovered.receipts) == 2


def test_index_recovers_when_initial_event_is_durable_before_its_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = LocalRegistryStore(tmp_path / "registry")

    def fail_anchor_write(path: Path, value: str) -> None:
        raise OSError("injected anchor write failure")

    monkeypatch.setattr(store, "_write_immutable_text", fail_anchor_write)
    with pytest.raises(OSError, match="anchor write failure"):
        store.index(projection(), actor="tester")
    assert store.list() == []

    restarted = LocalRegistryStore(store.root)
    with pytest.raises(RegistryConflict, match="exact source set and intent"):
        restarted.index(projection(), actor="different-indexer")
    recovered = restarted.index(projection(), actor="tester")
    assert recovered.state is LifecycleState.CANDIDATE
    assert len(restarted.list()) == 1


def test_interrupted_explicit_timestamp_index_requires_exact_timestamp_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = LocalRegistryStore(tmp_path / "registry")

    def fail_anchor_write(path: Path, value: str) -> None:
        raise OSError("injected anchor write failure")

    monkeypatch.setattr(store, "_write_immutable_text", fail_anchor_write)
    with pytest.raises(OSError, match="anchor write failure"):
        store.index(
            projection(),
            actor="tester",
            rationale="Explicitly timed index.",
            occurred_at=NOW,
        )

    restarted = LocalRegistryStore(store.root)
    with pytest.raises(RegistryConflict, match="exact source set and intent"):
        restarted.index(
            projection(),
            actor="tester",
            rationale="Explicitly timed index.",
        )
    with pytest.raises(RegistryConflict, match="exact source set and intent"):
        restarted.index(
            projection(),
            actor="tester",
            rationale="Changed rationale.",
            occurred_at=NOW,
        )
    recovered = restarted.index(
        projection(),
        actor="tester",
        rationale="Explicitly timed index.",
        occurred_at=NOW,
    )
    assert recovered.receipts[0].occurred_at == NOW


def test_journal_only_interruption_binds_semantic_source_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    original_write = store._write_immutable  # noqa: SLF001 - fault injection

    def fail_projection_write(path: Path, value: object) -> None:
        if isinstance(value, RegistryProjection):
            raise OSError("injected projection write failure")
        original_write(path, value)  # type: ignore[arg-type]

    monkeypatch.setattr(store, "_write_immutable", fail_projection_write)
    with pytest.raises(OSError, match="projection write failure"):
        store.index(projection(), actor="tester")

    changed_source = projection().source.model_copy(
        update={"definition_digest": "f" * 64}
    )
    changed_compatibility = projection().compatibility.model_copy(
        update={"evaluated_source_digest": "f" * 64}
    )
    changed = projection().model_copy(
        update={
            "summary": "Changed source.",
            "source": changed_source,
            "compatibility": changed_compatibility,
        }
    )
    monkeypatch.setattr(store, "_write_immutable", original_write)
    with pytest.raises(RegistryConflict, match="exact source set and intent"):
        store.index(changed, actor="tester")
    assert store.list() == []

    recovered = store.index(projection(), actor="tester")
    assert recovered.projection.summary == projection().summary


def test_missing_committed_receipt_anchor_fails_closed(tmp_path: Path) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    identity = projection().identity
    store.index(projection(), actor="tester")
    anchor_path = store._anchors_path(identity) / "000001.sha256"  # noqa: SLF001
    anchor_path.rename(store.root / "removed-anchor.sha256")

    with pytest.raises(RegistryConflict, match="no safe integrity anchor"):
        LocalRegistryStore(store.root).get(identity)


def test_failed_immutable_staging_never_exposes_partial_final_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "events" / "000001.json"

    def fail_flush(descriptor: int) -> None:
        raise OSError("injected staging flush failure")

    monkeypatch.setattr(os, "fsync", fail_flush)
    with pytest.raises(OSError, match="staging flush failure"):
        LocalRegistryStore._write_exclusive_bytes(target, b"partial")  # noqa: SLF001

    assert not target.exists()
    assert list(target.parent.iterdir()) == []


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


def test_bootstrap_write_failure_exposes_no_partial_catalogue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    requested = (projection(), projection(version="2.0.0"))
    original_write = store._write_immutable  # noqa: SLF001 - fault injection
    projection_writes = 0

    def fail_on_second_projection(path: Path, value: object) -> None:
        nonlocal projection_writes
        if isinstance(value, RegistryProjection):
            projection_writes += 1
            if projection_writes == 2:
                raise OSError("injected durable-write failure")
        original_write(path, value)  # type: ignore[arg-type]

    monkeypatch.setattr(store, "_write_immutable", fail_on_second_projection)
    with pytest.raises(OSError, match="injected durable-write failure"):
        store.index_many(requested, actor="bootstrap-reviewer")

    assert store.list() == []
    monkeypatch.setattr(store, "_write_immutable", original_write)
    with pytest.raises(RegistryConflict, match="exact source set and intent"):
        store.index_many((requested[0],), actor="bootstrap-reviewer")
    assert store.list() == []
    with pytest.raises(RegistryConflict, match="exact source set and intent"):
        store.index_many(requested, actor="different-bootstrap-reviewer")
    indexed, conflicts = store.index_many(requested, actor="bootstrap-reviewer")
    assert conflicts == []
    assert len(indexed) == 2
    assert len(store.list()) == 2


def test_interrupted_mixed_batch_rejects_committed_subset_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = LocalRegistryStore(tmp_path / "registry")
    existing = projection()
    missing = projection(version="2.0.0")
    store.index(existing, actor="initial-indexer")
    original_index_locked = store._index_locked  # noqa: SLF001 - fault injection

    def fail_new_item(
        item: RegistryProjection,
        *,
        actor: str,
        rationale: str,
        occurred_at: datetime | None,
    ) -> object:
        if item.identity == missing.identity:
            raise OSError("injected new-item failure")
        return original_index_locked(
            item,
            actor=actor,
            rationale=rationale,
            occurred_at=occurred_at,
        )

    monkeypatch.setattr(store, "_index_locked", fail_new_item)
    with pytest.raises(OSError, match="new-item failure"):
        store.index_many((existing, missing), actor="bootstrap-reviewer")
    with pytest.raises(RegistryConflict, match="exact source set and intent"):
        store.index_many((existing,), actor="bootstrap-reviewer")
    assert [item.projection.identity for item in store.list()] == [existing.identity]

    monkeypatch.setattr(store, "_index_locked", original_index_locked)
    indexed, conflicts = store.index_many(
        (existing, missing), actor="bootstrap-reviewer"
    )
    assert conflicts == []
    assert len(indexed) == 2
