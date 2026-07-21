from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException


ROOT = Path(__file__).resolve().parents[2]
APPLICATION_DIR = ROOT / "apps" / "portfolio-risk-workbench"


@pytest.fixture(autouse=True)
def data_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_DATA_ROOT", str(tmp_path / "risk-data"))


@pytest.fixture
def application() -> FastAPI:
    spec = importlib.util.spec_from_file_location("workbench", APPLICATION_DIR / "app.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def call(app: FastAPI, method: str, path: str, **kwargs: object) -> object:
    route = next(item for item in app.routes if item.path == path and method in getattr(item, "methods", set()))
    return route.endpoint(**kwargs)


@pytest.mark.parametrize("path", ["/", "/plan", "/data", "/portfolio", "/findings", "/alerts", "/agents", "/agent-runs", "/research", "/notebooks"])
def test_pages_are_synthetic_catalogues(application: FastAPI, path: str) -> None:
    response = call(application, "GET", path)
    assert response.status_code == 200
    assert b"local synthetic prototype" in response.body


def test_monitoring_alert_detail_and_review_decisions(application: FastAPI) -> None:
    run = call(application, "POST", "/actions/monitoring-run")
    assert run["status"] == "succeeded"
    alerts = call(application, "GET", "/api/alerts")["alerts"]
    alert_id = alerts[0]["alert_id"]
    assert call(application, "GET", "/api/alerts/{alert_id}", alert_id=alert_id)["alert"]["alert_id"] == alert_id
    for decision in ("approve", "reject", "request_changes"):
        review = call(application, "POST", "/actions/alert-draft-review", reviewer="reviewer-1", decision=decision)
        assert review["effects"] == []
        assert review["data"]["decision_point"]["decision"] == decision
    assert call(application, "GET", "/api/agent-runs")["agent_runs"]
    assert call(application, "GET", "/api/findings")["findings"]


def test_review_requires_reviewer(application: FastAPI) -> None:
    call(application, "POST", "/actions/alert-draft-synthesize")
    with pytest.raises(HTTPException) as error:
        call(application, "POST", "/actions/alert-draft-review", decision="approve")
    assert error.value.status_code == 422


def test_news_and_alert_actions_have_no_effects(application: FastAPI) -> None:
    assert call(application, "POST", "/actions/news-event-classify")["effects"] == []
    assert call(application, "POST", "/actions/alert-draft-synthesize")["effects"] == []


def test_manifest_hashes_and_no_broker_or_order_endpoint(application: FastAPI) -> None:
    manifest = json.loads((APPLICATION_DIR / "servicefabric-package.json").read_text())
    for item in manifest["source_files"]:
        assert item["sha256"] == hashlib.sha256((APPLICATION_DIR / item["path"]).read_bytes()).hexdigest()
    paths = {route.path for route in application.routes}
    assert not any("broker" in path or "order" in path for path in paths)
