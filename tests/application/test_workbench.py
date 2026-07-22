from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import inspect
import io
import json
import os
import re
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from risk_data import PortfolioConfirmationRequest
from starlette.datastructures import UploadFile
from starlette.datastructures import Headers
from starlette.formparsers import MultiPartException


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
VALID_CSV = b"instrument_id,quantity,currency,as_of\ninstrument-alpha,2,USD,2026-07-21T00:00:00Z\n"
VALID_YAML = b"profile: personal_portfolio\nas_of: '2026-07-21T00:00:00Z'\nbase_currency: USD\npositions:\n  - instrument_id: instrument-alpha\n    quantity: '2.5'\n    currency: USD\ncash_balances:\n  USD: '100'\n"


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
    result = route.endpoint(**kwargs)
    return asyncio.run(result) if inspect.isawaitable(result) else result


def upload(filename: str, content: bytes, content_type: str) -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(content), size=len(content), headers={"content-type": content_type})


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
    assert "Switch to personal profile to import" in portfolio
    assert 'href="/portfolio/import?profile=personal_portfolio"' in portfolio
    assert "Snapshot history" in portfolio


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
    for state in ("Data zone", "Query manifest", "Provenance", "Quality flags"):
        assert f">{state}</th>" in body
    assert "local-synthetic-market-data" in body
    assert "local-synthetic-market_prices" in body
    for provider in ("wrds", "crsp", "compustat", "ravenpack", "accern", "bloomberg"):
        assert f">{provider}</th>" in body
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


def test_wave_1b_portfolio_route_boundaries_are_present_without_data_logic(application: FastAPI) -> None:
    available = {(method, route.path) for route in application.routes for method in getattr(route, "methods", set())}
    required = {
        ("GET", "/portfolio/import"),
        ("POST", "/portfolio/import/preview"),
        ("GET", "/portfolio/import/preview/{preview_id}"),
        ("POST", "/portfolio/import/confirm/{preview_id}"),
        ("GET", "/portfolio/snapshots"),
        ("GET", "/portfolio/snapshots/{snapshot_id}"),
        ("GET", "/portfolio/compare"),
        ("POST", "/portfolio/compare/result"),
        ("POST", "/api/portfolio/previews"),
        ("GET", "/api/portfolio/previews/{preview_id}"),
        ("POST", "/api/portfolio/previews/{preview_id}/confirm"),
        ("GET", "/api/portfolio/snapshots"),
        ("GET", "/api/portfolio/snapshots/{snapshot_id}"),
        ("GET", "/api/portfolio/comparisons"),
    }
    assert required <= available
    assert not any("sql" in path.lower() for _, path in available)
    assert "risk_data.portfolio" not in (APPLICATION_DIR / "app.py").read_text()


def test_wave_1b_semantic_forms_disclose_safe_input_and_confirmation(application: FastAPI) -> None:
    import_page = html(application, "/portfolio/import", profile="research")
    compare_page = html(application, "/portfolio/compare")
    assert "Personal portfolio" in import_page
    assert "Research profile" not in import_page
    assert 'enctype="multipart/form-data"' in import_page
    assert 'type="file"' in import_page
    assert "CSV or YAML" in import_page
    assert "1,000,000 bytes" in import_page
    assert "server filesystem path is never accepted" in import_page
    assert 'name="left_snapshot_id"' in compare_page
    assert 'name="right_snapshot_id"' in compare_page
    assert "Read-only comparison" in compare_page

    routes = {
        route.path: route
        for route in application.routes
        if "POST" in getattr(route, "methods", set())
    }
    assert {parameter.name for parameter in routes["/portfolio/import/confirm/{preview_id}"].dependant.body_params} == {
        "confirm_digest",
        "confirm_snapshot",
    }
    assert {parameter.name for parameter in routes["/portfolio/compare/result"].dependant.body_params} == {
        "left_snapshot_id",
        "right_snapshot_id",
    }


def test_fixed_query_manifests_bind_reviewed_typed_catalogue(application: FastAPI) -> None:
    body = html(application, "/data")
    for manifest in (
        "local-synthetic-market_prices",
        "local-synthetic-fundamentals",
        "local-synthetic-latest_market_prices",
        "local-synthetic-latest_fundamentals",
    ):
        assert manifest in body
    assert "Only these reviewed fixed views are exposed" in body


