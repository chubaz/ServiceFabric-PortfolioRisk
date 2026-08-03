# PLATFORM-P2 — artifact repository and retained runs

- Status: accepted
- Accepted candidate: `b8eacc67ca9344944631c425e133c639395df9cf`
- Clean-worktree QA: `3d1617a033104a91d8da48e5a50664dcb9f8ba09`
- Integration branch: `integration/platform-artifact-repository`
- Baseline: `9440bbaeb3f43f04ff259dbde0eb2824b7f9c6f1`
- Roadmap: `apps/portfolio-risk-workbench/labs/DEVELOPMENT_ROADMAP.md`
- Lane manifest: `config/agent/platform-development/phase2-lanes.json`

## Outcome

Create a governed local-development repository for generated files and retained
runs without making artifacts authoritative for agent, capability, portfolio,
dataset, workflow, or experiment meaning. Reuse existing PortfolioRisk artifact
references and ServiceFabric immutable artifact-store semantics through an
application projection.

## Visible, testable increment

The Labs application gains an Artifact Repository workspace where a user can:

1. browse retained runs and individual artifacts;
2. inspect complete digest manifests, provenance, data truth, rights,
   retention, publication state, references, and integrity;
3. safely preview or download a declared file;
4. archive and restore eligible records;
5. preview governed deletion consequences, confirm deletion, and restore during
   a bounded recovery window;
6. see why published, evidence-locked, referenced, corrupt, or otherwise
   ineligible material cannot be deleted.

## Contract and storage boundary

- Mutable repository bytes live outside Git under an explicit local runtime
  root; API responses expose opaque locators, never absolute host paths.
- Content bytes are immutable and content-addressed. Repository metadata is a
  projection that adds run association, retention, rights, data truth,
  approvals, references, archive/tombstone state, and receipts.
- Every retained run has a stable opaque identity and a complete manifest over
  every retained file. Added, missing, changed, or undeclared files fail
  integrity verification.
- Cache and intermediate outputs are distinct from retained evidence. Phase 2
  does not make the existing capability cache authoritative.
- Ordinary deletion is denied for published or evidence-locked artifacts. A
  deletion first records a tombstone with a seven-day recovery deadline; final
  byte removal is allowed only after the deadline and when no active reference
  remains. Phase 2 runs no automatic cleanup daemon.
- Existing run admission is explicit and previewed. No run folder is silently
  imported or promoted, and incomplete rights/data-truth metadata fails closed.
- No endpoint executes an artifact, agent, workflow, model call, SQL statement,
  portfolio effect, or external publication.

## Execution waves

### Wave A — activation

Freeze the accepted Phase 1 merge, bounded lanes, tasks, verification target,
and current programme pointer.

### Wave B — parallel read-only audits

1. Canonical artifact contracts and storage/persistence semantics.
2. Existing Agent Lab run-folder migration and compatibility.
3. Repository UI, download, archive, retention, and deletion interaction.

Each specialist may change only its exact handoff. Integration owns all shared
contracts, migrations, application code, and tests.

### Wave C — integration implementation

Implement the artifact package, external store, retained-run adapter, APIs,
repository workspace, integrity and retention operations, tests, and explicit
migration behavior after reconciling all three audits.

### Wave D — independent QA and acceptance

Review an exact candidate in a clean worktree. Preserve every blocked verdict,
repair only in integration, repeat review after every changed candidate, and
complete the pull-request lifecycle only after all gates pass.

## Exit gates

1. Artifact and run manifests are strict, immutable, digest-complete, and map
   to existing canonical references without redefining them.
2. Storage is external to Git, path-safe, symlink-safe, atomic, restart-safe,
   concurrent-write safe, and content-addressed.
3. Browse, preview, download, verify, archive, tombstone, restore, and eligible
   final deletion are usable through the application.
4. Published/evidence-locked or actively referenced material cannot use
   ordinary deletion.
5. Existing Agent Run Review can retain compatible outputs without exposing
   licensed rows, absolute paths, or undeclared files.
6. Registry, Agent, Dataset, Workflow Cycle, and Full Experiment workspaces
   regress cleanly; no financial effect is introduced.
7. Focused, application, architecture, browser, CI, and independent adversarial
   QA gates pass against one exact candidate.
8. The accepted candidate and merge commit are recorded before Phase 2 closes.

## Non-goals

- no ExperimentDefinition, ExperimentSet, scheduler, queue, or worker pool;
- no Markdown report-composer redesign;
- no decision-review lifecycle or portfolio mutation;
- no production publication or deployment;
- no Studio–Codex execution, RavenPack, MCP, provider, or broker integration;
- no automatic TTL cleanup daemon;
- no Phase 3 work in this workstream.
