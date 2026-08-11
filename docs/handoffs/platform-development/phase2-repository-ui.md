# Phase 2 Artifact Repository UI and policy audit

- Status: complete read-only audit
- Lane: P2-03 — artifact repository UI and policy
- Branch: `feature/platform-p2-repository-ui`
- Programme baseline: `9440bbaeb3f43f04ff259dbde0eb2824b7f9c6f1`
- Audited head before this handoff: `89be56bb509e2e2f9a8cd1f81b3246dbf2ded87d`
- Implementation authority: none; this lane changes only this handoff

## Executive recommendation

Add one **Artifacts** workspace to the existing Labs shell. Its page heading is **Artifact Repository**. It is a compact three-level browser:

```text
Retained run
  └─ Generated artifact
       └─ Declared file
```

The first useful experience should let a user answer six questions without reading a raw manifest:

1. Which retained run produced this material?
2. What generated artifacts and declared files belong to it?
3. What data truth, rights, retention, publication, and provenance apply?
4. Was every retained byte verified against an immutable digest manifest?
5. May this file be previewed or downloaded safely?
6. What exactly happens if the record is archived, tombstoned, restored, or permanently finalized?

The workspace is not a directory browser, definition registry, experiment manager, or execution console. It never exposes an absolute host path and never runs a file, report, dashboard, agent, workflow, model call, query, script, or financial effect.

## Product boundary and mental model

Keep the accepted Definition Registry and the Artifact Repository visibly separate:

| Definition Registry | Artifact Repository |
|---|---|
| Indexes reusable definition metadata and source pointers. | Retains generated immutable bytes and complete file manifests. |
| Answers “What can be used?” | Answers “What did a retained run produce?” |
| Source definition remains authoritative. | Content digest and manifest identify retained bytes. |
| Lifecycle concerns candidate/validated/published definition state. | Lifecycle concerns integrity, retention, archive, tombstone, recovery, and byte finalization. |
| Does not store run files. | Does not become authoritative for agent, workflow, portfolio, dataset, or experiment meaning. |

Use this concise boundary notice below the page heading:

> Retained files are immutable, content-addressed local outputs. The repository records provenance and policy around them; it does not define or execute the agent, workflow, data, or experiment that produced them.

## Orthogonal states

Never compress these into a single `status` badge.

| Axis | Example values | Question answered |
|---|---|---|
| Data truth | Licensed local historical; public real; reviewed synthetic fixture; synthetic behavior sample; simulated; mixed; unavailable | What observations underpin this output? |
| Rights | Local research only; redistribution prohibited; internal reusable; public/redistributable; incomplete/blocked | Who may access or distribute the bytes? |
| Retention | Run-retained; experiment evidence; evidence-locked; policy unavailable | How long and under which policy must it remain? |
| Publication | Unpublished local; published locally | Has this generated artifact been locally published under repository policy? This is not product deployment. |
| Integrity | Not currently verified; verifying; verified at a stated time; failed; verification unavailable; bytes removed | Do the current bytes exactly match the declared manifest? |
| Visibility | Active; archived | Is the record in the default browse view? Archive does not remove bytes. |
| Deletion | None; recoverable tombstone; recovery expired; finalized | Is the record in a governed deletion lifecycle? |
| References | No active references; referenced by N records; reference check unavailable | Can exclusive bytes become eligible for final removal? |
| Operation | Available; temporarily locked; stale review; failed | Is another repository operation in progress or did concurrency invalidate this review? |

Missing policy or rights metadata is `unavailable` and fails closed. It is never rendered as unrestricted access or a zero reference count.

## Navigation and route

Place the tab immediately after **Registry** and before **Simulated cycle**:

```text
Database · Portfolio · Agent · Agent graph · Registry · Artifacts · Simulated cycle · Full experiment
```

Exact route:

```text
?workspace=artifacts
```

The page root is `#lab-artifacts` with heading `#lab-artifacts-title`.

Requirements:

- Add `artifacts` to the existing route allowlist and server runtime truth views.
- Workspace clicks update browser history; back/forward restores the selected workspace.
- The active tab alone carries `aria-current="page"`; inactive tabs omit the attribute.
- The mobile navigation remains horizontally scrollable and scrolls the active tab into view without stealing focus.
- Opaque selections may optionally be deep-linked as `run`, `artifact`, and `file` query values. Ignore unknown or unauthorized IDs without disclosing existence.
- Do not place absolute paths, digests, rights-sensitive names, or signed download tokens in the URL.

## Runtime truth strip

Use the existing server-authoritative four-cell strip:

| Cell | Exact recommended value |
|---|---|
| Profile | `Development` |
| Data | `Retained generated outputs · data truth disclosed per record` |
| Authority | `Browse and govern local artifacts only · execution and external effects prohibited` |
| Persistence | `Content-addressed local repository · outside Git · not production publication` |

When the repository service is unavailable, the strip must not claim the repository is empty or verified.

## Exact page anatomy

```text
┌ Artifact Repository ─────────────────────────────────────────────────────────┐
│ Browse retained run outputs and verify every declared file.   [Ready]       │
│ [Immutable local-output boundary]                  [Refresh] [Review runs]   │
├ Summary ─────────────────────────────────────────────────────────────────────┤
│ 18 retained runs · 52 artifacts · 214 files · 2 need attention             │
├ Filters ─────────────────────────────────────────────────────────────────────┤
│ Search________________  View ▾  Integrity ▾  Retention ▾  Sort ▾  [Clear]   │
├ Runs ───────────────────┬ Artifacts ───────────────┬ Detail / files ─────────┤
│ Daily Risk Review       │ Risk review brief        │ risk-review.md           │
│ 15 Sep 2008             │ Verified · 8 files       │ [Rights] [Data truth]    │
│ Synthetic sample       │ Run-retained · 82 KB     │ [Preview] [Download]     │
│ 3 artifacts · Verified │                           │                          │
│                         │ Evidence bundle           │ Manifest / provenance    │
│                         │ Referenced · 6 files      │ File list                │
│                         │                           │ Receipts                  │
└─────────────────────────┴───────────────────────────┴──────────────────────────┘
```

