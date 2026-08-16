# Professor Demo v0.1 — Day 1 gate

- Gate date: 12 August 2026
- Status: apparatus demonstration passed with limitations
- Case: five-company capital-preservation equity case
- Observation date: 7 March 2016
- Architectures: B0, B1 and A1
- Retained comparison digest: `aefee03b407937daee11`

## What was verified

The backend reconstructed the Case from the frozen manifest, checked the
licensed data revisions, executed the same point-in-time input through all
three architectures, mapped every result to `ArchitectureOutput`, evaluated
the outputs, retained the three Runs and comparison, and reloaded them from the
Saved results repository.

All nine required preflight checks passed.  The Case contains five named
holdings with complete CRSP valuation and Compustat fundamental coverage, 73
eligible RavenPack event records grouped into 15 event clusters, and four
deterministic mandate findings.  The observed one-day return was -6.1%, the
lifetime drawdown was 25.1%, and the largest issuer weight was 70.5%.  These
features make the Case useful for demonstrating non-trivial behaviour.

The retained comparison completed 3/3 Runs with unchanged controls and no
critical runtime defect.  B0 cost $0.000000, B1 cost $0.002760 and A1 cost
$0.007212.  B1 processing took 11.2 seconds and A1 processing took 28.1
seconds.  The comparison is descriptive and archive-ready.

## Baseline critique

| Method | Useful for | Present limitation |
|---|---|---|
| B0 | Transparent, exactly repeatable policy and metric reference | Cannot infer risk meaning beyond programmed classifications and rules |
| B1 | Cheapest generative treatment and simplest agent comparison | One synthesis step must connect all evidence and may omit useful relationships |
| A1 | Separates event, market, exposure and synthesis work | Costs more, takes longer and introduces coordination risk without guaranteeing a better decision |

The current 100% detection, citation and policy-agreement values confirm
structural compliance with the deterministic reference labels.  They are not
evidence that the architectures have perfect real-world detection quality.

## Capability audit

The demonstration now requires and exposes nine versioned capabilities:

1. point-in-time historical context assembly;
2. portfolio risk metric calculation;
3. event relevance classification;
4. fundamental-state classification;
5. mandate policy evaluation;
6. mandate reference-label generation;
7. daily-session timeliness measurement;
8. evidence structural audit;
9. execution telemetry collection.

The second, fifth, seventh, eighth and ninth responsibilities were previously
implicit in larger routines.  They are now explicit capabilities so the
preflight can fail visibly if an experimental method cannot calculate risk,
apply the mandate, or supply the evaluation record.

Capabilities for independent event and severity labels, future-outcome
tracking, alpha persistence, calibration, counterfactual regret and
perturbation-based robustness remain deferred.  They require real labels,
matured outcomes or declared perturbation sets; fabricating them would make the
meeting demo look more complete while weakening the thesis.

## Scientific limitations

The portfolio quantities were approved in 2026 and retrojected to 2016.  The
Case is therefore suitable for testing the apparatus, not for an unbiased
historical performance claim.  The portfolio called `defensive_multi_asset`
is also five equities rather than a true multi-asset portfolio; the Demo uses
an accurate display name instead of repeating the misleading source label.

The `diversified` source portfolio is not suitable for this one-day demo
because one position lacks complete historical valuation coverage in the
shared RavenPack period.  The `technology_concentrated` source portfolio has
complete data but its current company composition does not support the label
well enough for a professor-facing Case.

## Reproduction

With the local Risk Lab running:

```bash
python scripts/thesis/run_professor_demo.py preflight
python scripts/thesis/run_professor_demo.py all --authorize-model-calls
```

The first command is deterministic and makes no model call.  The second
executes and retains B0, B1 and A1, then verifies the four resulting artifacts.
The same flow is available as one consented action on the Demo page.

## Day 1 conclusion

The apparatus boundary and meeting journey are ready.  A thesis-valid freeze
still requires a portfolio that was formed using information available at the
historical start date and independent labels or future outcomes for the
currently unavailable evaluation dimensions.  Those are scientific design
decisions, not hidden software failures.
