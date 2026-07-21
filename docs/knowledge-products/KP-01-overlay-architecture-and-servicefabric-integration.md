# KP-01: Overlay Architecture and ServiceFabric Integration

Status: draft. Deadlines: draft T+2h; review T+4h.

## Architecture boundary

Portfolio Risk is an overlay repository, not a fork of ServiceFabric. `vendor/servicefabric` is pinned and read-only. ServiceFabric retains authority over canonical package, tool, invocation, result, evidence, effect, operation, application, and runtime contracts. Overlay adapters may compose those contracts but do not own risk calculations or tool business logic.

## Implemented behavior

ADR-0001 records the separate-overlay decision and pinned upstream commit. Wave 0A documents lane ownership and an integration order from domain through planning, data, agents, application, and integration. The planning package is a local immutable catalogue; it is not an execution path and does not invoke ServiceFabric.

## Planned behavior

Future application and agent adapters will use canonical ServiceFabric invocation and result contracts. No new execution path may bypass the runtime. Integration must review that claim using focused tests and architecture checks before accepting a specialist candidate.

## Limits

This product makes no assertion that a runtime adapter or user interface already exists. The upstream submodule must not be edited, formatted, committed, or advanced by this work.
