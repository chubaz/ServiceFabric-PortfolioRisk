from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_s5_implements_each_pre_fixture_object_pack_without_a_worker() -> None:
    contract = read(
        "packages/risk_experiments/src/risk_experiments/experiment_objects.py"
    )
    for name in (
        "PortfolioGovernancePack",
        "WorldContextPack",
        "ResourceEnvelope",
        "AuthorityEnvelope",
        "OutputEvaluationPack",
        "ExperimentObjectSet",
    ):
        assert f"class {name}" in contract
    for digest in (
        "world_context_digest",
        "resource_envelope_digest",
        "authority_envelope_digest",
        "evaluation_envelope_digest",
        "fixture_context_digest",
    ):
        assert digest in contract
    assert "undeclared_resource_rule" in contract
    assert 'external_effects: Literal["disabled"]' in contract
    assert "worker" not in contract.casefold()


def test_s5_preserves_object_responsibilities_and_registry_boundaries() -> None:
    plan = read(
        "docs/workplans/platform-development/"
        "studio-foundation-5-experiment-object-model.md"
    )
    registry = read("packages/risk_registry/src/risk_registry/models.py")
    experiment = read("packages/risk_experiments/src/risk_experiments/models.py")
    assert "A mandate states what the portfolio is for" in plan
    assert "The `resource_envelope_digest` covers the complete reachable index" in plan
    assert 'EXPERIMENT_OBJECT_SET = "experiment_object_set"' in registry
    assert "object_set: RegistryIdentity | None" in experiment
    assert "an experiment object set requires a scientific-design identity" in experiment


def test_s5_tutorials_cover_all_object_packs_and_reproducibility() -> None:
    index = read("docs/tutorials/s5/README.md")
    script = read("scripts/thesis/tutorial_s5_objects.py")
    for number in range(1, 8):
        assert f"{number}. [" in index
    for section in (
        "scientific",
        "governance",
        "world",
        "resources",
        "authority",
        "outputs",
        "reproducibility",
    ):
        assert f'"{section}"' in script
    assert '"not_thesis_evidence": True' in script


def test_s5_has_one_focused_network_free_verification_target() -> None:
    makefile = read("Makefile")
    gate = makefile.split(".PHONY: verify-studio-foundation-s5\n", 1)[1]
    assert "tests/experiments/test_experiment_objects.py" in gate
    assert "tests/tutorials/test_s5_object_tutorial.py" in gate
    assert "tutorial_s5_objects.py all" in gate
    assert "update_manifest_hashes.py" in gate
    assert "git diff --check" in gate
    for forbidden in ("OPENAI_API_KEY", "curl ", "start worker", "execute_trade"):
        assert forbidden not in gate
