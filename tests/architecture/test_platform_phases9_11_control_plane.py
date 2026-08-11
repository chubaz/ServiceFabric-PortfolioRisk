from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_program_keeps_labels_and_execution_closed():
    source = (ROOT / "packages/risk_experiments/src/risk_experiments/experimental_program.py").read_text()
    runtime = (ROOT / "apps/portfolio-risk-workbench/labs/experimental_program_runtime.py").read_text()
    assert 'labels_reachable_by_processing: Literal[False]' in source
    assert '"outputs_generated": False' in runtime
    assert '"labels_opened": False' in runtime
    assert '"metrics_calculated": False' in runtime