Reuse the existing `.lab-heading`, `.lab-panel`, `.panel-heading`, `.truth-chip`, `.button`, `.field`, `.empty-state`, and Registry master-detail visual language. Do not add a frontend framework, remote assets, visual node canvas, folder-tree library, or raw host-filesystem browser.

### Heading

- Eyebrow: `Governed local outputs`
- H1: `Artifact Repository`
- Description: `Browse retained runs, verify immutable files, and review retention or deletion consequences.`
- Status pill: `Loading`, `Ready`, `Partial`, `Unavailable`
- Primary action: `Refresh repository`
- Conditional secondary action: `Review temporary runs` only when the retained-run migration adapter reports eligible candidates

### Summary

After a successful response show:

- `N retained runs`
- `N artifacts`
- human-readable retained byte total
- `N need attention`

`Need attention` includes failed/unavailable integrity, incomplete policy, unavailable references, expired-but-blocked tombstones, and failed operations. The API supplies the aggregate; JavaScript must not reconstruct policy severity.

## Browse controls

Use one concise filter toolbar.

| Control | ID | Options/behavior |
|---|---|---|
| Search | `#artifact-search` | Search safe display labels and opaque run/artifact IDs. Do not search file bytes or host paths. |
| View | `#artifact-view-filter` | `Active`, `Archived`, `Recovery`, `All records`. Default `Active`. `Recovery` includes recoverable, expired, blocked, and finalized tombstones. |
| Integrity | `#artifact-integrity-filter` | `All integrity states`, `Verified`, `Not currently verified`, `Needs attention`. Server owns mapping into `Needs attention`. |
| Retention | `#artifact-retention-filter` | `All retention`, then server-supported classes such as `Run-retained`, `Experiment evidence`, `Evidence-locked`. Publication remains separate. |
| Sort | `#artifact-sort` | `Newest run`, `Oldest run`, `Name A–Z`, `Largest retained size`, `Needs attention first`. Server owns deterministic ties. |
| Clear | `#artifact-clear-filters` | Restore defaults, reload results, and return focus to Search. |

Do not add kind, model, provider, portfolio, experiment, or date-range filters in the first increment. The run/artifact hierarchy already supplies context, and Phase 3 experiment concepts must not enter this workspace.

## Information hierarchy

### Level 1 — retained run

The run list is a vertical selectable list, newest first by default. Every card shows:

1. human-readable run label;
2. created/completed time;
3. producing agent or workflow name and immutable definition version/reference;
4. opaque run ID;
5. artifact and declared-file counts plus total retained size;
6. concise data-truth label;
7. aggregate integrity state with verification time;
8. archived/tombstoned/attention badge where relevant.

Do not show:

- the host folder path;
- raw input rows;
- provider credentials;
- model prompts or chain-of-thought;
- `real` without a qualified data-truth label;
- a generic `successful` badge as a substitute for integrity.

Aggregate integrity copy:

- `All artifacts verified · {time}` only when the server confirms the complete run manifest and every artifact/file;
- `Integrity attention · 1 of 3 artifacts failed` for a mixed aggregate;
- `Verification unavailable` when the check could not run;
- never infer a run is verified from its execution status.

### Level 2 — generated artifact

The middle list shows artifacts associated with the selected run. A content-addressed artifact may be referenced by more than one run; the card therefore says `Referenced by N records` rather than implying exclusive run ownership.

Always show:

1. display label and artifact category;
2. opaque artifact ID and shortened digest;
3. declared file count and total size;
4. integrity state and last verification time;
5. retention and publication labels;
6. active-reference count;
7. archived/tombstoned/locked/corrupt state where applicable.

The full digest belongs in detail with a `Copy digest` button. Do not recreate the earlier SHA-only UX problem by making the digest the main title.

If a retained run has zero declared artifacts, render `Run manifest incomplete` and an integrity failure. A valid retained run is never represented by an ordinary empty artifact list.

### Level 3 — artifact detail and declared files

The detail heading shows artifact label, category, opaque ID, digest, run association, and the most restrictive active warning. Then show four short sections.

#### Overview and policy

Display separate labelled facts:

- data truth and limitations;
- rights/access and redistribution boundary;
- retention class and policy reference;
- publication state;
- archive/deletion state;
- current references and whether reference checking succeeded;
- integrity result and timestamp;
- producing run and immutable producer definitions;
- creation/admission time;
- artifact size and file count.

Use a short rights banner before file access, for example:

> Licensed-derived output · local research use only · redistribution prohibited.

The exact label and permitted actions come from the server. The browser never infers download permission from the data-truth label.

#### Files

List manifest-declared files only. Each row contains:

- relative declared path;
- media type;
- byte size;
- shortened content digest;
- current per-file integrity result;
- `Preview` and `Download` actions only when expressly allowed.

The UI never accepts a typed path and never sends an absolute path. An undeclared, added, missing, changed, or symlinked file is an integrity failure, not a browsable file.

Selecting a file opens a bounded preview below the list and updates a breadcrumb:

```text
Runs / Daily Risk Review / Risk review brief / risk-review.md
```

Breadcrumb segments are buttons that return to the corresponding pane; they do not expose filesystem directories.

#### Provenance and references

Show:

- canonical `ArtifactReference` identity/digest/media/reference projection;
- producing run ID;
- producing agent/workflow/model/capability revisions when supplied;
- source artifact/evidence references;
- data-context snapshot references without embedded licensed rows;
- admission receipt and adapter revision;
- active inbound references grouped by owning record type;
- supersession or derivation links.

