from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import case_replay_runtime


NOW = datetime(2015, 8, 25, 9, tzinfo=timezone.utc)


class Store:
    def __init__(self, *, value=None, values=()):
        self.value = value
        self.values = values

    def get_case(self, _case_id):  # type: ignore[no-untyped-def]
        return self.value

    def list(self):  # type: ignore[no-untyped-def]
        return list(self.values)

    def get(self, _batch_id):  # type: ignore[no-untyped-def]
        return self.value

    def get_optional(self, *_args):  # type: ignore[no-untyped-def]
        return self.value


def test_replay_adapter_includes_unselected_ex_ante_context_and_never_reads_gold_roles(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    case = SimpleNamespace(observable_state=SimpleNamespace(
        observation_ids=("event-control", "market-signal"),
    ))
    bundle = SimpleNamespace(
        batch_id="batch-one", unit_id="unit-one", context_execution_id="execution-one",
    )
    reference = SimpleNamespace(compiled_case_id="case-one", bundle=bundle)
    unit = SimpleNamespace(
        unit_id="unit-one", evidence_ids=("market-signal",),
        observation_time=NOW - timedelta(days=1), available_at=NOW,
        scope_type=SimpleNamespace(value="instrument"), scope_id="security-one",
        direction=SimpleNamespace(value="negative"), score_band=SimpleNamespace(value="extreme"),
    )
    batch = SimpleNamespace(
        selected_units=(unit,), plan=SimpleNamespace(dataset_snapshot_id="snapshot-one"),
    )
    candidate = SimpleNamespace(
        candidate_id="candidate-control", channel=SimpleNamespace(value="events"),
        canonical_entity_id="security-one", source_record_id="news-one",
        display_title="Control event", display_summary="Eligible but not Gold-selected.",
        observed_at=NOW - timedelta(hours=1), available_at=NOW + timedelta(minutes=1),
        eligible_at_replay_time=True, evidence_ids=("event-control",), quality_flags=(),
    )
    execution = SimpleNamespace(
        execution_id="execution-one",
        proposal=SimpleNamespace(candidates=(candidate,)),
    )
    context = SimpleNamespace(execution=execution)
    plan = SimpleNamespace(latest=SimpleNamespace(plan_id="plan-one"))
    gold_store = Store(value=case, values=(reference,))
    monkeypatch.setattr(case_replay_runtime, "gold_case_store", lambda: gold_store)
    monkeypatch.setattr(case_replay_runtime, "labelling_store", lambda: Store(value=batch))
    monkeypatch.setattr(case_replay_runtime, "context_work_store", lambda: Store(value=plan))
    monkeypatch.setattr(case_replay_runtime, "context_execution_store", lambda: Store(value=context))

    observations, triggers = case_replay_runtime.resolve_case_replay_inputs("case-one")

    assert {item.observation_id for item in observations} == {"market-signal", "event-control"}
    assert [item.replay_at for item in triggers] == [NOW, NOW + timedelta(minutes=1)]
    assert triggers[1].event_id is not None and triggers[1].event_id.startswith("event-")
    preview = case_replay_runtime.case_replay_preview("case-one")
    assert preview["source"] == "licensed historical records"
    assert preview["gold_reference_visible_to_architecture"] is False


def test_replay_adapter_fails_closed_when_compiled_case_stream_cannot_be_resolved(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    case = SimpleNamespace(observable_state=SimpleNamespace(observation_ids=("missing-observation",)))
    bundle = SimpleNamespace(batch_id="batch-one", unit_id="unit-one", context_execution_id="execution-one")
    reference = SimpleNamespace(compiled_case_id="case-one", bundle=bundle)
    unit = SimpleNamespace(
        unit_id="unit-one", evidence_ids=("market-signal",), observation_time=NOW,
        available_at=NOW, scope_type=SimpleNamespace(value="instrument"), scope_id="security-one",
        direction=SimpleNamespace(value="negative"), score_band=SimpleNamespace(value="extreme"),
    )
    batch = SimpleNamespace(selected_units=(unit,), plan=SimpleNamespace(dataset_snapshot_id="snapshot-one"))
    context = SimpleNamespace(execution=SimpleNamespace(
        execution_id="execution-one", proposal=SimpleNamespace(candidates=()),
    ))
    monkeypatch.setattr(case_replay_runtime, "gold_case_store", lambda: Store(value=case, values=(reference,)))
    monkeypatch.setattr(case_replay_runtime, "labelling_store", lambda: Store(value=batch))
    monkeypatch.setattr(case_replay_runtime, "context_work_store", lambda: Store(value=SimpleNamespace(latest=SimpleNamespace(plan_id="plan-one"))))
    monkeypatch.setattr(case_replay_runtime, "context_execution_store", lambda: Store(value=context))

    try:
        case_replay_runtime.resolve_case_replay_inputs("case-one")
    except Exception as error:
        assert "does not reconcile" in str(error)
    else:
        raise AssertionError("unresolved Case inputs must fail closed")
