"""Delegate snapshot and exposure arithmetic to the canonical registry."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from decimal import Decimal, localcontext
from pathlib import Path

from pydantic import BaseModel, ConfigDict

# The integration-owned Thesis harness supplies the canonical package paths but
# omits risk_planning, which risk_capabilities imports for an unrelated
# registered capability. Add only that repository-local canonical dependency;
# no alternate runtime or calculation path is introduced.
_REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
_RISK_PLANNING_SRC = _REPOSITORY_ROOT / "packages" / "risk_planning" / "src"
if _RISK_PLANNING_SRC.is_dir() and str(_RISK_PLANNING_SRC) not in sys.path:
    sys.path.insert(0, str(_RISK_PLANNING_SRC))

from risk_capabilities import (
    CapabilityRegistry,
    EvidenceReference,
    ExposureSummaryRequest,
    PortfolioSnapshotRequest,
    PositionSpecification,
)
from risk_data import NormalizedMarketRecord
from risk_domain import CashBalance, ExposureSnapshot, InstrumentIdentifier, PortfolioSnapshot

from ..contracts import HistoricalMarketObservation, PortfolioDefinition, utc_datetime


RECONCILIATION_TOLERANCE = Decimal("1e-28")


class SnapshotBuildResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    portfolio_snapshot: PortfolioSnapshot
    exposure_snapshot: ExposureSnapshot
    evidence_references: tuple[EvidenceReference, ...]
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]


class SnapshotBuilder:
    def __init__(self, registry: CapabilityRegistry | None = None) -> None:
        self.registry = registry or CapabilityRegistry()

    @staticmethod
    def _identifier(instrument_id: str) -> InstrumentIdentifier:
        value = instrument_id.removeprefix("instrument-").replace("-", "").upper()[:10]
        if not value or not value.isalnum():
            raise ValueError(f"instrument {instrument_id} cannot form a canonical fictional identifier")
        return InstrumentIdentifier(identifier_type="ticker", value=value)

    @staticmethod
    def _identity(portfolio: PortfolioDefinition, as_of: datetime, dataset_revision: str) -> str:
        payload = json.dumps(
            {
                "portfolio": portfolio.model_dump(mode="json"),
                "as_of": as_of.isoformat(),
                "dataset_revision": dataset_revision,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def build(
        self,
        portfolio: PortfolioDefinition,
        as_of: datetime,
        latest_prices: tuple[HistoricalMarketObservation, ...],
        dataset_revision: str,
    ) -> SnapshotBuildResult:
        as_of = utc_datetime(as_of)
        price_by_id = {row.instrument_id: row for row in latest_prices}
        required_ids = {position.instrument_id for position in portfolio.positions}
        if set(price_by_id) != required_ids:
            missing = sorted(required_ids - set(price_by_id))
            raise ValueError(f"missing latest eligible prices for positions: {missing}")
        for instrument_id in sorted(required_ids):
            row = price_by_id[instrument_id]
            if row.available_at > as_of:
                raise ValueError(f"future price is not eligible for {instrument_id}")
            if row.close is None:
                raise ValueError(f"missing price for position {instrument_id}; no zero value is inferred")

        evidence = tuple(
            EvidenceReference(
                evidence_id=f"market:{row.instrument_id}:{row.timestamp.isoformat()}",
                reference=row.evidence_ref,
                source_type="synthetic_fixture",
                digest=row.content_digest,
                description=(
                    f"fixture_revision={row.fixture_revision}; "
                    f"quality_state={row.quality_state}; "
                    f"units={','.join(row.units)}; "
                    f"limitations={' | '.join(row.limitations)}"
                ),
            )
            for row in sorted(latest_prices, key=lambda item: item.instrument_id)
        )
        normalized = tuple(
            NormalizedMarketRecord(
                instrument_id=row.instrument_id,
                identifier=self._identifier(row.instrument_id),
                observed_at=row.timestamp,
                price=row.close,
                currency=row.currency,
                synthetic=True,
                fixture_seed=20260728,
                source_id=row.source_id,
            )
            for row in sorted(latest_prices, key=lambda item: item.instrument_id)
        )
        identity = self._identity(portfolio, as_of, dataset_revision)
        snapshot_result = self.registry.invoke(
            "portfolio.snapshot.create",
            PortfolioSnapshotRequest(
                snapshot_id=f"thesis-portfolio-{identity[:24]}",
                as_of=as_of,
                base_currency=portfolio.base_currency,
                positions=tuple(
                    PositionSpecification(
                        instrument_id=item.instrument_id,
                        quantity=item.quantity,
                        currency=portfolio.base_currency,
                    )
                    for item in portfolio.positions
                ),
                cash_balances=tuple(CashBalance(currency=item.currency, amount=item.amount) for item in portfolio.cash),
                normalized_observations=normalized,
                evidence_references=evidence,
            ),
        )
        if snapshot_result.status != "succeeded" or snapshot_result.data is None:
            raise ValueError(f"portfolio.snapshot.create failed: {'; '.join(snapshot_result.warnings)}")
        snapshot = snapshot_result.data
        exposure_result = self.registry.invoke(
            "portfolio.exposure.summarize",
            ExposureSummaryRequest(
                snapshot_id=f"thesis-exposure-{identity[:24]}",
                portfolio_snapshot=snapshot,
                evidence_references=evidence,
            ),
        )
        if exposure_result.status != "succeeded" or exposure_result.data is None:
            raise ValueError(f"portfolio.exposure.summarize failed: {'; '.join(exposure_result.warnings)}")
        exposure = exposure_result.data

        with localcontext() as context:
            context.prec = 34
            expected_nav = sum((item.market_value for item in snapshot.positions), Decimal("0")) + sum(
                (item.amount for item in snapshot.cash_balances), Decimal("0")
            )
            total_weight = sum((item.weight for item in exposure.position_exposures), Decimal("0")) + exposure.cash_weight
        if exposure.nav != expected_nav:
            raise ValueError("canonical NAV does not reconcile to positions plus cash")
        if abs(total_weight - Decimal("1")) > RECONCILIATION_TOLERANCE:
            raise ValueError("canonical position and cash weights do not reconcile to one")
        return SnapshotBuildResult(
            portfolio_snapshot=snapshot,
            exposure_snapshot=exposure,
            evidence_references=evidence,
            assumptions=snapshot_result.assumptions + exposure_result.assumptions,
            warnings=snapshot_result.warnings + exposure_result.warnings,
            limitations=snapshot_result.limitations + exposure_result.limitations,
        )