Each reference has a safe label, opaque identifier, type, and active/inactive state. If the owning record is browsable, open its existing workspace; otherwise show read-only metadata. The repository cannot remove a reference on behalf of its owner.

#### Receipts and developer details

Show append-only receipts for:

- admission/retention;
- verification;
- archive/restore;
- tombstone/restore;
- finalization attempt/outcome;
- blocked/failed operations.

Each receipt shows actor type/ID from the server, timestamp, operation, result, rationale, prior/resulting state, and receipt identifier. Do not call a receipt human approval unless its authoritative actor and contract say so.

Raw manifest JSON is permitted only inside a closed `Developer details` disclosure. It is not the primary view and must not contain absolute locators.

## Integrity verification

### Integrity states

Use exact readable labels:

- `Not currently verified`
- `Verifying…`
- `Verified · {absolute time}`
- `Integrity failed · {N} problem(s)`
- `Verification unavailable`
- `Bytes permanently removed`

`Verified` is timestamped; it is never a timeless property. A service error is `Verification unavailable`, not `Corrupt`. Use `Integrity failed`/`Corrupt` only after a completed check finds missing, unexpected, changed, size-mismatched, manifest-mismatched, or unsafe content.

### Verify interaction

`Verify all files` is available for a selected retained artifact or run. It:

1. requests server-side verification against the immutable complete manifest;
2. marks only the verification region `aria-busy`;
3. keeps prior results visible as `Previous verification`;
4. updates state only from the returned receipt and refreshed record;
5. lists missing, unexpected, changed, and manifest errors by declared safe relative path;
6. never offers to repair, replace, or delete a corrupt file.

Exact success copy:

> Verified all {N} declared files. No missing, unexpected, changed, or undeclared bytes were found.

Exact failure copy:

> Integrity failed. Content access and ordinary deletion are blocked. Review the verification receipt; this interface will not repair or hide the discrepancy.

If a verification request conflicts with another operation:

> Repository record changed while verification was running. Refresh before acting on this result.

## Safe file preview

Preview is a convenience view, not execution.

First-increment allowlist:

- UTF-8 plain text, Markdown, JSON, CSV, and source text rendered as escaped text;
- PNG, JPEG, or WebP images only when the server confirms type, digest, and size;
- all other media receive metadata-only detail and a download decision.

Do not render Markdown as HTML in Phase 2. Do not inline SVG. Do not execute HTML, JavaScript, D3, notebooks, PDFs with active behavior, archives, binaries, or model files. HTML may be shown only as escaped source text within the text preview bound; an interactive dashboard preview remains outside this repository increment.

Recommended default preview bounds, finalized by the API contract:

- maximum 256 KiB returned preview bytes;
- maximum 5,000 displayed text lines;
- maximum 5 MiB for allowlisted raster images;
- explicit `Preview truncated` label with shown/total bytes;
- no client request can raise the server maximum.

Before returning bytes, the server rechecks that the file is declared, remains path-contained and symlink-safe, and matches its digest/size. If that check fails, deny the preview and update integrity state.

Preview error copy:

- `Preview unavailable for this media type or size.`
- `Preview blocked by the artifact rights policy.`
- `Preview blocked because integrity verification failed.`
- `Restore this tombstoned record before accessing retained bytes.`

Never use an unsandboxed same-origin iframe for repository content.

## Safe download

The primary action is `Download declared file`, never `Open`, `Run`, or `Download folder`.

Requirements:

- Resolve only opaque artifact ID plus declared file identity; reject typed paths and traversal.
- Revalidate the selected file digest and size immediately before streaming.
- Enforce the server-provided rights decision; incomplete rights fail closed.
- Deny download for corrupt, finalized, or tombstoned records and when an operation lock makes state uncertain.
- Use attachment disposition with a sanitized filename and `X-Content-Type-Options: nosniff`.
- Return expected content digest, media type, and size as safe response metadata.
- Never expose the storage root, absolute locator, redirect to `file://`, or create an unbounded archive.
- Do not offer whole-run ZIP download in the first increment.

Before a rights-restricted download, show a small confirmation:

> This file is restricted to local research use. Downloading does not grant redistribution rights.

Confirmation is not an approval receipt and does not weaken policy.

## Archive and archive restore

Archive is a visibility change, not deletion or byte mutation.

### Archive

`Archive record` appears only when the server marks the selected run or artifact eligible. The confirmation names the exact target and scope:

> Archive this artifact? It will move out of the Active view. Its immutable bytes, manifest, references, integrity history, and receipts remain unchanged.

Buttons: `Cancel` and `Archive artifact` (or `Archive run`). Require a short rationale if the accepted contract requires one. Do not imply that archiving one run archives a shared artifact; the server consequence preview must state the exact associations affected.

### Restore archived record

In the Archived view, use `Restore to Active`:

> Restore this archived record to the Active view? No bytes, references, retention, publication, or integrity state will change.

Archive and restore update only after a confirmed server receipt. Published or evidence-locked records may still be archivable if policy allows; archive never makes them deletion-eligible.

## Governed deletion lifecycle

Use four visibly separate actions. No step is optimistic.

```text
Preview deletion consequences      read-only
        ↓ eligible + explicit confirmation
Create recoverable tombstone       bytes remain; 7-day server deadline
        ├─ Restore during window    active/previous state restored by receipt
        └─ After deadline
             ↓ no active refs + integrity/policy eligible + confirmation
          Permanently remove bytes tombstone and receipts remain
```

The server clock is authoritative for every deadline. Browser countdowns are display-only.

### 1. Preview deletion consequences

The action is `Preview deletion`, not `Delete`.

The server returns a review plan containing:

