from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from pydantic import ValidationError
import pytest

from risk_capabilities import (
    CapabilityRegistry,
    ContextualMonitoringWorkflowRequest,
    EvidenceReference,
    invoke_contextual_monitoring_workflow,
)
from risk_analytics import MonitoringReportRequest, render_monitoring_report
from risk_domain import PortfolioSnapshot, Position
from risk_domain.monitoring import (
    ContextualMonitoringRequest,
    DateEffectiveMapping,
    MonitoringEvidence,
    MonitoringMetric,
    MonitoringPolicyVersion,
    OutcomeLabel,
    PolicyEvaluationRequest,
    PointInTimeObservation,
    PortfolioDataContextRequest,
    ReplayRun,
    ReplaySpecification,
    ReplayStep,
    create_portfolio_data_context,
    evaluate_monitoring_policy,
    evaluate_replay,
    run_contextual_monitoring,
)


START = datetime(2026, 6, 29, 16, tzinfo=UTC)
EVIDENCE = (
    MonitoringEvidence(
        evidence_id="synthetic-monitoring-evidence",
        reference="fixture://synthetic/monitoring",
        digest="sha256:" + "2" * 64,
    ),
)
CAPABILITY_EVIDENCE = (
    EvidenceReference(
        evidence_id="synthetic-analytics-evidence",
        reference="fixture://synthetic/analytics",
        source_type="synthetic_fixture",
        digest="sha256:" + "2" * 64,
    ),
)


def policy(
    reviewed_at: datetime = START, *, stale_seconds: int = 86400
) -> MonitoringPolicyVersion:
    return MonitoringPolicyVersion(
        policy_id="fictional-monitoring-policy",
        version=1,
        daily_percentage_move_threshold=Decimal("0.05"),
        concentration_threshold=Decimal("0.40"),
        event_relevance_minimum=Decimal("0.60"),
        negative_sentiment_threshold=Decimal("-0.50"),
        stale_data_maximum_age_seconds=stale_seconds,
        historical_var_limit=Decimal("0.10"),
        scenario_loss_limit=Decimal("1000"),
        cadence="daily",
        cadence_metadata="Descriptive metadata; explicitly invoked only.",
        reviewed_by="fictional-human-reviewer",
        reviewed_at=reviewed_at,
        evidence=EVIDENCE,
    )


def context_request(
    as_of: datetime, instrument_id: str = "fictional-instrument-orchid"
) -> PortfolioDataContextRequest:
    snapshot = PortfolioSnapshot(
        snapshot_id="fictional-portfolio-snapshot",
        as_of=as_of,
        base_currency="USD",
        positions=(
            Position(
                instrument_id=instrument_id,
                quantity=Decimal("10"),
                price=Decimal("100"),
                market_value=Decimal("1000"),
                currency="USD",
            ),
        ),
    )
    return PortfolioDataContextRequest(
            portfolio_snapshot_id=snapshot.snapshot_id,
            portfolio_snapshot=snapshot,
            market_dataset_snapshot_id="fictional-market-snapshot",
            market_dataset_revision="market-revision-1",
            market_dataset_retrieved_at=START - timedelta(days=1),
            market_observations=(
                PointInTimeObservation(
                    dataset_snapshot_id="fictional-market-snapshot",
                    dataset_revision="market-revision-1",
                    entity_id="fictional-entity-orchid",
                    observed_at=as_of - timedelta(hours=1),
                    available_at=as_of - timedelta(minutes=30),
                    retrieved_at=START - timedelta(days=1),
                    value=Decimal("100"),
                    evidence=EVIDENCE,
                ),
            ),
            crosswalk_snapshot_id="fictional-crosswalk-snapshot",
            crosswalk_dataset_revision="crosswalk-revision-1",
            crosswalk_retrieved_at=START - timedelta(days=2),
            crosswalk_records=(
                DateEffectiveMapping(
                    crosswalk_snapshot_id="fictional-crosswalk-snapshot",
                    crosswalk_dataset_revision="crosswalk-revision-1",
                    source_instrument_id=instrument_id,
                    target_entity_id="fictional-entity-orchid",
                    effective_start=date(2020, 1, 1),
                    open_ended=True,
                    available_at=START - timedelta(days=2),
                    evidence=EVIDENCE,
                ),
            ),
            as_of=as_of,
            stale_data_maximum_age_seconds=86400,
            evidence=EVIDENCE,
    )


def context(as_of: datetime, instrument_id: str = "fictional-instrument-orchid"):
    return create_portfolio_data_context(context_request(as_of, instrument_id))


