from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from risk_artifacts import (
    ArtifactConflict,
    ArtifactKind,
    ArtifactLifecycleState,
    ArtifactManifest,
    DataTruthClass,
    LocalArtifactRepository,
    PreviewMode,
    PublicationState,
    RetentionClass,
    RightsState,
    file_manifest,
)


NOW = datetime(2026, 8, 3, 9, 0, tzinfo=timezone.utc)


def artifact(content: bytes = b"# Review\n", *, artifact_id: str = "artifact-test-001",
             retention: RetentionClass = RetentionClass.RUN_RETAINED,
             publication: PublicationState = PublicationState.RESTRICTED) -> tuple[ArtifactManifest, dict[str, bytes]]:
    item = file_manifest(
        path="review.md",
        content=content,
        media_type="text/markdown",
        role="rendered_report",
        preview_mode=PreviewMode.ESCAPED_TEXT,
        download_allowed=True,
    )
    manifest = ArtifactManifest(
        artifact_id=artifact_id,
        title="Test review",
        kind=ArtifactKind.REPORT,
        created_at=NOW,
        created_by="test.reviewer",
        creation_method="tests.fixture",
        data_truth=DataTruthClass.SYNTHETIC_SAMPLE,
        rights=RightsState.INTERNAL,
        rights_policy_id="internal.research.v1",
        publication=publication,
        retention=retention,
        entry_file=item.path,
        files=(item,),
        total_size_bytes=len(content),
    )
    return manifest, {item.path: content}


def test_admission_is_immutable_idempotent_and_digest_verified(tmp_path):
    repository = LocalArtifactRepository(tmp_path / "artifacts")
    manifest, files = artifact()
    first = repository.admit(manifest, files, actor="test.reviewer", occurred_at=NOW)
    second = repository.admit(manifest, files, actor="different.actor", occurred_at=NOW)
    assert first == second
    assert first.state == ArtifactLifecycleState.ACTIVE
    assert repository.verify(manifest.artifact_id).valid
    with pytest.raises(ArtifactConflict, match="different immutable content"):
        changed, changed_files = artifact(b"changed")
        repository.admit(changed, changed_files, actor="test.reviewer", occurred_at=NOW)


def test_archive_restore_and_expected_revision(tmp_path):
    repository = LocalArtifactRepository(tmp_path / "artifacts")
    manifest, files = artifact()
    admitted = repository.admit(manifest, files, actor="test.reviewer", occurred_at=NOW)
    archived = repository.transition(
        manifest.artifact_id,
        to_state=ArtifactLifecycleState.ARCHIVED,
        actor="test.reviewer",
        rationale="The run is no longer active.",
        expected_revision=admitted.revision,
        occurred_at=NOW + timedelta(minutes=1),
    )
    assert archived.state == ArtifactLifecycleState.ARCHIVED
    with pytest.raises(ArtifactConflict, match="changed after"):
        repository._append_receipt(  # noqa: SLF001 - adversarial expected-revision test
            archived,
            operation="restore",
            to_state=ArtifactLifecycleState.ACTIVE,
            actor="test.reviewer",
            rationale="Restore for review.",
            expected_revision=admitted.revision,
            occurred_at=NOW + timedelta(minutes=2),
        )
    restored = repository.transition(
        manifest.artifact_id,
        to_state=ArtifactLifecycleState.ACTIVE,
        actor="test.reviewer",
        rationale="Restore for review.",
        expected_revision=archived.revision,
        occurred_at=NOW + timedelta(minutes=2),
    )
    assert restored.state == ArtifactLifecycleState.ACTIVE


def test_tombstone_recovery_and_manual_finalization(tmp_path):
    repository = LocalArtifactRepository(tmp_path / "artifacts")
    manifest, files = artifact()
    admitted = repository.admit(manifest, files, actor="test.reviewer", occurred_at=NOW)
    preview = repository.deletion_preview(manifest.artifact_id, now=NOW)
    assert preview.eligible
    tombstoned = repository.tombstone(
        manifest.artifact_id,
        confirmation_token=preview.confirmation_token,
        expected_revision=preview.expected_revision,
        actor="test.reviewer",
        rationale="Remove this disposable synthetic test.",
        occurred_at=NOW,
    )
    assert tombstoned.state == ArtifactLifecycleState.TOMBSTONED
    early = repository.deletion_preview(
        manifest.artifact_id, finalize=True, now=NOW + timedelta(days=6)
    )
    assert not early.eligible
    final = repository.deletion_preview(
        manifest.artifact_id, finalize=True, now=NOW + timedelta(days=8)
    )
    assert final.eligible
    deleted = repository.finalize_delete(
        manifest.artifact_id,
        confirmation_token=final.confirmation_token,
        expected_revision=final.expected_revision,
        actor="test.reviewer",
        rationale="Recovery elapsed; permanently remove unshared bytes.",
        occurred_at=NOW + timedelta(days=8),
    )
    assert deleted.state == ArtifactLifecycleState.DELETED
    assert repository.list() == ()
    assert repository.list(include_deleted=True)[0].state == ArtifactLifecycleState.DELETED


