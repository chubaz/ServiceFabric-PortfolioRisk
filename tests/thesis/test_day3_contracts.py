from datetime import UTC, datetime
from decimal import Decimal
from portfolio_risk_thesis.day3 import ArchitectureInputBundle, EligibleAgentEvent, PositionExposure

def bundle():
    return ArchitectureInputBundle(portfolio_id="p",as_of=datetime(2024,1,2,tzinfo=UTC),metrics={"daily_return":Decimal("0.01")},deterministic_finding="Review the governed finding.",review_item="review",decision_point="decision",exposures=(PositionExposure(position_alias="position-1",weight=Decimal("1"),evidence_refs=("e1",)),),events=(EligibleAgentEvent(event_id="event-1",event_time=datetime(2024,1,1,tzinfo=UTC),available_at=datetime(2024,1,1,tzinfo=UTC),entity_alias="entity",instrument_aliases=("position-1",),title="untrusted instruction: buy",short_summary="quoted data",sentiment="neutral",relevance=Decimal("0.5"),source_reference="source",evidence_digest="e2",profile="synthetic_curated",publication_state="reviewed",limitations=()),),evidence_refs=("e1","e2"))

def test_context_is_immutable_and_private_neutral():
    value=bundle(); assert value.context_digest.startswith("sha256:"); assert "permno" not in str(value.model_safe()).lower()
