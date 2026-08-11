from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_s4_closure_preserves_the_bounded_evidence_gate() -> None:
    plan = read(
        "docs/workplans/platform-development/"
        "studio-foundation-4-experiment-run-audit.md"
    )
    assert "implementation complete and locally verified" in plan
    assert "Verification: `make verify-studio-foundation-s4`" in plan
    assert "candidate commit pending" in plan
    assert "no experiment generator" in plan
    assert "no automatic object repair" in plan


def test_s4_has_one_focused_network_free_verification_target() -> None:
    makefile = read("Makefile")
    gate = makefile.split(".PHONY: verify-studio-foundation-s4", 1)[1]
    assert "tests/artifacts/test_run_comparison.py" in gate
    assert "tests/application/test_experiment_run_audit.py" in gate
    assert "tests/architecture/test_experiment_run_audit_control_plane.py" in gate
    assert "update_manifest_hashes.py" in gate
    assert "git diff --check" in gate
    for forbidden in ("OPENAI_API_KEY", "curl ", "start worker", "execute_trade"):
        assert forbidden not in gate


def test_pre_fixture_cycle_freezes_reachable_resources_not_agent_choices() -> None:
    current = read("docs/workplans/current.md")
    plan = read(
        "docs/workplans/platform-development/"
        "studio-foundation-5-experiment-object-model.md"
    )
    assert "studio-foundation-5-experiment-object-model.md" in current
    for digest in (
        "world_context_digest",
        "resource_envelope_digest",
        "authority_envelope_digest",
        "evaluation_envelope_digest",
        "fixture_context_digest",
    ):
        assert digest in plan
    assert "ExperimentRunTrace" in plan
    assert "SupraAgentPolicy" in plan
    assert "RiskPolicySet" in plan
    assert "runtime discovery or installation" in plan


def test_pre_fixture_readiness_inventory_tracks_s5_without_claiming_acceptance() -> None:
    inventory = read("docs/thesis/experiment-object-readiness.md")
    assert "provisional engineering assessment, not an acceptance record" in inventory
    assert "`MandateVersion`" in inventory and "S5.2 objective" in inventory
    assert "Candidate mandate content requires portfolio-owner review" in inventory
    assert "`MarketEnvironmentSnapshot`" in inventory
    assert "`CapabilityPack`" in inventory
    assert "S5.1 Scientific identity" in inventory
    assert "Supra-agent resolution" in inventory
    assert "Admission remains\nblocked" in inventory
    assert "Contract completion is not methodological approval" in inventory
    assert "must not block" in inventory
