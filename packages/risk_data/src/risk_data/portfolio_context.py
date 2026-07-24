"""Adapters from governed Part 1 crosswalk snapshots to monitoring contexts."""

from __future__ import annotations

from typing import Literal

from risk_domain.monitoring import (
    DateEffectiveMapping,
    MonitoringEvidence,
    PortfolioDataContext,
    PortfolioDataContextRequest,
    create_portfolio_data_context,
)

from .research_contracts import CrosswalkSnapshot


def date_effective_mappings_from_crosswalk(
    snapshot: CrosswalkSnapshot,
    *,
    portfolio_identifier_side: Literal["source", "target"] = "target",
) -> tuple[DateEffectiveMapping, ...]:
    """Convert explicit Part 1 links without ticker, name, fuzzy, or heuristic matching."""

    evidence = (
        MonitoringEvidence(
            evidence_id=f"crosswalk:{snapshot.snapshot_id}",
            reference=f"local-crosswalk://{snapshot.snapshot_id}",
            digest=snapshot.source_digest,
            description="Explicit date-effective Part 1 crosswalk snapshot.",
        ),
    )
    mappings: list[DateEffectiveMapping] = []
    for record in snapshot.records:
        if portfolio_identifier_side == "target":
            portfolio_id = record.target_identifier.entity_id
            market_entity_id = record.target_identifier.entity_id
            fundamental_entity_id = record.source_identifier.entity_id
        else:
            portfolio_id = record.source_identifier.entity_id
            market_entity_id = record.target_identifier.entity_id
            fundamental_entity_id = record.source_identifier.entity_id
        mappings.append(
            DateEffectiveMapping(
                crosswalk_snapshot_id=snapshot.snapshot_id,
                crosswalk_dataset_revision=snapshot.source_digest,
                source_instrument_id=portfolio_id,
                target_entity_id=market_entity_id,
                fundamental_entity_id=fundamental_entity_id,
                effective_start=record.effective_from,
                effective_end=record.effective_to,
                open_ended=record.open_ended,
                available_at=record.available_at,
                reviewed_primary=record.link_primary.strip().upper()
                in {"P", "PRIMARY", "TRUE", "1"},
                evidence=evidence,
            )
        )
    return tuple(
        sorted(
            mappings,
            key=lambda item: (
                item.source_instrument_id,
                item.effective_start,
                item.target_entity_id,
            ),
        )
    )


def create_portfolio_context(
    request: PortfolioDataContextRequest,
) -> PortfolioDataContext:
    """Expose the canonical domain context builder through the data package."""

    return create_portfolio_data_context(request)
