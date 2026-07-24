from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from pydantic import ValidationError
import pytest

from risk_domain import PortfolioSnapshot, Position
from risk_domain.monitoring import (
    DateEffectiveMapping,
    MonitoringEvidence,
    PointInTimeObservation,
    PortfolioDataContextRequest,
    create_portfolio_data_context,
)


AS_OF = datetime(2026, 7, 1, 16, tzinfo=UTC)
EVIDENCE = (
    MonitoringEvidence(
        evidence_id="synthetic-context-evidence",
        reference="fixture://synthetic/context",
        digest="sha256:" + "1" * 64,
    ),
)


def portfolio(*instrument_ids: str) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        snapshot_id="fictional-portfolio-snapshot",
        as_of=AS_OF,
        base_currency="USD",
        positions=tuple(
            Position(
                instrument_id=instrument_id,
                quantity=Decimal("1"),
                price=Decimal("100"),
                market_value=Decimal("100"),
                currency="USD",
            )
            for instrument_id in instrument_ids
        ),
    )


def mapping(
    instrument_id: str,
    entity_id: str,
    *,
    start: date = date(2020, 1, 1),
    end: date | None = None,
    primary: bool = False,
    crosswalk_snapshot_id: str = "fictional-crosswalk-snapshot",
    crosswalk_revision: str = "crosswalk-revision-1",
) -> DateEffectiveMapping:
    return DateEffectiveMapping(
        crosswalk_snapshot_id=crosswalk_snapshot_id,
        crosswalk_dataset_revision=crosswalk_revision,
        source_instrument_id=instrument_id,
        target_entity_id=entity_id,
        effective_start=start,
        effective_end=end,
        open_ended=end is None,
        available_at=AS_OF - timedelta(days=30),
        reviewed_primary=primary,
        evidence=EVIDENCE,
    )


def observation(
    entity_id: str,
    *,
    observed_at: datetime = AS_OF - timedelta(hours=1),
    available_at: datetime | None = AS_OF - timedelta(minutes=30),
    retrieved_at: datetime = AS_OF - timedelta(days=1),
    snapshot_id: str = "fictional-market-snapshot",
    revision: str = "market-revision-1",
) -> PointInTimeObservation:
    return PointInTimeObservation(
        dataset_snapshot_id=snapshot_id,
        dataset_revision=revision,
        entity_id=entity_id,
        observed_at=observed_at,
        available_at=available_at,
        retrieved_at=retrieved_at,
        value=Decimal("101"),
        unit="USD",
        evidence=EVIDENCE,
    )


def request(
    instruments: tuple[str, ...],
    mappings: tuple[DateEffectiveMapping, ...],
    observations: tuple[PointInTimeObservation, ...],
    **updates: object,
) -> PortfolioDataContextRequest:
    snapshot = portfolio(*instruments)
    values: dict[str, object] = {
        "portfolio_snapshot_id": snapshot.snapshot_id,
        "portfolio_snapshot": snapshot,
        "market_dataset_snapshot_id": "fictional-market-snapshot",
        "market_dataset_revision": "market-revision-1",
        "market_dataset_retrieved_at": AS_OF - timedelta(days=1),
        "market_observations": observations,
        "crosswalk_snapshot_id": "fictional-crosswalk-snapshot",
        "crosswalk_dataset_revision": "crosswalk-revision-1",
        "crosswalk_retrieved_at": AS_OF - timedelta(days=2),
        "crosswalk_records": mappings,
        "as_of": AS_OF,
        "stale_data_maximum_age_seconds": 86400,
        "evidence": EVIDENCE,
    }
    values.update(updates)
    return PortfolioDataContextRequest(**values)


def test_exact_date_effective_mapping_and_coverage_are_preserved() -> None:
    context = create_portfolio_data_context(
        request(
            ("fictional-instrument-orchid", "fictional-instrument-cobalt"),
            (
                mapping("fictional-instrument-orchid", "fictional-entity-orchid"),
                mapping("fictional-instrument-cobalt", "fictional-entity-cobalt"),
            ),
            (
                observation("fictional-entity-orchid"),
                observation("fictional-entity-cobalt"),
            ),
        )
    )

    assert not context.blocked
    assert context.mapping_coverage.coverage == Decimal("1")
    assert context.mapping_coverage.complete
    assert [item.mapping_rule for item in context.bindings] == [
        "exact_date_effective",
        "exact_date_effective",
    ]
    assert context.digest == create_portfolio_data_context(
        request(
            ("fictional-instrument-orchid", "fictional-instrument-cobalt"),
            (
                mapping("fictional-instrument-orchid", "fictional-entity-orchid"),
                mapping("fictional-instrument-cobalt", "fictional-entity-cobalt"),
            ),
            (
                observation("fictional-entity-orchid"),
                observation("fictional-entity-cobalt"),
            ),
        )
    ).digest


