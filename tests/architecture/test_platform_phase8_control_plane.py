from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_phase8_is_effect_free_and_not_a_scheduler():
    source = (ROOT / "packages/risk_experiments/src/risk_experiments/run_trace.py").read_text()
    runtime = (ROOT / "apps/portfolio-risk-workbench/labs/run_trace_runtime.py").read_text()
    assert 'labels_accessed: Literal[False]' in source
    assert 'metric_calculated: Literal[False]' in source
    assert 'external_effects: Literal["disabled"]' in source
    assert "scheduler" in runtime