- target type, safe label, opaque identity, revision, and digest;
- affected run associations and artifact records;
- declared file and byte counts;
- shared content that will remain because other references exist;
- current references and reference-check completeness;
- rights, retention, publication, evidence lock, archive, deletion, and integrity states;
- eligibility and every blocking reason;
- proposed seven-day recovery deadline;
- metadata/receipts preserved after finalization;
- exact non-effects: no definition, dataset, portfolio, workflow, or external effect changes.

Opening the preview performs no write and creates no tombstone. If the selected record revision changes, invalidate the plan.

### 2. Create recoverable tombstone

For an eligible plan, open a native dialog with:

- the consequence summary above;
- actor/reviewer identifier required by the accepted contract;
- required rationale;
- checkbox: `I understand that this hides the record and starts a seven-day recovery window. No bytes are removed today.`;
- `Cancel` and `Create recoverable tombstone`.

Exact boundary copy:

> This is a local repository metadata action. It does not delete canonical definitions or source data, and it creates no financial or external effect.

After confirmation, refresh from the server and show the tombstone receipt plus an absolute deadline in UTC and the user's local timezone. Do not say `Deleted`.

### 3. Restore during recovery

The Recovery view shows:

- `Recoverable until {absolute deadline}`;
- whole-day/hour countdown as secondary display;
- tombstone actor, rationale, and receipt;
- affected associations and bytes still retained;
- `Restore from recovery`.

Restore dialog copy:

> Restore this record before the recovery deadline? Repository visibility will return to its recorded prior state. Immutable bytes are unchanged.

Require actor/rationale if the contract requires them. A successful restore appends a receipt; it never deletes the tombstone history.

After the deadline, the restore action is absent and copy says:

> Recovery window expired. Bytes have not been removed automatically. Review finalization eligibility.

### 4. Finalize permanent byte removal

There is no cleanup daemon. After the deadline, show `Preview permanent removal` only when a fresh server review can be requested.

Finalization preview must recheck:

- recovery deadline passed;
- no active reference remains;
- publication/evidence lock still permits the operation;
- integrity and operation state are safe;
- target revision/tombstone receipt matches;
- shared content and exact removable bytes.

The final confirmation requires:

- actor and rationale;
- checkbox: `I understand that the eligible bytes cannot be recovered after this action.`;
- typed phrase `REMOVE BYTES`;
- `Cancel` and `Permanently remove eligible bytes`.

Exact consequence copy:

> Eligible content bytes will be permanently removed. The opaque identity, digest, tombstone, policy metadata, and operation receipts remain for audit. Canonical source definitions and active referenced content are not removed.

Only show success after the final receipt and refreshed record confirm `Bytes permanently removed`. If removal fails or its outcome is uncertain:

> Permanent removal was not confirmed. Do not assume bytes were removed. Review the failure receipt and verify repository state.

The UI provides no bypass, force delete, administrator override, or manual deadline edit.

## Deletion blockers and exact copy

Display every blocker returned by the server; never replace the list with a generic disabled button.

| Blocker | Heading | Supporting copy / permitted next step |
|---|---|---|
| Published | `Ordinary deletion blocked · Published locally` | `Published artifacts require a separate supersession or exceptional-retention policy. Archiving does not weaken this restriction.` |
| Evidence locked | `Deletion blocked · Evidence locked` | `This material is retained under {policy/reference}. Ordinary deletion and finalization are unavailable.` |
| Active references | `Deletion blocked · {N} active reference(s)` | `Resolve references in their owning records. The repository cannot remove them.` List safe references. |
| Reference check unavailable | `Deletion blocked · References unavailable` | `The repository cannot prove that the bytes are unreferenced. Retry the check; do not assume zero references.` |
| Integrity failed/corrupt | `Deletion blocked · Integrity failed` | `Deletion cannot hide missing, unexpected, or changed bytes. Review the verification receipt and follow a separate reconciliation process.` |
| Integrity unavailable | `Deletion blocked · Integrity unavailable` | `Verify repository state before reviewing deletion.` |
| Rights/retention unavailable | `Deletion blocked · Policy unavailable` | `Rights or retention metadata is incomplete. Complete governed metadata before continuing.` |
| Temporary operation lock | `Repository operation in progress` | `Another verified operation owns this record. Refresh after it completes.` |
| Stale preview | `Deletion plan expired` | `The record changed after review. Generate a new consequence preview.` |
| Already tombstoned | `Already in recovery` | Show deadline and Restore/Finalize eligibility; no second tombstone. |
| Deadline not reached | `Permanent removal not yet eligible` | `Recovery remains available until {deadline}.` |
| Deadline passed but newly referenced | `Finalization blocked · active reference found` | `Bytes remain tombstoned. Recovery has expired and no automatic removal will occur.` |
| Finalized | `Bytes permanently removed` | `Only tombstone, digest, policy metadata, and receipts remain. Recovery and content access are unavailable.` |

`Corrupt`, `Unavailable`, `Locked`, `Referenced`, and `Tombstoned` must be text labels, not color-only styling.

## Existing Agent Lab run admission

Phase 2 needs a visible route from temporary Agent Run Review folders to governed retention, but no folder is silently imported.

Recommended smallest flow, reconciled with P2-02:

1. `Review temporary runs` opens an admission drawer/dialog listing adapter-discovered candidates.
2. Candidate cards say `Temporary Agent Lab run · not retained` and show safe label, run ID, created time, data truth, declared current files, and migration warnings.
3. Selecting `Preview retention` performs validation without writing.
4. The preview shows resulting run/artifact/file manifests, rights/data truth, retention class, digests, excluded undeclared files, and all blockers.
5. Incomplete rights, data truth, immutable producer references, or digest coverage fails closed.
6. `Retain run` explicitly writes the governed repository record and content-addressed bytes after confirmation.
7. The temporary source folder is not automatically deleted.
8. The Agent page then offers `Open retained copy in Artifact Repository` and clearly distinguishes it from the temporary test folder.

Exact consequence copy:

