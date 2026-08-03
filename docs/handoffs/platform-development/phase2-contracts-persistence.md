# Phase 2 specialist handoff — artifact contracts and persistence

- Lane: P2-01 artifact contracts and persistence audit
- Branch: `feature/platform-p2-artifact-contracts`
- Programme baseline: `9440bbaeb3f43f04ff259dbde0eb2824b7f9c6f1`
- Audit base/head before this handoff: `89be56bb509e2e2f9a8cd1f81b3246dbf2ded87d`
- Pinned ServiceFabric gitlink: `7632b61d94a966346f95eb6c5bb2a5ea27f3bc14`
- Scope: read-only audit; this handoff is the only repository change

## Executive finding

Phase 2 can be implemented safely without replacing a canonical PortfolioRisk
or ServiceFabric contract, but it cannot truthfully reuse the
`ApplicationArtifactManifest` as the general run-output manifest. The smallest
safe design is:

1. retain PortfolioRisk's existing generic `ArtifactReference` as the
   evidence-facing artifact identity;
2. reuse ServiceFabric's content-addressed store invariants and file-manifest
   field semantics through a hardened adapter;
3. add a bounded repository projection, an immutable generic bundle manifest,
   and an immutable retained-run manifest in the new integration-owned
   `risk_artifacts` package;
4. keep lifecycle, retention, publication, integrity, data truth, rights,
   approval and reference state as independent fields backed by append-only
   receipts; and
5. make existing-run admission an explicit preview/confirm/copy operation,
   never a scan that silently promotes `.agent-runs`.

The current Agent Lab folder is reviewable but not admissible as trusted
evidence without migration. Its writes are non-atomic across the run, file
entries lack content digests, its manifest publishes an absolute host path,
listing silently skips damage, file loading can follow a declared symlink, and
deletion is immediate `shutil.rmtree` with no lock, reference check, tombstone,
receipt or recovery.

## Exact contracts and semantics to reuse

| Existing path / contract | Exact reuse | Boundary |
|---|---|---|
| `packages/risk_domain/src/risk_domain/models.py::ArtifactReference` | Keep `artifact_id`, `digest`, `media_type` and opaque `reference` as the generic PortfolioRisk reference used by findings, events, snapshots and agent runs. | Do not add repository paths, rights, retention or lifecycle to this business reference. Resolve its opaque reference through the repository adapter. |
| `packages/risk_domain/src/risk_domain/monitoring.py::MonitoringEvidence` | Keep publication-safe evidence ID/reference/digest/description links. | It is not an artifact manifest and must not acquire bytes or retention policy. |
| `vendor/servicefabric/packages/servicefabric_contracts/src/servicefabric_contracts/artifacts.py::ArtifactReference` | Reuse a discriminated variant only when it is semantically exact: for example `StaticBundleArtifact` for a true static bundle and `ProcessBundleArtifact` for a true process bundle. | `GraphRevisionArtifact`, external service/MCP references and `NoArtifact` are not local generated-file records. Do not coerce reports or run folders into deployment artifacts. |
| `vendor/servicefabric/packages/servicefabric_contracts/src/servicefabric_contracts/applications.py::ArtifactFileManifest` | Reuse the safe relative POSIX path, SHA-256 content digest, media type, byte size, unique sorted path and exact total-size semantics. | The class is nested in an application-build contract. Mirror/adapt its semantics in a generic repository manifest; do not pretend every output has an application revision, builder or entry document. |
| `...applications.py::ApplicationArtifactManifest` and `servicefabric_builder/identity.py::manifest_content_digest` | Reuse the pattern of an immutable, deterministic manifest whose identity excludes incidental publication time and binds exact ordered files and producer inputs. | This manifest specifically requires application/build/source fields and an entry document. It must remain authoritative only for application artifacts. |
| `vendor/servicefabric/packages/servicefabric_artifacts/servicefabric_artifacts/store.py::FileArtifactStore` | Reuse content-addressed `sha256/<prefix>/<digest>` layout, temporary creation in the destination parent, create-without-replacement, same-digest idempotency, immutable manifest, exact verification and undeclared/missing/changed-file failure. | Wrap or strengthen it. It does not provide generic run metadata, references, rights, lifecycle, tombstones or purge recovery and does not comprehensively reject internal symlinks. |
| `vendor/servicefabric/packages/servicefabric_contracts/src/servicefabric_contracts/evidence.py::EvidenceRecord` | Map a retained artifact to `evidence_type="artifact"`, opaque locator, content digest, collection time, trust classification, claims and provenance refs when a canonical ServiceFabric evidence receipt is required. | Do not copy evidence payloads into repository metadata. An `EvidenceRecord` reference is not permission to delete its artifact. |
| `vendor/servicefabric/packages/servicefabric_agentic_contracts/.../contracts.py::VerificationEvidence.artifact_ref` | Preserve as an existing run/result link to an opaque retained artifact reference. | It is a string reference, not a manifest or integrity assertion. |
| `packages/risk_data/src/risk_data/research_contracts.py::RightsState` and `PublicationRestriction` | Reuse exact source rights values (`reviewed_synthetic`, `licensed_restricted`) and restrictions (`synthetic_only`, `internal_research_only`, `no_publication`) for every data-bearing source. | Rights state is not data truth, publication state, retention or approval. Mixed-source outputs inherit the intersection of allowed uses; any `no_publication` source prevents publication. |
| `packages/risk_registry/src/risk_registry/models.py` and `store.py` | Reference exact published definition revisions and reuse the append-only receipt, expected-revision, pending-intent, catalogue-head, cross-process lock, atomic write, `fsync`, symlink refusal and recovery patterns. | The Registry indexes definitions only. Artifact bytes and run outputs must never be inserted into `RegistryProjection` or its lifecycle stream. |

