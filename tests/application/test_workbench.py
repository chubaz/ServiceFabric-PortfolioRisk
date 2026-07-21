from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from fastapi import FastAPI


ROOT = Path(__file__).resolve().parents[2]
APPLICATION_DIR = ROOT / "apps" / "portfolio-risk-workbench"


@pytest.fixture(scope="module")
def application() -> FastAPI:
    spec = importlib.util.spec_from_file_location("portfolio_risk_workbench", APPLICATION_DIR / "app.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def request(application: FastAPI, method: str, path: str) -> tuple[int, bytes]:
    route = next(
        route
        for route in application.routes
        if route.path == path and method in getattr(route, "methods", set())
    )
    result = route.endpoint()
    if isinstance(result, dict):
        return 200, json.dumps(result).encode()
    return result.status_code, result.body


@pytest.fixture(autouse=True)
def temporary_data_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_DATA_ROOT", str(tmp_path / "risk-data"))


def test_health(application: FastAPI) -> None:
    status, body = request(application, "GET", "/health")
    assert status == 200
    assert json.loads(body) == {"status": "healthy"}


def test_status_action(application: FastAPI) -> None:
    status, body = request(application, "POST", "/actions/status")
    assert status == 200
    assert json.loads(body) == {
        "application_id": "portfolio-risk-workbench",
        "version": "0.1.0",
        "synthetic_mode": True,
        "external_providers": "disabled",
        "human_review": "required",
    }


def test_api_status(application: FastAPI) -> None:
    status, body = request(application, "GET", "/api/status")
    assert status == 200
    assert json.loads(body)["synthetic_mode"] is True


@pytest.mark.parametrize("path", ["/", "/plan", "/data", "/portfolio", "/findings", "/agents"])
def test_pages_are_available_and_disclose_synthetic_mode(application: FastAPI, path: str) -> None:
    status, body = request(application, "GET", path)
    assert status == 200
    assert b"Wave 0B is a local synthetic prototype." in body


def test_manifest_source_files_exist_and_hashes_match() -> None:
    manifest = json.loads((APPLICATION_DIR / "servicefabric-package.json").read_text())
    for entry in manifest["source_files"]:
        source = APPLICATION_DIR / entry["path"]
        assert source.is_file()
        assert entry["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_manifest_declares_only_reviewed_loopback_hosting() -> None:
    manifest = json.loads((APPLICATION_DIR / "servicefabric-package.json").read_text())
    assert manifest["adapter"] == "reviewed-fastapi-v1"
    assert manifest["start"] == {"adapter": "reviewed-fastapi-v1", "module": "app:app"}
    assert manifest["declared_resources"]["network"] == "loopback-only"
    assert manifest["public_hosting"] is False
    assert manifest["declared_resources"]["memory_mib"] <= 256


def test_no_order_or_broker_route_exists(application: FastAPI) -> None:
    paths = {route.path for route in application.routes}
    assert not any("order" in path or "broker" in path for path in paths)


def test_wave_0b_api_and_action_routes(application: FastAPI) -> None:
    assert request(application, "GET", "/api/plan")[0] == 200
    assert request(application, "POST", "/actions/planning-list-due")[0] == 200
    assert request(application, "GET", "/api/datasets")[0] == 200
    assert request(application, "POST", "/actions/data-synthetic-ingest")[0] == 200
    assert request(application, "GET", "/api/datasets")[0] == 200
    assert request(application, "POST", "/actions/portfolio-snapshot-create")[0] == 200
    assert request(application, "GET", "/api/portfolio/latest")[0] == 200
    assert request(application, "POST", "/actions/portfolio-exposure-summarize")[0] == 200
    assert request(application, "GET", "/api/exposures/latest")[0] == 200
    assert request(application, "POST", "/actions/market-anomaly-detect")[0] == 200
    findings_status, findings_body = request(application, "GET", "/api/findings")
    assert findings_status == 200
    assert json.loads(findings_body)["human_review_required"] is True
