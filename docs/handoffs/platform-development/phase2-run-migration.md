# Phase 2 specialist handoff — existing Agent Lab run migration audit

- Lane: existing-run migration audit (`P2-02`)
- Branch: `feature/platform-p2-run-migration`
- Audit base / head before this handoff: `89be56bb509e2e2f9a8cd1f81b3246dbf2ded87d`
- Accepted Phase 1 baseline: `9440bbaeb3f43f04ff259dbde0eb2824b7f9c6f1`
- Scope: code, contracts, tests, and synthetic temporary-directory probes only
- Repository change: this handoff only

## Executive answer

Existing Agent Lab runs can be retained in Phase 2, but they cannot be copied
or promoted merely because a readable `manifest.json` exists. The current
folder is an unversioned review convenience. Its manifest has names and byte
counts but no content digests, rights, retention, publication policy, source
revision bindings, or integrity receipt. Real-data runs can contain licensed
rows and portfolio detail in several files. Broken folders are currently
silently omitted, undeclared files are ignored, malformed JSON is returned as
text, and deletion is immediate.

The compatible migration is therefore an explicit, previewed, fail-closed
**admission adapter**:

1. discover a server-configured legacy run by opaque candidate ID;
2. verify the exact current twelve-file layout without rendering contents;
3. calculate fresh digests and validate all cross-file disclosures;
4. require an explicit rights/retention admission policy where the source does
   not carry authoritative metadata;
5. copy immutable bytes atomically into the content-addressed repository;
6. create a retained-run projection and immutable admission receipt; and
7. leave the legacy source untouched.

Admission does not turn a Lab `AgentBlueprint`, generated Python module,
provider receipt, report, or test-harness checkpoint release into a published
definition, canonical run, human approval, or research evidence. `completed`
means only that local execution reached its runtime end. All admitted runs
remain development-only and non-effectful; current synthetic behavior samples
and licensed local runs both default to no publication.

## Audit boundary

No `.agent-runs` directory, user run folder, private portfolio, provider row,
credential, or model response was inspected. The map below is derived from the
producer and consumer code and from code-generated synthetic temporary runs.
This is not a statement that any particular user run is admissible.

The adapter must never scan arbitrary client-supplied paths. The legacy root is
server configuration; the UI receives opaque candidate IDs only. Content can
be hashed for admission without being rendered or returned to the browser.

## Exact current producer map

### Roots and their distinct meanings

| Current root | Producer | Contents | Migration meaning |
|---|---|---|---|
| `PORTFOLIO_RISK_AGENT_RUN_ROOT`, default `.agent-runs/agent-lab` | `agent_studio.run_blueprint` -> `_persist_run` | one folder per isolated Agent Lab run | only source eligible for this retained-run adapter |
| `PORTFOLIO_RISK_AGENT_OUTPUT_ROOT`, default `.agent-runs/generated-agents` | `compile_blueprint` | `blueprint.json` and generated `agent.py` keyed by blueprint digest | rebuildable compiler output; do not discover as a retained run |
| `PORTFOLIO_RISK_CAPABILITY_MEMORY_ROOT`, default `.agent-runs/capability-memory` | `_store_capability_memory` | slow, successful, effect-free call cache | cache; never evidence and never part of run admission |
| browser memory / `localStorage` | `labs.js` | drafts, output-pass assembly, graph state | not a server run folder and not imported in Phase 2 |
| process memory | workflow-cycle runtime | clocks, dashboards, findings, proposals, decisions | not durable and not imported in Phase 2 |

`run_blueprint` always calls `compile_blueprint(..., persist=True)`, including
when `persist_run=False`. A transient test can therefore leave generated-agent
compiler output without a retained run. Conversely, the run manifest does not
record a verified generated-module locator or source digest. A same-named or
same-blueprint generated folder must not be guessed as the run's executable
authority.

### Request-to-folder sequence