The frozen vendor contracts remain read-only. The Phase 2 adapter owns local
repository policy; it does not alter canonical artifact or evidence meaning.

## Minimal integration-owned projection

Three small persistence records are sufficient. They are repository contracts,
not new portfolio, agent, workflow, dataset or experiment business objects.

### Immutable generic artifact bundle manifest

Required fields:

- `schema_version`;
- stable opaque `artifact_id`;
- `content_digest`, calculated over canonical JSON containing only the schema
  version, unique path-sorted file entries and exact total size;
- one or more file entries: safe relative logical path, `sha256:` content
  digest, media type and byte size;
- `file_count` and `total_size_bytes`, both reconciled exactly;
- immutable producer provenance: exact run reference, definition/revision
  references, adapter ID/revision/digest, repository commit when relevant, and
  exact source/evidence references;
- data-truth assertions and source-rights assertions described below; and
- `manifest_digest`, over the complete canonical record except itself.

Blob deduplication keys only on each file content digest. Bundle
`content_digest` keys on the complete ordered file inventory. Timestamps,
retention, archive state and local admission actor do not enter the content
digest; they enter the immutable manifest/projection digest or lifecycle
receipts. Equal bytes may therefore deduplicate without falsely equating two
runs or their approvals.

### Retained-run manifest

Required fields:

- stable opaque `repository_run_id` and the non-authoritative source run ID;
- source adapter ID/revision/digest and admission preview digest;
- exact agent/role, capability, workflow, portfolio snapshot, dataset snapshot,
  as-of and model/runtime references that are available; missing references
  remain explicit gaps and never become mutable `latest` aliases;
- complete path-sorted mapping of every retained source regular file to one
  exact artifact ID/digest; undeclared, added, missing or changed files fail;
- explicit missing/unavailable expected items with reason and source reference,
  but no fabricated file or zero-valued artifact;
- run-level data-truth, rights/publication restriction, operating profile,
  authority/effects and review-checkpoint disclosures;
- exact artifact-reference set and total file/byte counts; and
- canonical `run_manifest_digest`.

The repository-owned manifest is metadata outside the imported payload set and
must not recursively list itself. A legacy Agent Lab `manifest.json` may be
retained as an ordinary source file, but none of its claims—including its
absolute `folder`—is trusted or copied without adapter validation.

### Repository projection and receipts

The bounded browse projection contains only:

