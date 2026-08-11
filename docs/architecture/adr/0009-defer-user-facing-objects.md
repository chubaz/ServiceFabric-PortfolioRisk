# ADR 0009: Defer user-facing reports, dashboards and investment theses

## Status

Accepted for the active thesis prototype on 2026-08-11.

## Decision

The active thesis apparatus contains structured Cases, Runs,
ArchitectureOutputs, traces and EvaluationRecords. It does not require a Report,
Dashboard or Investment Thesis object.

Report and Dashboard implementations already exist, so they are preserved as
post-thesis incubator material rather than deleted. They are removed from active
Registry discovery, Studio selection, Application composition and new
historical-replay files. Existing retained artifacts and Registry records are
not rewritten or deleted.

Investment Thesis is not an implemented Registry kind. Its roadmap concept is
deferred without creating a placeholder implementation.

The active development focus is:

1. Scenario;
2. Capability;
3. Risk Analysis;
4. Integration and Connector;
5. Workflow; and
6. Graph.

Agent definitions remain supporting architecture components. Their thesis-run
outputs are structured data. Presentation-specific instructions, renderers and
visual composition are not part of headless execution.

## Consequences

- Architecture performance is evaluated from `ArchitectureOutput`, never from
  rendered prose or a dashboard.
- New retained historical runs use JSON entry files and do not create
  `report.md`.
- Historical Report and Dashboard code remains testable and readable but is no
  longer advertised as an active system object.
- Reintroduction requires a post-thesis decision or an explicitly scoped visual
  demonstration, with presentation quality evaluated separately.

The machine-readable archive record is
`config/incubator/post-thesis-user-facing-objects.yaml`.