| Sequence | Code path | Current behavior | Durable truth available |
|---:|---|---|---|
| 1 | `POST /api/agents/run` | Recreates input through `prepare_agent_input`; caller-supplied context is replaced by server-hydrated context. | source mode, point-in-time metadata, scenario, portfolio/as-of metadata |
| 2 | `run_blueprint` | Compiles and writes generated blueprint/module, imports it, and invokes LangGraph. | compiler result exists separately, but is not bound into the saved manifest |
| 3 | generated `gather_evidence` | Runs the first canonical exposure/MetricPack chain and retains other latches as supplied-context bindings. | capability results distinguish `canonical_registry` from `supplied_context` |
| 4 | generated `assemble_context` | Creates `OverallDefaultContext` only after calculations. | calculation result digests are carried in run state where available |
| 5 | generated `draft` | Uses deterministic interpretation or a schema-constrained OpenAI Responses call. | live mode has bounded model receipts; deterministic mode has none |
| 6 | generated `human_review` | May pause; the isolated test harness may explicitly release the interrupt. | checkpoint receipt says `human_approval: false` for harness release |
| 7 | `_run_presentation`, `_run_activity` | Derives human-facing output and an activity projection. | projections duplicate parts of source inputs/results and are not new evidence |
| 8 | `_persist_run` | Creates the final folder and writes files one at a time, then writes manifest twice. | non-atomic legacy folder; a crash can leave partial state |

The run ID is emitted as
`run-YYYYMMDDTHHMMSSZ-<8 lowercase hex>`. The loader also accepts the short-lived
legacy `+0000` suffix. The hash is based on an ephemeral LangGraph thread ID and
creation time, not on the complete run contents.

## Exact current consumer map

| Consumer | Current behavior | Phase 2 consequence |
|---|---|---|
| `GET /api/agents/runs` -> `list_agent_runs` | Reads each `manifest.json`; silently omits unreadable/malformed folders. | repository discovery must show `damaged` candidates rather than making them disappear |
| `GET /api/agents/runs/{run_id}` -> `load_agent_run` | Reads manifest-declared files up to 2 MB; skips missing/unsafe/oversize files; returns malformed JSON as text. | admission must reject these cases, never normalize them silently |
| `DELETE /api/agents/runs/{run_id}` -> `delete_agent_run` | Calls `shutil.rmtree` immediately. | not an admissible repository deletion path; imported records use Phase 2 lifecycle/tombstone rules |
| `renderAgentRunRepository` | Lists mode, agent name, time, runtime status, and execution mode. | retain truthful mode/status but do not imply review, publication, or evidence acceptance |
| `renderSavedAgentRun` | Reads input, provenance, blueprint, output, and activity into the run-review UI. | repository preview policy must prevent licensed/raw material from entering this path |
| `renderRunFiles` | Displays the absolute folder and every manifest file; file content can be viewed. | replace with opaque repository locator and per-file preview/download eligibility |
| browser delete action | Confirms removal of the whole local folder. | repository uses archive/tombstone/restore/purge preview; legacy source is not deleted by admission |

No other server component consumes these run folders. Output-pass assembly,
the workflow cycle, the graph composer, thesis runners, and the Phase 1
definition registry have separate state and must not be swept into migration.

## Exact legacy file contract

The current writer declares twelve files: the manifest plus eleven payloads.
Every file is UTF-8 text. The Phase 2 source adapter should use the following
closed allow-list for this legacy format; additions require a new reviewed
adapter version.

