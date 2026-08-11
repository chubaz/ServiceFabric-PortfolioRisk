from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
LABS_ROOT = ROOT / "apps" / "portfolio-risk-workbench" / "labs"
sys.path.insert(0, str(LABS_ROOT))

import duckdb_server  # noqa: E402
from mandate_application import MandateApplicationRequest  # noqa: E402
from mandate_studio import MandateRegistrationRequest  # noqa: E402


def register_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_REGISTRY_ROOT", str(tmp_path / "registry"))
    duckdb_server.mandate_studio_register(
        MandateRegistrationRequest(
            mandate_id="institutional-diversified-growth",
            actor="test.reviewer",
        )
    )


def test_application_is_blocked_until_both_exact_versions_are_registered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_REGISTRY_ROOT", str(tmp_path / "registry"))

    catalogue = duckdb_server.mandate_application_catalogue()

    assert catalogue["registry"]["ready"] is False
    with pytest.raises(PermissionError, match="register the exact"):
        duckdb_server.run_mandate_application(
            MandateApplicationRequest(),
            duckdb_server.registry_store(),
        )


def test_reviewed_snapshot_runs_real_capabilities_and_routes_one_breach(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register_bundle(tmp_path, monkeypatch)

    result = duckdb_server.mandate_application_run(MandateApplicationRequest())

    assert result["summary"] == {
        "compliant": 1,
        "attention": 0,
        "breach": 1,
        "unable_to_assess": 1,
    }
    assert [item["capability_id"] for item in result["capability_receipts"]] == [
        "portfolio.snapshot.create",
        "portfolio.exposure.summarize",
    ]
    assert all(item["status"] == "succeeded" for item in result["capability_receipts"])
    assert all(item["execution_mode"] == "canonical_registry" for item in result["capability_receipts"])
    assert result["assessments"][1]["constraint_id"] == "issuer-concentration"
    assert result["assessments"][1]["status"] == "breach"
    assert result["assessments"][2]["status"] == "unable_to_assess"
    assert "does not supply" in result["assessments"][2]["explanation"]
    assert len(result["decision_proposals"]) == 1
    assert result["decision_proposals"][0]["human_review_required"] is True
    assert result["decision_proposals"][0]["effects"] == []
    assert result["interpretation"]["llm_called"] is False
    assert result["effects"] == []


def test_missing_price_stops_valuation_and_never_becomes_false_compliance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register_bundle(tmp_path, monkeypatch)

    result = duckdb_server.mandate_application_run(
        MandateApplicationRequest(scenario_id="missing_price")
    )

    assert result["summary"]["unable_to_assess"] == 3
    assert result["summary"]["compliant"] == 0
    assert result["summary"]["breach"] == 0
    assert result["capability_receipts"][0]["status"] == "failed"
    assert "no zero value is inferred" in result["capability_receipts"][0]["warnings"][0]
    assert result["decision_proposals"] == []


def test_application_uses_exact_point_in_time_and_temporary_output_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register_bundle(tmp_path, monkeypatch)

    result = duckdb_server.mandate_application_run(MandateApplicationRequest())

    assert result["input"]["data_truth"] == "reviewed_synthetic"
    assert result["input"]["point_in_time_rule"] == "timestamp_lte_as_of_and_available_at_lte_as_of"
    assert result["input"]["eligible_market_observations"] == result["input"]["required_positions"]
    assert result["persistence"] == "temporary_application_work_product"
    assert all(item["effects"] == [] for item in result["assessments"])