def test_portfolio_csv_yaml_preview_confirmation_and_comparison_end_to_end(application: FastAPI) -> None:
    csv_preview = call(
        application,
        "POST",
        "/api/portfolio/previews",
        file=upload("portfolio.csv", VALID_CSV, "text/csv"),
        profile="personal_portfolio",
        base_currency="USD",
        as_of="2026-07-21T00:00:00Z",
    )
    assert csv_preview["valid"] is True
    assert csv_preview["preview"]["document"]["input_format"] == "csv"
    assert csv_preview["preview"]["document"]["content_digest"].startswith("sha256:")

    yaml_preview = call(
        application,
        "POST",
        "/api/portfolio/previews",
        file=upload("portfolio.yaml", VALID_YAML, "application/yaml"),
        profile="personal_portfolio",
        base_currency="USD",
        as_of="",
    )
    assert yaml_preview["valid"] is True
    assert yaml_preview["preview"]["document"]["input_format"] == "yaml"

    preview_id = csv_preview["preview_id"]
    assert call(application, "GET", "/api/portfolio/previews/{preview_id}", preview_id=preview_id)["valid"] is True
    first = call(
        application,
        "POST",
        "/api/portfolio/previews/{preview_id}/confirm",
        preview_id=preview_id,
        request=PortfolioConfirmationRequest(confirm=True, preview_digest=preview_id),
    )
    assert first["confirmation"]["created"] is True
    first_snapshot_id = first["confirmation"]["snapshot_id"]

    repeated = call(
        application,
        "POST",
        "/api/portfolio/previews/{preview_id}/confirm",
        preview_id=preview_id,
        request=PortfolioConfirmationRequest(confirm=True, preview_digest=preview_id),
    )
    assert repeated["confirmation"]["created"] is False
    assert repeated["confirmation"]["snapshot_id"] == first_snapshot_id

    corrected_csv = VALID_CSV.replace(b",2,USD", b",3,USD")
    corrected_preview = call(
        application,
        "POST",
        "/api/portfolio/previews",
        file=upload("corrected.csv", corrected_csv, "text/csv"),
        profile="personal_portfolio",
        base_currency="USD",
        as_of="2026-07-21T00:00:00Z",
    )
    corrected = call(
        application,
        "POST",
        "/api/portfolio/previews/{preview_id}/confirm",
        preview_id=corrected_preview["preview_id"],
        request=PortfolioConfirmationRequest(confirm=True, preview_digest=corrected_preview["preview_id"]),
    )
    second_snapshot_id = corrected["confirmation"]["snapshot_id"]
    assert second_snapshot_id != first_snapshot_id

    snapshots = call(application, "GET", "/api/portfolio/snapshots")["snapshots"]
    assert {item["snapshot_id"] for item in snapshots} == {first_snapshot_id, second_snapshot_id}
    assert call(application, "GET", "/api/portfolio/snapshots/{snapshot_id}", snapshot_id=first_snapshot_id)["snapshot"]["digest"].startswith("sha256:")

    comparison = call(application, "GET", "/api/portfolio/comparisons", left_snapshot_id=first_snapshot_id, right_snapshot_id=second_snapshot_id)["comparison"]
    assert comparison["position_changes"][0]["change_type"] == "changed"
    comparison_page = call(application, "POST", "/portfolio/compare/result", left_snapshot_id=first_snapshot_id, right_snapshot_id=second_snapshot_id, profile="personal_portfolio")
    comparison_body = comparison_page.body.decode()
    assert comparison_page.status_code == 200 and "Changed positions" in comparison_body
    assert first_snapshot_id in comparison_body and second_snapshot_id in comparison_body

    personal = html(application, "/portfolio", profile="personal_portfolio")
    assert "Private · local · no publication" in personal
    assert first_snapshot_id in personal and second_snapshot_id in personal
    assert "Net asset value" in personal and "100.0%" in personal


