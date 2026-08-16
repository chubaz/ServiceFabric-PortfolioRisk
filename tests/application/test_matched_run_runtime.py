from pathlib import Path

import matched_run_runtime


def test_setup_is_honest_when_no_gold_backed_case_exists(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_LABEL_ROOT", str(tmp_path / "labels"))
    result = matched_run_runtime.matched_run_setup()
    assert result["ready"] is False
    assert result["cases"] == []
    assert "Gold reference" in result["blocker"]
    assert {item["id"] for item in result["architectures"]} == {"B0", "B1", "A1"}


def test_setup_capability_packages_are_versioned_and_bounded(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_LABEL_ROOT", str(tmp_path / "labels"))
    result = matched_run_runtime.matched_run_setup()
    assert [(item["package_id"], item["capability_count"]) for item in result["packages"]] == [
        ("market-event-core", 3), ("full-selected", 9),
    ]


def test_workbench_exposes_compile_and_retained_result_routes() -> None:
    source = Path("apps/portfolio-risk-workbench/labs/duckdb_server.py").read_text()
    assert '"/api/experiments/matched-run-plans/setup"' in source
    assert '"/api/experiments/matched-run-plans/compile"' in source
    assert '"/api/experiments/matched-run-plans/{matrix_id}/results"' in source
    assert '"/api/experiments/matched-run-plans/{matrix_id}/cells/{cell_id}/result"' in source
    assert '"/api/experiments/matched-run-plans/{matrix_id}/bundle"' in source
    assert '"/api/experiments/reproducibility-bundles"' in source
    assert "compile_matched_plan(request)" in source
    assert "list_trajectory_results(matrix_id)" in source


def test_run_view_explains_that_compilation_does_not_execute() -> None:
    html = Path("apps/portfolio-risk-workbench/labs/index.html").read_text()
    javascript = Path("apps/portfolio-risk-workbench/labs/labs.js").read_text()
    assert 'id="matched-run-form"' in html
    assert "Compilation itself never calls a model" in html
    assert "Nothing was executed" in javascript
    assert "cycles with output" in javascript
    assert "Comparison ready" in javascript
    assert "View timeline" in javascript
    assert "simulated time frozen during processing" in javascript
