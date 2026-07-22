from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from risk_agents import (
    ACTIVE_AGENT_ROLE_IDS,
    AnalysisPlanStep,
    Day1AnalysisRunRequest,
    DeterministicAnalysisOrchestrator,
)
from risk_analytics import AnalysisEvidence, AnalysisHorizon, ScenarioShock
from risk_capabilities import (
    CapabilityRegistry,
    EvidenceReference,
    NewsClassificationRequest,
    ReportRequest,
    ReturnsRequest,
    ScenarioRequest,
    SyntheticNewsEvent,
)
from risk_domain import MarketObservation, PortfolioSnapshot, Position, QualityFlag


START = datetime(2026, 7, 22, 12, tzinfo=UTC)
ANALYSIS_EVIDENCE = (
    AnalysisEvidence(
        evidence_id="timeline-analysis-evidence",
        reference="fixture://synthetic/day1/timeline",
        digest="sha256:" + "b" * 64,
        description="Reviewed synthetic timeline observations.",
    ),
)
NEWS_EVIDENCE = (
    EvidenceReference(
        evidence_id="timeline-news-evidence",
        reference="fixture://synthetic/day1/news",
        source_type="synthetic_fixture",
        digest="sha256:" + "c" * 64,
        description="Reviewed synthetic news context.",
    ),
)
HORIZON = AnalysisHorizon(label="daily", expected_interval_seconds=86_400)


def returns_request() -> ReturnsRequest:
    prices = tuple(
        MarketObservation(
            instrument_id="ALPHA",
            observed_at=START + timedelta(days=index),
            price=Decimal(value),
            currency="USD",
            synthetic=True,
            quality_flags=(QualityFlag.COMPLETE,),
        )
        for index, value in enumerate(("100", "110", "99"))
    )
    return ReturnsRequest(
        analysis_id="timeline-returns",
        snapshot_id="timeline-prices",
        prices=prices,
        horizon=HORIZON,
        evidence=ANALYSIS_EVIDENCE,
    )


def scenario_request() -> ScenarioRequest:
    portfolio = PortfolioSnapshot(
        snapshot_id="timeline-portfolio",
        as_of=START,
        base_currency="USD",
        positions=(
            Position(
                instrument_id="ALPHA",
                quantity=Decimal("1"),
                price=Decimal("100"),
                market_value=Decimal("100"),
                currency="USD",
            ),
        ),
    )
    return ScenarioRequest(
        analysis_id="timeline-scenario",
        portfolio=portfolio,
        shocks=(ScenarioShock(instrument_id="ALPHA", percentage_shock=Decimal("-0.10")),),
        horizon=AnalysisHorizon(label="instantaneous"),
        evidence=ANALYSIS_EVIDENCE,
    )


def news_request() -> NewsClassificationRequest:
    return NewsClassificationRequest(
        event=SyntheticNewsEvent(
            event_id="timeline-synthetic-event",
            instrument_id="ALPHA",
            headline="Synthetic ALPHA context",
            sentiment="negative",
            relevance="high",
        ),
        evidence_references=NEWS_EVIDENCE,
    )


def workflow_request() -> Day1AnalysisRunRequest:
    source_registry = CapabilityRegistry()
    reviewed_source = source_registry.invoke("risk.returns.simple", returns_request()).data
    planned = (
        ("risk.agent.market_data", "risk.returns.simple", returns_request()),
        ("risk.agent.portfolio_exposure", "risk.scenario.evaluate", scenario_request()),
        ("risk.agent.news_sentiment", "news.event.classify", news_request()),
        (
            "risk.agent.alert_recommendation",
            "risk.report.render",
            ReportRequest(
                analysis_id="timeline-report",
                title="Timeline review report",
                result=reviewed_source,
            ),
        ),
    )
    return Day1AnalysisRunRequest(
        timeline_id="day1-analysis-timeline",
        steps=tuple(
            AnalysisPlanStep(
                sequence=index,
                role=role,
                capability_id=capability_id,
                started_at=START + timedelta(minutes=index),
                observed_at=START + timedelta(minutes=index, seconds=30),
                request=capability_request,
            )
            for index, (role, capability_id, capability_request) in enumerate(planned, start=1)
        ),
    )


