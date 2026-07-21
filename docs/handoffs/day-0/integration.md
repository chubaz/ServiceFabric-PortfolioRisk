# Day 0 Integration Handoff

- Lane: integration
- Branch: `integration/day0`
- Base: `day0-prepared`
- Head: pending focused integration commit

## Activation

Wave 0A was activated by setting `D0-WAVE-0A` as current, marking preparation
complete, and marking Wave 0A in progress. The integration order is domain,
planning, data, agents, application, integration.

## Shared harness

The integration lane owns the root Python 3.11 tooling configuration, Day 0
dependency lock, environment bootstrap, lane-path checker, manifest hash
updater, Make targets, architecture boundary tests, CI, and shared ADRs.

## Evidence

Run `make verify-wave-0a`, `git diff --check`, JSON validation, and
`scripts/day0/check_lane_paths.py <lane> --base integration/day0 --candidate <candidate>`.

## Deviations and blockers

The preparation environment check currently depends on valid GitHub CLI
authentication. Dependency-lock generation requires explicit approval for the
networked package resolver.

## Limitations

No specialist implementation packages, provider integrations, portfolio data,
broker connectivity, or external LLM provider are included in this activation.

## Rollback

Revert the focused integration activation commit(s), restore the preparation
workplan pointer and queued Wave 0A state, and retain the ServiceFabric pin.

## Recommended next action

Resolve the Day 0 dependency lock from approved PyPI metadata, then let lanes
begin focused skeleton work in the defined integration order.