> Retention creates immutable content-addressed artifacts and repository metadata outside Git. The temporary Agent Lab folder remains separate. No definition is published and nothing is executed.

Do not design batch silent admission, background watch/import, experiment association, or automatic source-folder cleanup in Phase 2.

The current Agent page's immediate `Delete run` applies to ungoverned temporary folders, not repository records. Integration must reconcile that behavior with P2-02 and must not present it as governed repository deletion. Once a retained copy exists, deleting the temporary folder must not affect the retained artifact and must say so explicitly.

## Loading, empty, recovery, and error states

| State | Heading | Concise copy | Action |
|---|---|---|---|
| Initial loading | `Loading Artifact Repository…` | `Reading retained run manifests and repository policy.` | None |
| Empty repository | `No retained runs yet` | `Review an eligible temporary Agent Lab run to create the first governed retained copy. Nothing is imported automatically.` | `Review temporary runs` if candidates exist |
| No filter matches | `No retained runs match these filters` | `Clear one or more filters. Repository records have not been removed.` | `Clear filters` |
| Service unavailable | `Artifact Repository unavailable` | `The local service did not respond. No integrity, archive, restore, or deletion result is assumed.` | `Retry` |
| Partial list | `Some records are unavailable` | `Available retained runs remain visible. Unavailable records are not counted as empty.` | `Review details`, `Retry` |
| Selected run incomplete | `Run manifest incomplete` | `This retained run does not declare a complete artifact/file set. Content actions are blocked.` | `Verify`, view receipt |
| Artifact corrupt | `Integrity failed` | `Current bytes do not match the immutable manifest. Preview, download, and ordinary deletion are blocked.` | `View verification receipt` |
| Rights locked | `Content access blocked` | `The current rights policy does not permit preview or download.` | View policy |
| Referenced | `Referenced by {N} records` | `References are retained and block permanent removal where policy requires.` | View references |
| Archived | `Archived` | `Hidden from Active; immutable bytes and receipts remain.` | `Restore to Active` if eligible |
| Recoverable tombstone | `In recovery` | `No bytes removed. Restore before {deadline}.` | `Restore from recovery` |
| Expired tombstone | `Recovery expired` | `No automatic cleanup occurred. Generate a fresh finalization preview.` | `Preview permanent removal` |
| Finalized | `Bytes permanently removed` | `Identity, digest, policy metadata, tombstone, and receipts remain.` | View receipts |
| Action failure | `{Operation} not confirmed` | `Refresh the record. Do not assume repository state changed.` | `Refresh record` |

Safe errors include a request/receipt ID where available. Never return a raw stack trace, storage root, absolute path, credential, or licensed record.

## Responsive behavior

### Wide: above 1280 px

- Filter toolbar in one row.
- Three-pane grid: `minmax(240px, .55fr) minmax(260px, .62fr) minmax(0, 1.3fr)`.
- Runs and artifacts may have independently bounded list scrolling, but the detail page should use normal document flow to avoid a third nested scroll trap.
- Keep the selected run/artifact visible when possible.

### Medium: 761–1280 px

- Filters wrap to two rows.
- Runs and artifacts become two columns across the top; detail spans the full row below.
- Policy facts become a two-column grid.
- File actions wrap without overlapping status badges.
- Do not abbreviate data truth, rights, or deletion state to icons.

### Narrow: 760 px and below

- Single order: heading → boundary → filters → run list → artifact list → detail → file preview.
- After selecting a run/artifact, scroll to the next heading and expose `Back to runs` / `Back to artifacts` controls.
- Dialogs use full available width and normal vertical scrolling.
- File rows stack path/metadata above actions.
- Digests and relative paths use `overflow-wrap:anywhere`; no page-level horizontal scroll.
- Recovery deadlines show absolute time above the countdown.
- A contextual selected-item action bar may be sticky only when it does not obscure content or dialog controls.
- The global truth strip remains visible in its existing two-by-two layout.

Do not hide integrity, rights, references, recovery deadline, or permanent-removal consequence on small screens.

## Accessibility

1. Page root: `<section id="lab-artifacts" aria-labelledby="lab-artifacts-title">`.
2. Lists have visible headings and semantic names: `Retained runs`, `Artifacts in {run}`, `Declared files in {artifact}`.
3. Use buttons for single selection, with `aria-pressed` or listbox semantics applied consistently; never nest file/action buttons inside another button.
4. Result-count and action-result regions are `aria-live="polite"`; do not make entire run, artifact, or file lists live.
5. Loading/verification regions use `aria-busy`; failed user-triggered operations focus a concise error summary.
6. Every integrity, rights, retention, reference, archive, and deletion state has text. Color is secondary.
7. Native dialogs trap focus, close on Escape where safe, and return focus to the opener. Initial focus is on the heading or Cancel for deletion/finalization, never the destructive confirm.
8. Consequence lists are programmatically associated with their confirmation checkbox and action.
9. Disabled actions have an adjacent visible reason and `aria-describedby`; do not rely on an unavailable tooltip.
10. General buttons, links, summaries, selectors, copy controls, breadcrumbs, and dialog controls need visible `:focus-visible`. The current Labs CSS still exposes only a specialized Agent-help focus rule; Phase 2 should add the generic rule without changing the visual language.
11. Preview regions have an accessible name, size/truncation announcement, and keyboard-scrollable content.
12. Copy-digest feedback is announced without replacing the digest text.
13. Critical policy copy must not use the existing 6–8 px microtype. Use the common body/label sizes and at least the existing 40 px interactive target.
14. Countdown changes should not announce every tick. Announce state changes such as `24 hours remaining`, `Recovery expired`, or changed eligibility once.

## Stable selectors

Use semantic roles and labels first. Add stable `data-testid` values; dynamic identities belong in escaped `data-run-id`, `data-artifact-id`, or `data-file-id` attributes.

