from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from risk_agents import DeterministicMonitoringOrchestrator, MonitoringRunRequest
from risk_capabilities import AnomalyDetectionRequest, CapabilityRegistry, CapabilityStopped, EvidenceReference, SyntheticNewsEvent
from risk_data import NormalizedMarketRecord
from risk_domain import CashBalance, InstrumentIdentifier, PortfolioSnapshot, Position


NOW = datetime(2026, 7, 21, 12, tzinfo=UTC)
EVIDENCE = (EvidenceReference(evidence_id="wave-0c-evidence", reference="fixture://synthetic/alpha", source_type="synthetic_fixture"),)


def market(instrument: str, price: str, days_before: int) -> NormalizedMarketRecord:
    return NormalizedMarketRecord(instrument_id=instrument, identifier=InstrumentIdentifier(identifier_type="ticker", value=instrument.split("-")[-1].upper()), observed_at=NOW - timedelta(days=days_before), price=Decimal(price))


def request() -> MonitoringRunRequest:
    portfolio = PortfolioSnapshot(snapshot_id="alpha-portfolio", as_of=NOW, base_currency="USD", positions=(Position(instrument_id="instrument-alpha", quantity=Decimal("200"), price=Decimal("100"), market_value=Decimal("20000"), currency="USD"), Position(instrument_id="instrument-beta", quantity=Decimal("100"), price=Decimal("100"), market_value=Decimal("10000"), currency="USD")), cash_balances=(CashBalance(currency="USD", amount=Decimal("10000")),))
    observations = (market("instrument-alpha", "100", 3), market("instrument-alpha", "101", 2), market("instrument-alpha", "100", 1), market("instrument-alpha", "57", 0))
    return MonitoringRunRequest(portfolio_snapshot=portfolio, market_request=AnomalyDetectionRequest(normalized_observations=observations, percentage_threshold=Decimal("0.20"), evidence_references=EVIDENCE), news_event=SyntheticNewsEvent(event_id="synthetic-alpha-event", instrument_id="instrument-alpha", headline="Synthetic ALPHA event", sentiment="negative", relevance="high"), evidence_references=EVIDENCE)


def test_four_agent_run_is_deterministic_evidenced_and_effect_free() -> None:
    first_registry, second_registry = CapabilityRegistry(), CapabilityRegistry()
    first = DeterministicMonitoringOrchestrator(first_registry).run(request())
    second = DeterministicMonitoringOrchestrator(second_registry).run(request())
    assert first == second
    assert first.status == "succeeded"
    assert len(first.outputs) == 4
    assert all(output.evidence_references == EVIDENCE for output in first.outputs)
    assert first.effects == ()
    assert first.alert_draft is not None and first.alert_draft.human_review_required is True
    assert first.alert_draft.executable_order_recommendation is False
    assert [entry.capability_id for entry in first_registry.invocation_history] == ["market.anomaly.detect", "portfolio.exposure.summarize", "news.event.classify", "alert.draft.synthesize"]


def test_monitoring_outputs_include_concentration_anomaly_and_synthetic_news_findings() -> None:
    result = DeterministicMonitoringOrchestrator(CapabilityRegistry()).run(request())
    findings = [finding for output in result.outputs for finding in output.findings]
    assert any(finding.kind == "concentration" and "0.5" in finding.summary for finding in findings)
    assert any(finding.kind == "market_anomaly" for finding in findings)
    assert any(finding.kind == "news_event" and "Synthetic" in finding.summary for finding in findings)


def test_missing_evidence_fails_contract_validation() -> None:
    with pytest.raises(ValueError):
        MonitoringRunRequest.model_validate({**request().model_dump(mode="python"), "evidence_references": ()})


def test_stopped_and_failed_capabilities_are_recorded_and_stop_orchestration() -> None:
    def stopped(_: object):
        raise CapabilityStopped("fixture stop")

    registry = CapabilityRegistry(handlers={"market.anomaly.detect": stopped})
    result = DeterministicMonitoringOrchestrator(registry).run(request())
    assert result.status == "stopped"
    assert result.alert_draft is None
    assert registry.invocation_history[0].status == "stopped"

    def failed(_: object):
        raise ValueError("fixture failure")

    failed_registry = CapabilityRegistry(handlers={"market.anomaly.detect": failed})
    failed_result = DeterministicMonitoringOrchestrator(failed_registry).run(request())
    assert failed_result.status == "failed"
    assert failed_registry.invocation_history[0].status == "failed"
