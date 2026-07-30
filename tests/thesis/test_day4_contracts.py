import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from portfolio_risk_thesis.day3.contracts import digest
from portfolio_risk_thesis.day4.contracts import (
    AUTHORIZED_MODEL_CALLS,
    ArchitectureObservation,
    Day4ExecutionPlan,
    Day4Task,
    Day4WindowSet,
    HistoricalWindow,
    PortfolioDayKey,
)


def _dates(start: datetime) -> tuple[datetime, ...]:
    return tuple(start + timedelta(days=index) for index in range(5))


def test_window_contracts_are_strict_frozen_utc_and_non_overlapping():
    start = datetime(2024, 1, 2, 21, tzinfo=UTC)
    windows = Day4WindowSet(
        windows=(
            HistoricalWindow(
                window_id="stress_a",
                kind="stress",
                rationale="Reviewed first stress window.",
                review_dates=_dates(start),
                trigger_available_at=start,
                relevant_portfolios=("portfolio-a",),
            ),
            HistoricalWindow(
                window_id="stress_b",
                kind="stress",
                rationale="Reviewed second stress window.",
                review_dates=_dates(start + timedelta(days=20)),
                trigger_available_at=start + timedelta(days=20),
                relevant_portfolios=("portfolio-b",),
            ),
            HistoricalWindow(
                window_id="control",
                kind="control",
                rationale="Reviewed quiet control.",
                review_dates=_dates(start + timedelta(days=40)),
            ),
        )
    )
    assert windows.window_set_digest.startswith("sha256:")
    with pytest.raises(ValidationError):
        windows.windows = ()
    with pytest.raises(ValidationError):
        HistoricalWindow.model_validate(
            windows.windows[0].model_dump(mode="python") | {"unexpected": True}
        )
    with pytest.raises(ValidationError):
        HistoricalWindow(
            window_id="stress_a",
            kind="stress",
            rationale="Overlapping.",
            review_dates=_dates(start),
            trigger_available_at=None,
        )


def test_portfolio_day_and_task_digests_cover_semantic_identity():
    key = PortfolioDayKey(
        portfolio_id="portfolio-a",
        window_id="stress_a",
        as_of=datetime(2024, 1, 2, 21, tzinfo=UTC),
    )
    common = {
        "experiment_digest": digest("experiment"),
        "key": key,
        "architecture_id": "B1",
        "repetition": 0,
        "context_digest": digest("context"),
        "model_snapshot": "fixture-structured-v1",
        "prompt_manifest_digest": digest("prompts"),
        "expected_model_calls": 1,
    }
    task = Day4Task(**common)
    assert task.task_id.startswith("sha256:")
    assert task == Day4Task.model_validate(task.model_dump(mode="python"))
    changed = Day4Task(**(common | {"repetition": 1}))
    assert changed.task_id != task.task_id
    with pytest.raises(ValidationError):
        Day4Task(**(common | {"expected_model_calls": 4}))


def test_architecture_observation_classifies_abstention_and_provider_failure():
    key = PortfolioDayKey(
        portfolio_id="portfolio-a",
        window_id="control",
        as_of=datetime(2024, 3, 1, 21, tzinfo=UTC),
    )
    base = {
        "task_id": digest("task"),
        "key": key,
        "architecture_id": "B0",
        "repetition": 0,
        "context_digest": digest("context"),
        "semantic_output_digest": digest("output"),
        "severity": 0,
        "critic_passed": True,
        "latency_ms": 1,
        "input_tokens": 0,
        "output_tokens": 0,
    }
    abstention = ArchitectureObservation(**base, status="ABSTAIN")
    assert abstention.observation_class == "abstention"
    failure = ArchitectureObservation(
        **base,
        status="ABSTAINED_AGENT_OUTPUT",
        execution_failure=True,
        provider_error="provider_error",
    )
    assert failure.observation_class == "execution_failure"
    with pytest.raises(ValidationError):
        ArchitectureObservation(**base, status="NO_ISSUE", effects=("trade",))


def test_execution_plan_rejects_any_count_or_call_math_drift():
    key_start = datetime(2024, 1, 2, 21, tzinfo=UTC)
    contexts = tuple(
        PortfolioDayKey(
            portfolio_id=f"portfolio-{portfolio}",
            window_id=window,
            as_of=key_start + timedelta(days=window_index * 20 + day),
        )
        for window_index, window in enumerate(("stress_a", "stress_b", "control"))
        for portfolio in ("a", "b", "c")
        for day in range(5)
    )
    experiment_digest = digest("experiment")
    task_args = {
        "experiment_digest": experiment_digest,
        "model_snapshot": "fixture-structured-v1",
        "prompt_manifest_digest": digest("prompts"),
    }
    tasks = [
        Day4Task(
            **task_args,
            key=key,
            architecture_id=architecture,
            repetition=0,
            context_digest=digest(key.key_digest),
            expected_model_calls={"B0": 0, "B1": 1, "A1": 4}[architecture],
        )
        for key in contexts
        for architecture in ("B0", "B1", "A1")
    ]
    anchors = tuple(
        next(
            key
            for key in contexts
            if key.portfolio_id == f"portfolio-{portfolio}" and key.window_id == window
        )
        for portfolio in ("a", "b", "c")
        for window in ("stress_a", "stress_b", "control")
    )
    tasks.extend(
        Day4Task(
            **task_args,
            key=key,
            architecture_id=architecture,
            repetition=1,
            context_digest=digest(key.key_digest),
            expected_model_calls={"B1": 1, "A1": 4}[architecture],
        )
        for key in anchors
        for architecture in ("B1", "A1")
    )
    plan = Day4ExecutionPlan(
        experiment_digest=experiment_digest,
        contexts=contexts,
        tasks=tuple(tasks),
    )
    assert len(plan.contexts) == 45
    assert len(plan.tasks) == 153
    assert sum(task.expected_model_calls for task in plan.tasks) == AUTHORIZED_MODEL_CALLS
    assert plan.plan_digest.startswith("sha256:")
    with pytest.raises(ValidationError):
        Day4ExecutionPlan(
            experiment_digest=experiment_digest,
            contexts=contexts,
            tasks=tuple(tasks[:-1]),
        )


def test_reviewed_manifest_schema_freezes_review_effect_and_panel_bounds(example_root):
    schema = json.loads(
        (
            example_root.parents[1]
            / "data"
            / "schemas"
            / "thesis-experiment-results"
            / "day4-experiment-manifest-v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert schema["properties"]["reviewed"]["const"] is True
    assert schema["properties"]["effects"]["maxItems"] == 0
    assert schema["properties"]["portfolios"]["minItems"] == 3
    assert schema["properties"]["portfolios"]["maxItems"] == 3
    assert schema["additionalProperties"] is False
