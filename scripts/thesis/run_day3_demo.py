#!/usr/bin/env python3
"""Write a reproducible fixture-only Day 3 comparison outside Git."""
from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from portfolio_risk_thesis.day3.contracts import ArchitectureInputBundle, PositionExposure, digest
from portfolio_risk_thesis.day3.providers import FixtureStructuredModelProvider
from portfolio_risk_thesis.day3.prompts import prompt_reference
from portfolio_risk_thesis.day3.runner import run, write_run
from portfolio_risk_thesis.day3.treatments import ROLES


def fixture_bundle() -> ArchitectureInputBundle:
    return ArchitectureInputBundle(
        portfolio_id="synthetic-diversified", as_of=datetime(2024, 1, 2, tzinfo=UTC),
        metrics={"daily_return": Decimal("-0.04"), "annualized_volatility": Decimal("0.20"), "maximum_drawdown": Decimal("0.10"), "historical_var_95": Decimal("0.02"), "historical_expected_shortfall_95": Decimal("0.03")},
        deterministic_finding="The deterministic kernel requires human review.", review_item="Review deterministic threshold evidence.", decision_point="human_review", exposures=(PositionExposure(position_alias="position-001", weight=Decimal("1"), evidence_refs=("synthetic-evidence",)),), evidence_refs=("synthetic-evidence",), warnings=("event_source_not_configured",), limitations=("Synthetic fixture only.",),
    )


def main() -> int:
    root = Path(os.environ["THESIS_DATA_ROOT"]).resolve()
    if not root.is_absolute():
        raise ValueError("THESIS_DATA_ROOT must be absolute")
    bundle = fixture_bundle()
    response = lambda architecture: {"architecture_id": architecture, "status": "REVIEW", "severity": 1, "summary": "Fixture review output.", "human_review_required": True, "effects": []}
    prompt_ids = {
        ROLES[0]: "a1-market-data",
        ROLES[1]: "a1-portfolio-exposure",
        ROLES[2]: "a1-news-sentiment",
        ROLES[3]: "a1-alert-synthesis",
    }
    responses = {
        (
            "B1",
            ROLES[-1],
            prompt_reference("b1-synthesizer").digest,
            bundle.context_digest,
        ): response("B1")
    }
    responses.update(
        {
            (
                "A1",
                role,
                prompt_reference(prompt_ids[role]).digest,
                bundle.context_digest,
            ): response("A1")
            for role in ROLES
        }
    )
    output = write_run(root, bundle, run(bundle, FixtureStructuredModelProvider(responses)))
    print(output.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
