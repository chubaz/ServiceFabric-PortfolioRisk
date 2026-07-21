"""Cross-package foundation gate for the merged Day 0 Wave 0A overlay."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import importlib
import importlib.util
from pathlib import Path

import pytest
import fastapi.routing

from connectors.synthetic import SyntheticCompustatLikeConnector, SyntheticCrspLikeConnector
from connectors.wrds import WrdsCompustatConnector, WrdsCrspConnector
from risk_agents import AGENT_ROLES
from risk_data import ConnectorDisabledError, QuerySpec
from risk_planning import load_seed_catalog


ROOT = Path(__file__).resolve().parents[2]
APPLICATION_FILE = ROOT / "apps" / "portfolio-risk-workbench" / "app.py"
START = datetime(2026, 6, 1, tzinfo=UTC)
END = datetime(2026, 7, 21, tzinfo=UTC)


def load_application():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("portfolio_risk_workbench", APPLICATION_FILE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


async def asgi_get(path: str) -> tuple[int, bytes]:
    """Send an HTTP request through the application's ASGI boundary."""
    messages: list[dict[str, object]] = []
    received = False
    response_complete = asyncio.Event()

    async def receive() -> dict[str, object]:
        nonlocal received
        if not received:
            received = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await response_complete.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, object]) -> None:
        messages.append(message)
        if message["type"] == "http.response.body" and not message.get("more_body", False):
            response_complete.set()

    await load_application()(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        },
        receive,
        send,
    )
    start = next(message for message in messages if message["type"] == "http.response.start")
    body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return start["status"], body  # type: ignore[return-value]


def test_all_day0_packages_import() -> None:
    for package in ("risk_domain", "risk_planning", "risk_data", "risk_capabilities", "risk_agents", "connectors"):
        assert importlib.import_module(package)


def test_all_seed_knowledge_products_load() -> None:
    catalog = load_seed_catalog(ROOT)
    assert [product.knowledge_product_id for product in catalog.knowledge_products] == [f"KP-{number:02d}" for number in range(6)]


@pytest.mark.parametrize(
    ("connector", "query"),
    [
        (SyntheticCrspLikeConnector(), QuerySpec(dataset="market", instrument_ids=("instrument-nova", "instrument-orbit", "instrument-quasar"), start_at=START, end_at=END)),
        (SyntheticCompustatLikeConnector(), QuerySpec(dataset="fundamental", instrument_ids=("instrument-nova", "instrument-orbit"), start_at=START, end_at=END)),
    ],
)
def test_synthetic_connectors_are_deterministic(connector, query) -> None:  # type: ignore[no-untyped-def]
    first = connector.ingest(query)
    second = connector.ingest(query)
    assert first == second
    assert first.snapshot.synthetic is True
    assert all(record.synthetic for record in first.snapshot.records)


def test_all_four_agent_roles_exist() -> None:
    assert {role.role_id for role in AGENT_ROLES} == {
        "risk.agent.news_sentiment",
        "risk.agent.market_data",
        "risk.agent.portfolio_exposure",
        "risk.agent.alert_recommendation",
    }


def test_fastapi_application_is_healthy_and_external_providers_are_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    async def run_inline(function, *args, **kwargs):  # type: ignore[no-untyped-def]
        return function(*args, **kwargs)

    monkeypatch.setattr(fastapi.routing, "run_in_threadpool", run_inline)
    health_status, health_body = asyncio.run(asgi_get("/health"))
    status_code, status_body = asyncio.run(asgi_get("/api/status"))

    assert health_status == 200
    assert health_body == b'{"status":"healthy"}'
    assert status_code == 200
    assert b'"external_providers":"disabled"' in status_body


@pytest.mark.parametrize("connector", [WrdsCrspConnector(), WrdsCompustatConnector()])
def test_external_provider_connectors_remain_disabled(connector) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ConnectorDisabledError, match="disabled during Day 0"):
        connector.ingest(QuerySpec(dataset="market", instrument_ids=("instrument-nova",), start_at=START, end_at=END))