- opaque record ID, artifact/run reference and immutable manifest digest;
- derived display name and media summary;
- run association and exact canonical definition/evidence references;
- data-truth summary, rights summary and effective publication restriction;
- retention class, publication state, lifecycle head/revision, integrity state
  and last verified time;
- exact approval and active-reference counts plus links to their bounded edge
  records; and
- created/admitted times and receipt head digest.

Append-only receipts carry actor, rationale, UTC time, intent/idempotency
digest, expected prior revision/state, from/to state, prior receipt digest,
consequence-preview digest, approval references and recovery deadline where
applicable. A materialized snapshot/catalogue is derived and reconstructable.

### Prohibited duplication

Repository projections and lifecycle receipts must reject arbitrary fields and
must never embed:

- artifact bytes, licensed rows, positions or private source records;
- agent/capability/workflow definitions, prompts, model responses, tool
  results, reports, dashboard documents or evidence payloads;
- provider credentials, secret references that reveal local configuration,
  absolute host paths, worktree paths or raw filesystem locators;
- copied registry lifecycle, permissions, denied effects or compatibility
  claims; or
- inferred data truth, rights, approval or publication from a filename,
  directory, model, workspace, source label or existing Lab manifest.

Display summaries are derived from the manifest and source adapters and remain
rebuildable. The metadata response should retain the Phase 1 64 KB bounded
projection principle.

## Opaque identity and locator semantics

- API identity is a validated opaque ID. Filesystem names are a SHA-256 of the
  typed identity or a validated content digest, never a user/run/path string.
- PortfolioRisk `ArtifactReference.reference` should be
  `artifact://<opaque-artifact-id>` (or an equally bounded repository scheme),
  not `file://`, an absolute path or a worktree-relative path.
- File preview/download uses artifact ID plus an opaque file-entry ID resolved
  from the manifest. It never accepts a raw host path and need not accept a
  caller-supplied relative path.
- Logical filenames may be displayed after escaping, but they are not storage
  locators and cannot determine authorization.
- A digest identifies bytes/inventory, not approval, recency, trust, rights or
  publication. Those claims require their own exact records.

## Data truth, rights, approval and provenance

### Data truth

Use two explicit dimensions rather than one ambiguous `real/live/fixture`
label:

1. origin: `observed_real`, `derived_from_real`, `synthetic`, `simulated`,
   `mixed`, `missing`, or `unavailable`;
2. fixture status: `not_fixture`, `reviewed_fixture`, or
   `unreviewed_behavior_sample`.

Every present component records exact source/snapshot refs, as-of/available-at
eligibility and derivation. `mixed` requires enumerated components; the current
cycle therefore remains “real daily anchors + simulated seeded intraday,” not
simply real or synthetic. `missing` and `unavailable` are run-manifest gaps and
cannot claim artifact bytes. A fixture is a reviewed provenance status, not a
synonym for all synthetic material.

### Rights and publication

Every data-bearing component records the exact source reference,
`RightsState`, `PublicationRestriction`, whether source rows are contained, and
the policy/adapter revision that computed the effective restriction. A
non-data artifact needs an explicit `no_data_content` declaration and admission
receipt; absence of rights metadata is not that declaration. Rights and
restrictions propagate monotonically: an adapter may make use more restrictive
but cannot downgrade a source. `reviewed_synthetic` never by itself means
public. Incomplete or contradictory rights fail admission closed.

Publication state is independently `unpublished` or
`published_local_development`; Phase 2 performs no production/external
publication. “Published” must not be inferred from Registry definition state or
from a retention class.

### Approval

- Admission confirmation binds actor and time to the exact no-write preview
  digest. A changed source inventory invalidates it.
- Review/checkpoint release, evidence lock, retention release, publication and
  deletion are distinct intents and require distinct references/receipts.
- Reuse existing `DecisionPoint`, ServiceFabric approval/evidence or registry
  receipts only where their intent is exact; store references and digests, not
  copied decisions.
- An approval cannot change rights, waive an active reference, turn a test-
  harness release into human approval, or authorize external effects.
- Published/evidence-locked ordinary deletion remains denied even if a generic
  deletion confirmation is supplied.

