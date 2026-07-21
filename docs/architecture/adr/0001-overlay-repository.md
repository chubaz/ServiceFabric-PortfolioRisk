# ADR-0001: Maintain Portfolio Risk as a Separate ServiceFabric Overlay

- Status: Accepted
- Date: 2026-07-20

## Context

ServiceFabric owns canonical package, tool, invocation, result, evidence,
effect, operation, application, and runtime contracts. Portfolio-risk
requirements are application-domain concerns and must not be introduced into
ServiceFabric core without an upstream ServiceFabric workplan.

## Decision

Create a separate public repository:

```text
chubaz/ServiceFabric-PortfolioRisk
```

Consume ServiceFabric as a read-only Git submodule at:

```text
vendor/servicefabric
```

Pin the submodule to:

```text
7632b61d94a966346f95eb6c5bb2a5ea27f3bc14
```

Risk-specific applications, domain objects, connectors, capabilities, agents,
tests, and documentation are implemented in the overlay repository.

## Consequences

- ServiceFabric core can evolve independently.
- The portfolio-risk repository can move quickly without weakening upstream
  architecture tests.
- Every integration is reproducible against a recorded upstream commit.
- Advancing the upstream pin requires an explicit reviewed change.
- No upstream code is copied into the overlay.