def monitoring_run(as_of: datetime, *, breach: bool = True):
    metrics = (
        MonitoringMetric(
            metric="daily_return",
            value=Decimal("-0.10") if breach else Decimal("-0.01"),
            instrument_id="fictional-instrument-orchid",
            evidence=EVIDENCE,
        ),
    )
    result = invoke_contextual_monitoring_workflow(
        CapabilityRegistry(),
        ContextualMonitoringWorkflowRequest(
            run_id=f"monitoring-run:{as_of.isoformat()}",
            context_request=context_request(as_of),
            policy_version=policy(),
            evaluation_id=f"policy-evaluation:{as_of.isoformat()}",
            run_at=as_of,
            metrics=metrics,
            evidence_references=CAPABILITY_EVIDENCE,
        ),
    )
    assert result.data is not None
    return result.data


def replay(*runs) -> ReplayRun:
    specification = ReplaySpecification(
        specification_id="fictional-replay-specification",
        start=runs[0].as_of,
        end=runs[-1].as_of,
        cadence_seconds=86400,
        portfolio_snapshot_id="fictional-portfolio-snapshot",
        market_dataset_snapshot_id="fictional-market-snapshot",
        market_dataset_revision="market-revision-1",
        crosswalk_snapshot_id="fictional-crosswalk-snapshot",
        crosswalk_dataset_revision="crosswalk-revision-1",
        policy_revision=policy().revision,
        lookback_window_seconds=3 * 86400,
        evaluation_horizon_seconds=86400,
        minimum_labelled_outcomes=3,
        labelled_outcome_method="reviewed synthetic threshold label",
        evidence=EVIDENCE,
    )
    return ReplayRun(
        run_id="fictional-replay-run",
        specification=specification,
        steps=tuple(
            ReplayStep(
                sequence=index,
                as_of=run.as_of,
                data_context=context(run.as_of),
                monitoring_run=run,
                abstained=False,
                evidence=EVIDENCE,
            )
            for index, run in enumerate(runs, start=1)
        ),
        evidence=EVIDENCE,
    )


def test_fixed_policy_has_no_expression_language_and_versions_are_deterministic() -> None:
    first = policy()
    second = policy()
    assert first == second
    assert first.revision.startswith("policy:")
    assert first.human_review_required
    with pytest.raises(ValidationError, match="expression"):
        MonitoringPolicyVersion(
            **policy().model_dump(mode="python", exclude={"digest", "revision"}),
            expression="return < -0.05",
        )
    schema_properties = MonitoringPolicyVersion.model_json_schema()["properties"]
    assert not {"expression", "sql", "python", "shell", "formula", "dsl"}.intersection(
        schema_properties
    )


def test_fixed_policy_evaluation_is_effect_free_and_uses_reviewed_thresholds() -> None:
    data_context = context(START)
    result = evaluate_monitoring_policy(
        PolicyEvaluationRequest(
            evaluation_id="policy-evaluation-1",
            policy_version=policy(),
            context=data_context,
            evaluated_at=START,
            metrics=(
                MonitoringMetric(
                    metric="daily_return",
                    value=Decimal("-0.08"),
                    instrument_id="fictional-instrument-orchid",
                    evidence=EVIDENCE,
                ),
                MonitoringMetric(
                    metric="concentration",
                    value=Decimal("0.50"),
                    instrument_id="fictional-instrument-orchid",
                    evidence=EVIDENCE,
                ),
            ),
            evidence=EVIDENCE,
        )
    )
    assert {item.breach_type for item in result.breaches} == {
        "daily_percentage_move",
        "concentration",
    }
    assert result.effects == ()
    assert result.human_review_required


def test_policy_stale_threshold_is_applied_independently_of_context_warning_limit() -> None:
    request = context_request(START).model_copy(
        update={
            "stale_data_maximum_age_seconds": 10 * 86400,
            "market_observations": (
                context_request(START).market_observations[0].model_copy(
                    update={"observed_at": START - timedelta(days=3)}
                ),
            ),
        }
    )
    data_context = create_portfolio_data_context(request)
    assert not any(
        item.code == "stale_market_data" for item in data_context.quality_issues
    )

    result = evaluate_monitoring_policy(
        PolicyEvaluationRequest(
            evaluation_id="policy-stale-threshold",
            policy_version=policy(stale_seconds=86400),
            context=data_context,
            evaluated_at=START,
            evidence=EVIDENCE,
        )
    )
    assert [item.breach_type for item in result.breaches] == ["stale_data"]


