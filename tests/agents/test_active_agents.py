from datetime import UTC, datetime
from decimal import Decimal

import pytest

from risk_agents import ACTIVE_AGENT_ROLE_IDS, RegisteredCapabilityAgent
from risk_capabilities import CapabilityRegistry, EvidenceReference, PortfolioSnapshotRequest, PositionSpecification
from risk_data import NormalizedMarketRecord
from risk_domain import InstrumentIdentifier


def test_all_role_cards_are_active_and_delegate_to_registry() -> None:
    assert ACTIVE_AGENT_ROLE_IDS == ("risk.agent.news_sentiment", "risk.agent.market_data", "risk.agent.portfolio_exposure", "risk.agent.alert_recommendation")
    registry = CapabilityRegistry()
    agent = RegisteredCapabilityAgent("risk.agent.portfolio_exposure", registry)
    evidence = (EvidenceReference(evidence_id="evidence", reference="fixture://synthetic/test", source_type="synthetic_fixture"),)
    now = datetime(2026, 7, 21, tzinfo=UTC)
    request = PortfolioSnapshotRequest(snapshot_id="agent-snapshot", as_of=now, positions=(PositionSpecification(instrument_id="instrument-alpha", quantity=Decimal("1")),), normalized_observations=(NormalizedMarketRecord(instrument_id="instrument-alpha", identifier=InstrumentIdentifier(identifier_type="ticker", value="ALPHA"), observed_at=now, price=Decimal("100")),), evidence_references=evidence)
    assert agent.invoke("portfolio.snapshot.create", request).data.snapshot_id == "agent-snapshot"
    with pytest.raises(ValueError, match="not granted"):
        agent.invoke("market.anomaly.detect", request)
    assert RegisteredCapabilityAgent("risk.agent.news_sentiment", registry).role.role_id == "risk.agent.news_sentiment"
