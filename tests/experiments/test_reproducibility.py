from datetime import UTC, datetime

from risk_experiments import (
    LocalReproducibilityStore, build_bundle_manifest, canonical_digest,
)


def test_bundle_is_content_verified_and_lifecycle_is_recoverable(tmp_path) -> None:
    comparison = {"matrix_id": "matrix-one", "status": "valid"}
    files = {
        "comparison.json": (b'{"status":"valid"}', "application/json", "system"),
        "supervisor-report.md": (b"# Result\n", "text/markdown", "supervisor"),
    }
    manifest = build_bundle_manifest(
        matrix_id="matrix-one", case_id="case-one", comparison=comparison,
        files=files, exact_versions={"evaluator": "v1"}, created_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    store = LocalReproducibilityStore(tmp_path)
    saved = store.save(manifest, {name: item[0] for name, item in files.items()})
    assert saved.verified is True
    assert canonical_digest(comparison) == manifest.comparison_digest
    assert store.archive(manifest.bundle_id).state == "archived"
    assert store.restore(manifest.bundle_id).state == "active"
    removed = store.remove(manifest.bundle_id, confirmation=manifest.bundle_id)
    assert removed.state == "removed"
