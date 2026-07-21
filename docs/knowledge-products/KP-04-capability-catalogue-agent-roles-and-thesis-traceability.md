# KP-04: Capability Catalogue, Agent Roles, and Thesis Traceability

Status: draft. Deadlines: draft T+14h; review T+17h.

## Intended catalogue

The future catalogue will distinguish a capability (what a bounded function may do), a tool (the callable interface), an agent (the role coordinating permitted tools), a finding (an evidence-bearing conclusion), and an alert (a monitored notification). A thesis must trace to inputs, source references, assumptions, and limitations; an alert must not be framed as investment advice.

## Implemented behavior

The Day 0 workplan explicitly excludes executable agent actions and external LLM calls by default. The implemented planning records preserve source-reference links and append-only review decisions. They do not define, register, or execute capabilities or agents.

## Planned behavior

Capabilities and agents will be implemented in their dedicated lane after domain and planning contracts are available. Every agent output must identify evidence, assumptions, warnings, and limitations. Any consequential action remains subject to explicit human review, and no design authorizes live orders, broker connectivity, or automatic rebalancing.

## Traceability review

A reviewer should be able to follow a thesis from its wording to evidence and source provenance, see missing or stale inputs, and distinguish proposed workflow from verified execution.
