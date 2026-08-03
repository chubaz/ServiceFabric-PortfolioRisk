# P1-05 — independent QA

## Objective

Review the exact integrated candidate for contract reuse, persistence safety,
source truth, UI clarity, regression safety, and Phase 1 completeness.

## Only writable path

`docs/handoffs/platform-development/phase1-independent-qa.md`

## Required checks

- inspect the candidate diff and all three audit handoffs;
- prove that indexed records do not duplicate source definitions;
- exercise lifecycle failures, restart persistence, idempotent bootstrap,
  version comparison, provenance, and collision handling;
- test the Registry workspace through the running application;
- run `make verify-platform-phase1`, application and architecture regressions;
- record PASS or exact blockers without repairing the candidate.

Stop without merging. Integration owns any repair and must request a fresh
review of a changed candidate.
