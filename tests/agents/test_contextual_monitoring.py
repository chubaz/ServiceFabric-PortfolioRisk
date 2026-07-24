from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from risk_agents import (
    ACTIVE_AGENT_ROLE_IDS,
    DeterministicContextualMonitoringOrchestrator,
)
from risk_capabilities import (
    CapabilityRegistry,
    ContextualMonitoringWorkflowRequest,
    EvidenceReference,
)
from risk_domain import PortfolioSnapshot, Position
from risk_domain.monitoring import (
    ContextualMonitoringRequest,
    DateEffectiveMapping,
    MonitoringEvidence,
    MonitoringMetric,
    MonitoringPolicyVersion,
    PointInTimeObservation,
    PolicyEvaluationRequest,
    PortfolioDataContextRequest,
    create_portfolio_data_context,
    evaluate_monitoring_policy,
)


NOW = datetime(2026, 7, 1, 16, tzinfo=UTC)
EVIDENCE = (
    MonitoringEvidence(
        evidence_id="synthetic-agent-evidence",
        reference="fixture://synthetic/agents",
        digest="sha256:" + "4" * 64,
    ),
)


CAPABILITY_EVIDENCE = (
    EvidenceReference(
        evidence_id="synthetic-agent-evidence",
        reference="fixture://synthetic/agents",
        source_type="synthetic_fixture",
        digest="sha256:" + "4" * 64,
    ),
)


def contextual_request() -> ContextualMonitoringWorkflowRequest:
    snapshot = PortfolioSnapshot(
        snapshot_id="fictional-portfolio-snapshot",
        as_of=NOW,
        base_currency="USD",
        positions=(
            Position(
                instrument_id="fictional-instrument-orchid",
                quantity=Decimal("1"),
                price=Decimal("100"),
                market_value=Decimal("100"),
                currency="USD",
            ),
        ),
    )
    context_request = PortfolioDataContextRequest(
            portfolio_snapshot_id=snapshot.snapshot_id,
            portfolio_snapshot=snapshot,
            market_dataset_snapshot_id="fictional-market-snapshot",
            market_dataset_revision="market-revision-1",
            market_dataset_retrieved_at=NOW - timedelta(days=1),
            market_observations=(
                PointInTimeObservation(
                    dataset_snapshot_id="fictional-market-snapshot",
                    dataset_revision="market-revision-1",
                    entity_id="fictional-entity-orchid",
                    observed_at=NOW - timedelta(hours=1),
                    available_at=NOW - timedelta(minutes=30),
                    retrieved_at=NOW - timedelta(days=1),
                    value=Decimal("100"),
                    evidence=EVIDENCE,
                ),
            ),
            crosswalk_snapshot_id="fictional-crosswalk-snapshot",
            crosswalk_dataset_revision="crosswalk-revision-1",
            crosswalk_retrieved_at=NOW - timedelta(days=2),
            crosswalk_records=(
                DateEffectiveMapping(
                    crosswalk_snapshot_id="fictional-crosswalk-snapshot",
                    crosswalk_dataset_revision="crosswalk-revision-1",
                    source_instrument_id="fictional-instrument-orchid",
                    target_entity_id="fictional-entity-orchid",
                    effective_start=date(2020, 1, 1),
                    open_ended=True,
                    available_at=NOW - timedelta(days=2),
                    evidence=EVIDENCE,
                ),
            ),
            as_of=NOW,
            stale_data_maximum_age_seconds=86400,
            evidence=EVIDENCE,
    )
    monitoring_policy = MonitoringPolicyVersion(
        policy_id="fictional-policy",
        version=1,
        daily_percentage_move_threshold=Decimal("0.05"),
        concentration_threshold=Decimal("0.40"),
        event_relevance_minimum=Decimal("0.60"),
        negative_sentiment_threshold=Decimal("-0.50"),
        stale_data_maximum_age_seconds=86400,
        cadence="manual",
        cadence_metadata="Explicit invocation only.",
        reviewed_by="fictional-human-reviewer",
        reviewed_at=NOW,
        evidence=EVIDENCE,
    )
    metrics = (
        MonitoringMetric(
            metric="daily_return",
            value=Decimal("-0.10"),
            instrument_id="fictional-instrument-orchid",
            evidence=EVIDENCE,
        ),
        MonitoringMetric(
            metric="volatility",
            value=Decimal("0.30"),
            instrument_id="fictional-instrument-orchid",
            evidence=EVIDENCE,
        ),
        MonitoringMetric(
            metric="drawdown",
            value=Decimal("0.15"),
            instrument_id="fictional-instrument-orchid",
            evidence=EVIDENCE,
        ),
        MonitoringMetric(
            metric="contribution",
            value=Decimal("-0.04"),
            instrument_id="fictional-instrument-orchid",
            evidence=EVIDENCE,
        ),
    )
    return ContextualMonitoringWorkflowRequest(
        run_id="fictional-contextual-monitoring-run",
        context_request=context_request,
        policy_version=monitoring_policy,
        evaluation_id="fictional-policy-evaluation",
        run_at=NOW,
        metrics=metrics,
        evidence_references=CAPABILITY_EVIDENCE,
    )


def test_contextual_run_uses_exactly_existing_four_roles_and_is_effect_free() -> None:
    registry = CapabilityRegistry()
    run = DeterministicContextualMonitoringOrchestrator(registry).run(
        contextual_request()
    )

    assert tuple(step.role for step in run.four_agent_timeline) == (
        "risk.agent.market_data",
        "risk.agent.portfolio_exposure",
        "risk.agent.news_sentiment",
        "risk.agent.alert_recommendation",
    )
    assert len(ACTIVE_AGENT_ROLE_IDS) == 4
    assert len(run.capability_receipts) == 4
    history_ids = tuple(item.capability_id for item in registry.invocation_history)
    assert history_ids == (
        "portfolio.data_context.create",
        "events.query.as_of",
        "monitoring.policy.evaluate",
        "monitoring.alert.synthesize",
        "monitoring.run.contextual",
    )
    assert {
        receipt.capability_id for receipt in run.capability_receipts
    }.issubset(history_ids)
    assert all(receipt.effects == () for receipt in run.capability_receipts)
    assert run.effects == ()
    assert run.alert_draft.effects == ()
    assert run.alert_draft.investment_advice is False
    assert set(run.alert_draft.suggested_next_steps).issubset(
        {"continue_monitoring", "scenario_analysis", "further_review"}
    )
    assert run.human_review_required
    assert "transaction" in " ".join(run.limitations).lower()
