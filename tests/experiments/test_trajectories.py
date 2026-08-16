from datetime import datetime, timedelta, timezone
from time import sleep

from risk_experiments import (
    ArchitectureConfig, ArchitectureDecision, ArchitectureOutput,
    CycleExecutionResult, ExperimentalCapabilityConfig, IdentityCondition,
    LocalTrajectoryStore, MatchedRunCell, ReplayObservation, ReplayTrigger,
    RunBudget, RunInput, execute_point_in_time_trajectory,
)


START = datetime(2016, 6, 1, 14, 0, tzinfo=timezone.utc)


def _cell(treatment: str = "B0") -> MatchedRunCell:
    capability = ExperimentalCapabilityConfig(
        capability_id="market-metrics", version="1.0.0",
        implementation_class="deterministic", parameterization="preconfigured",
        evaluation_roles=("architecture_input",), parameter_digest="sha256:" + "1" * 64,
    )
    agent = treatment == "B1"
    architecture = ArchitectureConfig(
        architecture_id="b1-single-agent" if agent else "b0-baseline",
        architecture_type="single_agent" if agent else "deterministic",
        version="1.0.0", deterministic=not agent,
        model_reference="model-one" if agent else None,
        interpretation_mode="single_agent" if agent else "fixed_rules",
    )
    return MatchedRunCell(
        cell_id=f"cell-{treatment.lower()}", case_digest="sha256:" + "3" * 64,
        treatment_id=treatment, capability_package_id="market-core",
        capability_package_digest="sha256:" + "4" * 64, repetition=1,
        seed="seed:1", identity_condition=IdentityCondition.NAMED_HISTORICAL,
        run_input=RunInput(
            case_id="case-one", architecture_id=architecture.architecture_id,
            information_regime="point-in-time", capability_references=("market-metrics",),
            capability_configurations=(capability,), repetition=1,
            observation_ids=("observation-a",),
        ), architecture=architecture,
        prompt_reference="prompt-one" if agent else None,
        model_reference="model-one" if agent else None,
        context_policy_reference="case-observable-state-v1",
        memory_policy="cleared_each_run",
        budget=RunBudget(
            max_model_calls=2 if agent else 0, max_input_tokens=1000 if agent else 0,
            max_output_tokens=200 if agent else 0, max_cost_usd=.2 if agent else 0,
            max_processing_seconds=60,
        ),
    )


def _observation(name: str, available_at: datetime) -> ReplayObservation:
    return ReplayObservation(
        observation_id=name, kind="event", observed_at=available_at,
        available_at=available_at, evidence_ids=(f"evidence-{name}",),
        content_reference=f"observation:{name}", content_digest="sha256:" + "2" * 64,
    )


def _triggers() -> tuple[ReplayTrigger, ...]:
    return (
        ReplayTrigger(trigger_id="trigger-one", kind="scheduled_cycle", replay_at=START),
        ReplayTrigger(trigger_id="trigger-two", kind="daily_close", replay_at=START + timedelta(hours=2)),
    )


def _abstain(context) -> CycleExecutionResult:
    return CycleExecutionResult(
        cycle_id=context.cycle_id, status="abstained", reason="Evidence is insufficient.",
        capability_calls=1, model_calls=0, capability_processing_ms=0,
        model_processing_ms=0, validation_processing_ms=0, input_tokens=0,
        cached_input_tokens=0, output_tokens=0, estimated_cost_usd=0,
    )


def test_releases_observations_only_when_available_and_freezes_replay_time() -> None:
    cell = _cell()
    observations = (
        _observation("observation-early", START - timedelta(minutes=1)),
        _observation("observation-late", START + timedelta(hours=1)),
    )
    trajectory = execute_point_in_time_trajectory(
        matrix_id="matrix-one", cell=cell, triggers=_triggers(),
        observations=observations, processor=_abstain,
    )
    assert [tuple(item.observation_id for item in cycle.context.eligible_observations) for cycle in trajectory.cycles] == [
        ("observation-early",), ("observation-early", "observation-late"),
    ]
    assert trajectory.status == "completed_with_abstentions"
    assert all(
        cycle.processing_receipt.replay_paused_at
        == cycle.processing_receipt.replay_resumed_at
        == cycle.context.replay_at
        for cycle in trajectory.cycles
    )


