# D0-WAVE-0B: Bounded Synthetic Vertical Slice

- Status: active
- Integration branch: `integration/day0`
- Prerequisite: completed `D0-WAVE-0A`

## Scope

Wave 0B turns the accepted Day 0 foundation into a bounded, local-only
synthetic vertical slice. Work may add contract-bound transformations and
reviewable displays across the existing domain, planning, data, capability,
agent, and application lanes. Every output remains evidence-linked, explicitly
synthetic where applicable, and subject to human review.

The wave may improve package installation and integration harnesses only where
needed to exercise that bounded path through the canonical ServiceFabric
runtime. It does not authorize a new provider, external service, or execution
path outside that runtime.

## Dependencies

- Wave 0A architecture, immutable contracts, deterministic fixtures, role
  cards, reviewed application manifest, and foundation gate remain intact.
- The pinned `vendor/servicefabric` commit remains read-only and authoritative
  for application invocation and result contracts.
- Local Day 0 dependency lock and Python 3.11 environment remain reproducible.
- Specialist work proceeds in the lane order recorded in
  `config/agent/day0/lanes.json`; integration accepts focused candidates only.

## Acceptance

- Every changed package has focused tests and a lane handoff with evidence,
  limitations, and rollback instructions.
- `make verify-wave-0b` passes, including domain, planning, data,
  capabilities, agents, application, and cross-package integration suites.
- Synthetic connector results remain deterministic, labelled synthetic, and
  preserve missing and quality-state information.
- Agent outputs preserve evidence, assumptions, warnings, limitations, and the
  explicit human-review boundary.
- The FastAPI application remains loopback-only and healthy; its declared
  manifest hashes are current and no external provider is enabled.
- Architecture and repository checks confirm no ServiceFabric submodule change,
  no provider credential, no private data, and no forbidden execution surface.

## Exclusions

- Live or licensed market, fundamental, news, or portfolio data; provider API
  access; credentials; caches; and broker connectivity.
- Live orders, automatic rebalancing, investment advice, or any consequential
  action without explicit human review.
- External LLM calls, mutable snapshot updates, edits beneath
  `vendor/servicefabric/**`, and changes to the upstream pin.
- Production hosting, public network exposure, and any bypass of canonical
  ServiceFabric invocation and result contracts.

## Rollback

Revert the focused Wave 0B integration commits in reverse acceptance order,
restore `config/agent/day0/status.json` to Wave 0A complete / Wave 0B queued,
and point `docs/workplans/current.md` back to the completed Wave 0A record.
Keep the ServiceFabric pin unchanged. Specialist candidate branches stay
independent and can be corrected without merging.
