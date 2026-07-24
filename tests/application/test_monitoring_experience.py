from __future__ import annotations

import asyncio
import importlib.util
import inspect
import io
import json
import socket
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from starlette.datastructures import UploadFile
from risk_domain import PortfolioSnapshot, Position


ROOT = Path(__file__).resolve().parents[2]
APPLICATION_DIR = ROOT / "apps" / "portfolio-risk-workbench"


@pytest.fixture
def application(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> FastAPI:
    monkeypatch.setenv("PORTFOLIO_RISK_DATA_ROOT", str(tmp_path / "risk-data"))
    spec = importlib.util.spec_from_file_location(
        "monitoring_workbench", APPLICATION_DIR / "app.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def call(app: FastAPI, method: str, path: str, **kwargs: object) -> object:
    route = next(
        item
        for item in app.routes
        if item.path == path and method in getattr(item, "methods", set())
    )
    result = route.endpoint(**kwargs)
    return asyncio.run(result) if inspect.isawaitable(result) else result


def model(app: FastAPI, path: str, name: str):
    route = next(item for item in app.routes if item.path == path)
    return route.endpoint.__globals__[name]


def upload(filename: str, content: bytes) -> UploadFile:
    return UploadFile(
        filename=filename,
        file=io.BytesIO(content),
        size=len(content),
        headers={"content-type": "text/csv"},
    )


def create_context_policy(
    app: FastAPI, *, move_threshold: str = "0.05"
) -> tuple[dict[str, object], dict[str, object]]:
    service = model(app, "/api/monitoring/contexts", "monitoring_workspace")()
    snapshot, selection = model(
        app, "/api/monitoring/contexts", "_hosted_monitoring_fixture"
    )(service)
    ExplicitConfirmation = model(
        app, "/api/monitoring/contexts", "ExplicitConfirmation"
    )
    PolicyFields = model(app, "/api/monitoring/policies", "PolicyFields")
    preview = service.preview_context(snapshot, selection)
    context = service.confirm_context(
        ExplicitConfirmation(preview_id=preview["preview_id"], confirm=True)
    )
    policy = call(
        app,
        "POST",
        "/api/monitoring/policies",
        request=PolicyFields(
            confirm=True, daily_percentage_move_threshold=move_threshold
        ),
    )
    return context, policy


def test_monitoring_navigation_routes_and_fixed_forms(application: FastAPI) -> None:
    available = {
        (method, route.path)
        for route in application.routes
        for method in getattr(route, "methods", set())
    }
    required = {
        ("GET", "/monitoring/context"),
        ("POST", "/monitoring/context/preview"),
        ("POST", "/monitoring/context/confirm"),
        ("GET", "/monitoring/contexts"),
        ("GET", "/monitoring/contexts/{context_id}"),
        ("GET", "/monitoring/events"),
        ("GET", "/monitoring/events/import"),
        ("POST", "/monitoring/events/import/preview"),
        ("GET", "/monitoring/events/previews/{preview_id}"),
        ("POST", "/monitoring/events/previews/{preview_id}/confirm"),
        ("GET", "/monitoring/events/snapshots/{snapshot_id}"),
        ("GET", "/monitoring/policies"),
        ("GET", "/monitoring/policies/new"),
        ("POST", "/monitoring/policies/preview"),
        ("POST", "/monitoring/policies/confirm"),
        ("GET", "/monitoring/policies/{policy_id}"),
        ("GET", "/monitoring/runs"),
        ("GET", "/monitoring/run"),
        ("POST", "/monitoring/run"),
        ("GET", "/monitoring/runs/{run_id}"),
        ("GET", "/monitoring/replay"),
        ("POST", "/monitoring/replay"),
        ("GET", "/monitoring/replays/{replay_id}"),
        ("GET", "/monitoring/evaluations/{evaluation_id}"),
        ("GET", "/monitoring/reports/{source_id}"),
        ("GET", "/monitoring/reports/{source_id}.md"),
    }
    assert required <= available
    context = call(application, "GET", "/monitoring/context").body.decode()
    event_import = call(application, "GET", "/monitoring/events/import").body.decode()
    policy = call(application, "GET", "/monitoring/policies/new").body.decode()
    run_form = call(application, "GET", "/monitoring/run").body.decode()
    replay = call(application, "GET", "/monitoring/replay").body.decode()
    for label in ("Context", "Events", "Policies", "Runs", "Replay", "Evaluation"):
        assert f">{label}</a>" in context
    assert "Monitoring" in context
    assert "server path" in event_import and 'name="path"' not in event_import
    assert "Price move threshold" in policy and "Cadence metadata" in policy
    assert 'name="mapping_case"' not in context
    assert 'name="daily_return"' not in run_form
    assert 'name="concentration"' not in run_form
    for prohibited in (
        'name="expression"',
        'name="code"',
        'name="sql"',
        'name="formula"',
    ):
        assert prohibited not in policy.lower()
        assert prohibited not in replay.lower()
    assert "No background scheduler" in replay


def test_context_confirmation_blocks_mapping_issues_and_preserves_profiles(
    application: FastAPI,
) -> None:
    service = model(application, "/api/monitoring/contexts", "monitoring_workspace")()
    snapshot, selection = model(
        application, "/api/monitoring/contexts", "_hosted_monitoring_fixture"
    )(service)
    ExplicitConfirmation = model(
        application, "/api/monitoring/contexts", "ExplicitConfirmation"
    )
    unmatched_position = Position(
        instrument_id="unmapped-reviewed-instrument",
        quantity=Decimal("1"),
        price=Decimal("10"),
        market_value=Decimal("10"),
        currency="USD",
    )
    unmatched_snapshot = PortfolioSnapshot(
        snapshot_id="unmapped-reviewed-portfolio",
        as_of=snapshot.as_of,
        base_currency="USD",
        positions=(unmatched_position,),
    )
    blocked = service.preview_context(
        unmatched_snapshot,
        selection.model_copy(
            update={"portfolio_snapshot_id": unmatched_snapshot.snapshot_id}
        ),
    )
    assert blocked["context"]["mapping_coverage"]["unmapped_count"] > 0
    assert blocked["confirmable"] is False
    with pytest.raises(ValueError, match="prevents confirmation"):
        service.confirm_context(
            ExplicitConfirmation(preview_id=blocked["preview_id"], confirm=True)
        )

    context, policy = create_context_policy(application)
    request = context["request"]
    assert request["market_dataset_snapshot_id"].startswith("research-")
    assert {
        item["entity_id"] for item in request["market_observations"]
    } == {item.instrument_id for item in snapshot.positions}
    assert {"41.00", "22.25"} <= {
        item["value"]
        for item in request["market_observations"]
        if item["field_name"] == "valuation_price"
    }
    assert {
        item["source_instrument_id"] for item in request["crosswalk_records"]
    } == {item.instrument_id for item in snapshot.positions}
    body = call(
        application,
        "GET",
        "/monitoring/contexts/{context_id}",
        context_id=context["context_id"],
    ).body.decode()
    assert "Mapping coverage" in body and "Stale and missing data" not in body
    assert "Effects" in body and "Empty" in body

    personal_preview = service.preview_context(
        snapshot,
        selection.model_copy(update={"profile": "personal_portfolio"}),
    )
    personal = service.confirm_context(
        ExplicitConfirmation(
            preview_id=personal_preview["preview_id"], confirm=True
        )
    )
    assert personal["profile"] == "personal_portfolio"
    RunSelectionRequest = model(
        application, "/api/monitoring/runs", "RunSelectionRequest"
    )
    personal_run = service.run(
        RunSelectionRequest(
            context_id=personal["context_id"], policy_id=policy["policy_id"]
        )
    )
    personal_report = service.report(personal_run["run_id"])
    assert personal_report["profile"] == "personal_portfolio"
    personal_body = call(
        application,
        "GET",
        "/monitoring/reports/{source_id}",
        source_id=personal_run["run_id"],
    ).body.decode()
    assert "Private local profile" in personal_body
    assert "no publication action is available" in personal_body

    newer_snapshot = PortfolioSnapshot(
        snapshot_id="future-reviewed-portfolio",
        as_of=selection.as_of.replace(day=2),
        base_currency=snapshot.base_currency,
        positions=snapshot.positions,
    )
    with pytest.raises(ValueError, match="newer than the context"):
        service.preview_context(
            newer_snapshot,
            selection.model_copy(
                update={"portfolio_snapshot_id": newer_snapshot.snapshot_id}
            ),
        )
    with pytest.raises(ValueError, match="daily_market revision"):
        service.preview_context(
            snapshot,
            selection.model_copy(update={"market_dataset_revision": "missing-revision"}),
        )
    with pytest.raises(ValueError, match="crosswalk revision"):
        service.preview_context(
            snapshot,
            selection.model_copy(
                update={"crosswalk_dataset_revision": "sha256:" + ("0" * 64)}
            ),
        )


def test_event_upload_available_time_amendments_retractions_and_privacy(
    application: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    def prohibited(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("network attempted")

    content = (
        ROOT / "data/fixtures/synthetic/day23/ravenpack-like-events.csv"
    ).read_bytes()
    preview = call(
        application,
        "POST",
        "/api/events/previews",
        file=upload("events.csv", content),
        provider_profile="synthetic_local",
        provider_id="workbench-local-events",
        provider_name="Workbench local events",
        dataset_revision="event-revision-1",
        publication_restriction="synthetic_only",
        retrieved_at="2026-07-01T16:00:00Z",
    )
    monkeypatch.setattr(socket, "socket", prohibited)
    states = {item["amendment_state"] for item in preview["records"]}
    assert states == {"original", "amendment", "retraction"}
    assert any(item["available_at"] is None for item in preview["records"])
    assert "absolute_path" not in json.dumps(preview)
    LocalImportConfirmation = model(
        application, "/api/events/previews/{preview_id}/confirm", "LocalImportConfirmation"
    )
    snapshot = call(
        application,
        "POST",
        "/api/events/previews/{preview_id}/confirm",
        preview_id=preview["preview_id"],
        request=LocalImportConfirmation(
            confirm=True,
            preview_digest=preview["preview_digest"],
            source_digest=preview["source"]["source_digest"],
        ),
    )
    body = call(
        application,
        "GET",
        "/monitoring/events/snapshots/{snapshot_id}",
        snapshot_id=snapshot["snapshot_id"],
    ).body.decode()
    assert "Event time" in body and "Available time" in body
    assert "Amendment" in body and "Retraction" in body
    assert "No fuzzy or ticker matching" in body
    assert snapshot["network_used"] is False


def test_contextual_run_replay_evaluation_and_reports(application: FastAPI) -> None:
    context, policy = create_context_policy(application, move_threshold="0.01")
    RunSelectionRequest = model(
        application, "/api/monitoring/runs", "RunSelectionRequest"
    )
    run = call(
        application,
        "POST",
        "/api/monitoring/runs",
        request=RunSelectionRequest(
            context_id=context["context_id"], policy_id=policy["policy_id"]
        ),
    )
    assert len(run["run"]["four_agent_timeline"]) == 4
    assert run["run"]["alert_draft"]["state"] == "draft"
    assert run["run"]["effects"] == [] and run["effects"] == []
    body = call(
        application,
        "GET",
        "/monitoring/runs/{run_id}",
        run_id=run["run_id"],
    ).body.decode()
    assert "Four-agent timeline" in body and "Draft alert" in body
    assert "Review never authorizes" not in body
    assert "never authorizes a trade" in body
    context_as_of = datetime.fromisoformat(context["context"]["as_of"])
    with pytest.raises(ValueError, match="cannot precede"):
        model(application, "/api/monitoring/runs", "monitoring_workspace")().run(
            RunSelectionRequest(
                context_id=context["context_id"],
                policy_id=policy["policy_id"],
                run_at=context_as_of.replace(day=30, month=6),
            )
        )

    ReplaySelectionRequest = model(
        application, "/api/monitoring/replays", "ReplaySelectionRequest"
    )
    replay_at = datetime(2026, 6, 30, 21, tzinfo=UTC)
    replay = call(
        application,
        "POST",
        "/api/monitoring/replays",
        request=ReplaySelectionRequest(
            context_id=context["context_id"],
            policy_id=policy["policy_id"],
            start=replay_at,
            end=replay_at,
        ),
    )
    evaluation = call(
        application,
        "GET",
        "/api/monitoring/evaluations/{evaluation_id}",
        evaluation_id=replay["evaluation_id"],
    )["evaluation"]
    assert evaluation["true_positive"] == 0
    assert evaluation["false_positive"] > 0
    assert evaluation["false_negative"] == 1
    assert evaluation["precision"] == "0" and evaluation["recall"] == "0"
    assert any(
        warning["code"] == "small_labelled_sample"
        for warning in evaluation["warnings"]
    )
    report = call(
        application,
        "GET",
        "/api/monitoring/reports/{source_id}",
        source_id=replay["replay_id"],
    )
    assert report["report"]["html"].startswith('<article class="monitoring-report"')
    assert report["report"]["markdown"].startswith("# Local Monitoring")
    assert report["publication_available"] is False
    assert report["pdf_available"] is False and report["effects"] == []
    assert replay["replay"]["specification"]["labelled_outcome_method"] == (
        "reviewed_synthetic_threshold_label"
    )
    assert replay["outcomes"][0]["outcome_id"] == "fictional-outcome-002"
    assert "-0.08" not in json.dumps(replay)
    assert "0.025" in json.dumps(replay)

    with pytest.raises(ValueError, match="maximum of 366 steps"):
        model(application, "/api/monitoring/replays", "monitoring_workspace")().replay(
            ReplaySelectionRequest(
                context_id=context["context_id"],
                policy_id=policy["policy_id"],
                start=replay_at,
                end=replay_at.replace(year=2028),
            )
        )


def test_undefined_metrics_render_not_available_with_warnings(
    application: FastAPI,
) -> None:
    context, policy = create_context_policy(application, move_threshold="0.20")
    ReplaySelectionRequest = model(
        application, "/api/monitoring/replays", "ReplaySelectionRequest"
    )
    as_of = datetime(2026, 6, 30, 21, tzinfo=UTC)
    replay = call(
        application,
        "POST",
        "/api/monitoring/replays",
        request=ReplaySelectionRequest(
            context_id=context["context_id"],
            policy_id=policy["policy_id"],
            start=as_of,
            end=as_of,
            outcome_label_snapshot_id="reviewed-empty-outcomes",
        ),
    )
    record = call(
        application,
        "GET",
        "/api/monitoring/evaluations/{evaluation_id}",
        evaluation_id=replay["evaluation_id"],
    )
    evaluation = record["evaluation"]
    assert evaluation["precision"] is None
    assert evaluation["recall"] is None
    assert evaluation["coverage"] is None
    codes = {item["code"] for item in evaluation["warnings"]}
    assert {"undefined_precision", "undefined_recall", "undefined_coverage"} <= codes
    body = call(
        application,
        "GET",
        "/monitoring/evaluations/{evaluation_id}",
        evaluation_id=replay["evaluation_id"],
    ).body.decode()
    assert body.count("Not available") >= 3
    assert "0.0%" not in body
    assert "Sample warning" in body and "Matching methodology" in body


def test_part2_actions_are_declared_effect_free_and_no_generic_endpoint(
    application: FastAPI,
) -> None:
    available = {
        (method, route.path)
        for route in application.routes
        for method in getattr(route, "methods", set())
    }
    assert not any("capability" in path and "invoke" in path for _, path in available)
    assert not any(
        prohibited in path.lower()
        for _, path in available
        for prohibited in (
            "provider-enable",
            "network",
            "sql",
            "notebook-execute",
            "broker",
            "order",
            "trade",
            "rebalance",
            "optimization",
        )
    )
    expected = {
        "portfolio.data_context.create": "/actions/portfolio-data-context-create",
        "events.query.as_of": "/actions/events-query-as-of",
        "monitoring.policy.evaluate": "/actions/monitoring-policy-evaluate",
        "monitoring.run.contextual": "/actions/monitoring-run-contextual",
        "monitoring.replay": "/actions/monitoring-replay",
        "monitoring.evaluate": "/actions/monitoring-evaluate",
        "monitoring.report.render": "/actions/monitoring-report-render",
    }
    manifest = json.loads(
        (APPLICATION_DIR / "servicefabric-package.json").read_text(encoding="utf-8")
    )
    declared = {item["tool_id"]: item["path"] for item in manifest["capabilities"]}
    assert expected.items() <= declared.items()
    for capability_id, path in expected.items():
        result = call(application, "POST", path)
        assert result["capability_id"] == capability_id
        assert result["effects"] == []
        assert result["human_review_required"] is True
