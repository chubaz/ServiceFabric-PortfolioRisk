#!/usr/bin/env python3
"""Read-only tutorials for the S5 experiment-object contracts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
for path in (
    ROOT / "tests",
    ROOT / "packages" / "risk_experiments" / "src",
    ROOT / "packages" / "risk_registry" / "src",
):
    sys.path.insert(0, str(path))

from experiments.test_experiment_objects import experiment_object_set  # noqa: E402
from risk_experiments import ExperimentObjectSet, ScenarioDefinition, WorldContextPack  # noqa: E402


SECTIONS = (
    "scientific",
    "governance",
    "world",
    "resources",
    "authority",
    "outputs",
    "reproducibility",
)


def scientific() -> dict[str, object]:
    value = experiment_object_set().scientific_design
    identities = value.comparison_identity()
    assert len(identities) == 5
    return {
        "question": value.research_question.question,
        "hypothesis": value.hypothesis.statement,
        "comparison_identities": identities,
        "pack_digest": value.pack_digest,
    }


def governance() -> dict[str, object]:
    value = experiment_object_set().portfolio_governance
    assert value.risk_policy.mandate_reference == value.mandate.reference
    return {
        "portfolio": value.portfolio.reference,
        "mandate": value.mandate.reference,
        "risk_policy": value.risk_policy.reference,
        "rule_ids": [item.rule_id for item in value.risk_policy.rules],
        "pack_digest": value.object_digest,
    }


def world() -> dict[str, object]:
    value = experiment_object_set().world_context
    assert all(item.available_at <= value.data_manifest.as_of for item in value.data_manifest.datasets)
    return {
        "as_of": value.data_manifest.as_of.isoformat(),
        "datasets": [item.reference for item in value.data_manifest.datasets],
        "environment": value.environment.reference,
        "scenario": value.scenario.reference,
        "portfolio_view": value.portfolio_view.reference,
        "world_pack_digest": value.object_digest,
    }


def resources() -> dict[str, object]:
    objects = experiment_object_set()
    value = objects.resource_envelope
    capability = value.capability_pack.capabilities[0].reference
    dataset = objects.world_context.data_manifest.datasets[0].reference
    assert value.allows_capability(capability)
    assert value.allows_dataset(capability, dataset)
    assert not value.allows_capability("capability:risk:undeclared@1.0.0")
    return {
        "reachable_capabilities": [item.reference for item in value.capability_pack.capabilities],
        "selected_example": capability,
        "dataset_access_allowed": value.allows_dataset(capability, dataset),
        "undeclared_capability_allowed": False,
        "resource_envelope_digest": value.object_digest,
    }


def authority() -> dict[str, object]:
    value = experiment_object_set().authority_envelope
    assert value.autonomy.mode == "human_only"
    assert not value.supra_agent.enabled
    assert value.effects.external_effects == "disabled"
    return {
        "agent": value.processing.agent.reference,
        "graph": value.processing.graph.reference,
        "workflow": value.processing.workflow.reference,
        "resolution_mode": value.autonomy.mode,
        "supra_agent_enabled": value.supra_agent.enabled,
        "external_effects": value.effects.external_effects,
        "authority_envelope_digest": value.object_digest,
    }


def outputs() -> dict[str, object]:
    objects = experiment_object_set()
    value = objects.output_evaluation
    assert value.report_template.hidden_calculations is False
    assert value.dashboard.hidden_calculations is False
    return {
        "metric": objects.scientific_design.metric.reference,
        "evaluation_suite": value.evaluation_suite.reference,
        "report_template": value.report_template.reference,
        "dashboard": value.dashboard.reference,
        "out_of_sample_policy": value.evaluation_suite.out_of_sample_policy,
        "hidden_calculations": False,
    }


def reproducibility() -> dict[str, object]:
    original = experiment_object_set()
    repeat = experiment_object_set()
    assert repeat.fixture_context_digest == original.fixture_context_digest

    scenario_payload = original.world_context.scenario.model_dump(mode="json")
    scenario_payload["transformation"] = "Apply a declared tutorial stress."
    scenario_payload["object_digest"] = None
    changed_scenario = ScenarioDefinition.model_validate(scenario_payload)
    world_payload = original.world_context.model_dump(mode="json")
    world_payload["scenario"] = changed_scenario.model_dump(mode="json")
    world_payload["portfolio_view"]["scenario_reference"] = changed_scenario.reference
    world_payload["portfolio_view"]["object_digest"] = None
    world_payload["object_digest"] = None
    changed_world = WorldContextPack.model_validate(world_payload)
    object_payload = original.model_dump(mode="json")
    object_payload["world_context"] = changed_world.model_dump(mode="json")
    for field in (
        "world_context_digest",
        "resource_envelope_digest",
        "authority_envelope_digest",
        "evaluation_envelope_digest",
        "fixture_context_digest",
    ):
        object_payload[field] = None
    changed = ExperimentObjectSet.model_validate(object_payload)
    assert changed.world_context_digest != original.world_context_digest
    assert changed.resource_envelope_digest == original.resource_envelope_digest
    return {
        "repeat_digest_equal": True,
        "original_fixture_digest": original.fixture_context_digest,
        "changed_fixture_digest": changed.fixture_context_digest,
        "changed_components": ["world_context"],
        "unchanged_components": ["resource_envelope", "authority_envelope", "evaluation_envelope"],
    }


RUNNERS = {
    "scientific": scientific,
    "governance": governance,
    "world": world,
    "resources": resources,
    "authority": authority,
    "outputs": outputs,
    "reproducibility": reproducibility,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect and verify the reviewed-synthetic S5 tutorial object set."
    )
    parser.add_argument("section", choices=(*SECTIONS, "all"))
    args = parser.parse_args()
    selected = SECTIONS if args.section == "all" else (args.section,)
    result = {
        "fixture": "reviewed_synthetic_tutorial_only",
        "not_thesis_evidence": True,
        "sections": {name: RUNNERS[name]() for name in selected},
        "status": "PASS",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