| File | Current producer and meaning | Sensitive/duplicated content | Retained mapping and default access |
|---|---|---|---|
| `manifest.json` | `_persist_run`; summary of run and file names/sizes | absolute host folder, portfolio ID, model/mode metadata | retain original as `legacy_manifest`; never expose `folder`; canonical admission manifest lives separately |
| `input.json` | exact frozen source context | real mode embeds local licensed `source_records`, positions, quantities, prices, history, aliases, and point-in-time inputs | `run_input`; restricted; no browser preview/download for licensed runs |
| `input-provenance.json` | source-mode and retrieval summary | portfolio/as-of, datasets, record counts, quality; no current rights contract | `input_provenance`; metadata preview only after policy check |
| `blueprint.json` | invocation-time Lab blueprint snapshot | full authoring configuration; not a registry revision and may contain user-authored text | `invocation_configuration`; not auto-indexed or published as an Agent |
| `activity.json` | presentation projection built from trace/calls | duplicates capability requests, results, evidence IDs, model receipt, and rationale summaries | `activity_log`; rights inherit from input and receipts; redact/deny preview when restricted |
| `research-plan.json` | deterministic capability-chain plan | operational explanation; may still reveal scope | `research_plan`; run-scoped artifact, not a reusable workflow definition |
| `capability-executions.json` | exact canonical calls plus supplied-context bindings | requests/results can contain holdings, values, evidence/source references; not all entries are canonical calls | `capability_receipts`; restricted when derived from licensed/private input |
| `model-executions.json` | live model-call receipts, or empty for deterministic runs | provider/model/response ID, tokens, timings, prompt/output digests; no raw prompt or raw response | `model_receipts`; local restricted metadata; response ID is not content evidence |
| `output.json` | assembled output envelope | duplicates capability results, model output, narrative, critique, review, and presentation | `agent_output`; run-retained, rights inherited from every source |
| `review.json` | critique and checkpoint state | test-harness release can appear approved in graph state while explicitly not human approval | `review_receipt`; preserve exact actor/status; never translate harness release into human approval |
| `review-brief.md` | deterministic Markdown renderer | human-readable derived metrics/findings; may disclose licensed/private facts | `rendered_report`; preview/download only when rights permit |
| `transcript.md` | Markdown work record | embeds JSON activity payloads and therefore can duplicate inputs/results | `run_transcript`; treat as sensitive, not as a safe redacted summary |

### Manifest fields currently available

`run_id`, `agent_name`, `output_contract`, `status`, `data_mode`, `data_label`,
`execution_mode`, `execution_model`, `scenario`, `portfolio_id`, `as_of`,
`created_at`, `elapsed_ms`, `operating_profile`, `authority_boundary`,
`external_effects`, `persistence_class`, `folder`, and `files` are present.
Each file entry carries only `name`, `bytes`, and `kind`.

### Required metadata missing from the legacy manifest

- manifest format ID and version;
- digest and media type for every retained file;
- digest of a canonical complete-file manifest;
- stable opaque repository/run identity;
- immutable source observation and adapter version;
- agent/blueprint registry revision and generated-code revision;
- capability/tool, method, policy, and code revisions;
- dataset/snapshot revision rather than only local query labels;
- complete evidence references;
- data-truth class as a strict contract;
- rights state, access scope, and publication restriction;
- retention class, archive state, evidence lock, references, approvals, and
  supersession;
- integrity state and admission receipt;
- creator/creation method in a reviewed identity contract;
- parent experiment/workflow association;
- deletion/tombstone/recovery policy.

These fields must not be fabricated from a folder name or friendly label.
File sizes and SHA-256 digests are objective derived values and may be computed
by the adapter. Rights, approvals, publication, definition revisions, and
experiment association require authoritative declarations or remain absent and
block the operation that needs them.

### Legacy manifest self-size defect

The writer first writes a manifest without `manifest.json` in `files`, records
that first file size, prepends the entry, and rewrites a larger manifest. The
declared size of `manifest.json` is therefore stale by construction. A
synthetic temporary-directory probe observed 1,716 declared bytes versus 1,802
actual bytes.

Compatibility rule: admission must not trust the legacy manifest's self-size.
It should record both values as a warning, compute the original manifest's
actual digest/size, and create a separate canonical admission manifest covering
all twelve legacy files. All non-manifest declared sizes must match exactly.
Do not rewrite the source manifest to make it appear valid.

## Generated agent versus retained run

The following identities must remain separate:

```text
Lab AgentBlueprint draft
  -> compiler digest / generated-agent directory
       -> generated blueprint.json + agent.py (rebuildable)
  -> one invocation
       -> retained run input/configuration/receipts/outputs (historical record)
```