def test_retains_one_valid_architecture_output_per_successful_cycle() -> None:
    cell = _cell("B1")

    def processor(context) -> CycleExecutionResult:
        output = ArchitectureOutput(
            output_id=f"output-{context.cycle_id[6:]}", run_id=context.run_id,
            architecture_type="single_agent", assessment_state="clear", severity=0,
            confidence=0.5, confidence_kind="ordinal_judgement",
            confidence_method="bounded controlled test judgement", findings=(),
            supporting_evidence_ids=(), risk_interpretation="No supported material finding.",
            expectations="Continue point-in-time monitoring.",
            decision=ArchitectureDecision(
                monitoring_action="continue_monitoring", portfolio_action="none",
                alternatives_considered=("investigate",), human_review_required=False,
            ), missing_information=("additional evidence",), assumptions=(),
            architecture_id=cell.architecture.architecture_id,
            capabilities_used=cell.run_input.capability_references,
            cycle_id=context.cycle_id, as_of=context.replay_at,
            trigger_available_at=context.trigger.replay_at,
            produced_at=context.replay_at + timedelta(milliseconds=1),
            input_context_digest=context.input_context_digest,
            case_id=context.case_id, repetition=cell.repetition,
        )
        return CycleExecutionResult(
            cycle_id=context.cycle_id, status="output", architecture_output=output,
            capability_calls=3, model_calls=1, capability_processing_ms=0,
            model_processing_ms=0, validation_processing_ms=0,
            input_tokens=100, cached_input_tokens=20, output_tokens=25,
            estimated_cost_usd=0.01, pricing_reference="controlled-test-pricing",
        )

    trajectory = execute_point_in_time_trajectory(
        matrix_id="matrix-one", cell=cell, triggers=_triggers(),
        observations=(_observation("observation-early", START),), processor=processor,
    )
    assert trajectory.status == "completed"
    assert len(trajectory.cycles) == 2
    assert trajectory.total_model_calls == 2
    assert trajectory.total_capability_calls == 6
    assert trajectory.total_cost_usd == 0.02
    assert trajectory.cycles[1].context.previous_output_ids == (
        trajectory.cycles[0].result.architecture_output.output_id,
    )


def test_stops_after_an_explicit_error_cycle() -> None:
    cell = _cell()

    def fail(context) -> CycleExecutionResult:
        return CycleExecutionResult(
            cycle_id=context.cycle_id, status="error", reason="Capability failed safely.",
            capability_calls=1, model_calls=0, capability_processing_ms=0,
            model_processing_ms=0, validation_processing_ms=0, input_tokens=0,
            cached_input_tokens=0, output_tokens=0, estimated_cost_usd=0,
        )

    trajectory = execute_point_in_time_trajectory(
        matrix_id="matrix-one", cell=cell, triggers=_triggers(),
        observations=(), processor=fail,
    )
    assert trajectory.status == "failed"
    assert len(trajectory.cycles) == 1


def test_trajectory_store_retains_exact_result(tmp_path) -> None:
    cell = _cell()
    trajectory = execute_point_in_time_trajectory(
        matrix_id="matrix-one", cell=cell, triggers=(_triggers()[0],),
        observations=(), processor=_abstain,
    )
    store = LocalTrajectoryStore(tmp_path)
    assert store.save(trajectory).trajectory_digest == trajectory.trajectory_digest
    assert store.get(trajectory.trajectory_id).trajectory_digest == trajectory.trajectory_digest
    assert [item.trajectory_id for item in store.list()] == [trajectory.trajectory_id]


def test_mixed_frequency_cycles_block_simulated_time_during_real_processing() -> None:
    triggers = (
        ReplayTrigger(
            trigger_id="trigger-event-morning", kind="event_available",
            event_id="event-morning", replay_at=START,
        ),
        ReplayTrigger(
            trigger_id="trigger-event-afternoon", kind="event_available",
            event_id="event-afternoon", replay_at=START + timedelta(minutes=37),
        ),
        ReplayTrigger(
            trigger_id="trigger-close", kind="daily_close",
            replay_at=START + timedelta(hours=6, minutes=30),
        ),
    )

    def processor(context) -> CycleExecutionResult:
        sleep(0.002)
        return CycleExecutionResult(
            cycle_id=context.cycle_id, status="abstained", reason="Controlled timing proof.",
            capability_calls=1, model_calls=1, capability_processing_ms=0.4,
            model_processing_ms=0.6, validation_processing_ms=0.2,
            input_tokens=10, cached_input_tokens=0, output_tokens=2,
            estimated_cost_usd=0.001, pricing_reference="controlled-timing-proof",
        )

    trajectory = execute_point_in_time_trajectory(
        matrix_id="matrix-mixed-frequency", cell=_cell("B1"), triggers=triggers,
        observations=(_observation("observation-early", START),), processor=processor,
    )
    assert [item.context.replay_at for item in trajectory.cycles] == [item.replay_at for item in triggers]
    assert all(item.processing_receipt.processing_wall_ms >= 1.2 for item in trajectory.cycles)
    assert all(
        item.processing_receipt.replay_triggered_at
        == item.processing_receipt.replay_paused_at
        == item.processing_receipt.replay_resumed_at
        == item.context.replay_at
        for item in trajectory.cycles
    )
    assert trajectory.total_model_calls == 3
    assert trajectory.total_capability_calls == 3


def test_overlapping_graph_component_timings_reconcile_to_blocked_wall_time() -> None:
    def processor(context) -> CycleExecutionResult:
        return CycleExecutionResult(
            cycle_id=context.cycle_id, status="abstained", reason="Parallel timing proof.",
            capability_calls=1, model_calls=2, capability_processing_ms=500,
            model_processing_ms=2500, validation_processing_ms=250,
            input_tokens=10, cached_input_tokens=0, output_tokens=2,
            estimated_cost_usd=.001, pricing_reference="controlled-parallel-proof",
        )

    trajectory = execute_point_in_time_trajectory(
        matrix_id="matrix-parallel-timing", cell=_cell("B1"),
        triggers=(_triggers()[0],), observations=(), processor=processor,
    )
    receipt = trajectory.cycles[0].processing_receipt
    assert receipt.metadata["reported_component_ms"]["overlap_reconciled"] is True
    assert (
        receipt.capability_processing_ms + receipt.model_processing_ms
        + receipt.validation_processing_ms
    ) <= receipt.processing_wall_ms + 1
