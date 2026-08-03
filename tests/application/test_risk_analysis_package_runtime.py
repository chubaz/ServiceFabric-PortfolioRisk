from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
LABS_ROOT = ROOT / "apps" / "portfolio-risk-workbench" / "labs"
for package in ("risk_reports", "risk_experiments", "risk_decisions"):
    sys.path.insert(0, str(ROOT / "packages" / package / "src"))
sys.path.insert(0, str(LABS_ROOT))

import risk_analysis_package_runtime as runtime  # noqa: E402


def test_reviewed_synthetic_package_run_uses_capabilities_and_persists_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "RISK_PACKAGE_RUN_ROOT", tmp_path)

    result = runtime.execute_package(runtime.PackageRunRequest())
    manifest = result["manifest"]
    contents = result["contents"]

    assert manifest["status"] == "completed"
    assert manifest["data_truth"] == "reviewed_synthetic"
    assert manifest["narrative_mode"] == "deterministic_preview"
    assert manifest["capability_call_count"] == 9
    assert manifest["finding_count"] == 3
    assert manifest["human_review_required"] is True
    assert manifest["effects"] == []
    assert Path(manifest["folder"]).parent == tmp_path

    receipts = contents["capability-receipts.json"]
    assert [item["sequence"] for item in receipts] == list(range(1, 10))
    assert all(item["status"] == "succeeded" for item in receipts)
    assert all(item["effects"] == [] for item in receipts)
    assert {item["resolved_implementation"] for item in receipts} == {
        "portfolio.exposure.summarize",
        "risk.contribution.summarize",
        "risk.drawdown.maximum",
        "risk.expected_shortfall.historical",
        "risk.report.render",
        "risk.returns.simple",
        "risk.scenario.evaluate",
        "risk.var.historical",
        "risk.volatility.annualized",
    }

    assert contents["model-receipt.json"] == {
        "provider": "none",
        "input_tokens": 0,
        "output_tokens": 0,
        "reason": "deterministic preview selected",
    }
    assert contents["report-validation.json"]["valid"] is True
    assert "Northstar Industries" in contents["dossier.html"]
    assert contents["input.json"]["fixture"]["evidence_packet"]["data_truth"] == "reviewed_synthetic"

    required_files = {
        "input.json",
        "execution-plan.json",
        "capability-receipts.json",
        "analysis-results.json",
        "candidate-findings.json",
        "narrative-output.json",
        "model-receipt.json",
        "report-plan.json",
        "report.json",
        "report-validation.json",
        "dossier.md",
        "dossier.html",
        "manifest.json",
    }
    assert required_files <= {item["name"] for item in manifest["files"]}

    loaded = runtime.load_package_run(manifest["run_id"])
    assert loaded["manifest"]["run_id"] == manifest["run_id"]
    assert loaded["contents"]["report.json"]["rendered_html"]
    assert runtime.list_package_runs()[0]["run_id"] == manifest["run_id"]

    deletion = runtime.delete_package_run(manifest["run_id"])
    assert deletion["deleted"] is True
    assert deletion["recoverable"] is False
    assert runtime.list_package_runs() == []


def test_package_run_repository_rejects_unsafe_identifiers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "RISK_PACKAGE_RUN_ROOT", tmp_path)

    with pytest.raises(ValueError, match="invalid package run identifier"):
        runtime.load_package_run("../../outside")


def test_live_narrative_is_an_explicit_mode_without_implicit_provider_call() -> None:
    request = runtime.PackageRunRequest(narrative_mode="live_llm", model="gpt-5.6-terra")

    assert request.narrative_mode == "live_llm"
    assert request.model == "gpt-5.6-terra"