def test_no_ticker_name_or_heuristic_fallback_and_incomplete_coverage_is_not_100_percent() -> None:
    context = create_portfolio_data_context(
        request(
            ("ORCH", "fictional-instrument-cobalt"),
            (mapping("fictional-instrument-cobalt", "fictional-entity-cobalt"),),
            (observation("fictional-entity-cobalt"),),
        )
    )

    assert context.blocked
    assert context.mapping_coverage.mapped_count == 1
    assert context.mapping_coverage.unmapped_count == 1
    assert context.mapping_coverage.coverage == Decimal("0.5")
    assert not context.mapping_coverage.complete
    assert any(item.code == "missing_mapping" for item in context.quality_issues)


def test_overlapping_active_links_block_unless_one_reviewed_primary_resolves_them() -> None:
    mappings = (
        mapping("fictional-instrument-orchid", "fictional-entity-orchid"),
        mapping(
            "fictional-instrument-orchid",
            "fictional-entity-orchid-secondary",
            primary=True,
        ),
    )
    ambiguous = create_portfolio_data_context(
        request(
            ("fictional-instrument-orchid",),
            mappings,
            (observation("fictional-entity-orchid-secondary"),),
        )
    )
    resolved = create_portfolio_data_context(
        request(
            ("fictional-instrument-orchid",),
            mappings,
            (observation("fictional-entity-orchid-secondary"),),
            reviewed_primary_rule="reviewed_primary=true",
        )
    )

    assert ambiguous.blocked
    assert ambiguous.bindings[0].state == "ambiguous"
    assert any(item.code == "ambiguous_mapping" for item in ambiguous.quality_issues)
    assert not resolved.blocked
    assert resolved.bindings[0].entity_id == "fictional-entity-orchid-secondary"
    assert resolved.bindings[0].mapping_rule == "reviewed_primary"


def test_point_in_time_selection_never_substitutes_observed_at_or_future_revision() -> None:
    eligible = observation(
        "fictional-entity-orchid",
        observed_at=AS_OF - timedelta(hours=3),
        available_at=AS_OF - timedelta(hours=2),
    )
    future_availability = observation(
        "fictional-entity-orchid",
        observed_at=AS_OF - timedelta(hours=1),
        available_at=AS_OF + timedelta(minutes=1),
    )
    absent_availability = observation(
        "fictional-entity-orchid",
        observed_at=AS_OF,
        available_at=None,
    )
    context = create_portfolio_data_context(
        request(
            ("fictional-instrument-orchid",),
            (mapping("fictional-instrument-orchid", "fictional-entity-orchid"),),
            (eligible, future_availability, absent_availability),
        )
    )

    assert context.latest_market_observations == (eligible,)
    assert any(
        item.code == "missing_availability" and item.severity == "warning"
        for item in context.quality_issues
    )
    retrospectively_retrieved = create_portfolio_data_context(
        request(
            ("fictional-instrument-orchid",),
            (mapping("fictional-instrument-orchid", "fictional-entity-orchid"),),
            (
                eligible.model_copy(
                    update={"retrieved_at": AS_OF + timedelta(days=30)}
                ),
            ),
            market_dataset_retrieved_at=AS_OF + timedelta(seconds=1),
        )
    )
    assert not retrospectively_retrieved.blocked
    assert retrospectively_retrieved.latest_market_observations[0].available_at <= AS_OF


def test_stale_data_warns_and_missing_required_market_data_blocks() -> None:
    stale = create_portfolio_data_context(
        request(
            ("fictional-instrument-orchid",),
            (mapping("fictional-instrument-orchid", "fictional-entity-orchid"),),
            (
                observation(
                    "fictional-entity-orchid",
                    observed_at=AS_OF - timedelta(days=3),
                ),
            ),
        )
    )
    missing = create_portfolio_data_context(
        request(
            ("fictional-instrument-orchid",),
            (mapping("fictional-instrument-orchid", "fictional-entity-orchid"),),
            (),
        )
    )

    assert not stale.blocked
    assert any(item.code == "stale_market_data" for item in stale.quality_issues)
    assert missing.blocked
    assert any(
        item.code == "missing_required_market_data"
        for item in missing.quality_issues
    )


def test_crosswalk_records_must_match_the_selected_snapshot_and_revision() -> None:
    with pytest.raises(ValidationError, match="selected snapshot and revision"):
        request(
            ("fictional-instrument-orchid",),
            (
                mapping(
                    "fictional-instrument-orchid",
                    "fictional-entity-orchid",
                    crosswalk_revision="crosswalk-revision-other",
                ),
            ),
            (observation("fictional-entity-orchid"),),
        )


def test_context_contracts_are_frozen() -> None:
    context = create_portfolio_data_context(
        request(
            ("fictional-instrument-orchid",),
            (mapping("fictional-instrument-orchid", "fictional-entity-orchid"),),
            (observation("fictional-entity-orchid"),),
        )
    )
    with pytest.raises(ValidationError):
        context.as_of = AS_OF + timedelta(days=1)
