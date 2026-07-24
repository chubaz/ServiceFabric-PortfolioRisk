from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from pydantic import ValidationError
import pytest

from risk_capabilities import (
    CAPABILITY_BY_ID,
    CapabilityRegistry,
    EvidenceReference,
    PortfolioDataContextCapabilityRequest,
    ReplayCapabilityRequest,
    ReplayStepInput,
)
from risk_domain import PortfolioSnapshot, Position
from risk_domain.monitoring import (
    DateEffectiveMapping,
    MonitoringEvidence,
    MonitoringPolicyVersion,
    PointInTimeObservation,
    PortfolioDataContextRequest,
    ReplaySpecification,
)


START = datetime(2026, 6, 29, 16, tzinfo=UTC)
DOMAIN_EVIDENCE = (
    MonitoringEvidence(
        evidence_id="synthetic-capability-evidence",
        reference="fixture://synthetic/capability",
        digest="sha256:" + "3" * 64,
    ),
)
CAPABILITY_EVIDENCE = (
    EvidenceReference(
        evidence_id="synthetic-capability-evidence",
        reference="fixture://synthetic/capability",
        source_type="synthetic_fixture",
        digest="sha256:" + "3" * 64,
    ),
)


def context_request(as_of: datetime, *, complete: bool = True) -> PortfolioDataContextRequest:
    snapshot = PortfolioSnapshot(
        snapshot_id="fictional-portfolio-snapshot",
        as_of=START,
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
    observations = (
        PointInTimeObservation(
            dataset_snapshot_id="fictional-market-snapshot",
            dataset_revision="market-revision-1",
            entity_id="fictional-entity-orchid",
            observed_at=START,
            available_at=START,
            retrieved_at=START - timedelta(days=1),
            value=Decimal("100"),
            evidence=DOMAIN_EVIDENCE,
        ),
    ) if complete else ()
    return PortfolioDataContextRequest(
        portfolio_snapshot_id=snapshot.snapshot_id,
        portfolio_snapshot=snapshot,
        market_dataset_snapshot_id="fictional-market-snapshot",
        market_dataset_revision="market-revision-1",
        market_dataset_retrieved_at=START - timedelta(days=1),
        market_observations=observations,
        crosswalk_snapshot_id="fictional-crosswalk-snapshot",
        crosswalk_dataset_revision="crosswalk-revision-1",
        crosswalk_retrieved_at=START - timedelta(days=2),
        crosswalk_records=(
            DateEffectiveMapping(
                crosswalk_snapshot_id="fictional-crosswalk-snapshot",
                crosswalk_dataset_revision="crosswalk-revision-1",
                source_instrument_id="fictional-instrument-orchid",
                target_entity_id="fictional-entity-orchid",
                effective_start=date(2020, 1, 1),
                open_ended=True,
                available_at=START - timedelta(days=2),
                evidence=DOMAIN_EVIDENCE,
            ),
        ),
        as_of=as_of,
        stale_data_maximum_age_seconds=10 * 86400,
        evidence=DOMAIN_EVIDENCE,
    )


def policy() -> MonitoringPolicyVersion:
    return MonitoringPolicyVersion(
        policy_id="fictional-monitoring-policy",
        version=1,
        daily_percentage_move_threshold=Decimal("0.05"),
        concentration_threshold=Decimal("0.40"),
        event_relevance_minimum=Decimal("0.60"),
        negative_sentiment_threshold=Decimal("-0.50"),
        stale_data_maximum_age_seconds=86400,
        cadence="manual",
        cadence_metadata="Explicit invocation only.",
        reviewed_by="fictional-human-reviewer",
        reviewed_at=START,
        evidence=DOMAIN_EVIDENCE,
    )


def test_new_capabilities_are_registered_evidence_bound_and_effect_free() -> None:
    expected = {
        "portfolio.data_context.create",
        "events.query.as_of",
        "monitoring.policy.evaluate",
        "monitoring.alert.synthesize",
        "monitoring.run.contextual",
        "monitoring.report.render",
        "monitoring.replay",
        "monitoring.evaluate",
    }
    registry = CapabilityRegistry()
    assert expected.issubset(registry.capability_ids)
    for capability_id in expected:
        descriptor = CAPABILITY_BY_ID[capability_id]
        assert descriptor.requires_evidence
        assert descriptor.requires_human_review
        assert not descriptor.allowed_effects
        assert {
            "order_submission",
            "broker_connectivity",
            "trade_execution",
            "automatic_rebalancing",
            "optimization",
            "provider_call",
            "external_llm_call",
        }.issubset(descriptor.denied_effects)

    result = registry.invoke(
        "portfolio.data_context.create",
        PortfolioDataContextCapabilityRequest(
            request=context_request(START),
            evidence_references=CAPABILITY_EVIDENCE,
        ),
    )
    assert result.status == "succeeded"
    assert result.data.mapping_coverage.complete
    assert result.effects == ()
    assert result.human_review_required


def test_replay_capability_builds_fresh_context_per_step_and_retains_abstention() -> None:
    monitoring_policy = policy()
    specification = ReplaySpecification(
        specification_id="fictional-replay-specification",
        start=START,
        end=START + timedelta(days=1),
        cadence_seconds=86400,
        portfolio_snapshot_id="fictional-portfolio-snapshot",
        market_dataset_snapshot_id="fictional-market-snapshot",
        market_dataset_revision="market-revision-1",
        crosswalk_snapshot_id="fictional-crosswalk-snapshot",
        crosswalk_dataset_revision="crosswalk-revision-1",
        policy_revision=monitoring_policy.revision,
        lookback_window_seconds=86400,
        evaluation_horizon_seconds=86400,
        labelled_outcome_method="reviewed synthetic threshold label",
        evidence=DOMAIN_EVIDENCE,
    )
    request = ReplayCapabilityRequest(
        run_id="fictional-replay",
        specification=specification,
        policy_version=monitoring_policy,
        step_inputs=(
            ReplayStepInput(
                context_request=context_request(START),
                evaluation_id="evaluation-step-1",
            ),
            ReplayStepInput(
                context_request=context_request(START + timedelta(days=1), complete=False),
                evaluation_id="evaluation-step-2",
            ),
        ),
        evidence_references=CAPABILITY_EVIDENCE,
    )
    registry = CapabilityRegistry()
    result = registry.invoke("monitoring.replay", request)

    assert result.status == "succeeded"
    assert tuple(step.as_of for step in result.data.steps) == specification.replay_times()
    assert all(step.data_context.as_of == step.as_of for step in result.data.steps)
    assert result.data.steps[1].abstained
    assert result.data.steps[1].monitoring_run.status == "stopped"
    assert result.data.effects == ()
    history_ids = tuple(item.capability_id for item in registry.invocation_history)
    assert history_ids.count("portfolio.data_context.create") == 2
    assert history_ids.count("events.query.as_of") == 2
    assert history_ids.count("monitoring.policy.evaluate") == 2
    assert history_ids.count("monitoring.alert.synthesize") == 2
    assert history_ids.count("monitoring.run.contextual") == 2
    assert history_ids[-1] == "monitoring.replay"


def test_replay_rejects_step_revision_drift_under_the_same_snapshot_id() -> None:
    monitoring_policy = policy()
    specification = ReplaySpecification(
        specification_id="fictional-pinned-replay",
        start=START,
        end=START,
        cadence_seconds=86400,
        portfolio_snapshot_id="fictional-portfolio-snapshot",
        market_dataset_snapshot_id="fictional-market-snapshot",
        market_dataset_revision="market-revision-1",
        crosswalk_snapshot_id="fictional-crosswalk-snapshot",
        crosswalk_dataset_revision="crosswalk-revision-1",
        policy_revision=monitoring_policy.revision,
        lookback_window_seconds=86400,
        evaluation_horizon_seconds=86400,
        labelled_outcome_method="reviewed synthetic threshold label",
        evidence=DOMAIN_EVIDENCE,
    )
    drifted = context_request(START).model_copy(
        update={"market_dataset_revision": "market-revision-2"}
    )
    with pytest.raises(ValidationError, match="fall back"):
        ReplayCapabilityRequest(
            run_id="fictional-drifted-replay",
            specification=specification,
            policy_version=monitoring_policy,
            step_inputs=(
                ReplayStepInput(
                    context_request=drifted,
                    evaluation_id="evaluation-drifted",
                ),
            ),
            evidence_references=CAPABILITY_EVIDENCE,
        )


def test_monitoring_capability_requests_fail_without_evidence() -> None:
    with pytest.raises(ValidationError, match="at least 1"):
        PortfolioDataContextCapabilityRequest(
            request=context_request(START),
            evidence_references=(),
        )
