# D0-QA: Part 3/6 Soft-QA Entry Point

- Status: ready for review; not passed
- Integration branch: `integration/day0`
- Prerequisites: preparation and Waves 0A, 0B, and 0C complete

## Purpose

This document is the pointer for Part 3/6 soft QA. It records where a human
reviewer starts; it is not evidence that soft QA has passed.

## Review entry point

1. Inspect `docs/handoffs/day-0/integration.md` and every specialist handoff.
2. Run `make preflight` and `make verify-day0` with Python 3.11.
3. Run `make demo-day0-headless` and inspect the six JSON artifacts beneath
   `PORTFOLIO_RISK_DATA_ROOT/day0-monitoring`.
4. Run the local-only `make servicefabric-smoke`; confirm the upstream Text
   Utility gate, four required Workbench capability calls, cleanup, and the
   post-stop rejection.
5. Review the Workbench pages and synthetic/human-review disclosures.
6. Record soft-QA findings and an explicit human decision in the next reviewed
   handoff. Do not infer approval from passing automation.

## Acceptance topics

- Deterministic synthetic ingestion and immutable evidence lineage.
- Exact NAV, largest-position weight, concentration limit, ALPHA anomaly, and
  concentration finding assertions.
- Four distinct agent roles and effect-free draft alert behavior.
- Human DecisionPoint creation and absence of broker or order objects.
- Canonical ServiceFabric invocation and post-stop capability unavailability.
- Synthetic-only, no-trading, no-provider, and no-investment-advice boundaries.

## Current limitations

The full process-host smoke is a documented local Linux check. GitHub Actions
runs the deterministic headless journey and all test suites but does not claim
the local process-host lifecycle is portable. Soft QA remains pending explicit
human review.
