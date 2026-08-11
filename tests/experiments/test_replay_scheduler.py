from datetime import datetime, timedelta, timezone
from time import sleep

from risk_experiments import (
    BlockingReplayScheduler,
    ReplayProcessingOutcome,
    ReplayTrigger,
)


NOW = datetime(2017, 12, 1, 10, tzinfo=timezone.utc)


def test_processing_blocks_accelerated_replay_until_output_exists() -> None:
    scheduler = BlockingReplayScheduler()
    observed_replay_times = []

    def process(trigger: ReplayTrigger) -> ReplayProcessingOutcome:
        observed_replay_times.append(scheduler.replay_at)
        sleep(0.01)
        observed_replay_times.append(scheduler.replay_at)
        return ReplayProcessingOutcome(
            output_id=f"output-{trigger.trigger_id}",
            capability_calls=2,
            model_calls=1,
            capability_processing_ms=2,
            model_processing_ms=4,
            validation_processing_ms=1,
        )

    receipts = scheduler.run((
        ReplayTrigger(
            trigger_id="event-trigger-01", kind="event_available",
            replay_at=NOW, event_id="event-01",
        ),
        ReplayTrigger(
            trigger_id="daily-close-01", kind="daily_close",
            replay_at=NOW + timedelta(hours=11),
        ),
    ), process)

    assert observed_replay_times[:2] == [NOW, NOW]
    assert receipts[0].replay_paused_at == receipts[0].replay_resumed_at == NOW
    assert receipts[0].processing_wall_ms >= 9
    assert receipts[0].capability_calls == 2
    assert receipts[1].replay_triggered_at == NOW + timedelta(hours=11)


def test_scheduler_orders_event_availability_before_daily_close() -> None:
    scheduler = BlockingReplayScheduler()
    order = []

    def process(trigger: ReplayTrigger) -> ReplayProcessingOutcome:
        order.append(trigger.trigger_id)
        return ReplayProcessingOutcome(output_id=f"output-{trigger.trigger_id}")

    scheduler.run((
        ReplayTrigger(trigger_id="close", kind="daily_close", replay_at=NOW + timedelta(hours=6)),
        ReplayTrigger(trigger_id="event", kind="event_available", replay_at=NOW, event_id="event-01"),
    ), process)
    assert order == ["event", "close"]
