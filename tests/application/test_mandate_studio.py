from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
LABS_ROOT = ROOT / "apps" / "portfolio-risk-workbench" / "labs"
sys.path.insert(0, str(LABS_ROOT))

import duckdb_server  # noqa: E402
import mandate_studio  # noqa: E402


def test_mandate_catalogue_exposes_reviewed_compiled_bundles() -> None:
    payload = mandate_studio.catalogue()

    assert payload["authority"] == "design_time_only"
    assert payload["applicable_law"] == "reference_metadata_only"
    assert payload["effects"] == []
    assert len(payload["records"]) == 3
    for record in payload["records"]:
        assert record["design_state"] == "compiled_and_reviewed"
        assert record["validation"]["valid"] is True
        assert record["validation"]["constraint_count"] == record["validation"]["rule_count"]
        assert all(item["capability_status"] == "runtime_available" for item in record["validation"]["bindings"])
        assert all(item["effects"] == [] for item in record["validation"]["bindings"])
        assert record["experiment_ready"] is record["validation"]["executable"]
        assert record["validation"]["capability_gap_count"] == len(
            record["validation"]["capability_proposal_candidates"]
        )


def test_validation_proves_metric_construction_not_only_capability_presence() -> None:
    records = {item["mandate"]["object_id"]: item for item in mandate_studio.catalogue()["records"]}
    diversified = records["institutional-diversified-growth"]
    bindings = {item["rule_id"]: item for item in diversified["validation"]["bindings"]}

    assert bindings["cash-minimum"]["metric_status"] == "constructible"
    assert bindings["real-return-objective"]["capability_status"] == "runtime_available"
    assert bindings["real-return-objective"]["metric_status"] == "capability_gap"
    assert diversified["validation"]["executable"] is False
    proposal = next(
        item
        for item in diversified["validation"]["capability_proposal_candidates"]
        if item["rule_id"] == "real-return-objective"
    )
    assert proposal["status"] == "identified_requires_human_design"
    assert proposal["backlog_effect"] == "not_saved_until_human_review"


def test_pension_mandate_declares_fuller_policy_and_private_assignment_data() -> None:
    record = next(
        item
        for item in mandate_studio.catalogue()["records"]
        if item["mandate"]["object_id"] == "liability-aware-pension"
    )

    assert len(record["mandate"]["constraints"]) == 7
    assert len(record["risk_policy"]["rules"]) == 7
    requirements = {item["data_role"]: item for item in record["mandate"]["data_requirements"]}
    assert requirements["benefit_outflow_forecast"]["confidentiality"] == "restricted"
    assert requirements["benefit_outflow_forecast"]["binding_scope"] == "experiment_assignment"
    assert requirements["benefit_outflow_forecast"]["missing_data_rule"] == "unable_to_assess_and_escalate"


def test_design_preview_is_a_diff_brief_and_never_a_saved_definition() -> None:
    result = mandate_studio.design_preview(
        mandate_studio.MandateDesignPreviewRequest(
            base_mandate_id="institutional-diversified-growth",
            name="Diversified climate-aware research mandate",
            objective="Preserve purchasing power while studying climate-transition exposure.",
            change_request="Add a reviewed climate-transition monitoring trigger and route material findings to the risk officer.",
        )
    )

    assert result["status"] == "design_brief_ready"
    assert result["requested_diff"].startswith("Add a reviewed")
    assert result["preserved"]["effects"] == []
    assert "Apply only this requested diff" in result["studio_codex_brief"]
    assert "Do not interpret law" in result["studio_codex_brief"]


def test_api_registers_exact_mandate_and_policy_as_two_candidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_REGISTRY_ROOT", str(tmp_path / "registry"))
    before = duckdb_server.mandate_studio_catalogue()
    record = next(
        item
        for item in before["records"]
        if item["mandate"]["object_id"] == "european-corporate-bond-income"
    )
    assert record["registry"]["registered"] is False

    result = duckdb_server.mandate_studio_register(
        mandate_studio.MandateRegistrationRequest(
            mandate_id="european-corporate-bond-income",
            actor="test.reviewer",
        )
    )

    assert result["registered"] is True
    assert result["production_publication"] is False
    assert result["effects"] == []
    assert {item["projection"]["identity"]["kind"] for item in result["records"]} == {
        "mandate",
        "risk_policy",
    }
    after = duckdb_server.mandate_studio_catalogue()
    registered = next(
        item
        for item in after["records"]
        if item["mandate"]["object_id"] == "european-corporate-bond-income"
    )
    assert registered["registry"]["registered"] is True
    assert registered["registry"]["mandate_state"] == "candidate"
    assert registered["registry"]["policy_state"] == "candidate"


def test_mandate_registration_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_REGISTRY_ROOT", str(tmp_path / "registry"))
    request = mandate_studio.MandateRegistrationRequest(
        mandate_id="liability-aware-pension",
        actor="test.reviewer",
    )
    first = duckdb_server.mandate_studio_register(request)
    second = duckdb_server.mandate_studio_register(request)

    assert [item["reference"] for item in first["records"]] == [
        item["reference"] for item in second["records"]
    ]
    assert len(duckdb_server.registry_store().list()) == 2