Rules:

1. Scan only the configured legacy run root, never `generated-agents` or
   `capability-memory`.
2. Treat the run's `blueprint.json` as captured invocation configuration. It is
   not a canonical AgentRole, registry publication, or proof that `agent.py`
   executed unchanged.
3. Do not infer a generated module link from blueprint name/digest. The legacy
   manifest omits a verified link and source digest.
4. If a future run producer supplies an immutable registry revision and
   generated-code artifact reference, retain those references. Never backfill
   them into old runs by matching mutable files.
5. Generated code can enter the artifact repository only through a separate,
   explicit artifact admission with its own lifecycle and security review.
6. Deleting or archiving a retained run must not delete a published agent
   definition or shared generated object. Retiring an agent definition must not
   delete its historical runs.

## Data truth, rights, and publication boundary

### Current modes

| Legacy mode | Evidence available in code | Required admission classification | Publication ceiling |
|---|---|---|---|
| `synthetic_behavior_sample` | provenance says `licensed_data_used: false`, `point_in_time: false`, `reviewed_fixture: false` and warns that values are code-generated | synthetic, unreviewed behavior sample; development only | `no_publication`; it is not a reviewed fixture or empirical evidence |
| `real_duckdb` | provenance says licensed local CRSP/Compustat, point-in-time query, portfolio/as-of/datasets, and limitations | licensed historical local research data; point-in-time method with disclosed timestamp limitations | `no_publication`; rights restricted unless a separate reviewed rights policy says more |
| missing/unknown/legacy label | no strict truth contract | unresolved | admission blocked |

`REAL` means historical local licensed input, not a live feed. A successful
model call does not change data truth. A Markdown renderer does not remove
source rights. Every derived file inherits the most restrictive data rights and
publication restriction of all of its inputs unless a separate reviewed
redaction/declassification operation proves otherwise.

### Required admission policy

The preview may suggest the safest compatible policy, but final admission
requires a policy receipt with:

- truth class and source mode;
- rights state and local access scope;
- publication restriction;
- retention class;
- reviewer/actor and timestamp;
- purpose and run association, if known;
- acknowledgement that admission does not constitute approval/publication.

For `real_duckdb`, the operator must select or confirm a reviewed local rights
policy; the boolean `licensed_data_used` is not an entitlement record. For a
synthetic behavior sample, the adapter may lock truth/publication to the safe
values above, but it must still show them before admission.

### File access policy

- Never preview licensed `input.json`, `capability-executions.json`, raw
  `activity.json`, or `transcript.md` through the browser/API.
- Do not assume `review-brief.md` or `output.json` is safe: derived metrics,
  holdings, and company facts retain input restrictions.
- A local download endpoint must evaluate per-file rights, retention,
  publication, and reference state before opening bytes; denied material stays
  available only to an explicitly authorized local inspection path.
- API responses expose opaque locators and safe metadata, never the legacy
  `folder`, repository root, source root, or CAS path.
- Provider response IDs, source references, native identifiers, and portfolio
  identifiers are metadata subject to the same local access policy.
- No imported file is executable. HTML/JavaScript is not part of the current
  twelve-file format; if encountered it is undeclared and rejected.

## Deterministic discovery and preview

### Discovery

1. The server owns one configured legacy root. Refuse a missing root, a root
   inside application source when policy forbids it, a symlink root, or a root
   that escapes its configured boundary.
2. Enumerate direct child directories only with non-following filesystem calls.
   Do not recursively discover arbitrary paths.
3. Validate the child name against the current `Z` or legacy `+0000` run-ID
   regex. A malformed name is visible as `rejected`, not silently ignored.
4. Require directory name, manifest `run_id`, and requested candidate identity
   to agree.
5. Assign an opaque discovery ID. Do not return the child path.
6. Read bounded metadata only. A missing/unreadable manifest becomes a
   `damaged` preview record; no content is returned.

### Preview token

Preview calculates and binds:

- adapter format/version;
- source run ID and canonical source-manifest digest;
- sorted exact file-name, actual-size, SHA-256, media-type tuples;
- cross-file validation result and warnings;
- truth/rights/retention proposal and unresolved requirements;
- admission consequences, deduplication result, references, and restrictions;
- an expiry and actor/session binding.

The confirmation token must cover this complete preview. Admission re-stats and
re-hashes the source while holding the per-source lock. Any difference returns
`source_changed_since_preview`; it never imports the changed bytes under an
old confirmation.

## Admission algorithm

1. Acquire a lock for the opaque legacy candidate and proposed retained-run
   identity.
2. Validate the preview token, actor, expiry, and required policy confirmation.
3. Open the source directory without following symlinks and verify the exact
   closed file set.
4. Require every entry to be a regular file, a single safe leaf name, UTF-8,
   within the declared bound, and unchanged during hashing.
5. Parse JSON files strictly; validate the Markdown files as inert text. Reject
   NUL bytes and unsupported encodings.
6. Validate file-specific shapes and all cross-file rules below.
7. Derive fresh SHA-256 digests, sizes, media types, and a canonical sorted file
   manifest. Preserve the original legacy manifest as one source artifact.
8. Compute a stable opaque retained-run ID from the adapter namespace, legacy
   run ID, and complete canonical source digest. Do not use an absolute path.
9. Stage content-addressed blobs and metadata under repository temporary state;
   fsync files/directories; atomically promote identical blobs or fail on any
   digest/byte mismatch.
10. Atomically publish the retained-run projection, references, and immutable
    admission receipt only after every blob is present and verified.
11. Re-open through the repository API and run full integrity verification.
12. Return the existing record/receipt for an identical re-admission. Leave the
    source folder unchanged in every case.

### Cross-file validation

- `manifest.data_mode == input-provenance.data_mode`.
- Synthetic mode requires the exact explicit unreviewed-sample flags and
  `scenario` agreement; it may not be called a reviewed fixture.
- Real mode requires `licensed_data_used: true`, `point_in_time: true`, matching
  portfolio/as-of, and a non-empty dataset list and point-in-time rule.
- Manifest `operating_profile` remains `development`.
- `authority_boundary` remains findings/proposals only and
  `external_effects` is empty.
- Status is only `completed` or `waiting_for_human_review` for this adapter.
  Runtime completion does not imply review completion.
- `blueprint.json` name and output contract agree with the manifest where
  present; the blueprint remains invocation configuration.
- Deterministic execution requires `execution_model: null` and an empty
  `model-executions.json`.
- Live-model execution requires at least one strict receipt with provider,
  model, response identifier, non-negative token/timing counts, `store: false`,
  empty tools, and valid prompt/output digests. No raw provider payload is
  invented if absent.
- Capability entries retain the distinction between canonical execution and
  supplied-context binding. Canonical receipts require valid input/output
  digests, evidence IDs as declared, empty effects, timings, and explicit
  success/stop state.
- `review.json` checkpoint fields agree with the manifest/status and output.
  `actor_type: test_harness` plus `human_approval: false` remains a test release,
  regardless of an internal graph `approved` boolean.
- `review-brief.md` and `transcript.md` are retained exactly; they are not
  reparsed to manufacture findings, evidence, or approval.
- The exact twelve legacy files are present. Missing and undeclared files are
  both integrity failures.

## Required rejection cases

Return stable machine-readable rejection codes and human explanations. At
minimum:

| Code | Condition |
|---|---|
| `legacy_root_unavailable` | configured source root is unavailable or unsafe |
| `invalid_candidate_id` | caller supplies a path or unknown opaque candidate |
| `invalid_run_id` | folder/manifest ID fails regex or does not agree |
| `symlink_or_special_file` | root, directory, or file is a symlink/device/socket/FIFO |
| `path_escape` | a name is absolute, contains separators/traversal, or resolves outside source |
| `manifest_missing` / `manifest_invalid` | absent, malformed, oversized, non-object, or unsupported format |
| `source_changed_since_preview` | any name, size, digest, metadata, or policy input changed |
| `file_missing` / `undeclared_file` | exact twelve-file set is not present |
| `file_oversized` / `run_oversized` | bounded legacy-import limits are exceeded |
| `invalid_utf8` / `invalid_json` | a declared file cannot be parsed as its declared media type |
| `declared_size_mismatch` | non-manifest legacy size differs from actual size |
| `truth_conflict` | mode/provenance/scenario/license/point-in-time values disagree |
| `rights_unresolved` | authoritative rights/access/publication policy is incomplete |
| `execution_conflict` | deterministic/live mode conflicts with model receipts |
| `review_conflict` | status/checkpoint/human-review claims disagree |
| `effects_not_allowed` | any external financial or undeclared effect appears |
| `definition_reference_unresolved` | caller requests definition linkage not proven by source |
| `content_conflict` | same retained/source identity is associated with different bytes |
| `repository_integrity_failure` | staged/final content cannot be reverified |

The known manifest self-size defect is a warning only under this exact adapter
version. It is not a blanket permission to ignore other size mismatches.

## Idempotence, concurrency, and collision policy

- An identical source run, complete canonical file digest, and admission policy
  returns the existing retained-run record and original success receipt. It
  does not duplicate lifecycle events, references, or blobs.
- Two concurrent identical admissions converge under locks. One commits; the
  other revalidates and returns the committed identity.
- Same legacy `run_id` with a different complete digest is a conflict, not a
  new version silently. The UI shows both source observations only after an
  explicit operator resolution workflow.
- Same SHA-256 locator with non-identical bytes is a fatal collision/integrity
  error. Never overwrite.
- Distinct retained runs may reference the same content-addressed blob. Blob
  retention/deletion follows active references, not one run's folder lifecycle.
- Admission receipts carry request/idempotency key, source digest, canonical
  manifest digest, policy digest, previous state, resulting identity, actor,
  timestamp, and operation result.
- The legacy `created_at` is source metadata. Repository admission time is a
  separate timestamp and never replaces it.

## Partial, corrupt, and interrupted source behavior

Current writes are not atomic. A crash can leave a directory with some files,
no manifest, an earlier manifest, or truncated JSON. The migration must:

1. list the candidate as `damaged` with reason codes rather than omitting it;
2. never admit a subset or synthesize the missing files;
3. never rewrite or delete the source while diagnosing it;
4. allow a later preview after an external producer finishes or repairs the
   source, producing a new complete source digest;
5. keep the repository unchanged when validation fails;
6. ensure any unreferenced staged CAS bytes are invisible and recoverable by a
   separate maintenance process, not treated as an admitted run.

`waiting_for_human_review` is not filesystem corruption. It may be retained as
an incomplete review snapshot with publication denied and review still open.
A test-harness-released run is also retainable, but its review state is
`test_checkpoint_released`, never `human_approved`.

## Retained-run projection mapping

The repository needs a thin association record, not a replacement for
PortfolioRisk `AgentRun` or a new authoritative agent definition.

| Retained projection field | Legacy source | Rule |
|---|---|---|
| opaque retained run ID | adapter namespace + legacy run ID + complete digest | stable and path-free |
| source observation | legacy adapter ID/version, run ID, manifest/file digests | immutable; no absolute path in API |
| source run time | `created_at` | timezone-aware validation required |
| runtime status | manifest `status` | distinct from review/publication state |
| agent display | `agent_name` | display only; not registry identity |
| agent definition ref | none proven | absent; do not match by name |
| invocation configuration artifact | `blueprint.json` | immutable captured input only |
| input artifacts | input and provenance files | rights-bound, point-in-time disclosure preserved |
| activity/research | activity and research-plan files | projections, not new evidence |
| capability/model receipts | execution files | preserve exact receipt types and limitations |
| output/review | output and review files | review state normalized without changing source bytes |
| renderings | brief and transcript | derived artifacts inheriting source restrictions |
| artifact references | CAS digest/media/opaque locator for each file | adapt to existing artifact semantics |
| truth/rights/publication | validated provenance + policy receipt | most restrictive inheritance |
| retention/lifecycle | explicit admission policy and Phase 2 receipts | independent of runtime status |
| associations | optional explicit workflow/experiment refs | never inferred from folder names |

