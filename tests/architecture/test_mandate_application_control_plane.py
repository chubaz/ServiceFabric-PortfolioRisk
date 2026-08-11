from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_mandate_application_reuses_canonical_objects_and_capabilities() -> None:
    source = (ROOT / "apps/portfolio-risk-workbench/labs/mandate_application.py").read_text()

    assert "build_calibration_pilot" in source
    assert "mandate_bundle" in source
    assert 'invoke("portfolio.snapshot.create"' in source
    assert 'invoke("portfolio.exposure.summarize"' in source
    assert "RiskFinding" in source
    assert "DecisionProposal" in source
    assert "temporary_application_work_product" in source


def test_application_ui_exposes_policy_results_receipts_and_decision_review() -> None:
    html = (ROOT / "apps/portfolio-risk-workbench/labs/index.html").read_text()
    javascript = (ROOT / "apps/portfolio-risk-workbench/labs/labs.js").read_text()

    assert 'id="mandate-application"' in html
    assert "Calculation first. Interpretation second. Human decision last." in html
    assert "Capability work record" in javascript
    assert "Temporary application work product" in javascript
    assert "LLM called" in javascript
    assert 'const selectedScenario = $("#mandate-application-scenario").value' in javascript
    assert '$("#mandate-application-scenario").value = selectedScenario' in javascript
