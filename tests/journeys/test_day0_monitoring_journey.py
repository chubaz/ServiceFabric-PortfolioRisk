import json
from decimal import Decimal
from pathlib import Path

import pytest
from risk_capabilities import DecisionPoint
from risk_domain import AgentRun, DatasetSnapshot, ExposureSnapshot, PortfolioSnapshot
from scripts.day0.run_monitoring_demo import execute_monitoring_journey, write_monitoring_artifacts


def _contains_forbidden_object(value: object) -> bool:
    if type(value).__name__.lower() in {"order", "broker"}:
        return True
    if isinstance(value, dict):
        return any(str(key).lower() in {"order", "orders", "broker", "brokers"} or _contains_forbidden_object(item) for key, item in value.items())
    if isinstance(value, (tuple, list)):
        return any(_contains_forbidden_object(item) for item in value)
    if hasattr(value, "model_dump"):
        return _contains_forbidden_object(value.model_dump(mode="python"))
    return False


def test_day0_monitoring_journey(tmp_path: Path) -> None:
    result = execute_monitoring_journey(tmp_path / "portfolio-risk-data")

    assert isinstance(result["dataset_snapshot"], DatasetSnapshot)
    assert isinstance(result["portfolio_snapshot"], PortfolioSnapshot)
    assert isinstance(result["exposure_snapshot"], ExposureSnapshot)
    assert result["exposure_snapshot"].nav == Decimal("40000.00")
    assert result["exposure_snapshot"].largest_position_weight == Decimal("0.50")
    assert result["concentration_limit"] == Decimal("0.40")
    assert all(
        observation.observed_at <= result["portfolio_snapshot"].as_of
        for observation in result["portfolio_snapshot"].market_observations
    )
    assert any(item.instrument_id == "instrument-alpha" for item in result["market_output"].data.anomalies)
    assert any(item.kind == "concentration" for item in result["findings"])
    assert result["news_output"].data.synthetic_disclosure

    assert len(result["agent_runs"]) == 4
    assert all(isinstance(item, AgentRun) for item in result["agent_runs"])
    assert {item.agent_role for item in result["agent_runs"]} == {
        "risk.agent.market_data",
        "risk.agent.portfolio_exposure",
        "risk.agent.news_sentiment",
        "risk.agent.alert_recommendation",
    }
    assert result["alert_draft"].status == "draft"
    assert result["alert_draft"].human_review_required is True
    assert result["alert_draft"].effects == ()
    assert result["monitoring"].effects == ()
    assert isinstance(result["decision_point"], DecisionPoint)
    assert result["review"].data.decision_point == result["decision_point"]
    assert result["review"].effects == ()
    assert not _contains_forbidden_object(result)

    paths = write_monitoring_artifacts(result)
    assert set(paths) == {
        "portfolio_snapshot",
        "exposure_snapshot",
        "findings",
        "agent_runs",
        "alert_draft",
        "evidence_manifest",
    }
    assert all(path.is_file() and result["data_root"] in path.parents for path in paths.values())
    agent_artifact = json.loads(paths["agent_runs"].read_text())
    assert len(agent_artifact["capability_outputs"]) == 4
    assert all(
        item["assumptions"] is not None and item["limitations"] is not None
        for item in agent_artifact["capability_outputs"]
    )
    evidence_manifest = json.loads(paths["evidence_manifest"].read_text())
    assert evidence_manifest["human_review"]["decision_point"]["decision_id"] == result["decision_point"].decision_id


def test_reused_dataset_snapshot_rejects_tampered_artifact(tmp_path: Path) -> None:
    root = tmp_path / "portfolio-risk-data"
    result = execute_monitoring_journey(root)
    price_file = result["data_root"] / "market" / "prices.parquet"
    price_file.write_bytes(price_file.read_bytes() + b"tampered")

    with pytest.raises(ValueError, match="dataset snapshot artifact (size|digest) differs"):
        execute_monitoring_journey(root)
