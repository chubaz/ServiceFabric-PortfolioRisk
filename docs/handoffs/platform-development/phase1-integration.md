# Phase 1 integration handoff

- Lane: P1-00/P1-04 integration
- Branch: `integration/platform-registry-kernel`
- Baseline: `21339db19357277ca9a9a1ca50107f1a884d7aeb`
- Candidate: this handoff's parent implementation commit; the independent-QA
  handoff records the exact reviewed commit
- Status: ready for independent QA

## Activation evidence

Phase 0 PR #20 was squash-merged to `main` as the baseline above after every
required GitHub workflow passed. Phase 1 was created from that exact commit in
a clean worktree.

## Implementation evidence

- Added `packages/risk_registry`, a reusable typed projection index for the
  seven approved asset kinds. The canonical definition remains at its source;
  registry attributes reject embedded definitions and artifacts and stay below
  the 64 KB metadata boundary.
- Added path-safe local persistence with a cross-process mutation lock,
  immutable source projections, immutable ordered lifecycle event files,
  reconstructable aggregate snapshots, atomic replacement, filesystem sync,
  symlink refusal, idempotent rediscovery, collision detection, and transparent
  upgrade of aggregate-only development records.
- Added source adapters for exactly 44 reviewed existing definitions: 4 agent
  roles, 29 capability descriptors, 1 evaluation manifest, 3 report renderers,
  1 dashboard renderer, 3 scenarios, and 3 workflow treatments.
- Only the agent-role and capability-descriptor registries are treated as
  canonical reusable definition contracts. Accepted application-local sources
  are visible as candidates but cannot pass the publication transition.
- Added catalogue, explicit bootstrap/index, detail, lifecycle transition, and
  version-comparison APIs. All responses state the development-only boundary;
  no endpoint executes an asset or creates a financial effect.
- Added a Registry workspace to the current Workbench with source preview,
  explicit indexing, search and filters, master-detail inspection, provenance,
  digests, compatibility, lineage, lifecycle receipts, transition rationale,
  comparison, and truthful publication blocking.
- Kept Agent, Dataset, Agent Graph, Simulated Cycle, and Full Experiment routes
  intact and corrected navigation history/`aria-current` behavior.
- Updated the application package manifest and historical control-plane tests
  so the current pointer truthfully names PLATFORM-P1 without rewriting prior
  accepted programme history.

## Tests

- `make verify-platform-phase1 DAY0_VENV=.../state/venvs/thesis-sprint` — PASS,
  23 focused tests plus environment, repository, package and diff gates.
- `make test-application test-architecture DAY0_VENV=.../state/venvs/thesis-sprint`
  — PASS, 102 application tests and 105 architecture tests.
- Browser verification at `http://127.0.0.1:8767/?workspace=registry` — PASS:
  all 44 sources and seven kinds visible; one canonical agent moved through
  candidate, validated, and locally published; a scenario stopped at validated;
  restart retained both records and their receipts; console contained no errors.
- Recovery test — PASS: a corrupt aggregate snapshot was ignored and the exact
  document was reconstructed from its immutable projection and event stream.

## Deviations, blockers, and limitations

- Local publication is registry lifecycle state only. It does not deploy, run,
  distribute, or grant new authority to a definition.
- Candidate-source adapters for evaluation, report, dashboard, scenario, and
  workflow definitions deliberately remain non-publishable until a later phase
  creates or adopts reusable canonical contracts.
- Phase 1 stores no run outputs, report/dashboard files, datasets, copied source
  definitions, or retention/deletion policy. Those remain later-phase concerns.
- The initial dependency gate required one network-enabled installation of the
  repository's pinned bootstrap dependencies; the resulting verification gate
  then passed.

## Rollback

Remove the Phase 1 worktree/branch and return the current programme pointer to
the accepted Phase 0 record. Persistent registry data is outside Git and can be
removed independently once its exact configured root is verified.

## Recommended next action

Run P1-05 against the exact candidate in a clean worktree. If it passes, record
the accepted candidate commit, close Phase 1, and complete the pull-request
lifecycle without starting Phase 2.