def test_four_role_timeline_is_deterministic_digested_and_review_pending() -> None:
    first_registry = CapabilityRegistry()
    second_registry = CapabilityRegistry()
    first = DeterministicAnalysisOrchestrator(first_registry).run(workflow_request())
    second = DeterministicAnalysisOrchestrator(second_registry).run(workflow_request())
    assert first == second
    assert first.status == "succeeded"
    assert tuple(step.role for step in first.steps) == ACTIVE_AGENT_ROLE_IDS[1:3] + ACTIVE_AGENT_ROLE_IDS[:1] + ACTIVE_AGENT_ROLE_IDS[3:]
    assert [step.sequence for step in first.steps] == [1, 2, 3, 4]
    assert all(step.input_digest.startswith("sha256:") for step in first.steps)
    assert all(step.output_digest.startswith("sha256:") for step in first.steps)
    assert all(step.evidence and step.effects == () for step in first.steps)
    assert all(step.review.state == "pending" for step in first.steps)
    assert all(step.review_state == "pending" for step in first.steps)
    assert first.steps[0].methodology == "simple-return"
    assert first.steps[1].methodology == "deterministic-scenario"
    assert first.steps[2].methodology == "registered-capability"
    assert first.steps[3].methodology == "risk-report"
    assert first.steps[3].receipt.output_digest == first.steps[3].output_digest
    assert first.effects == ()
    assert [record.capability_id for record in first_registry.invocation_history] == [
        "risk.returns.simple",
        "risk.scenario.evaluate",
        "news.event.classify",
        "risk.report.render",
    ]


def test_workflow_round_trips_json_with_concrete_capability_requests() -> None:
    original = workflow_request()
    restored = Day1AnalysisRunRequest.model_validate_json(original.model_dump_json())
    assert restored == original
    assert isinstance(restored.steps[0].request, ReturnsRequest)
    assert isinstance(restored.steps[1].request, ScenarioRequest)
    assert isinstance(restored.steps[2].request, NewsClassificationRequest)
    assert isinstance(restored.steps[3].request, ReportRequest)
    timeline = DeterministicAnalysisOrchestrator(CapabilityRegistry()).run(restored)
    assert timeline.status == "succeeded"


def test_workflow_rejects_extra_or_duplicate_role_steps() -> None:
    original = workflow_request()
    extra = original.steps[0].model_copy(update={"sequence": 5})
    with pytest.raises(ValidationError, match="at most 4"):
        Day1AnalysisRunRequest(timeline_id="extra-role", steps=(*original.steps, extra))

    duplicate = original.steps[3].model_copy(
        update={"role": "risk.agent.market_data"}
    )
    with pytest.raises(ValidationError, match="one step for each agent role"):
        Day1AnalysisRunRequest(
            timeline_id="duplicate-role",
            steps=(*original.steps[:3], duplicate),
        )


def test_failed_capability_remains_failed_timeline_step_and_is_not_zero() -> None:
    def fail(_: object):
        raise ValueError("reviewed fixture failure; observation remains missing")

    registry = CapabilityRegistry(handlers={"risk.returns.simple": fail})
    timeline = DeterministicAnalysisOrchestrator(registry).run(workflow_request())
    assert timeline.status == "failed"
    assert len(timeline.steps) == 1
    failed = timeline.steps[0]
    assert failed.status == "failed"
    assert "remains missing" in failed.warnings[0]
    assert failed.effects == ()
    assert failed.output_digest.startswith("sha256:")
    assert registry.invocation_history[0].status == "failed"


def test_workflow_uses_four_existing_roles_and_has_no_external_execution_surface() -> None:
    assert ACTIVE_AGENT_ROLE_IDS == (
        "risk.agent.news_sentiment",
        "risk.agent.market_data",
        "risk.agent.portfolio_exposure",
        "risk.agent.alert_recommendation",
    )
    orchestrator = DeterministicAnalysisOrchestrator(CapabilityRegistry())
    assert not hasattr(orchestrator, "provider")
    assert not hasattr(orchestrator, "broker")
    assert not hasattr(orchestrator, "optimize")
