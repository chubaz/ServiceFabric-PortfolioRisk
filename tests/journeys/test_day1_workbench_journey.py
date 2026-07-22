"""Final deterministic Day 1 Workbench integration journey."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import inspect
import io
import json
from decimal import Context, Decimal, localcontext
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from risk_data import PortfolioConfirmationError, PortfolioConfirmationRequest, PortfolioInputService
from starlette.datastructures import UploadFile

from scripts.day1.run_day1_demo import (
    AS_OF,
    EXTERNAL_PROVIDERS,
    OUTPUT_NAMES,
    _latest_observations,
    _observations,
    _yaml_input,
    execute_day1_journey,
    write_day1_artifacts,
)


ROOT = Path(__file__).resolve().parents[2]
APPLICATION_DIR = ROOT / "apps" / "portfolio-risk-workbench"
PROHIBITED_ROUTE_TERMS = ("broker", "order", "trade", "rebalance", "optimization")


def application() -> FastAPI:
    spec = importlib.util.spec_from_file_location("day1_final_workbench", APPLICATION_DIR / "app.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def call(app: FastAPI, method: str, path: str, **kwargs: object) -> Any:
    route = next(item for item in app.routes if item.path == path and method in getattr(item, "methods", set()))
    result = route.endpoint(**kwargs)
    return asyncio.run(result) if inspect.isawaitable(result) else result


def upload(filename: str, content: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        filename=filename,
        file=io.BytesIO(content),
        size=len(content),
        headers={"content-type": content_type},
    )


def test_day1_workbench_journey(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_root = tmp_path / "external-private-local-state"
    monkeypatch.setenv("PORTFOLIO_RISK_DATA_ROOT", str(data_root))
    result = execute_day1_journey(data_root)

    assert result["profiles"] == ("research", "personal_portfolio")
    assert result["research_preview"].valid
    assert result["research_preview"].document.profile == "research"
    assert result["personal_preview"].valid
    assert result["personal_preview"].document.profile == "personal_portfolio"
    assert result["personal_preview"].document.input_format.value == "yaml"
    assert not result["invalid_preview"].valid
    assert result["invalid_preview"].issues
    assert all(issue.message for issue in result["invalid_preview"].issues)

    service = PortfolioInputService(data_root)
    with pytest.raises(PortfolioConfirmationError, match="confirm=true"):
        service.confirm(
            result["personal_preview"],
            PortfolioConfirmationRequest(
                confirm=False,
                preview_digest=result["personal_preview"].preview_digest,
            ),
            _latest_observations(_observations()),
        )
    assert result["confirmation"].created
    assert result["corrected_confirmation"].created
    assert result["initial_snapshot"].snapshot_id != result["corrected_snapshot"].snapshot_id
    assert result["initial_snapshot"].digest != result["corrected_snapshot"].digest
    assert len(tuple((data_root / "portfolio-snapshots").glob("*.json"))) == 2
    assert result["comparison"].left_snapshot_id == result["initial_snapshot"].snapshot_id
    assert result["comparison"].right_snapshot_id == result["corrected_snapshot"].snapshot_id
    assert result["comparison"].position_changes[0].left_quantity == Decimal("10")
    assert result["comparison"].position_changes[0].right_quantity == Decimal("12")
    assert "read-only" in result["comparison"].limitations[0].lower()

    external = tuple(item for item in result["providers"] if item.provider_id in EXTERNAL_PROVIDERS)
    assert {item.provider_id for item in external} == EXTERNAL_PROVIDERS
    assert all(not item.enabled and item.access_state == "unavailable" for item in external)
    assert {item.view_name for item in result["query_manifests"]} == {
        "market_prices",
        "fundamentals",
        "latest_market_prices",
        "latest_fundamentals",
    }
    assert not hasattr(PortfolioInputService, "execute_sql")
    assert "execute_sql" not in inspect.getsource(PortfolioInputService)

    analyses = result["analyses"]
    assert analyses["simple_returns"].capability_id == "risk.returns.simple"
    assert analyses["log_returns"].capability_id == "risk.returns.log"
    assert analyses["annualized_volatility"].data.annualized_volatility >= 0
    assert analyses["maximum_drawdown"].data.maximum_drawdown > 0
    for method in ("historical_var", "historical_expected_shortfall"):
        tail = analyses[method]
        assert tail.data.value_at_risk >= 0
        assert tail.data.expected_shortfall >= tail.data.value_at_risk
        assert any("inadequate-tail-sample" in warning for warning in tail.warnings)

    contribution = analyses["contribution_summary"].data
    present = tuple(item.contribution for item in contribution.items if item.contribution is not None)
    with localcontext(Context(prec=34)):
        assert contribution.contribution_sum == sum(present, start=Decimal("0"))
    scenario = result["scenario"]
    assert scenario.capability_id == "risk.scenario.evaluate"
    assert scenario.data.shocks
    assert scenario.data.portfolio_profit_and_loss == sum(
        (item.profit_and_loss for item in scenario.data.positions), start=Decimal("0")
    )

    timeline = result["timeline"]
    assert len(timeline.steps) == 4
    assert tuple(step.sequence for step in timeline.steps) == (1, 2, 3, 4)
    assert all(step.review.state == "pending" and step.review.human_review_required for step in timeline.steps)
    assert timeline.effects == () and all(step.effects == () and step.receipt.effects == () for step in timeline.steps)

    report = result["report"]
    assert report.capability_id == "risk.report.render"
    assert report.human_review_required and report.effects == ()
    assert report.data.markdown.startswith("# ")
    assert "<article" in report.data.html and "<section" in report.data.html
    assert result["human_review"] == {"required": True, "state": "pending"}
    assert result["effects"] == ()

    paths = write_day1_artifacts(result)
    assert {path.name for path in paths.values()} == set(OUTPUT_NAMES.values())
    first_run_bytes = {key: path.read_bytes() for key, path in paths.items()}
    repeated_result = execute_day1_journey(data_root)
    assert not repeated_result["confirmation"].created
    assert not repeated_result["corrected_confirmation"].created
    repeated_paths = write_day1_artifacts(repeated_result)
    assert {key: path.read_bytes() for key, path in repeated_paths.items()} == first_run_bytes

    manifest = json.loads(paths["evidence_manifest"].read_text(encoding="utf-8"))
    assert manifest["effects"] == []
    assert manifest["human_review"] == {"required": True, "state": "pending"}
    assert {item["path"] for item in manifest["artifacts"]} == {
        f"day1-workbench/{name}" for key, name in OUTPUT_NAMES.items() if key != "evidence_manifest"
    }
    for item in manifest["artifacts"]:
        artifact = data_root / item["path"]
        assert item["digest"] == "sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest()


def test_day1_workbench_is_readable_and_has_no_execution_surfaces(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_DATA_ROOT", str(tmp_path / "workbench-state"))
    app = application()

    for profile in ("research", "personal_portfolio"):
        response = call(app, "GET", "/", profile=profile)
        assert response.status_code == 200
        body = response.body.decode()
        assert response.media_type == "text/html"
        assert "<main" in body and "<nav" in body
        assert profile in body

    valid = call(
        app,
        "POST",
        "/portfolio/import/preview",
        file=upload("portfolio.yaml", _yaml_input("10"), "application/yaml"),
        base_currency="USD",
        as_of="",
        profile="personal_portfolio",
    )
    assert valid.status_code == 200
    assert "Portfolio validation preview" in valid.body.decode()
    invalid = call(
        app,
        "POST",
        "/portfolio/import/preview",
        file=upload("portfolio.csv", b"instrument_id,quantity\ninstrument-alpha,nope\n", "text/csv"),
        base_currency="USD",
        as_of=AS_OF.isoformat(),
        profile="personal_portfolio",
    )
    assert invalid.status_code == 422
    invalid_body = invalid.body.decode().lower()
    assert "invalid" in invalid_body and "issue" in invalid_body

    preview_action = call(app, "POST", "/actions/portfolio-input-preview")
    provider_action = call(app, "POST", "/actions/provider-catalog-list")
    assert preview_action["capability_id"] == "portfolio.input.preview"
    assert preview_action["effects"] == []
    assert provider_action["capability_id"] == "provider.catalog.list"
    assert provider_action["effects"] == []
    assert all(
        not item["enabled"]
        for item in provider_action["data"]["providers"]
        if item["provider_id"] in EXTERNAL_PROVIDERS
    )

    manifest = json.loads(
        (APPLICATION_DIR / "servicefabric-package.json").read_text(encoding="utf-8")
    )
    declared = {item["tool_id"]: item["path"] for item in manifest["capabilities"]}
    assert declared["portfolio.input.preview"] == "/actions/portfolio-input-preview"
    assert declared["provider.catalog.list"] == "/actions/provider-catalog-list"

    routes = {route.path.lower() for route in app.routes}
    assert not any(term in path for path in routes for term in PROHIBITED_ROUTE_TERMS)
    assert not any("notebook" in path and any(term in path for term in ("execute", "run", "kernel")) for path in routes)
    assert not any("provider" in path and any(term in path for term in ("enable", "connect")) for path in routes)