### Provenance

Provenance uses exact immutable refs and digests for the producing run,
definition revisions, capability invocations/results, portfolio/data snapshots,
as-of time, code/adapter revision and evidence. Model/provider identity may be
recorded without credentials or private prompt/output content. Host paths are
never provenance; an opaque source reference and digest are.

## Lifecycle matrix

Integrity (`verified`, `corrupt`, `unavailable`) is an orthogonal observed
state and never a lifecycle transition.

| From | Operation | To | Preconditions / consequence |
|---|---|---|---|
| none | confirmed admission | `retained` | Exact preview digest, complete immutable copy, explicit truth/rights/retention, verified manifest and committed admission receipt. |
| `retained` | archive | `archived` | Expected revision and consequence confirmation. Bytes and references do not move or change. |
| `archived` | restore archive | `retained` | Expected revision; this is not tombstone recovery. |
| `retained` or `archived` | request deletion | `tombstoned` | Unpublished, not evidence-locked, integrity verified, no active reference, retention release if required, exact preview/confirmation. Record prior state and `recoverable_until = tombstoned_at + 7 days`. Bytes remain. |
| `tombstoned` | restore deletion | prior `retained`/`archived` state | Strictly before the UTC recovery deadline, bytes and manifest still verify, expected revision, no conflicting replacement. Append restore receipt. |
| `tombstoned` | finalize deletion | `purged` | At or after deadline, no active artifact/run/blob reference, exact manifest still identifies target, durable purge intent written before byte removal. Retain tombstone/purge receipts and identity; remove eligible unowned bytes. |
| `purged` | any ordinary operation | denied | Terminal. Re-creation is a new record/admission even if identical bytes later reappear. |

Corrupt or unavailable records fail closed: preview/download/archive/tombstone/
restore/finalize are denied through the ordinary path. They require a separate
manual diagnostic/recovery procedure, not “delete to fix.” Creating a new
reference to tombstoned or purged material is denied.

## Retention and deletion matrix

| Retention class | Ordinary archive | Tombstone request | Final purge |
|---|---|---|---|
| `ephemeral` | allowed | allowed after explicit preview, zero active refs and verified integrity | after seven days and zero blob owners; no automatic daemon |
| `run_retained` | allowed | allowed with run/owner confirmation and zero active refs | after seven days; shared content remains while any live manifest owns it |
| `experiment_evidence` | allowed | denied until an exact retention-release approval/policy receipt exists; then normal checks | after deadline and zero references/owners |
| `published` | allowed for catalogue visibility only | denied by ordinary API | denied by ordinary API; supersede/deprecate through its owning publication policy |
| `evidence_locked` | allowed only if policy permits hiding | denied by ordinary API | denied by ordinary API; future explicit evidence-governance procedure required |

Changing retention class is itself an append-only governed transition. It may
become more restrictive without losing history. Relaxing
`experiment_evidence`, `published` or `evidence_locked` requires a specific
policy/approval receipt and cannot occur inside a deletion request.

Run deletion never silently cascades. The preview may offer one explicit
all-or-nothing operation over the run record and artifacts exclusively owned by
that run. Shared or externally referenced artifacts remain; any blocked member
blocks the proposed batch unless the user deliberately selects “run record
only.” Every consequence is enumerated before confirmation.

## Reference semantics

- Store typed edges with referencing kind, exact referencing ID/revision,
  referenced artifact ID/digest, purpose, source adapter, created receipt and
  active/released state. A numeric count is only a projection of these edges.
- Only reviewed adapters create/release references; do not trust arbitrary
  user-supplied strings or scan report text for IDs.
- Evidence, run membership, publication, report/dashboard composition and
  registry-definition linkage are distinct reference purposes.
- Reference creation/release and tombstone eligibility share one mutation lock
  and expected catalogue revision so a new reference cannot race deletion.
- Deduplicated blobs also have ownership edges from every live bundle manifest.
  Purging one artifact record removes only its ownership; the blob is removed
  only when the owner set is empty after the recovery deadline.
