from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException


ROOT = Path(__file__).resolve().parents[2]
APPLICATION_DIR = ROOT / "apps" / "portfolio-risk-workbench"
PACKAGE_PATHS = (
    "apps/portfolio-risk-workbench/app.py",
    "apps/portfolio-risk-workbench/presentation.py",
    "apps/portfolio-risk-workbench/pyproject.toml",
    "apps/portfolio-risk-workbench/risk-package-lock.json",
)
PAGES = (
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
    "/plan",
    "/settings",
    "/agent-runs",
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


def html(app: FastAPI, path: str, **kwargs: object) -> str:
    response = call(app, "GET", path, **kwargs)
    assert response.status_code == 200
    return response.body.decode()


@pytest.mark.parametrize("path", PAGES)
def test_every_page_is_semantic_human_readable_html(application: FastAPI, path: str) -> None:
    body = html(application, path)
    assert body.startswith("<!doctype html>")
    assert '<html lang="en">' in body
    assert '<header class="site-header">' in body
    assert '<nav class="primary-nav" aria-label="Primary navigation">' in body
    assert '<main id="main-content" tabindex="-1">' in body
    assert "<footer>" in body
    assert body.count("<h1>") == 1
    assert body.index("<h1>") < body.index("<h2")
    assert "<pre" not in body.lower()
    assert "application/json" not in body.lower()


@pytest.mark.parametrize("path", PAGES)
def test_navigation_profile_data_and_review_badges_are_persistent(application: FastAPI, path: str) -> None:
    body = html(application, path)
    for label in NAVIGATION:
        assert f">{label}</a>" in body
    assert "Research profile" in body
    assert "Synthetic · reviewed public fixture" in body
    assert "As-of evidence · no live refresh" in body
    assert "Human review required" in body
    assert 'class="skip-link" href="#main-content"' in body
    assert ":focus-visible" in (APPLICATION_DIR / "static" / "workbench.css").read_text()


def test_dashboard_and_portfolio_render_day0_snapshot_metrics(application: FastAPI) -> None:
    dashboard = html(application, "/")
    portfolio = html(application, "/portfolio")
    assert "Net asset value" in dashboard
    assert "Largest position" in dashboard
    assert "Pending review" in dashboard
    assert "No trading or investment advice" in dashboard
    assert "synthetic-portfolio-20260717" in portfolio
    assert "instrument-alpha" in portfolio
    assert "USD 1,000.00" in portfolio
    assert "Portfolio import arrives in Wave 1B" in portfolio


def test_risk_page_separates_exposure_from_unimplemented_analytics(application: FastAPI) -> None:
    body = html(application, "/risk")
    assert "Current Day 0 exposure arithmetic" in body
    assert "Position weights" in body
    assert 'role="img" aria-label=' in body
    widths = [float(value) for value in re.findall(r'style="width: ([0-9.]+)%"', body)]
    assert widths and all(0 <= value <= 100 for value in widths)
    assert "Risk analytics arrive in Wave 1C" in body
    assert "not VaR, stress testing, factor analysis, a forecast" in body


def test_profile_selection_is_local_private_and_profile_aware(application: FastAPI) -> None:
    settings = html(application, "/settings", profile="personal_portfolio")
    research = html(application, "/research", profile="personal_portfolio")
    notebooks = html(application, "/notebooks", profile="personal_portfolio")
    assert "Personal portfolio" in settings
    assert "Private · local · no publication" in settings
    assert 'value="personal_portfolio" checked' in settings
    assert "no broker connection" in settings
    assert "D1-RES-03" in research
    assert "D1-RES-02" not in research
    assert "D1-NB-03" in notebooks
    assert "D1-NB-01" not in notebooks


def test_research_default_profile_uses_reviewed_catalogue(application: FastAPI) -> None:
    body = html(application, "/research")
    assert "D1-RES-01" in body
    assert "D1-RES-02" in body
    assert "D1-RES-03" not in body
    assert "Methodology" in body
    assert "Evidence, assumptions, warnings, and limitations" in body
    assert "Day 1 screen contracts" in body
    assert "docs/design/day1-screen-contracts.md" in body
    assert "Defines required content and safe interactions" in body
    assert "{&#39;" not in body and "{'" not in body


def test_plan_binds_both_reviewed_planning_epochs(application: FastAPI) -> None:
    body = html(application, "/plan")
    assert "KP-00" in body and "KP-05" in body
    assert "D1-KP-01" in body and "D1-KP-05" in body
    assert "T0 +" in body and "T1 +" in body
    assert "Dependencies" in body and "Review status" in body
    assert "integration pending" not in body.lower()


def test_notebooks_are_catalogue_only_with_no_execution_surface(application: FastAPI) -> None:
    body = html(application, "/notebooks")
    assert "D1-NB-01" in body and "D1-NB-02" in body
    assert body.count("Not Executable") >= 1 or body.count("Not executable") >= 1
    assert "not run" in body
    assert "Risk analytics methodology and limitations" in body
    assert "docs/knowledge-products/D1-KP-03-risk-analytics-methodology-and-limitations.md" in body
    assert "{&#39;" not in body and "{'" not in body
    assert "<form" not in body
    assert "<button" not in body
    paths = {route.path for route in application.routes}
    assert not any(path.startswith("/notebooks/") for path in paths)


def test_providers_are_disabled_and_have_no_enablement_surface(application: FastAPI) -> None:
    body = html(application, "/providers")
    assert "All external providers are disabled" in body
    assert "no enable button" in body.lower()
    assert "<form" not in body
    assert "<button" not in body
    paths = {route.path.lower() for route in application.routes}
    assert not any("provider" in path and ("enable" in path or "connect" in path) for path in paths)


def test_empty_and_error_states_do_not_turn_missing_into_zero(application: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    assert "No findings recorded" in html(application, "/findings")
    assert "does not mean risk is zero" in html(application, "/findings")
    assert "No alert drafts" in html(application, "/alerts")
    data_body = html(application, "/data")
    assert "Missing values" in data_body
    assert "never represented as zero" in data_body
    assert "None" not in data_body
    data_route = next(item for item in application.routes if item.path == "/data" and "GET" in item.methods)
    currency_filter = data_route.endpoint.__globals__["render_page"].__globals__["currency"]
    percentage_filter = data_route.endpoint.__globals__["render_page"].__globals__["percentage"]
    assert currency_filter(None) == percentage_filter(None) == "Not available"

    monkeypatch.setitem(data_route.endpoint.__globals__, "records", lambda: (_ for _ in ()).throw(OSError("unavailable")))
    error_body = html(application, "/data")
    assert 'role="alert"' in error_body
    assert "has been treated as zero" in error_body

    monkeypatch.setitem(data_route.endpoint.__globals__, "records", lambda: ())
    empty_body = html(application, "/data")
    assert 'role="alert"' in empty_body
    assert "Dataset summary is unavailable" in empty_body
    assert "Market observations</h2>" not in empty_body


def test_alert_page_distinguishes_missing_from_unavailable_evidence(application: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = call(application, "GET", "/alerts/{alert_id}", alert_id="missing-alert")
    assert missing.status_code == 404
    assert "Alert not found" in missing.body.decode()

    route = next(item for item in application.routes if item.path == "/alerts/{alert_id}" and "GET" in item.methods)
    monkeypatch.setitem(
        route.endpoint.__globals__,
        "api_alert",
        lambda alert_id: (_ for _ in ()).throw(HTTPException(409, "data root unavailable")),
    )
    unavailable = call(application, "GET", "/alerts/{alert_id}", alert_id="unknown")
    body = unavailable.body.decode()
    assert unavailable.status_code == 409
    assert "Alert evidence unavailable" in body
    assert "could not be accessed" in body
    assert "Alert not found" not in body


def test_monitoring_alert_detail_and_review_decisions_are_effect_free(application: FastAPI) -> None:
    run = call(application, "POST", "/actions/monitoring-run")
    assert run["status"] == "succeeded"
    alerts = call(application, "GET", "/api/alerts")["alerts"]
    alert_id = alerts[0]["alert_id"]
    assert call(application, "GET", "/api/alerts/{alert_id}", alert_id=alert_id)["alert"]["alert_id"] == alert_id
    detail = html(application, "/alerts/{alert_id}", alert_id=alert_id)
    assert '<form method="post"' in detail
    assert 'name="reviewer" required' in detail
    assert 'name="decision" value="approve" required' in detail
    assert "Approval does not authorize a trade" in detail
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


def test_review_form_records_only_a_local_decision(application: FastAPI) -> None:
    call(application, "POST", "/actions/alert-draft-synthesize")
    alert_id = call(application, "GET", "/api/alerts")["alerts"][0]["alert_id"]
    response = call(
        application,
        "POST",
        "/alerts/{alert_id}/review",
        alert_id=alert_id,
        reviewer="reviewer-form",
        decision="approve",
        comment="Evidence reviewed.",
        profile="research",
    )
    assert response.status_code == 303
    decisions = call(application, "GET", "/api/alerts/{alert_id}", alert_id=alert_id)["decisions"]
    assert decisions[-1]["decision"] == "approve"
    assert decisions[-1]["human_reviewer_id"] == "reviewer-form"


def test_json_apis_and_day0_capabilities_are_preserved(application: FastAPI) -> None:
    expected = {
        ("GET", "/health"),
        ("GET", "/api/status"),
        ("GET", "/api/findings"),
        ("GET", "/api/alerts"),
        ("GET", "/api/alerts/{alert_id}"),
        ("GET", "/api/agent-runs"),
        ("POST", "/actions/status"),
        ("POST", "/actions/portfolio-exposure-summarize"),
        ("POST", "/actions/market-anomaly-detect"),
        ("POST", "/actions/news-event-classify"),
        ("POST", "/actions/alert-draft-synthesize"),
        ("POST", "/actions/monitoring-run"),
        ("POST", "/actions/alert-draft-review"),
    }
    available = {(method, route.path) for route in application.routes for method in getattr(route, "methods", set())}
    assert expected <= available
    exposure = call(application, "POST", "/actions/portfolio-exposure-summarize")
    anomaly = call(application, "POST", "/actions/market-anomaly-detect")
    news = call(application, "POST", "/actions/news-event-classify")
    alert = call(application, "POST", "/actions/alert-draft-synthesize")
    assert exposure["capability_id"] == "portfolio.exposure.summarize"
    assert anomaly["capability_id"] == "market.anomaly.detect"
    assert news["effects"] == alert["effects"] == exposure["effects"] == anomaly["effects"] == []


def test_no_broker_order_trade_or_rebalance_route(application: FastAPI) -> None:
    paths = {route.path.lower() for route in application.routes}
    prohibited = ("broker", "order", "trade", "rebalance")
    assert not any(term in path for path in paths for term in prohibited)


def test_manifest_declares_every_application_file_with_matching_hashes(application: FastAPI) -> None:
    manifest = json.loads((APPLICATION_DIR / "servicefabric-package.json").read_text())
    declared = {item["path"] for item in manifest["source_files"]}
    actual = {
        path.relative_to(APPLICATION_DIR).as_posix()
        for path in APPLICATION_DIR.rglob("*")
        if path.is_file()
        and path.name != "servicefabric-package.json"
        and "__pycache__" not in path.parts
    }
    assert declared == actual
    assert any(path.startswith("templates/") for path in declared)
    assert "static/workbench.css" in declared
    assert set(PACKAGE_PATHS) <= {f"apps/portfolio-risk-workbench/{path}" for path in declared}
    for item in manifest["source_files"]:
        assert item["sha256"] == hashlib.sha256((APPLICATION_DIR / item["path"]).read_bytes()).hexdigest()


def test_packaged_catalogues_match_reviewed_sources(application: FastAPI) -> None:
    assert (APPLICATION_DIR / "catalog" / "research.yaml").read_bytes() == (ROOT / "docs" / "research" / "catalog.yaml").read_bytes()
    assert (APPLICATION_DIR / "catalog" / "notebooks.yaml").read_bytes() == (ROOT / "notebooks" / "catalog" / "catalog.yaml").read_bytes()
    for source in sorted((ROOT / "seed" / "knowledge-products" / "day-1").glob("*.yaml")):
        assert (APPLICATION_DIR / "seed" / "knowledge-products" / "day-1" / source.name).read_bytes() == source.read_bytes()
