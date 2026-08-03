# P0-03 — UI terminology, operating profiles, and policy audit

## Objective

Review the Labs experience for clarity and policy truthfulness. Identify where
development, experimental, persistent-research, data provenance, authority,
decision state, and output status are hidden, inconsistent, or misleading.

## Read scope

- `apps/portfolio-risk-workbench/labs/**`
- application tests and package manifest
- roadmap sections 2, 3, 6, 8, 9, and 10
- decision/context/mandate contracts and relevant architecture tests

## Only writable path

`docs/handoffs/platform-development/phase0-ui-policy.md`

## Required output

- screen-by-screen terminology and interaction audit;
- exact profile and data-state vocabulary recommendation;
- development-only control leakage assessment;
- visible-increment proposal with compact copy and acceptance examples;
- accessibility, layout, error-state, and provenance gaps;
- test cases for the integration implementation.

## Non-goals and checks

Do not change HTML, CSS, JavaScript, APIs, or tests. Do not redesign the entire
application. Run `git diff --check`; the exact handoff must be the only changed
path. Stop without merging.