def test_replay_one_to_one_matching_precision_recall_lead_delay_and_sample_warning() -> None:
    first = monitoring_run(START)
    second = monitoring_run(START + timedelta(days=1))
    replay_run = replay(first, second)
    outcomes = (
        OutcomeLabel(
            outcome_id="fictional-outcome-orchid",
            instrument_id="fictional-instrument-orchid",
            outcome_time=second.as_of + timedelta(hours=2),
            trigger_available_at=START,
            label="fictional reviewed downside",
            method="reviewed synthetic threshold label",
            evidence=EVIDENCE,
        ),
        OutcomeLabel(
            outcome_id="fictional-outcome-cobalt",
            instrument_id="fictional-instrument-cobalt",
            outcome_time=second.as_of + timedelta(hours=3),
            trigger_available_at=START,
            label="fictional reviewed downside",
            method="reviewed synthetic threshold label",
            evidence=EVIDENCE,
        ),
    )
    evaluation = evaluate_replay(
        evaluation_id="fictional-evaluation",
        replay_run=replay_run,
        outcomes=outcomes,
        evaluated_at=second.as_of + timedelta(days=2),
    )

    assert evaluation.alert_count == 2
    assert evaluation.true_positive == 1
    assert evaluation.false_positive == 1
    assert evaluation.false_negative == 1
    assert evaluation.precision == Decimal("0.5")
    assert evaluation.recall == Decimal("0.5")
    assert evaluation.matches[0].alert_id == second.alert_draft.alert_id
    assert evaluation.median_lead_time_seconds == Decimal("7200")
    assert evaluation.median_detection_delay_seconds == Decimal("86400")
    assert any(item.code == "small_labelled_sample" for item in evaluation.warnings)
    assert "no predictive claim" in evaluation.methodology.lower()


def test_undefined_denominators_are_null_with_warnings_not_silent_zero() -> None:
    no_alert = monitoring_run(START, breach=False)
    replay_run = replay(no_alert)
    evaluation = evaluate_replay(
        evaluation_id="undefined-evaluation",
        replay_run=replay_run,
        outcomes=(),
        evaluated_at=START + timedelta(days=2),
    )

    assert evaluation.precision is None
    assert evaluation.recall is None
    assert evaluation.coverage is None
    codes = {item.code for item in evaluation.warnings}
    assert {"undefined_precision", "undefined_recall", "undefined_coverage"}.issubset(codes)


def test_negative_detection_delay_is_invalid() -> None:
    run = monitoring_run(START)
    replay_run = replay(run)
    outcome = OutcomeLabel(
        outcome_id="fictional-outcome",
        instrument_id="fictional-instrument-orchid",
        outcome_time=START + timedelta(hours=2),
        trigger_available_at=START + timedelta(minutes=30),
        label="fictional outcome",
        method="reviewed synthetic threshold label",
        evidence=EVIDENCE,
    )
    with pytest.raises(ValueError, match="negative detection delay"):
        evaluate_replay(
            evaluation_id="invalid-delay",
            replay_run=replay_run,
            outcomes=(outcome,),
            evaluated_at=START + timedelta(days=2),
        )


def test_monitoring_replay_report_is_deterministic_semantic_and_effect_free() -> None:
    run = monitoring_run(START)
    replay_run = replay(run)
    evaluation = evaluate_replay(
        evaluation_id="report-evaluation",
        replay_run=replay_run,
        outcomes=(),
        evaluated_at=START + timedelta(days=2),
    )
    request = MonitoringReportRequest(
        report_id="fictional-monitoring-report",
        title="Fictional Monitoring and Replay Review",
        monitoring_run=run,
        policy_version=policy(),
        replay_run=replay_run,
        evaluation=evaluation,
        evidence=EVIDENCE,
    )
    first = render_monitoring_report(request)
    second = render_monitoring_report(request)

    assert first == second
    assert first.digest == second.digest
    for heading in (
        "Data context",
        "Policy",
        "Findings",
        "Alert state",
        "Replay metrics",
        "Methodology",
        "Sample",
        "Assumptions",
        "Warnings",
        "Limitations",
        "Evidence",
        "Human-review state",
        "Effects",
    ):
        assert f"## {heading}" in first.markdown
        assert f"<h2 id=" in first.html and f">{heading}</h2>" in first.html
    assert "<article" in first.html and "<section" in first.html
    assert "Effects: empty" in first.markdown
    assert first.effects == ()
    assert "investment advice" in first.html.lower()
