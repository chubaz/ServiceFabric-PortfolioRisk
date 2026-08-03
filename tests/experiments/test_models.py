from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError
from risk_experiments import (
    DataTruth,
    ExperimentBudget,
    ExperimentDefinition,
    ExperimentSet,
    FactorDimension,
    PresentationMode,
    SourceBinding,
    TemporalWindow,
    canonical_digest,
)
from risk_registry import AssetKind, RegistryIdentity


def binding(role: str) -> SourceBinding:
    reference = f"canonical:{role}:alpha"
    return SourceBinding(
        role=role,
        reference=reference,
        revision="v1",
        digest=canonical_digest({"reference": reference, "revision": "v1"}),
    )


def definition(*, mode: PresentationMode = PresentationMode.INTERACTIVE_FOREGROUND) -> ExperimentDefinition:
    asset_kind = AssetKind.EVALUATION if mode == PresentationMode.EVALUATION_ONLY else AssetKind.WORKFLOW
    return ExperimentDefinition(
        experiment_id="experiment-alpha",
        version="0.1.0",
        name="Daily risk replay",
        purpose="Review portfolio risk through a bounded historical replay.",
        hypothesis="The governed workflow produces reviewable material findings.",
        owner="local.researcher",
        created_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
        temporal=TemporalWindow(start_date=date(2024, 1, 2), end_date=date(2024, 1, 5)),
        presentation_mode=mode,
        data_truth=DataTruth.REVIEWED_SYNTHETIC,
        source_bindings=tuple(
            sorted(
                (binding("portfolio"), binding("snapshot_policy"), binding("mandate"), binding("data_revision")),
                key=lambda item: (item.role, item.reference, item.revision),
            )
        ),
        system_assets=(RegistryIdentity(kind=asset_kind, namespace="risk", asset_id="daily-review", version="1.0.0"),),
        budget=ExperimentBudget(max_model_calls=8, max_cost_usd=Decimal("1.25")),
    )


def test_definition_is_digest_bound_and_effect_free() -> None:
    value = definition()
    assert value.definition_digest.startswith("sha256:")
    assert value.external_effects == "disabled"
    assert value.system_assets[0].reference == "workflow:risk:daily-review@1.0.0"


def test_definition_requires_temporal_order_and_canonical_bindings() -> None:
    with pytest.raises(ValidationError):
        TemporalWindow(start_date=date(2025, 1, 2), end_date=date(2025, 1, 1))
    with pytest.raises(ValidationError):
        ExperimentDefinition.model_validate(
            {**definition().model_dump(mode="json"), "source_bindings": [binding("portfolio").model_dump(mode="json")], "definition_digest": None}
        )


def test_experiment_set_bounds_combinatorics() -> None:
    value = ExperimentSet(
        experiment_set_id="set-alpha",
        name="Architecture comparison",
        research_question="Which reviewed architecture produces the strongest evidence coverage?",
        owner="local.researcher",
        experiment_ids=("experiment-alpha",),
        variable_factors=(FactorDimension(name="architecture", values=("b0", "b1", "a1")),),
        seeds=(11, 29),
        repeat_count=2,
        max_concurrency=2,
        created_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
    )
    assert value.definition_digest.startswith("sha256:")
    assert value.aggregation_rule == "per_experiment_then_set_summary"