def test_invalid_preview_and_confirmation_guards_render_visible_issues(application: FastAPI) -> None:
    invalid = call(
        application,
        "POST",
        "/api/portfolio/previews",
        file=upload("invalid.csv", b"instrument_id,quantity\ninstrument-alpha,nope\n", "text/csv"),
        profile="personal_portfolio",
        base_currency="USD",
        as_of="2026-07-21T00:00:00Z",
    )
    assert invalid["valid"] is False and invalid["preview"]["issues"]
    invalid_page = call(application, "GET", "/portfolio/import/preview/{preview_id}", preview_id=invalid["preview_id"], profile="personal_portfolio")
    invalid_body = invalid_page.body.decode()
    assert "Confirmation blocked" in invalid_body and "Create immutable snapshot" not in invalid_body
    with pytest.raises(HTTPException) as invalid_confirmation:
        call(
            application,
            "POST",
            "/api/portfolio/previews/{preview_id}/confirm",
            preview_id=invalid["preview_id"],
            request=PortfolioConfirmationRequest(confirm=True, preview_digest=invalid["preview_id"]),
        )
    assert invalid_confirmation.value.status_code == 422

    valid = call(
        application,
        "POST",
        "/api/portfolio/previews",
        file=upload("portfolio.csv", VALID_CSV, "text/csv"),
        profile="personal_portfolio",
        base_currency="USD",
        as_of="2026-07-21T00:00:00Z",
    )
    missing_checkbox = call(application, "POST", "/portfolio/import/confirm/{preview_id}", preview_id=valid["preview_id"], confirm_digest=valid["preview_id"], confirm_snapshot="", profile="personal_portfolio")
    assert missing_checkbox.status_code == 422 and "explicit confirm=true is required" in missing_checkbox.body.decode()
    with pytest.raises(HTTPException) as mismatch:
        call(
            application,
            "POST",
            "/api/portfolio/previews/{preview_id}/confirm",
            preview_id=valid["preview_id"],
            request=PortfolioConfirmationRequest(confirm=True, preview_digest="sha256:" + "0" * 64),
        )
    assert mismatch.value.status_code == 422 and "does not match" in mismatch.value.detail


def test_upload_boundaries_reject_unknown_and_oversized_input(application: FastAPI) -> None:
    with pytest.raises(HTTPException) as unknown:
        call(application, "POST", "/api/portfolio/previews", file=upload("portfolio.txt", b"not accepted", "text/plain"), profile="personal_portfolio", base_currency="USD", as_of="")
    with pytest.raises(HTTPException) as oversized:
        call(application, "POST", "/api/portfolio/previews", file=upload("portfolio.csv", b"x" * 1_000_001, "text/csv"), profile="personal_portfolio", base_currency="USD", as_of="")
    assert unknown.value.status_code == 422 and "Only CSV and YAML" in unknown.value.detail
    assert oversized.value.status_code == 422 and "1000000" in oversized.value.detail


def test_request_parser_rejects_oversized_file_before_spooling(application: FastAPI) -> None:
    parser_type = next(route for route in application.routes if route.path == "/api/portfolio/previews").endpoint.__globals__["BoundedPortfolioMultiPartParser"]
    boundary = "portfolio-boundary"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"portfolio.csv\"\r\n"
        "Content-Type: text/csv\r\n\r\n"
    ).encode() + b"x" * 1_000_001 + f"\r\n--{boundary}--\r\n".encode()

    async def stream():
        yield body

    parser = parser_type(Headers({"content-type": f"multipart/form-data; boundary={boundary}"}), stream())
    with pytest.raises(MultiPartException, match="maximum size of 1000000"):
        asyncio.run(parser.parse())
    assert parser.spool_max_size == 1_000_000


def test_yaml_research_profile_is_rejected_before_preview_persistence(application: FastAPI) -> None:
    research_yaml = VALID_YAML.replace(b"profile: personal_portfolio", b"profile: research")
    with pytest.raises(HTTPException) as error:
        call(
            application,
            "POST",
            "/api/portfolio/previews",
            file=upload("research.yaml", research_yaml, "application/yaml"),
            profile="personal_portfolio",
            base_currency="USD",
            as_of="",
        )
    assert error.value.status_code == 422
    assert "personal_portfolio" in error.value.detail
    assert not (Path(os.environ["PORTFOLIO_RISK_DATA_ROOT"]) / "portfolio-previews").exists()


def test_comparison_storage_error_renders_semantic_html(application: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    route = next(item for item in application.routes if item.path == "/portfolio/compare" and "GET" in item.methods)
    monkeypatch.setitem(route.endpoint.__globals__, "workspace", lambda: (_ for _ in ()).throw(OSError("storage unavailable")))
    response = call(application, "GET", "/portfolio/compare")
    assert response.status_code == 409
    assert "Comparison unavailable" in response.body.decode()


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
