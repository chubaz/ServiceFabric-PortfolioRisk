# Day 1 knowledge and research handoff

- Lane and branch: knowledge / `feature/day1-knowledge`
- Base: `day1-prepared` (`ba9a3b0b48091ad31c488c6ec1f9c90f984902f8`)
- Head: working tree over `0768a20064099f6e6e7282266931a289bc3034ff`; no commit, push, or merge was performed

## Changed paths

- `packages/risk_planning/**`: compatible T0/T1 planning epochs, exact Day 0 and Day 1 knowledge-product identifiers, Day 1 loader, and frozen research/notebook catalogue contracts.
- `seed/knowledge-products/day-1/**`: D1-KP-01 through D1-KP-05 with exact T1 deadlines, acyclic dependencies, and append-only review events.
- `docs/knowledge-products/**`: five human-readable Day 1 product records and catalogue index update.
- `docs/research/**`: reviewed research seed catalogue and its non-execution/data-boundary documentation.
- `notebooks/catalog/**`: reviewed notebook metadata catalogue and explicit catalogue-only documentation.
- `tests/planning/**` and `tests/research/**`: focused regression and Day 1 catalogue coverage.
- `docs/handoffs/day-1/knowledge.md`: this exact handoff.

## Tests and evidence

Executed `make preflight` (pass), `make test-day1-knowledge` (22 planning tests and 6 research tests pass), the existing planning suite through that target, and `git diff --check` (pass). The planning coverage includes regressions for the public `Deadline.at(t0=...)` keyword and rejection of catalogues that mix T0 and T1 products. The first environment bootstrap attempts could not reach the package index inside the network-restricted sandbox; the required pinned dependencies installed on the approved retry, after which the tests ran locally.

Evidence produced is limited to reviewed repository metadata, local contract validation, deterministic ordering, deadline resolution, dependency traversal, immutable review revisions, and test output. No provider, licensed source, personal portfolio, external LLM, notebook, kernel, shell, Python, SQL, broker, order, trade, or rebalance operation was accessed or executed by a catalogue method.

## Deviations and blockers

No scope deviation or blocker is known. Day 0 root seed loading remains the six-product KP-00 through KP-05 catalogue; Day 1 seeds have a separate loader and directory. All modified paths are within the knowledge lane allowance.

## Limitations

The catalogues describe reviewed metadata and future paths only. They do not establish application accessibility, analytical correctness, provider rights, local deployment security, integrated soft-QA approval, or production readiness. A reviewed catalogue record is not investment advice and does not authorize a consequential action.

## Rollback and recommended next action

Rollback is a focused revert of this uncommitted knowledge-lane change set; leave Day 0 records and `vendor/servicefabric/**` untouched. Integration should review the candidate with the knowledge lane-path checker, consume the catalogue contracts from the Workbench experience without adding execution controls, and record any integrated soft-QA outcome as a separate explicit human decision.
