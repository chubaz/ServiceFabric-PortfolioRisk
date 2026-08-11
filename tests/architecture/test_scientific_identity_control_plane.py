from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_scientific_pack_has_one_canonical_owner_and_bounded_scope() -> None:
    contract = read(
        "packages/risk_experiments/src/risk_experiments/scientific_design.py"
    )
    plan = read(
        "docs/workplans/platform-development/"
        "studio-foundation-5-1-scientific-identity-pack.md"
    )
    for name in (
        "ResearchQuestionDefinition",
        "HypothesisDefinition",
        "BaselineDefinition",
        "InformationRegimeDefinition",
        "RiskOutcomeDefinition",
        "MetricDefinition",
        "ScientificDesignPack",
    ):
        assert f"class {name}" in contract
    assert "risk_experiments` owns scientific experiment meaning" in plan
    assert "no metric calculation" in plan
    assert "no Fixture Context resolver" in plan


def test_experiment_and_registry_boundaries_require_exact_saved_identity() -> None:
    registry = read("packages/risk_registry/src/risk_registry/models.py")
    experiments = read("packages/risk_experiments/src/risk_experiments/models.py")
    server = read("apps/portfolio-risk-workbench/labs/duckdb_server.py")
    assert 'SCIENTIFIC_DESIGN = "scientific_design"' in registry
    assert "scientific_design: RegistryIdentity | None" in experiments
    assert "_experiment_definition_registry_assets" in server
    assert "definition.scientific_design" in server


def test_s5_1_has_a_focused_network_free_verification_target() -> None:
    makefile = read("Makefile")
    gate = makefile.split(".PHONY: verify-studio-foundation-s5-1", 1)[1]
    assert "tests/experiments/test_scientific_design.py" in gate
    assert "tests/artifacts/test_run_comparison.py" in gate
    assert "tests/application/test_experiment_api.py" in gate
    assert "test_scientific_identity_control_plane.py" in gate
    assert "git diff --check" in gate
    for forbidden in ("OPENAI_API_KEY", "curl ", "worker start", "execute_trade"):
        assert forbidden not in gate
