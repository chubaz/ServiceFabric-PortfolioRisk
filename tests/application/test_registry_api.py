from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[2]
LABS_ROOT = ROOT / "apps" / "portfolio-risk-workbench" / "labs"
sys.path.insert(0, str(LABS_ROOT))

import duckdb_server  # noqa: E402
from risk_registry import AssetKind, LifecycleState, RegistryIdentity  # noqa: E402


def test_catalogue_preview_is_truthful_and_covers_each_kind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "registry"
    monkeypatch.setenv("PORTFOLIO_RISK_REGISTRY_ROOT", str(root))
    result = duckdb_server.registry_catalogue()
    assert result["profile"] == "development"
    assert result["production_publication"] is False
    assert result["canonical_definitions_embedded"] is False
    assert result["storage"] == "local development registry"
    assert set(result["counts"]) == {
        "agent",
        "capability",
        "evaluation",
        "report",
        "dashboard",
        "scenario",
        "workflow",
    }
    assert result["states"] == {"discovered": len(result["records"])}
    assert all(record["indexed"] is False for record in result["records"])


def test_bootstrap_is_explicit_idempotent_and_persistent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_REGISTRY_ROOT", str(tmp_path / "registry"))
    request = duckdb_server.RegistryBootstrapRequest(actor="test.reviewer")
    first = duckdb_server.bootstrap_registry(request)
    second = duckdb_server.bootstrap_registry(request)
    assert first["discovered"] == first["indexed_total"]
    assert first["newly_indexed"] == first["indexed_total"]
    assert second["discovered"] == second["indexed_total"]
    assert second["newly_indexed"] == 0
    assert second["already_indexed"] == second["indexed_total"]
    assert first["conflicts"] == second["conflicts"] == []
    catalogue = duckdb_server.registry_catalogue(include_discovered=False)
    assert len(catalogue["records"]) == first["indexed_total"]
    assert catalogue["states"] == {"candidate": first["indexed_total"]}


def test_bootstrap_preview_declares_count_and_consequence_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_REGISTRY_ROOT", str(tmp_path / "registry"))
    preview = duckdb_server.preview_registry_bootstrap(
        duckdb_server.RegistryBootstrapRequest(actor="test.reviewer")
    )
    assert preview["would_index"] == preview["discovered"] == 44
    assert preview["already_indexed"] == 0
    assert preview["conflicts"] == []
    assert "do not copy, run, deploy" in preview["consequence"]
    assert duckdb_server.registry_store().list() == []


def test_item_lifecycle_detail_and_source_drift_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_REGISTRY_ROOT", str(tmp_path / "registry"))
    bootstrap = duckdb_server.bootstrap_registry(
        duckdb_server.RegistryBootstrapRequest(actor="test.reviewer")
    )
    record = next(
        item
        for item in bootstrap["records"]
        if item["projection"]["identity"]["kind"] == "agent"
    )
    identity = record["projection"]["identity"]
    validated = duckdb_server.transition_registry_item(
        duckdb_server.RegistryTransitionRequest(
            **identity,
            to_state=LifecycleState.VALIDATED,
            actor="test.reviewer",
            rationale="The source and projection passed focused validation.",
            expected_revision=record["revision"],
        )
    )
    assert validated["state"] == "validated"
    detail = duckdb_server.registry_item(
        AssetKind(identity["kind"]),
        identity["asset_id"],
        identity["version"],
        identity["namespace"],
    )
    assert detail["source_drift"] is False
    assert len(detail["receipts"]) == 2