The domain `AgentRun` requires a deterministic local provider disclosure,
canonical role, capability invocations, input/output digests, and evidence
references. A legacy live-LLM Lab run or free-form blueprint does not satisfy
that meaning. Do not manufacture a canonical `AgentRun`. Where a future source
already supplies a valid canonical run reference, the retained projection may
point to it.

## Repository lifecycle and legacy coexistence

- **Preview:** read-only source observation, no retained bytes.
- **Admit:** immutable CAS bytes and retained-run projection created; legacy
  source remains.
- **Archive/restore:** changes repository visibility/lifecycle only.
- **Tombstone/restore:** governed repository metadata with recovery deadline;
  legacy source remains.
- **Final purge:** removes only unreferenced repository bytes after policy and
  deadline. It never calls legacy `delete_agent_run`.
- **Legacy cleanup:** outside admission. If offered later, it requires a
  separate preview proving successful repository integrity and explicit user
  confirmation; no Phase 2 migration should perform it automatically.

An admitted run's repository integrity must not depend on continued existence
of its legacy source. Conversely, reverting Phase 2 code must not remove or
modify legacy source runs.

## Migration and regression test plan

All tests use reviewed synthetic data or generated temporary files; no private
run content is needed.

### Source-format and mapping tests

1. Generate a current synthetic run with `_persist_run`; preview recognizes all
   twelve files and the known manifest self-size warning.
2. Map every file to the exact artifact role above and prove no generated-agent
   or capability-memory file enters the run.
3. Prove `blueprint.json` is invocation configuration and does not create or
   publish a Phase 1 Agent registry item.
4. Admit `completed` and `waiting_for_human_review` samples with distinct review
   states.
5. Preserve a test-harness release as non-human approval.
6. Require empty model receipts for deterministic mode and strict receipts for
   live mode using synthetic receipt fixtures only.
7. Preserve canonical-call versus supplied-context-binding distinctions.

### Truth and rights tests

1. Synthetic behavior sample becomes unreviewed synthetic/no-publication and
   never reviewed fixture/evidence.
2. Real-mode metadata without an explicit rights policy is blocked; use a
   metadata-only synthetic contract fixture, not licensed rows.
3. Conflicting mode/license/point-in-time/scenario/portfolio/as-of values fail.
4. Every derived file receives the most restrictive source policy.
5. Licensed/raw roles deny browser preview/download and never return bytes in
   an API error.
6. API and UI contain no absolute legacy/repository path.

### Integrity and threat tests

1. Missing, added, renamed, changed, truncated, invalid-UTF-8, invalid-JSON,
   oversized, empty, symlinked, absolute, traversal, device, and nested files
   all fail closed.
2. Non-manifest recorded-size mismatch fails; only the exact known manifest
   self-size shape receives the compatibility warning.
3. Source mutation between preview and admission fails.
4. Same run ID/different bytes and same digest/different bytes fail.
5. Post-admission added, missing, or modified repository content fails verify.
6. Corrupt folders remain visible as damaged without entering repository state.

### Atomicity, restart, and idempotence tests

1. Repeat identical admission returns the same run ID/receipt and file/blob
   counts.
2. Concurrent identical admissions converge; concurrent conflicts fail.
3. Inject failures after each staged blob, metadata stage, atomic promotion,
   and receipt write; no partial retained run is visible.
4. Restart the process and reproduce catalogue, references, rights, lifecycle,
   and integrity state.
5. Verify a retained run after deleting only its temporary generated source
   fixture; repository remains complete.
6. Shared blobs survive archive/tombstone/purge of one referencing run.

### Lifecycle and regression tests