- Missing referenced bytes are corruption, never an automatically released
  reference. A purged record retains receipts so old references resolve to an
  explicit deleted state rather than a different artifact.

## Persistence, concurrency and crash invariants

Recommended external layout (names illustrative, never exposed by API):

```text
<runtime-root>/artifacts/
  blobs/sha256/ab/<digest>
  manifests/sha256/ab/<digest>.json
  records/<hashed-typed-id>/projection.json
  records/<hashed-typed-id>/events/000001.json ...
  runs/<hashed-typed-id>/manifest.json
  references/<hashed-key>.json
  pending/<intent-digest>.json
  locks/
  catalogue.json
```

All mutable bytes remain outside Git. Cache, temp and backup roots remain
separate; the current capability cache is never indexed as evidence.

### Publication/admission protocol

1. No-write preview validates IDs, inventory, types, quotas, truth, rights,
   references and source stability and returns a canonical consequence digest.
2. Confirmation revalidates the same source under a mutation lock. Open source
   files descriptor-relative with no symlink following, stream to a temporary
   file in the final blob parent, hash and count bytes, `fsync`, and recheck the
   source descriptor/inventory.
3. Create each digest path without replacement. If it exists, verify exact
   bytes; identical concurrent writes converge, any inconsistency fails closed.
4. Durably create the immutable bundle/run manifests and append-only admission
   event/anchors, then atomically commit the catalogue head and `fsync` each
   affected parent directory.
5. Only the committed catalogue makes a record list-visible. Orphaned complete
   blobs are invisible and may be adopted only by an exact pending-intent retry
   or quarantined by a manual recovery command.

### Locking

- Combine same-process `RLock` with POSIX cross-process `fcntl` locking behind
  an isolated lock interface.
- Use a catalogue/reference mutation lock plus per-record and per-digest locks.
  Acquire in fixed order: catalogue/reference, sorted record IDs, sorted blob
  digests. Never invert the order.
- Every mutating request carries expected record/catalogue revision and an
  idempotency/intent digest. Same intent converges; changed intent conflicts.
- Readers select only a catalogue-committed immutable prefix. They verify the
  manifest and lifecycle head; malformed state is reported, not silently
  omitted.
- Advisory locking and read-only modes are integrity aids, not protection from
  the operating-system owner. Non-POSIX support is unresolved and must fail
  closed until another lock implementation is tested.

### Crash boundaries and recovery

| Crash point | Required restart behavior |
|---|---|
| before a temp file is complete | Temp is never visible and is safely removable after verifying it is repository-owned. |
| after temp `fsync`, before immutable install | No final artifact is visible; exact retry restarts/converges. |
| after blob install, before manifest/event | Blob is an unowned invisible orphan; exact pending-intent retry may adopt it after full verification. |
| after immutable event/manifests, before catalogue replacement | Previous committed prefix remains readable; exact retry completes the head. Changed intent fails. |
| after catalogue replacement, before response | Idempotent retry returns the committed result without duplicating receipts. |
| after tombstone commit | Record is unavailable but bytes remain until the deadline; restart preserves the exact recovery deadline. |
| during final purge | A durable `purge_pending` intent exists before any unlink. Restart/manual recovery verifies target and owner set, resumes unlink, `fsync`s directories, then commits one purge receipt. It never restores visibility or points identity at new bytes. |

Phase 2 has no background cleanup daemon. Startup may reconcile incomplete
already-authorized operations; expiration alone does not initiate purge.

## Path, symlink, size and content threat model

