# Day 0 Soft-QA Handoff

- Reviewer: `lorenzoccasoni`
- Reviewed at: `2026-07-21T17:25:00.237275Z`
- QA run: `20260721T170519Z`
- Branch: `integration/day0`
- Reviewed head: `a37f45809ddaa838f39f2aeaa9d0a7426fe7be4e`
- Decision: **PASSED**
- Local evidence root: `state/day0/soft-qa/20260721T170519Z`
- Evidence-manifest SHA-256: `7dfc4c8557613c655ccbd4db176f280527a51aaeb7b5374d61ab4fc69dbffea3`

## Automated gates

- Fresh remote checkout: PASS
- ServiceFabric submodule pin: PASS
- `make verify-day0`: PASS
- `make demo-day0-headless`: PASS
- Independent artifact and digest validation: PASS
- `make servicefabric-smoke`: PASS
- Post-stop capability rejection: PASS
- Application manifest/hash validation: PASS
- GitHub Day 0 workflow before QA closeout: PASS

## User workflow checks

- Health and application status: PASS
- Synthetic-only and human-review disclosures: PASS
- Planning catalogue KP-00 through KP-05: PASS
- Portfolio, findings, alerts, agents, and agent-run pages: PASS
- Monitoring workflow and draft-alert creation: PASS
- Missing reviewer rejection: PASS
- Human `request_changes` DecisionPoint: PASS
- Empty effects: PASS
- No broker or order endpoint: PASS
- Research and notebook catalogue boundaries: PASS

## Financial assertions

- Portfolio NAV: `40000.00`
- Largest-position weight: `0.50`
- Concentration limit: `0.40`
- ALPHA anomaly: present
- Concentration finding: present
- Agent roles: four
- Alert status: `draft`
- Human review required: `true`
- External effects: none
- Broker/order objects: none

## Knowledge-product review

KP-00 through KP-05 were reviewed for suitability for the Day 0 supervisor
demonstration. Their catalogue review state remains draft pending explicit
supervisor review; this soft-QA decision does not impersonate supervisor
approval.

## Findings

None

## Accepted Day 0 limitations

- Synthetic and fictional data only.
- Local Linux/Crostini process-host scope.
- No real providers or licensed datasets.
- No external LLM provider.
- No FX conversion.
- No broker, order, trading, or automatic rebalancing capability.
- No investment advice.
- Full ServiceFabric process-host smoke remains local rather than a portable CI
  claim.

## Merge authorization

The reviewer authorizes PR #9 to leave draft status and merge into `main`.
