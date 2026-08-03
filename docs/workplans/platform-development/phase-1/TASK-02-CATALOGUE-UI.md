# P1-02 — registry catalogue UI audit

## Objective

Design the smallest useful Registry workspace within the existing Labs shell,
with truthful discovered/indexed and development/publication language.

## Read scope

- `apps/portfolio-risk-workbench/labs/index.html`
- `apps/portfolio-risk-workbench/labs/labs.js`
- `apps/portfolio-risk-workbench/labs/styles.css`
- relevant application tests and Phase 0 UI handoff

## Only writable path

`docs/handoffs/platform-development/phase1-catalogue-ui.md`

## Required output

- exact navigation, layout, controls, empty/loading/error states;
- concise card/detail information hierarchy;
- lifecycle transition and version-comparison interaction;
- accessible and responsive recommendations using existing visual language;
- truthful copy for local development indexing and absent external effects;
- test selectors, risks, and rollback.

## Non-goals and checks

Do not edit UI or server code. Run `git diff --check`; the handoff must be the
only changed path. Stop without merging.