| Threat | Required control / failure |
|---|---|
| absolute, traversal, empty, dot, NUL, backslash/Windows-drive or overlong path | Canonical bounded relative POSIX validation; reject before filesystem use. Normalize Unicode to NFC and reject duplicate/case-fold-colliding logical paths for cross-platform safety. |
| root or internal directory symlink | Check every existing root component with `lstat`; reject symlinks. Use descriptor-relative operations rather than trusting `Path.resolve()`. |
| source or stored file symlink | `O_NOFOLLOW`/`lstat`, regular-file requirement, and post-open `fstat`. Never preview, hash, copy or download through a symlink. |
| symlink swap / source mutation during admission | Hold source descriptors, compare device/inode/size/metadata before and after streaming, re-enumerate exact inventory, and bind confirmation to the observed digests. Any change invalidates preview. |
| hard-link manipulation inside store | Repository creates its own bytes; stored blobs/manifests must be regular files with expected ownership/mode and no unexpected link count. Never hard-link caller files into the store. |
| added, missing or undeclared file | Exact set equality against the run/bundle manifest; verification and admission fail closed. |
| oversized file/count/run | Default first release: at most 4,096 files, 128 MiB per file and 128 MiB total retained bundle (matching the strongest current ServiceFabric application-output bound). Stream with bounded memory. Higher limits require policy/version change. |
| archive/decompression bomb | Phase 2 does not unpack uploaded archives. Archive bytes are opaque downloads unless a later reviewed adapter adds bounded extraction. |
| digest or metadata substitution | Recompute file, bundle, manifest, receipt-chain and catalogue-head digests on read/verify; mismatched same-digest content is corruption, never overwrite. |
| malicious active HTML/SVG | Preview is inert escaped text or separately sandboxed with restrictive CSP and no network; download uses safe content disposition. Repository never executes an artifact. |
| absolute-path/API leakage | Serialize only opaque record/file locators. Error messages and provenance omit configured root and source host path. |
| verification denial of service | Bound preview bytes and verification concurrency/time; stream hashes. Timeout/partial verification reports `unavailable`, never `verified`. |
| rights-sensitive preview/download | Authorization and effective publication restriction are checked independently of possession of an artifact ID. Licensed content is never embedded in public metadata. |

`FileArtifactStore.root.resolve()` and `open_file(...).read_bytes()` are not
sufficient for this threat model: the existing vendor implementation does not
comprehensively refuse root/internal/file symlinks or protect repository policy
metadata. The adapter must add these checks without editing vendor code.

## Required focused adversarial tests

### Contract/projection tests

- extra fields fail; projection stays below 64 KB and contains none of the
  prohibited payload/definition/path/secret fields;
- paths are unique, deterministic, bounded and cross-platform collision-safe;
- file counts/sizes/digests, total, content digest and manifest digest reconcile;
- PortfolioRisk `ArtifactReference` round-trips with an opaque locator;
- application/static/process artifact adapters accept only semantically
  compatible canonical variants;
- data truth, fixture status, rights, publication, retention and approval remain
  independent and incomplete/contradictory combinations fail;
- `missing`/`unavailable` cannot claim bytes; `mixed` requires components.

### Admission and integrity tests

- preview performs zero writes; confirmation with changed inventory/digest,
  actor or policy fails;
- empty, corrupt, malformed, oversized, absolute-path, traversal, symlink,
  directory, socket and device entries fail;
- source mutation and symlink swap during hash/copy fail;
- existing identical content is idempotent; same identity/different manifest
  and simulated digest collision fail without overwrite;
- added/missing/changed/undeclared files and manifest substitution fail verify;
- malformed records remain visible as corrupt/unavailable rather than silently
  disappearing from list;
- no API response, locator, error or receipt exposes an absolute root.

### Concurrency and crash tests

- thread and separate-process same-digest publication converges to one valid
  blob/record; conflicting identity or metadata yields one winner and conflict;
- reference creation versus tombstone, restore versus finalize, two finalizers,
  and archive versus delete preserve one valid receipt sequence;
- injected failure at every tabled crash point leaves the prior committed view
  readable and exact retry recoverable;
- file and directory `fsync` calls, immutable link/create, temp cleanup and
  fixed lock order are asserted;
- restart reconstructs the same catalogue/lifecycle/reference state and never
  auto-purges merely because a deadline passed.

### Retention/reference/deletion tests

- every allowed lifecycle transition succeeds once with expected revision;
  every other transition fails;
- published and evidence-locked ordinary tombstone/finalize always fail;
- experiment evidence requires exact retention release;
- referenced and corrupt records cannot be tombstoned or finalized;
- restore works before but not at/after the deadline; finalize works at/after
  the deadline only with zero references/owners;
- deduplicated bytes survive deletion of one owner and are removed only after
  the last eligible owner is purged;