| Purpose | Stable selector |
|---|---|
| Workspace tab/root/status | `artifact-repository-tab`, `artifact-repository-workspace`, `artifact-repository-status` |
| Boundary/summary | `artifact-repository-boundary`, `artifact-repository-summary` |
| Refresh/admission | `artifact-repository-refresh`, `artifact-admission-open` |
| Search/view/integrity/retention/sort | `artifact-search`, `artifact-view-filter`, `artifact-integrity-filter`, `artifact-retention-filter`, `artifact-sort` |
| Clear filters | `artifact-clear-filters` |
| Run list/item | `artifact-run-list`, `artifact-run-item` + `data-run-id` |
| Artifact list/item | `artifact-list`, `artifact-item` + `data-artifact-id` |
| Breadcrumb/detail | `artifact-breadcrumb`, `artifact-detail` |
| Data truth/rights/retention/publication | `artifact-data-truth`, `artifact-rights`, `artifact-retention`, `artifact-publication` |
| Integrity/references | `artifact-integrity`, `artifact-references` |
| Verify | `artifact-verify` |
| File list/item | `artifact-file-list`, `artifact-file-item` + `data-file-id` |
| Preview/download | `artifact-file-preview`, `artifact-file-download` |
| Archive dialog/confirm | `artifact-archive-dialog`, `artifact-archive-confirm` |
| Archive restore dialog/confirm | `artifact-unarchive-dialog`, `artifact-unarchive-confirm` |
| Deletion preview | `artifact-delete-preview` |
| Tombstone dialog/actor/reason/ack/confirm | `artifact-tombstone-dialog`, `artifact-tombstone-actor`, `artifact-tombstone-reason`, `artifact-tombstone-ack`, `artifact-tombstone-confirm` |
| Recovery deadline | `artifact-recovery-deadline` |
| Tombstone restore dialog/confirm | `artifact-recovery-dialog`, `artifact-recovery-confirm` |
| Finalization preview | `artifact-finalize-preview` |
| Finalization dialog/phrase/confirm | `artifact-finalize-dialog`, `artifact-finalize-phrase`, `artifact-finalize-confirm` |
| Receipts | `artifact-receipts` |
| Empty/error/attention | `artifact-empty`, `artifact-error`, `artifact-attention` |
| Admission dialog/preview/confirm | `artifact-admission-dialog`, `artifact-admission-preview`, `artifact-admission-confirm` |

Exact IDs may mirror these values with hyphens. Tests should not select items by visible digest abbreviations or generated CSS class names.

## Minimum UI-facing service behavior

The browser consumes integration-owned view models and operation previews. It does not compute policy, deadlines, digest identities, reference eligibility, safe paths, or allowed transitions.

### Browse response must provide

- opaque run/artifact/file identities;
- safe display labels;
- run-to-artifact and artifact-to-file associations;
- immutable digests, media types, sizes, and manifest identity;
- data truth, rights, retention, publication, visibility, deletion, integrity, reference, and operation states as separate fields;
- last verification time and summary;
- allowed actions plus blocked reasons;
- concurrency revision/ETag;
- safe aggregate counts.

### Detail response must add

- complete declared-file metadata, never undeclared files;
- provenance and canonical artifact-reference projection;
- safe inbound references;
- policy references and limitations;
- append-only receipts;
- opaque preview/download references rather than paths.

### Mutation pattern

Every state change uses:

1. read-only server consequence preview;
2. current revision/ETag and preview token bound to exact intent;
3. explicit actor/rationale/confirmation as contracted;
4. atomic server operation;
5. append-only receipt;
6. refreshed record before UI success.

Illustrative interaction groups, reconciled with P2-01/P2-02 rather than treated as fixed routes:

```text
GET  browse/detail/receipts
POST verify
GET  bounded file preview
GET  declared-file download
POST archive preview + archive
POST unarchive preview + restore
POST deletion preview + tombstone
POST tombstone-restore preview + restore
POST finalization preview + finalize
GET  admission candidates
POST admission preview + retain
```

No endpoint accepts a host path, executes content, changes a canonical definition, or performs external publication/effects.

## Application and contract tests

Recommended focused files are `tests/artifacts/**`, `tests/application/test_artifact_repository_api.py`, and the existing Labs runtime/regression suites.

### Storage/integrity

1. Complete manifests cover every retained file with deterministic unique relative paths, digests, sizes, and media types.
2. Added, missing, changed, size-mismatched, undeclared, path-traversing, absolute, and symlinked files fail verification.
3. Artifact identity/manifest digest mismatch fails closed.
4. Repeated identical content converges to one content-addressed object without changing immutable bytes.
5. Shared content reports all active references and is not removed with one run association.
6. Atomic/concurrent writes either commit one valid object or fail with recoverable evidence; no partial object appears in browse.
7. Persistence survives service restart and no mutable bytes appear in Git.
8. API responses never expose absolute host paths or private runtime roots.

### Browse/detail/policy

1. Browse preserves run → artifact → declared-file hierarchy and stable opaque identities.
2. Data truth, rights, retention, publication, integrity, archive/deletion, references, and operation states remain independent.
3. Missing rights/data truth/reference policy renders unavailable and blocks dependent actions.
4. Synthetic, simulated, mixed, and licensed-derived content keeps exact qualified labels.
5. Empty, unavailable, and failed states are not reported as zero records.
6. Receipts retain actor, operation, result, rationale, prior/resulting state, timestamp, and identity.

### Preview/download

1. Preview accepts only a declared opaque file reference and allowlisted media/size.
2. Text/Markdown/JSON/CSV/HTML content is escaped and cannot execute markup or script.
3. SVG, active HTML, notebooks, archives, executables, and oversized files are not rendered.
4. Image preview is limited to verified allowlisted raster media and size.
5. Preview is capped server-side; client limits cannot enlarge it; truncation is explicit.
6. Digest/size is rechecked before preview/download; mismatch updates integrity and blocks bytes.
7. Rights-restricted or incomplete-rights content is denied as policy dictates.
8. Download uses attachment disposition, sanitized name, `nosniff`, exact length/digest, and no host redirect.
9. Traversal, encoded traversal, undeclared path, symlink, stale opaque token, and cross-artifact file ID are rejected without existence leakage.

