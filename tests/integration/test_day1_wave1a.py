"""Cross-lane acceptance contract for the Day 1 Wave 1A Workbench."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from fastapi import FastAPI


ROOT = Path(__file__).resolve().parents[2]
APPLICATION_DIR = ROOT / "apps" / "portfolio-risk-workbench"
USER_PAGES = (
    "/",
    "/portfolio",
    "/risk",
    "/findings",
    "/alerts",
    "/data",
    "/providers",
    "/research",
    "/notebooks",
    "/agents",
    "/agent-runs",
    "/plan",
    "/settings",
)
NAVIGATION = (
    "Dashboard",
    "Portfolio",
    "Risk",
    "Findings",
    "Alerts",
    "Data",
    "Providers",
    "Research",
    "Notebooks",
    "Agents",
    "Plan",
    "Settings",
)
JSON_APIS = ("/api/status", "/api/findings", "/api/alerts", "/api/agent-runs")
PROHIBITED_ROUTE_TERMS = ("broker", "order", "trade", "rebalance")


@pytest.fixture(autouse=True)
def data_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_DATA_ROOT", str(tmp_path / "risk-data"))


@pytest.fixture
def application() -> FastAPI:
    spec = importlib.util.spec_from_file_location("day1_wave1a_workbench", APPLICATION_DIR / "app.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def route(app: FastAPI, method: str, path: str):
    return next(item for item in app.routes if item.path == path and method in getattr(item, "methods", set()))


def rendered(app: FastAPI, path: str, *, profile: str = "research") -> str:
    response = route(app, "GET", path).endpoint(profile=profile)
    assert response.status_code == 200
    assert response.media_type == "text/html"
    return response.body.decode()


def test_wave_1a_user_pages_are_html_with_complete_safe_navigation(application: FastAPI) -> None:
    for path in USER_PAGES:
        body = rendered(application, path)
        assert body.startswith("<!doctype html>")
        assert '<main id="main-content" tabindex="-1">' in body
        assert "application/json" not in body.lower()
        for label in NAVIGATION:
            assert f">{label}</a>" in body
        assert "Research profile" in body
        assert "Synthetic · reviewed public fixture" in body
        assert "Human review required" in body


def test_wave_1a_profiles_json_evidence_and_execution_boundaries(application: FastAPI) -> None:
    personal = rendered(application, "/settings", profile="personal_portfolio")
    assert "Personal portfolio" in personal
    assert "Private · local · no publication" in personal

    for path in JSON_APIS:
        payload = route(application, "GET", path).endpoint()
        assert isinstance(payload, dict)

    run = route(application, "POST", "/actions/monitoring-run").endpoint()
    assert run["status"] == "succeeded"
    evidence = rendered(application, "/agent-runs")
    assert "Evidence inspection only" in evidence
    assert "Evidence, assumptions, warnings, and limitations" in evidence

    notebooks = rendered(application, "/notebooks")
    providers = rendered(application, "/providers")
    paths = {item.path.lower() for item in application.routes}
    assert "Notebook execution is prohibited" in notebooks
    assert "All external providers are disabled" in providers
    assert not any(path.startswith("/notebooks/") for path in paths)
    assert not any("provider" in path and ("enable" in path or "connect" in path) for path in paths)
    assert not any(term in path for path in paths for term in PROHIBITED_ROUTE_TERMS)


def test_wave_1a_manifest_declares_all_templates_and_static_assets() -> None:
    manifest = json.loads((APPLICATION_DIR / "servicefabric-package.json").read_text(encoding="utf-8"))
    declared = {entry["path"] for entry in manifest["source_files"]}
    required = {
        path.relative_to(APPLICATION_DIR).as_posix()
        for directory in (APPLICATION_DIR / "templates", APPLICATION_DIR / "static")
        for path in directory.rglob("*")
        if path.is_file()
    }
    assert required <= declared
