# P2-03 — artifact repository UI and policy audit

## Objective

Design the smallest intuitive Artifact Repository workspace inside the current
Labs shell, including reviewable retention and deletion consequences.

## Read scope

- `apps/portfolio-risk-workbench/labs/index.html`
- `apps/portfolio-risk-workbench/labs/labs.js`
- `apps/portfolio-risk-workbench/labs/styles.css`
- relevant application tests and Phase 0 UI handoff

## Only writable path

`docs/handoffs/platform-development/phase2-repository-ui.md`

## Required output

- exact navigation, browse/detail/run/file information hierarchy;
- preview/download/verify/archive/restore/delete interaction and confirmations;
- loading, empty, corrupt, locked, referenced, tombstoned, and error states;
- concise truthful copy for data truth, rights, retention, publication, and
  development-only persistence;
- accessibility, responsive behavior, selectors, tests, risks, and rollback.

Do not edit UI/server code. Run `git diff --check`; stop without merging.
