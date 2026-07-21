# ServiceFabric Portfolio Risk

ServiceFabric Portfolio Risk is a public application overlay for research and
development of portfolio-risk monitoring capabilities, data workflows,
reviewable alerts, and agentic orchestration.

## Repository boundary

This repository does not own or modify ServiceFabric core. ServiceFabric is
included as a read-only Git submodule under `vendor/servicefabric` and is
pinned to:

```text
7632b61d94a966346f95eb6c5bb2a5ea27f3bc14
```

Risk-specific applications, domain objects, connectors, capabilities, agents,
tests, and documentation belong in this repository.

## Day 0 status

Wave 0A is active on `integration/day0`. `main` remains the reviewed stable
baseline. No production hosting, live trading, broker connectivity, autonomous
order execution, or provider-licensed data is included.

## Data policy

Only synthetic fixtures and publicly redistributable metadata may be committed.
CRSP, Compustat, Bloomberg, RavenPack, Accern, private portfolio, credential,
and provider-licensed data must remain outside Git.

## Human review

Agent output is advisory and evidence-backed. Alerts, recommendations, data
publication, and consequential actions remain human-reviewed.