- batch run deletion preview is exact and logical mutation is all-or-nothing;
- terminal purged identity never resolves to replacement bytes.

### Migration and regression tests

- current Agent Lab run admission checks every physical file, rejects its
  absolute `folder`, derives no rights/truth from labels, and is opt-in;
- duplicate admission of the exact source/adapter/policy is idempotent; changed
  legacy folder under the same preview conflicts;
- test-harness checkpoint release remains non-human and effects remain empty;
- cache/generated-agent directories are not silently admitted as evidence;
- Registry, Agent, Dataset, Workflow Cycle and Full Experiment suites remain
  green; repository endpoints execute no SQL, model, agent, workflow, artifact,
  external publication or financial effect.

## Tests executed

```bash
PIP_NO_INDEX=1 make preflight \
  BOOTSTRAP_VENV=/private/tmp/platform-p1-r6-qa.Ff4OMP/venv
```

Result: **PASS** — environment, repository, exact ServiceFabric pin, upstream
doctor and `git diff --check`.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="packages/risk_domain/src" \
  .../state/venvs/thesis-sprint/bin/python -m pytest -p no:cacheprovider \
  tests/domain/test_models.py -q
```

Result: **PASS**, `16 passed`.

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="vendor/servicefabric/packages/servicefabric_contracts/src:\
vendor/servicefabric/packages/servicefabric_artifacts:\
vendor/servicefabric/packages/servicefabric_builder" \
  .../state/venvs/thesis-sprint/bin/python -m pytest -p no:cacheprovider \
  vendor/servicefabric/packages/servicefabric_contracts/tests/test_artifacts.py \
  vendor/servicefabric/tests/artifacts/test_store.py -q
```

Result: **PASS**, `5 passed`.

No licensed rows, private run folder, provider credential, model call or
external system was read or invoked.

## Unresolved integration decisions and residual risks

1. Confirm the generic contract names and schema version under
   `packages/risk_artifacts`; do not export them as new canonical portfolio or
   ServiceFabric contracts in Phase 2.
2. Confirm whether a repository artifact is always a bundle (recommended) or
   whether single-file and bundle records are distinct. In either case,
   `ArtifactReference.digest` must have one documented meaning and blob versus
   bundle digests must not be interchanged.
3. Define the reviewed attestation and policy revision for `no_data_content`.
   Existing rights enums cover data sources but not source-free generated code
   or operational logs.
4. Freeze which adapters may create/release active references and the exact
   meaning of an active reference for historical evidence. A mere ref count is
   unsafe.
5. Confirm the initial 128 MiB total quota and global repository quota. Quota
   exhaustion must fail without evicting retained/published/evidence material.
6. Decide which owning policy may publish a repository artifact locally.
   Registry publication of a definition must never imply publication of its
   artifacts.
7. Corrupt-store repair, backup restore, evidence-lock release and forced
   administrative purge need later explicit governance. Ordinary Phase 2
   endpoints must fail closed instead of improvising them.
8. `fcntl`, descriptor-relative no-follow behavior, Unicode/case behavior and
   directory durability require macOS and Linux tests. Non-POSIX operation is
   unsupported until a reviewed lock/filesystem adapter exists.
9. The local OS owner can rewrite all mutually consistent files. Digests,
   read-only modes and receipt chains detect accidents/tampering but are not a
   remote trust anchor. UI wording must retain the local-development boundary.

None of these questions authorizes an unsafe default. Missing rights, truth,
approval, reference or integrity information blocks admission/deletion.

## Deviations, limitations, rollback and next action

There was no implementation deviation: vendor, packages, applications, tests,
configuration and workplans remain unchanged. The audit inspected source and
reviewed tests only; no user's external runtime repository or private retained
run was inspected.

Rollback is removal of this handoff/branch. No artifact bytes or persistent
metadata were created. Integration should reconcile this handoff with the run-
migration and UI/policy audits, implement the bounded contracts and hardened
store only in P2-04, and request clean independent adversarial QA. Do not begin
Phase 3, add a cleanup daemon, or merge this specialist branch directly.