### Archive and restore

1. Archive preview is read-only and exact-target/revision bound.
2. Archive changes visibility only and appends a receipt; bytes, references, publication, retention, and integrity do not change.
3. Restore to Active returns the recorded visibility and appends a receipt.
4. Archiving does not weaken publication/evidence/reference deletion blocks.
5. Stale/concurrent operations fail without optimistic UI state.

### Tombstone, recovery, and finalization

1. Deletion preview performs no mutation and enumerates every consequence/blocker.
2. Published, evidence-locked, reference-unknown, actively referenced exclusive content, corrupt, integrity-unavailable, or policy-incomplete material denies ordinary deletion.
3. Eligible confirmation creates a tombstone and seven-day server-time recovery deadline but leaves bytes intact.
4. Tombstoned bytes disappear from Active, remain metadata-visible in Recovery, and deny normal content access.
5. Restore succeeds inside the window, appends a receipt, and preserves tombstone history.
6. Restore at/after the deadline is denied deterministically using an injectable clock.
7. No background daemon finalizes expired tombstones.
8. Finalization before the deadline is denied.
9. Finalization after the deadline rechecks references/policy/integrity/revision; any new blocker leaves bytes intact.
10. Eligible finalization removes only unreferenced content bytes and preserves opaque identity, digest, tombstone, policy metadata, and receipts.
11. Shared content survives when any active reference remains.
12. A crash/failure/uncertain outcome never reports success; restart recovery yields an inspectable failed/pending receipt and verifiable state.
13. Repeated tombstone, restore, and finalize requests are idempotent or conflict safely under the accepted contract.

### Admission

1. Candidate discovery does not retain or copy a temporary run.
2. Admission preview performs no write and lists incomplete metadata/undeclared files.
3. Missing rights, data truth, producer revision, or complete digest coverage blocks admission.
4. Successful explicit retention creates complete immutable manifests/receipts and leaves the temporary source unchanged.
5. Retaining the same exact run/content is idempotent; changed content conflicts or creates the contract-approved immutable identity rather than overwriting.
6. Licensed rows, private paths, credentials, and undeclared files are not exposed in API/UI metadata.

## Browser tests

Run against the real localhost application with a temporary repository root and reviewed synthetic fixtures only.

1. Open `?workspace=artifacts`; assert the Artifacts tab, four truth cells, boundary notice, and empty state.
2. Admit one synthetic temporary run through preview and confirmation; assert run → artifact → file navigation and no source-folder path.
3. Traverse all panes by keyboard; verify focus, accessible names, selected states, breadcrumb, and Back controls.
4. Preview escaped Markdown/HTML source and an allowlisted image; prove scripts/markup do not execute and bounds are stated.
5. Download one declared file; assert safe filename and displayed rights notice.
6. Trigger verification success, then use an isolated tamper fixture to render `Integrity failed`, declared diagnostics, and blocked content/deletion actions.
7. Archive and restore; assert Active/Archived filtering, receipts, and unchanged integrity/reference facts.
8. Exercise a published, evidence-locked, referenced, reference-unavailable, and corrupt fixture; assert exact blocker copy and no confirm button.
9. Tombstone an eligible artifact; assert no byte-removal claim, dual-timezone deadline, Recovery view, and blocked preview/download.
10. Restore inside the window; assert receipt and prior state.
11. With a controlled clock, expire a second tombstone; assert no automatic removal, no restore, and finalization preview.
12. Add an active reference before finalization; assert fresh preview blocks removal and bytes remain.
13. Finalize an eligible unreferenced fixture after the deadline using the phrase control; assert bytes removed, metadata/receipts retained, and recovery unavailable.
14. Repeat critical flows at 760 px and a medium width; assert no overlap or page-level horizontal scroll.
15. Simulate service failure during verify/tombstone/finalize; assert the UI says outcome not confirmed and does not optimistically change state.

The repository browser test must not use licensed data, network providers, model calls, external URLs, or financial effects.

## Regression and verification

Run at minimum:

```bash
python3 -m pytest tests/architecture/test_platform_phase2_control_plane.py -q
python3 -m pytest tests/artifacts -q
python3 -m pytest tests/application/test_artifact_repository_api.py -q
python3 -m pytest tests/application/test_registry_api.py -q
python3 -m pytest tests/application/test_labs_runtime.py -q
python3 -m pytest tests/application/test_workbench.py -q
make verify-platform-phase2
```

The change must regress the Definition Registry, Agent Run Review, Database, Portfolio, Agent graph, Simulated cycle, and Full experiment. In particular, Registry must remain definition-only and Agent Run Review must distinguish temporary folders from retained repository artifacts.

## Risks and mitigations

