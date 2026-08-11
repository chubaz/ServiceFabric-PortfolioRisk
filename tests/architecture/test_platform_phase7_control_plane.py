from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_p7_workplan_and_acceptance_preserve_the_calibration_boundary() -> None:
    current = read("docs/workplans/current.md")
    plan = read("docs/workplans/platform-development/phase-7-fixture-context.md")
    acceptance = read("docs/thesis/methodology-acceptance-calibration-pilot.md")
    assert "phase-7-fixture-context.md" in current
    assert "apparatus calibration only" in plan
    assert "future outcome labels" in plan
    assert "does not execute a worker" in plan
    for claim in (
        "thesis-level inference",
        "predictive superiority",
        "causal effect",
        "risk avoidance",
        "risk mitigation",
    ):
        assert claim in acceptance


def test_p7_contract_requires_validated_registry_and_verified_source_bytes() -> None:
    contract = read(
        "packages/risk_experiments/src/risk_experiments/fixture_context.py"
    )
    assert "ELIGIBLE_FIXTURE_STATES" in contract
    assert "LifecycleState.VALIDATED" in contract
    assert "LifecycleState.PUBLISHED" in contract
    assert "fixture source digest mismatch" in contract
    assert "LocalFixtureContextStore" in contract
    assert "external_effects" in contract
    assert "supra_agent_enabled" in contract


def test_p7_gate_is_network_free_and_never_admits_the_real_registry() -> None:
    makefile = read("Makefile")
    gate = makefile.split(".PHONY: verify-platform-phase7", 1)[1]
    assert "tests/experiments/test_fixture_context.py" in gate
    assert "tests/application/test_fixture_context_runtime.py" in gate
    assert "test_platform_phase7_control_plane.py" in gate
    assert "tutorial_p7_fixture.py" in gate
    assert "register_calibration_pilot.py" in gate
    for forbidden in ("--apply", "OPENAI_API_KEY", "curl ", "execute_trade"):
        assert forbidden not in gate