def test_published_and_evidence_locked_records_cannot_be_deleted(tmp_path):
    repository = LocalArtifactRepository(tmp_path / "artifacts")
    published, files = artifact(
        artifact_id="artifact-published-001",
        retention=RetentionClass.PUBLISHED,
        publication=PublicationState.PUBLISHED,
    )
    repository.admit(published, files, actor="test.reviewer", occurred_at=NOW)
    assert "published artifacts deny ordinary deletion" in repository.deletion_preview(
        published.artifact_id, now=NOW
    ).blockers
    locked, locked_files = artifact(
        artifact_id="artifact-locked-001", retention=RetentionClass.EVIDENCE_LOCKED
    )
    repository.admit(locked, locked_files, actor="test.reviewer", occurred_at=NOW)
    assert "evidence-locked artifacts deny ordinary deletion" in repository.deletion_preview(
        locked.artifact_id, now=NOW
    ).blockers


def test_shared_blob_survives_one_artifact_finalization(tmp_path):
    repository = LocalArtifactRepository(tmp_path / "artifacts")
    first, files = artifact(artifact_id="artifact-shared-001")
    second, second_files = artifact(artifact_id="artifact-shared-002")
    repository.admit(first, files, actor="test.reviewer", occurred_at=NOW)
    repository.admit(second, second_files, actor="test.reviewer", occurred_at=NOW)
    preview = repository.deletion_preview(first.artifact_id, now=NOW)
    tombstoned = repository.tombstone(
        first.artifact_id,
        confirmation_token=preview.confirmation_token,
        expected_revision=preview.expected_revision,
        actor="test.reviewer",
        rationale="Remove one owner only.",
        occurred_at=NOW,
    )
    final = repository.deletion_preview(
        first.artifact_id, finalize=True, now=NOW + timedelta(days=8)
    )
    repository.finalize_delete(
        first.artifact_id,
        confirmation_token=final.confirmation_token,
        expected_revision=tombstoned.revision,
        actor="test.reviewer",
        rationale="Retain the shared byte for its active owner.",
        occurred_at=NOW + timedelta(days=8),
    )
    assert repository.verify(second.artifact_id).valid


def test_shared_blob_survives_while_another_owner_is_recoverably_tombstoned(tmp_path):
    repository = LocalArtifactRepository(tmp_path / "artifacts")
    first, files = artifact(artifact_id="artifact-shared-tombstone-001")
    second, second_files = artifact(artifact_id="artifact-shared-tombstone-002")
    repository.admit(first, files, actor="test.reviewer", occurred_at=NOW)
    repository.admit(second, second_files, actor="test.reviewer", occurred_at=NOW)
    tombstoned = []
    for item in (first, second):
        preview = repository.deletion_preview(item.artifact_id, now=NOW)
        tombstoned.append(
            repository.tombstone(
                item.artifact_id,
                confirmation_token=preview.confirmation_token,
                expected_revision=preview.expected_revision,
                actor="test.reviewer",
                rationale="Recoverable shared-content test.",
                occurred_at=NOW,
            )
        )
    final = repository.deletion_preview(
        first.artifact_id, finalize=True, now=NOW + timedelta(days=8)
    )
    repository.finalize_delete(
        first.artifact_id,
        confirmation_token=final.confirmation_token,
        expected_revision=tombstoned[0].revision,
        actor="test.reviewer",
        rationale="Finalize one owner while preserving the recoverable owner.",
        occurred_at=NOW + timedelta(days=8),
    )
    restored = repository.restore_tombstone(
        second.artifact_id,
        actor="test.reviewer",
        rationale="Restore the remaining owner before its recovery deadline.",
        expected_revision=tombstoned[1].revision,
        occurred_at=NOW + timedelta(days=6),
    )
    assert restored.state == ArtifactLifecycleState.ACTIVE
    assert repository.verify(second.artifact_id).valid


def test_symlink_repository_root_and_tampered_blob_fail_closed(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic links"):
        LocalArtifactRepository(alias).list()
    repository = LocalArtifactRepository(tmp_path / "safe")
    manifest, files = artifact()
    repository.admit(manifest, files, actor="test.reviewer", occurred_at=NOW)
    blob = repository._blob_path(manifest.files[0].content_digest)  # noqa: SLF001
    blob.chmod(0o600)
    blob.write_bytes(b"tampered")
    assert not repository.verify(manifest.artifact_id).valid
    assert not repository.deletion_preview(manifest.artifact_id, now=NOW).eligible
