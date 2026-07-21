# KP-00: Day 0 Charter and Supervisor Promise

Status: draft. Deadlines are relative to the shared Day 0 anchor: draft T+90m; review T+3h.

## Purpose

Day 0 creates an executable skeleton for a portfolio-risk research overlay. Its promise to a supervisor is bounded: the system will preserve evidence, assumptions, warnings, and limitations, and it will require explicit human review for consequential actions. It is not investment advice and it will not place orders, connect to a broker, or rebalance a portfolio.

## Implemented behavior

The repository has a read-only pinned ServiceFabric dependency, architecture controls, and immutable domain contracts for snapshots and observations. The planning catalogue records six reviewable knowledge products with deterministic T0-relative deadlines. Missing data remains missing rather than being represented as zero; synthetic observations must be labelled.

## Planned behavior

Provider-backed research ingestion, capability execution, agent workflows, and application presentation remain later-lane or later-day work. Their proposals require supervisor review before any consequential use. No claimed portfolio, market, fundamental, or news observation is supplied by this document.

## Review questions

- Does the scope remain research and monitoring, not trading or advice?
- Is every claimed behavior supported by repository evidence?
- Are proposed actions clearly separated from implemented behavior?