def test_compare_endpoint_returns_version_differences(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_REGISTRY_ROOT", str(tmp_path / "registry"))
    store = duckdb_server.registry_store()
    source = duckdb_server.discover_registry_projections()[0]
    store.index(source, actor="test.reviewer")
    second = source.model_copy(
        update={
            "identity": RegistryIdentity(
                kind=source.identity.kind,
                namespace=source.identity.namespace,
                asset_id=source.identity.asset_id,
                version="99.0.0",
            ),
            "summary": "A comparison-only second source version.",
        }
    )
    store.index(second, actor="test.reviewer")
    result = duckdb_server.compare_registry_items(
        duckdb_server.RegistryCompareRequest(
            left=source.identity, right=second.identity
        )
    )
    assert result["same_asset"] is True
    assert {difference["field"] for difference in result["differences"]} >= {
        "identity",
        "summary",
    }


def test_candidate_source_cannot_be_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_REGISTRY_ROOT", str(tmp_path / "registry"))
    candidate = next(
        item
        for item in duckdb_server.discover_registry_projections()
        if not item.source.canonical
    )
    duckdb_server.registry_store().index(candidate, actor="test.reviewer")
    identity = candidate.identity.model_dump(mode="json")
    duckdb_server.transition_registry_item(
        duckdb_server.RegistryTransitionRequest(
            **identity,
            to_state="validated",
            actor="test.reviewer",
            rationale="The candidate source is structurally valid.",
            expected_revision=duckdb_server.registry_store()
            .get(candidate.identity)
            .receipts[-1]
            .receipt_digest,
        )
    )
    with pytest.raises(HTTPException) as caught:
        duckdb_server.transition_registry_item(
            duckdb_server.RegistryTransitionRequest(
                **identity,
                to_state="published",
                actor="test.reviewer",
                rationale="Attempted candidate publication.",
                expected_revision=duckdb_server.registry_store()
                .get(candidate.identity)
                .receipts[-1]
                .receipt_digest,
            )
        )
    assert caught.value.status_code == 409
    assert "canonical definition contract" in str(caught.value.detail)


def test_lifecycle_transition_rejects_stale_review_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_REGISTRY_ROOT", str(tmp_path / "registry"))
    source = duckdb_server.discover_registry_projections()[0]
    record = duckdb_server.index_registry_item(
        duckdb_server.RegistryIndexRequest(identity=source.identity, actor="reviewer")
    )
    identity = source.identity.model_dump(mode="json")
    duckdb_server.transition_registry_item(
        duckdb_server.RegistryTransitionRequest(
            **identity,
            to_state="validated",
            actor="reviewer",
            rationale="First reviewer accepted the source observation.",
            expected_revision=record["revision"],
        )
    )
    with pytest.raises(HTTPException) as caught:
        duckdb_server.transition_registry_item(
            duckdb_server.RegistryTransitionRequest(
                **identity,
                to_state="published",
                actor="stale-reviewer",
                rationale="Stale browser attempted publication.",
                expected_revision=record["revision"],
            )
        )
    assert caught.value.status_code == 409
    assert "changed after it was reviewed" in str(caught.value.detail)


def test_registry_workspace_exposes_source_truth_and_governed_controls() -> None:
    html = (LABS_ROOT / "index.html").read_text(encoding="utf-8")
    javascript = (LABS_ROOT / "labs.js").read_text(encoding="utf-8")
    css = (LABS_ROOT / "styles.css").read_text(encoding="utf-8")
    server = (LABS_ROOT / "duckdb_server.py").read_text(encoding="utf-8")

    assert 'data-workspace="registry"' in html
    assert 'id="lab-registry"' in html
    for identifier in (
        "registry-search",
        "registry-kind-filter",
        "registry-index-filter",
        "registry-lifecycle-filter",
        "registry-index-all",
        "registry-list",
        "registry-detail",
    ):
        assert f'id="{identifier}"' in html
    assert "It does not copy, run, deploy, or externally publish" in html
    assert "function loadRegistryCatalogue" in javascript
    assert 'agentApi("/api/registry/index"' in javascript
    assert 'agentApi("/api/registry/transition"' in javascript
    assert 'agentApi("/api/registry/bootstrap/preview"' in javascript
    assert "window.confirm" in javascript
    assert "expected_revision: record.revision" in javascript
    assert "Publication is blocked" in javascript
    assert ".registry-layout" in css
    assert '"registry": {' in server
    assert "Persistent local development registry · not production publication" in server
