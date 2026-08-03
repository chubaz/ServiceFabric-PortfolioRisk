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
  separately anchored receipt digests, an atomically replaced committed
  catalogue, reconstructable aggregate snapshots, filesystem sync, symlink
  refusal, idempotent rediscovery, collision detection, and transparent upgrade
  of aggregate-only development records. A multi-item bootstrap becomes visible
  only after every item is durable.
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
  45 focused tests plus environment, repository, package and diff gates.
- `make test-application test-architecture DAY0_VENV=.../state/venvs/thesis-sprint`
  — PASS, 104 application tests and 105 architecture tests.
- Browser verification at `http://127.0.0.1:8767/?workspace=registry` — PASS:
  all 44 sources and seven kinds visible; one canonical agent moved through
  candidate, validated, and locally published; a scenario stopped at validated;
  restart retained both records and their receipts; console contained no errors.
- Recovery test — PASS: a corrupt aggregate snapshot was ignored and the exact
  document was reconstructed from its immutable projection and event stream.
- GitHub's first candidate run exposed two checkout-environment defects that
  local data access had masked. The Phase 0 lane test now validates the accepted
  baseline-to-squash-merge range available on every clone, and the licensed
  DuckDB plane opens lazily only for data endpoints. The exact CI command passes
  with the private-data root deliberately unavailable.

## Independent-review history and repair

Independent QA correctly blocked candidate `e8fde6b28aa3e3851e1975d64175da2b7b75dcce`.
That verdict remains preserved in the first P1-05 handoff and was not
overridden. The subsequent integration repair addresses every reported blocker:

1. registry roots reject symlinked parent components and every internal path
   must resolve beneath the validated configured root; lock, record, projection,
   and event symlinks fail closed;
2. lifecycle receipts now carry stable intent IDs, payload digests and a strict
   prior-receipt digest chain; event files become read-only after durable write,
   byte tampering and snapshot/replay mismatch fail closed;
3. arbitrary attributes were removed from the closed projection contract, so
   grants, schemas, effects, shocks, policy and workflow topology stay at source;
4. identity includes the typed source namespace, provenance includes the exact
   repository commit, sources include adapter identity/digest, compatibility is
   bound to the exact definition and evaluator revision, and relationships point
   to exact registry revisions or declare an unavailable target;
5. version comparison rejects different kinds, namespaces or stable asset IDs;
6. bootstrap validates every identity before writing any, exposes a no-write
   consequence preview, reports conflicts and truthful counts, and the browser
   requires confirmation; lifecycle changes use server-provided transitions,
   explicit consequence confirmation and an expected-revision guard.

A final adversarial pass then closed three narrower integrity gaps: lifecycle
event and anchor filenames must be exactly contiguous; each receipt digest is
checked against both a read-only per-event anchor and the atomically committed
catalogue head; and partial files from an injected bootstrap write failure stay
uncommitted and invisible until a complete retry commits the whole catalogue.
The next clean review found that the projection itself still needed an
independent binding; the committed catalogue now also anchors the exact
canonical serialization digest of every projection, so a validly recomputed
same-identity replacement fails closed even without its derived snapshot.
Reads expose only the receipt prefix named by that committed catalogue, while
an exact durable trailing receipt from an interrupted transition is adopted by
an identical retry. A retry is also idempotent when the catalogue commit
completed but the caller received a post-commit failure.
Uncommitted durable lifecycle tails cannot be adopted by rediscovery or bulk
bootstrap. A failure between event and anchor installation remains readable at
the committed prefix and an exact retry completes the missing anchor. Immutable
projection, event, and anchor files are staged and atomically linked into their
final names, so incomplete bytes never become an authoritative final file.

The API no longer returns an absolute host registry path. The next P1-05 review
must assess a new exact commit; the earlier BLOCKED candidate cannot be accepted.

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