| Risk | Consequence | Required mitigation |
|---|---|---|
| Repository becomes a host folder browser | Path traversal, private path leakage, undeclared files | Opaque IDs, manifest-declared files only, no typed paths or absolute locators. |
| Artifact appears authoritative for agent/workflow meaning | Duplicated contracts and false provenance | Show immutable producer references; repository projection surrounds bytes only. |
| `Published` implies product deployment | User misreads local state | Always render `Published locally · not production deployment`. |
| Execution success is confused with integrity | Corrupt run appears trustworthy | Separate run outcome from current digest verification. |
| Digest dominates the UX | Repeats SHA-only object problem | Human label/purpose first; full digest in detail with copy. |
| Preview executes active content | XSS, local data exfiltration, false dashboard behavior | Escaped text, allowlisted raster only, no SVG/active HTML/iframe execution. |
| Download bypasses rights | Licensed/private redistribution | Server-owned permission, explicit rights notice, attachment/no-sniff, fail closed. |
| Archive is mistaken for deletion | User assumes bytes removed | Exact archive copy; bytes, references, receipts remain. |
| Tombstone is called deleted | User assumes irreversibility or byte removal | `Recoverable tombstone`, absolute deadline, `No bytes removed` copy. |
| Browser clock controls eligibility | Early/late finalization | Server clock/deadline authoritative; countdown display only. |
| New reference appears after preview | Referenced bytes removed | Finalization rechecks reference set and exact revision atomically. |
| Corrupt material can be deleted | Integrity failure is hidden | Ordinary deletion/finalization blocked; separate reconciliation outside UI. |
| Partial/uncertain deletion claims success | Evidence loss | No optimistic state; receipt + refreshed record + verification required. |
| Shared artifact treated as run-owned | Deleting one run removes other evidence | Consequence plan enumerates associations and shared content; active refs block bytes. |
| Recovery window implies automatic cleanup | Bytes disappear unexpectedly | State explicitly says no daemon; finalization requires a later human action. |
| Temporary run auto-imports | Unreviewed/licensed/incomplete material becomes retained | Explicit candidate preview, fail-closed metadata, separate confirm. |
| Phase 3 concepts leak in | Repository becomes experiment manager | No ExperimentDefinition, scheduling, queue, portfolio action, or multi-run apparatus. |
| Mobile nested panes become unusable | Rights/deletion context is missed | Ordered single-column layout, Back controls, no hidden policy fields. |

## Evidence inspected

- `AGENTS.md`
- `docs/workplans/current.md`
- `docs/workplans/platform-development/phase-2-artifact-repository.md`
- `docs/workplans/platform-development/phase-2/TASK-03-REPOSITORY-UI.md`
- `config/agent/platform-development/phase2-lanes.json`
- `docs/handoffs/platform-development/phase0-storage-runtime.md`
- `docs/handoffs/platform-development/phase0-ui-policy.md`
- `docs/handoffs/platform-development/phase1-catalogue-ui.md`
- `docs/handoffs/platform-development/phase2-integration.md`
- `apps/portfolio-risk-workbench/labs/index.html`
- `apps/portfolio-risk-workbench/labs/labs.js`
- `apps/portfolio-risk-workbench/labs/styles.css`
- `apps/portfolio-risk-workbench/labs/duckdb_server.py`
- `apps/portfolio-risk-workbench/labs/agent_studio.py`
- `apps/portfolio-risk-workbench/labs/DEVELOPMENT_ROADMAP.md`, especially artifact storage and retention sections
- `packages/risk_domain/src/risk_domain/models.py` `ArtifactReference`
- `vendor/servicefabric/packages/servicefabric_artifacts/servicefabric_artifacts/store.py`
- `vendor/servicefabric/packages/servicefabric_contracts/src/servicefabric_contracts/applications.py` artifact manifest contracts
- `tests/application/test_labs_runtime.py`
- `tests/application/test_registry_api.py`
- `tests/application/test_workbench.py`
- `tests/architecture/test_platform_development_control_plane.py`
- `tests/architecture/test_platform_phase1_control_plane.py`
- `tests/architecture/test_platform_phase2_control_plane.py`

## Validation executed

- `make preflight` — repository and ServiceFabric pin checks passed; bootstrap dependency installation then failed because the sandbox could not resolve the Python package index.
- `python3 -m pytest tests/architecture/test_platform_phase2_control_plane.py -q` — PASS, 4 tests.
- `git diff --check` — PASS before candidate commit.
- Lane path review — PASS; this handoff is the only changed path.

## Deviations, blockers, and limitations

- This lane did not inspect user-owned run folders, licensed data, or a mutable repository root. Findings are based on source, contracts, and synthetic-test behavior, not the contents of a specific local repository.
- P2-01 and P2-02 run in parallel. Final field names, transition policy, admission semantics, action granularity, and API routes must be reconciled with their accepted handoffs before implementation. The browser must consume the server's final allowed actions rather than hard-code this audit's illustrative values.
- The current Labs stylesheet still lacks a general focus-visible rule and uses microtype as small as 6–8 px in Agent Run Review. This audit requires the Artifact Repository to avoid repeating those issues; it does not authorize a broad redesign.
- No existing browser-test framework was found in the repository. Integration should implement the browser scenarios with its approved local harness or preserve them as explicit independent-QA probes without adding remote runtime assets.
- Phase 2 does not decide exceptional deletion of published/evidence-locked material, corruption repair, artifact rendering/composition, experiment retention, or automatic cleanup. The UI exposes no bypass for these deferred policies.

## Rollback

This lane adds only `docs/handoffs/platform-development/phase2-repository-ui.md`. Rollback is deletion of that file. No application, repository, run, artifact, file, registry, test, or external state is affected.

## Recommended integration sequence

1. Reconcile P2-01 canonical storage/deletion semantics and P2-02 retained-run admission mapping with this UX before naming API fields.
2. Implement the immutable external store and strict run/artifact/file projections with opaque IDs and complete manifests.
3. Add read-only browse/detail/integrity/reference APIs and the Artifacts workspace shell, truth strip, hierarchy, and all empty/error states.
4. Add bounded preview/download with file-level digest/rights enforcement.
5. Add verify, archive, and archive-restore receipts.
6. Add read-only deletion preview, recoverable tombstone, recovery, and manual finalization in that order.
7. Add explicit temporary-run admission only after migration validation passes.
8. Add focused application/storage/browser tests and regress Agent Run Review plus Definition Registry.
9. Run `make verify-platform-phase2`, preserve browser evidence, and submit one exact candidate to independent adversarial QA.

The smallest implementation should make retained work easy to review while making every destructive consequence harder to misunderstand than to understand.
