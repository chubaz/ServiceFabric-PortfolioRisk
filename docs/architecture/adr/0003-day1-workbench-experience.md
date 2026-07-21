# ADR-0003: Human-readable Day 1 Workbench

- Status: Accepted for preparation
- Date: 2026-07-21

## Decision

The Workbench primary interface is server-rendered Jinja2-style semantic HTML
with local static CSS and small progressive-enhancement JavaScript. JSON routes
remain stable developer and evidence-inspection APIs. Navigation covers
dashboard, portfolio, risk, findings, alerts, data, providers, research,
notebooks, agents, plan, and settings. Pages expose profile, synthetic/public
or private/local data state, and human-review state. Notebook routes are
catalogues only; PDF export, arbitrary execution, Node builds, frontend
framework migration, and remote UI assets are deferred or prohibited.

## Consequences

Reusable cards, tables, badges, disclosures, empty states, evidence drawers,
review forms, readable numbers, and keyboard-accessible responsive layout are
screen contracts for Wave 1A. Adapters do not replace canonical ServiceFabric
invocation or result ownership.
