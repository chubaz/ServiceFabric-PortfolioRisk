# Mixed-frequency timeliness and evaluation capabilities

## Accepted clock policy

The experiment keeps three clocks separate:

1. `event.available_at` — when an event became eligible to the architecture;
2. `workflow_cycle_at` — when the point-in-time daily context was complete and the architecture ran;
3. `market_observation_session` — the trading date represented by the daily close.

Acceleration changes only the wall-clock gap between replay triggers. Once a
trigger fires, replay time is frozen until the final validated architecture
output exists. Context preparation, retrieval, deterministic and statistical
capabilities, sub-agents, every model call, graph coordination, validation and
ArchitectureOutput mapping all contribute to trigger-to-output processing
time. Replay resumes at the same simulated timestamp; processing duration is
recorded against a separate monotonic wall clock.

Clock-time latency from event availability to the workflow cycle measures
system responsiveness. It does **not** measure market-response timeliness.
With daily prices, the economic response is observed only between consecutive
closes and is therefore interval-censored. Its unit is an integer trading
session and its minimum observation horizon is one session.

Events should be assigned to the first eligible response interval:

- event available before the declared session-close cutoff: previous close to
  the same-session close;
- event available after the cutoff or on a non-trading day: latest close to the
  next trading-session close.

Within-session market reaction time is not identifiable and must remain null.
Late-session, after-close and non-trading-day cohorts should be reported
separately to prevent unequal response opportunities from distorting results.

Portfolio actions use the first eligible end-of-day close after information
availability. Daily prices cannot identify the alpha lost between the event
and that close. The current apparatus can measure the wait to execution and
post-execution close-to-close signal persistence or branch regret. Exact
intraday alpha decay requires an independently admitted intraday quote or trade
source and must otherwise remain `not_measurable`.

Each retained event records event time, information availability time,
relevance-signal availability time, analysis trigger time, trigger-to-output
wall duration, and earliest eligible end-of-day execution time. This preserves
both information latency and architecture processing latency without turning
wall-clock processing seconds into simulated replay minutes.

## Execution regimes and comparability

The thesis apparatus distinguishes two regimes:

- `compressed_replay_v1`: idle gaps are accelerated, but trigger-to-output
  processing runs in real wall time and blocks replay time. Model calls,
  output tokens and timeouts are deliberately kept low for hundreds or
  thousands of comparable runs;
- `continuous_operations` (parked): the system remains active for the trading
  day, admits concurrent event and scheduled workflows, and measures queueing,
  saturation and service-level behaviour under a larger daily resource budget.

The regimes are compared using the same frozen Case, information boundary,
architecture version, capability versions, structured-output contract and
nine evaluation dimensions. Resource policy is treated as an experimental
factor, not hidden implementation detail. Every result therefore retains:

- trigger-to-output wall time and critical-path components;
- queueing time before analysis;
- capability and model call counts;
- input, cached-input and output tokens;
- monetary cost only when a reviewed pricing snapshot matches the exact model;
- outputs per event, workflow cycle and dollar of admitted budget;
- deadline misses, timeouts, retries and unfinished work.

Scaling should be studied as a response curve rather than a single large run.
Hold the Cases fixed and vary event arrival rate, concurrent portfolios, graph
width, call budget and wall-time budget. Quality may initially improve with
more compute, then plateau or deteriorate through context dilution,
coordination overhead, inconsistent agent conclusions, queueing and deadline
misses. Recommended reported quantities are quality per dollar, quality per
second, events processed per wall minute, p50/p95 trigger-to-output latency,
backlog size, deadline-success rate and marginal quality gained by each extra
unit of compute.

## Capability admission

Every capability used by an experiment declares two independent properties.

### Parameterization

- `preconfigured`: parameters, versions and thresholds are frozen before the
  Case runs and can be shared across B0, B1 and A1;
- `adaptive`: an admitted agent selects parameters during the run and the
  wrapper records the selector, request and result. B0 cannot use it.

### Implementation class

- `deterministic`: identical frozen input produces identical output;
- `statistical`: a fitted model with versioned training data, parameters,
  thresholds and temporal boundary;
- `generative`: a model-generated interpretation or parameter choice. It is
  unavailable to B0.

Reference-label capabilities are held out from every architecture. The same
statistical event-relevance output must not be both an architecture input and
its own reference label.

## Nine-dimension dependency map

| Dimension | Required capability | Current state |
|---|---|---|
| Detection quality | independent event-relevance reference labels | required |
| Severity understanding | independent severity and risk-channel labels | required |
| Timeliness | daily-session alignment; later materialisation labels | structural measurement ready; outcome labels required |
| Evidence quality | structural evidence audit; later semantic evidence review | structural measurement ready |
| Confidence calibration | confidence/outcome calibration | required |
| Decision quality | counterfactual branch outcomes | required |
| Robustness | controlled, identical perturbations | required |
| Stability | repetition and output-digest comparison | ready |
| Efficiency | wrapper telemetry | ready |

An unavailable dependency produces `not_measurable`; it never produces a proxy
score. Required capabilities are development items, not synthetic substitutes.
