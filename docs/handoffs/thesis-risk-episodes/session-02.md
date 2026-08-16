# Session 2 Handoff — Detector Foundation

**Contract:** `thesis-risk-episode-case-framework-v1`
**Session:** S02 — Build the detector foundation
**State:** accepted by continuation to S03

## Outcome

Session 2 delivers a narrow, working detector path from licensed, read-only
CRSP observations to deterministic statistical leads in the existing **Find
cases** stage. It does not add another user-facing object catalogue, studio, or
technical view.

The implemented path is:

```text
selected portfolio and period
  -> fixed point-in-time CRSP query
  -> same-date portfolio benchmark
  -> admitted detector definition
  -> bounded capability invocation
  -> immutable detector run
  -> compact named-company signal preview
```

Signals are investigation leads. They are not accepted risk episodes, alerts,
decisions, causes, or claims of portfolio materiality.

## Implemented contracts and computation

- Added strict `DetectorDefinition`, `DetectorObservation`, `AnomalySignal`,
  and `DetectorRun` research contracts under `risk_analytics`.
- Added an explicit finite `DetectorRegistry`; unregistered detector methods
  cannot execute.
- Implemented a signed robust residual z-score using only the preceding rolling
  window, with median centring and MAD scaling.
- Implemented two-sided CUSUM over the same robust standardized residuals, with
  explicit drift, threshold, reset, and direction.
- Each signal records its detector/version, scope, observation and availability
  times, signed scores, threshold, lookback, normalization, regime, interval,
  evidence references, and quality flags.
- Future observations are excluded at the contract boundary. The real-data
  adapter also enforces `available_at <= as_of` before analytics receive rows.
- Missing values and zero-scale windows are retained as explicit quality
  outcomes rather than silently imputed.
- Detector results are cached immutably by definition, data, parameters, and
  version. Exact reruns return identical values and digests. Cache tampering and
  path/symlink violations are rejected.

## Data and capability boundary

- Added one fixed, parameterized, read-only CRSP detector query. It accepts
  identifiers and time bounds, not arbitrary SQL.
- Added the admitted `market.anomaly.scan` capability with a strict request
  contract, a 500,000-observation bound, no effects, no findings, and explicit
  statistical limitations.
- Capability invocation records now retain request and output identities plus
  the detector cache identity. These records are persisted for engineering and
  reproducibility, but never returned in the research UI.
- The real-data runtime uses the existing reviewed portfolio positions and
  company-name mapping. It does not expose licensed source bytes or private
  paths.
- The current benchmark is the same-date equal-weight average of the selected
  portfolio securities. It is an explicit comparison series, not a factor
  model, sector model, or causal adjustment.

## User experience

Route: `?zone=research&workspace=experiments`

Inside the existing **Find cases** stage, the user selects the portfolio and
period and presses **Scan this period**. The result shows only:

- number of signals, securities and sessions;
- downside/upside counts;
- company name and ticker;
- observation date;
- direction;
- signed score and threshold;
- a plain-language detector label;
- one concise interpretation boundary.

Schemas, hashes, capability identifiers, receipts, provider revisions, and
cache records do not appear in the interface—not even in collapsed panels.
They remain available in machine-readable storage and this handoff.

## Real-data proof

Direct execution against the selected licensed CRSP/Compustat snapshot produced:

```text
diversified portfolio · 2015-08-01 to 2015-10-31
8 instruments · 64 sessions · 10 signals
4 downside · 6 upside
example: Microsoft · 2015-10-23 · upside · robust score 9.32 · threshold 4.50

technology portfolio · same period · 3 signals
defensive portfolio · same period · 5 signals
```

The live browser journey also completed successfully and rendered a separate
20-session selection with 10 signals across five named securities. Browser
error/warning log: empty.

## Verification

```text
focused Session 2 gate: PASS · 185 tests
analytics detector tests: PASS · 6
capability-focused tests: PASS · 10
data boundary tests: PASS · 3
application-focused tests: PASS · 17
Python compilation: PASS
JavaScript syntax: PASS
live detector API: PASS
live minimal UI contract: PASS
browser journey and visual inspection: PASS
```

The tests cover known signed paths, two-sided CUSUM, order-independent
reproducibility, point-in-time exclusion, missingness and zero-scale quality,
immutable caching and tamper rejection, fixed read-only data queries, bounded
capability execution, receipts on success/failure, compact UI payloads, and API
delegation.

## Files owned or added by S02

- `packages/risk_analytics/src/risk_analytics/detectors.py`
- `packages/risk_analytics/src/risk_analytics/__init__.py`
- `packages/risk_analytics/src/risk_analytics/schema_export.py`
- `packages/risk_data/src/risk_data/detector_inputs.py`
- `packages/risk_data/src/risk_data/__init__.py`
- `packages/risk_capabilities/src/risk_capabilities/analytics.py`
- `packages/risk_capabilities/src/risk_capabilities/catalog.py`
- `packages/risk_capabilities/src/risk_capabilities/registry.py`
- `packages/risk_capabilities/src/risk_capabilities/__init__.py`
- `apps/portfolio-risk-workbench/labs/case_discovery_runtime.py`
- `apps/portfolio-risk-workbench/labs/duckdb_server.py`
- `apps/portfolio-risk-workbench/labs/index.html`
- `apps/portfolio-risk-workbench/labs/labs.js`
- `apps/portfolio-risk-workbench/labs/styles.css`
- `apps/portfolio-risk-workbench/labs/registry_sources.py`
- `tests/analytics/test_detectors.py`
- `tests/data/test_detector_inputs.py`
- `tests/capabilities/test_detector_capability.py`
- `tests/capabilities/test_registry.py`
- `tests/application/test_case_discovery_runtime.py`
- `tests/application/test_labs_runtime.py`

## Deliberate scientific limits

- This is a bounded 18-security, portfolio-linked proof universe, not a
  market-wide detector and not a basis for population recall.
- The interactive request is limited to 366 days; broad historical sweeps will
  be compiled outside the user interaction path.
- Residuals currently use the selected portfolio average. Factor-, sector-, and
  regime-adjusted benchmarks require separately versioned definitions.
- Signals on adjacent dates or from different detectors are not yet grouped.
  Session 3 owns interval construction, candidate grouping, and ranked cases.
- No causal, event, or fundamental interpretation is inferred at this stage.
- A signal becoming visible does not make it a Silver or Gold case.

## Next-session readiness

S03 may start after the user accepts this handoff. It will construct
reproducible manifestation intervals and ranked candidates, add the bounded
change-point and group breadth/correlation methods, and preserve the rule that
association is not causality.