1. Imported files cannot execute, invoke a model/capability/SQL statement, or
   create a portfolio effect.
2. Published/evidence-locked/referenced records deny ordinary deletion.
3. Tombstone, restore within seven days, expired-deadline final-purge preview,
   and reference denial are explicit and receipt-backed.
4. Existing Agent Run Review, Agent Studio, Dataset, Workflow Cycle, Registry,
   and Full Experiment smoke paths remain green.
5. Existing immediate legacy delete is never called by repository operations.

## Focused evidence executed

- `tests/application/test_labs_runtime.py`: **7 passed**.
- `tests/agents` plus `tests/capabilities`: **33 passed**.
- `tests/analytics/test_analytics.py` plus
  `tests/analytics/test_monitoring_policy_replay_reports.py`: **21 passed**.
- Synthetic temporary-directory behavior probe:
  - declared legacy files: 12;
  - manifest declared size: 1,716 bytes;
  - manifest actual size: 1,802 bytes;
  - undeclared file was ignored by current loader;
  - corrupt `activity.json` was returned as raw text rather than rejected.

These results establish current behavior and regressions only. They do not
validate a private run or approve the current legacy manifest as repository
evidence.

## Risks and integration priorities

1. **Licensed-data exposure is the highest migration risk.** Real input and
   multiple derived files can contain licensed/private facts; preview and
   download must be per-file policy decisions, not a run-wide UI toggle.
2. **Best-effort loading is incompatible with admission.** Silent omission and
   corrupt-JSON fallback must not be reused by the migration validator.
3. **Legacy manifest metadata is insufficient.** Requiring explicit rights and
   calculating digests is necessary; guessing revisions or approvals is not.
4. **Generated-agent/run conflation would create false authority.** Keep
   compiler artifacts, definitions, invocation configurations, and run outputs
   distinct.
5. **The source writer can leave partial state.** Repository publication must
   be a separate atomic transaction.
6. **Self-referential manifest sizing needs an adapter-specific rule.** A naïve
   exact-size check rejects every current run; ignoring all sizes weakens
   integrity.
7. **Runtime status is not governance.** Completed, auto-released, reviewed,
   published, archived, and evidence-locked are independent states.
8. **Legacy immediate delete remains dangerous.** It should be visibly scoped
   to temporary legacy runs and never reused after admission.

## Unresolved policy choices for integration

The following should be reconciled with P2-01/P2-03 rather than decided inside
the adapter:

- exact per-file and total admission-size limits (the current viewer uses 2 MB
  per file; retaining that as the legacy preview ceiling is the safest
  compatibility default);
- the named rights-policy registry and reviewer authority for licensed runs;
- whether restricted local downloads are ever allowed or only out-of-band
  inspection is permitted;
- whether the original legacy manifest is exposed as a downloadable artifact
  after its absolute `folder` field is identified as sensitive;
- the canonical repository contract used for the retained-run projection and
  how it references existing PortfolioRisk/ServiceFabric artifact types;
- whether legacy temporary deletion remains in the Agent page after the
  Artifact Repository is available.

None of these choices permits automatic publication, private-row display,
definition promotion, or financial effects.

## Rollback

This lane adds documentation only. Revert this single handoff commit.

For the future migration implementation, rollback means disabling the adapter
and its new projections while leaving legacy source folders untouched. An
admission transaction that fails before publish removes only its temporary
stage. Already admitted immutable blobs and receipts are governed repository
state; do not delete them merely because application code is rolled back.

## Recommended integration sequence

1. Reconcile P2-01's artifact/store contracts and P2-03's UI policy with this
   exact source format.
2. Implement discovery and preview first, including damaged candidates and
   rights blockers, with no write path.
3. Implement atomic content admission and idempotent receipts.
4. Add per-file preview/download policy and opaque locators.
5. Add archive/tombstone/restore/purge operations only after reference and
   integrity tests pass.
6. Preserve the legacy Agent Run Review as a source view until the repository
   path is verified; do not silently redirect or delete old folders.

