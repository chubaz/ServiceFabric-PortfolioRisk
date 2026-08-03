# Phase 1 independent QA

- Task: P1-05
- Current review: R11
- Reviewed bookkeeping commit: `ff28b251b46154bb323d5acb12512990ee1cfe47`
- Accepted implementation candidate: `a68ef6fce9d39f5341fa8675c093db2eba95aed6`
- Review branch: `review/platform-p1-independent-qa-r11`
- Accepted Phase 0 baseline: `21339db19357277ca9a9a1ca50107f1a884d7aeb`
- Pinned ServiceFabric gitlink: `7632b61d94a966346f95eb6c5bb2a5ea27f3bc14`
- Current verdict: **PASS — ACCEPT BOOKKEEPING**
- Repair authority: integration only

## R5 executive result — preserved

R5 passes every declared automated gate and closes the three narrower R4
concerns that this review was explicitly asked to reproduce. Event filename
gaps now fail closed, a recomputed receipt is rejected by its immutable anchor,
event-plus-anchor replacement is rejected by the committed catalogue head, and
an injected second-item bootstrap failure leaves neither item list-visible nor
API-indexed before a successful retry.

The source catalogue remains truthful and bounded: all 44 existing definitions
across the seven required kinds are visible, projections contain none of the
tested kind-specific definition fields, summaries disclose no shocks or model
call counts, exact R5 repository and adapter provenance is present, all 36
declared relationships resolve to exact registry revisions, and no absolute
registry path is returned by the API.

Two independent persistence failures nevertheless remain release-blocking:

1. the immutable source projection is not bound to a digest anchor, lifecycle
   receipt, or committed catalogue entry, so a valid same-identity replacement
   projection is accepted when the derived aggregate snapshot is absent; and
2. a failure while committing the catalogue head after a lifecycle event has
   become durable leaves the existing asset unreadable and the transition
   impossible to retry.

These violate the Phase 1 gates for immutable source observations, append-only
and replayable lifecycle evidence, atomic/recoverable local persistence, and
restart safety. Candidate `b483e4e` must not be accepted.

## Preserved independent-review history

The first independent review remains authoritative for its exact candidate:

| Review | Exact candidate | Verdict | Findings |
|---|---|---|---|
| Initial P1-05 | `e8fde6b28aa3e3851e1975d64175da2b7b75dcce` | **BLOCKED** | Symlinked-parent escape; mutable unchained lifecycle files; copied definition payloads; incomplete exact provenance/relationships; unrelated comparison accepted; partial bootstrap and missing UI consequence/concurrency controls. |
| R5 | `b483e4ea37170b3bff4b67f6a0436e5ad4a1c326` | **BLOCKED** | Earlier six areas are materially repaired, but projection integrity and interrupted-transition recovery remain unsafe as detailed below. |

The original 368-line handoff was read from the preserved QA worktree at
`worktrees/platform-development/phase1-independent-qa/docs/handoffs/platform-development/phase1-independent-qa.md`.
This combined handoff does not reinterpret the first verdict or accept any
superseded candidate.

## Review scope

The review read and applied:

- `AGENTS.md`, `docs/workplans/current.md`, the complete Phase 1 workplan, lane
  manifest, and `TASK-05-INDEPENDENT-QA.md`;
- all eight accepted architecture decisions;
- all three Phase 1 specialist audit handoffs and the current integration
  handoff;
- the preserved first BLOCKED independent-QA handoff;
- the complete baseline-to-R5 change list and the focused R4-to-R5 repair diff;
- registry contracts and persistence, all source adapters, API routes,
  Registry HTML/JavaScript/CSS, package manifest, control-plane state, focused
  tests, application regressions, and architecture regressions; and
- the read-only pinned ServiceFabric checkout at the exact gitlink above.

No implementation, canonical definition, test, workplan, application, runtime
state, generated artifact, licensed data, or external effect was changed by
this lane.

## Blocking findings

### R5-B1 — source projection replacement is not integrity-anchored

**Code evidence**

`packages/risk_registry/src/risk_registry/store.py:250-255` commits only the
hashed filesystem key and lifecycle head receipt digest. The catalogue entry
does not retain a projection/record digest. `_reconstruct()` at lines 257-293
validates the projection's identity and the receipt anchors, but no receipt or
anchor contains the source definition digest, adapter digest, or a digest of
the complete projection. `get()` at lines 450-470 compares the reconstructed
document with the aggregate snapshot only when that snapshot exists.

This is also visible in the contract: `LifecycleReceipt` at
`packages/risk_registry/src/risk_registry/models.py:170-239` binds only the
registry reference and lifecycle intent. It does not bind the exact projection
or source/adapter digests.

**Independent reproduction**

Using R5 modules and the reviewed Python environment:

```python
store.index(projection, actor="qa")
store.transition(
    projection.identity,
    LifecycleState.VALIDATED,
    actor="qa",
    rationale="Original validation receipt.",
)

changed = projection.model_copy(
    update={
        "summary": "Unauthorized replacement source projection.",
        "source": projection.source.model_copy(
            update={"definition_digest": "f" * 64}
        ),
    }
)
projection_path = store._projection_path(projection.identity)
projection_path.chmod(0o600)
projection_path.write_text(changed.model_dump_json())
store._path(projection.identity).unlink()  # derived snapshot may be absent
loaded = LocalRegistryStore(store.root).get(projection.identity)
```

Observed result:

```text
projection_replacement_snapshot_absent ACCEPTED
Unauthorized replacement source projection.
ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
```

Deleting the aggregate snapshot is a supported recovery case, not deletion of
the authority. A fresh store therefore accepts a changed source observation
without changing any receipt, anchor, or committed catalogue head. This is a
strictly easier replacement than the recomputed-receipt attack R5 now rejects.

**Required repair outcome**

Bind the complete canonical projection digest, exact source definition digest,
and adapter digest to the initial receipt and committed catalogue entry. Verify
that binding before reconstruction can return a document, whether or not the
derived snapshot exists. Add projection-byte tamper, valid projection
replacement, changed source digest, missing snapshot, and restart tests.

### R5-B2 — interrupted lifecycle catalogue commit cannot recover or retry

**Code evidence**

`LocalRegistryStore.transition()` writes the immutable lifecycle event, writes
its anchor, replaces the aggregate snapshot, and only then commits the new
catalogue head at `store.py:570-578`. If the catalogue write fails after those
durable writes, the catalogue points to the prior head while reconstruction
finds the new head. `get()` rejects the mismatch, but there is no recovery or
idempotent retry path.

**Independent reproduction**

```python
first = store.index(projection, actor="qa")
store._write_catalog = lambda entries: (_ for _ in ()).throw(
    OSError("injected catalog commit failure")
)
store.transition(
    projection.identity,
    LifecycleState.VALIDATED,
    actor="qa",
    rationale="Transition interrupted after durable event.",
    expected_revision=first.receipts[-1].receipt_digest,
)
```

Observed after constructing a fresh store and then retrying:

```text
transition_injected_failure=RAISED OSError injected catalog commit failure
restart_after_transition_failure=BLOCKED RegistryConflict
registry lifecycle head does not match its catalogue anchor
transition_retry=BLOCKED RegistryConflict
registry lifecycle head does not match its catalogue anchor
```

The event-first protocol is correct only if a post-event interruption can be
reconciled deterministically. Here one local failure permanently removes an
otherwise valid indexed asset from catalogue/detail use until an undeclared
manual filesystem edit occurs.

**Required repair outcome**

Define and test a recoverable commit protocol for lifecycle transitions. On
restart, a complete valid anchored tail must either atomically advance the
catalogue through a validated recovery receipt or remain an explicitly pending
transaction that the identical command can safely finish. No partial transition
may make the previously committed version unreadable. Inject failure before
and after event, anchor, snapshot, catalogue replacement, and directory sync.

## Required R4 regressions reproduced

### Event and anchor sequence

Renaming `000002.json` to `000003.json` now fails closed:

```text
filename_gap REJECTED RegistryConflict
registry lifecycle event filenames must form a contiguous sequence
```

### Recomputed receipt and coordinated anchor tampering

Replacing receipt two with a new internally valid recomputed receipt while the
aggregate snapshot is absent now produces:

```text
event_replacement_anchor_intact REJECTED RegistryConflict
registry lifecycle integrity anchor mismatch
```

Replacing both the receipt and its per-event anchor, while leaving the committed
catalogue head intact, produces:

```text
event_and_anchor_replaced_catalog_head_intact REJECTED RegistryConflict
registry lifecycle head does not match its catalogue anchor
```

For completeness, an operating-system owner who rewrites the receipt, anchor,
catalogue head, and the catalogue's unkeyed self-digest together can still make
the replacement validate. That is an explicit local trust-model limitation,
not a separate Phase 1 blocker here: the accepted local ServiceFabric pattern
does not require a signature, remote transparency log, or external hardware
anchor. It must not be described as protection from a malicious filesystem
owner.

### Multi-item bootstrap failure and retry

A fault was injected on the second `RegistryProjection` write in `index_many`.
The first item's uncommitted files existed, but the committed catalogue remained
empty and both list and API views were truthful:

```text
batch_injected_failure RAISED OSError injected second projection failure
batch_visible_after_failure 0
batch_item1_api_indexed_after_failure False
batch_retry PASS 2 []
```

This satisfies the requested all-or-none visibility and retry behavior for the
tested bootstrap interruption.

## Other adversarial results

### Path and symlink safety — PASS

Independent probes rejected all tested unsafe paths before an outside write:

```text
root ValueError registry path components may not be symbolic links
parent ValueError registry path components may not be symbolic links
lock OSError Too many levels of symbolic links
catalog ValueError registry catalogue may not be a symbolic link
event_dir ValueError registry events directory is not a safe contained path
anchor_dir ValueError registry anchors directory is not a safe contained path
event_file ValueError registry immutable paths may not be symbolic links
anchor_file ValueError registry immutable paths may not be symbolic links
```

### Projection boundary and source truth — PASS except R5-B1 integrity

The live discovery result contained exactly 44 items:

```text
agent 4 · capability 29 · evaluation 1 · report 3
dashboard 1 · scenario 3 · workflow 3
```

A recursive inspection found no copied grants, schemas, effects, shocks,
workflow topology, model-call counts, prompts, routing, state schemas, or tool
latches. Scenario and workflow summaries contained no shock values, roles, or
model-call counts. Adding the old nested `attributes.details.definition`
payload was rejected as an extra field.

### Provenance, compatibility, and relationships — PASS

```text
repository_commits = [b483e4ea37170b3bff4b67f6a0436e5ad4a1c326]
adapter_digest_exact = True
relationships = 36
all_resolved_exact = True
```

Every relationship target was an exact reference present among the 44 source
projections. Candidate-source kinds remain visibly non-canonical and cannot be
locally published.

### Comparison and lifecycle concurrency — PASS

- Same-identity version comparison remained available.
- Cross-kind/unrelated comparison raised `RegistryConflict`; the API returned
  HTTP 409.
- Candidate-to-published shortcuts remained invalid.
- A stale `expected_revision` lifecycle submission returned HTTP 409.
- Server-provided allowed transitions, user rationale, confirmation copy, and
  the expected revision are used by the Registry workspace.

### API and effect boundary — PASS

An in-process FastAPI client exercised the exact R5 application:

```text
page=200 catalogue=200 records=44
preview_no_write=True bootstrap=200 indexed=44
transition=200 validated
stale_transition=409 unrelated_compare=409
absolute_path_exposed=False registry_root_key=False
kind_specific_effect_fields=0
```

The Registry routes expose catalogue/discovery, preview, index, detail,
lifecycle, and comparison only. They introduce no run, deployment, provider,
model, broker, order, trade, hedge, rebalance, optimization, portfolio mutation,
or external publication effect.

## Automated verification

The focused gate ran with an isolated copy of the verified bootstrap environment
and the required Day 0/Thesis Python environment:

```bash
PIP_NO_INDEX=1 make verify-platform-phase1 \
  BOOTSTRAP_VENV=/private/tmp/platform-p1-r5-qa.3jNa0Q/venv \
  DAY0_VENV=/Users/lorenzocc/Developer/servicefabric-lab/state/venvs/thesis-sprint
```

Result: **PASS** — environment, repository, exact ServiceFabric pin, package,
diff, and `38 passed in 2.58s`.

Full regressions:

```bash
PIP_NO_INDEX=1 make test-application test-architecture \
  DAY0_VENV=/Users/lorenzocc/Developer/servicefabric-lab/state/venvs/thesis-sprint
```

Result: **PASS** — `104 passed in 17.42s` for application tests and
`105 passed in 1.56s` for architecture tests.

`git diff --check` passed before this handoff. The worktree was clean at exact
R5 HEAD before QA documentation, and `vendor/servicefabric` remained unchanged
at its accepted read-only pin.

## Browser limitation

The in-app browser runtime reported no available browser instance. The exact R5
server was then started with an isolated `/private/tmp` registry root and a
localhost-only port, but sandbox policy denied binding `127.0.0.1:8881` with
`operation not permitted`; the required escalation was rejected by the
workspace's never-approval policy. No workaround was attempted.

Therefore independent visual, console, responsive, focus, and keyboard browser
QA is not claimed. The exact static workspace, API, in-process ASGI behavior,
all application tests, and the integration handoff's prior live-browser result
were reviewed, but they do not replace an independent live R5 browser session.
This limitation is secondary to the two code blockers above.

## R5 acceptance decision, rollback, and next action — preserved

**Do not accept or merge candidate
`b483e4ea37170b3bff4b67f6a0436e5ad4a1c326`.** Keep PLATFORM-P1 in progress
and independent QA blocked. Integration should make one bounded persistence
repair for R5-B1 and R5-B2, add the exact fault/tamper regressions, then request
a fresh clean-worktree review of a new immutable SHA.

No code or authoritative runtime state needs to be rolled back by this QA lane.
The candidate branch and failed probe evidence can remain for diagnosis.
Temporary registries and the isolated bootstrap environment under
`/private/tmp` are non-authoritative and disposable; the accepted Phase 0
baseline and all canonical source definitions remain unchanged.

## R6 independent review

- Exact candidate: `e9eab8dd704d4c04d90fff269118a4af21072db9`
- Review worktree: `phase1-independent-qa-r6`
- Verdict: **BLOCKED**
- R5 history above: preserved and unchanged in meaning

### R6 executive result

R6 successfully closes both exact R5 reproductions in their tested nominal
paths. The catalogue now anchors the complete serialized projection digest, so
a valid same-identity projection replacement is rejected by both `get()` and
`list()` even when the derived snapshot is absent. A complete anchored trailing
lifecycle receipt beyond the committed catalogue head remains hidden as a
pending transition; the last committed state stays readable, and an exact
transition retry adopts the tail without creating a duplicate receipt. A retry
after a catalogue replacement whose caller observed an error is also
idempotent.

The declared gates and all earlier source, path, UI, API, comparison,
provenance, non-duplication, and effect-boundary probes pass. Independent fault
injection at additional required write boundaries nevertheless found two new
release blockers:

1. interruption after the event file becomes durable but before its integrity
   anchor is installed makes the last committed asset unreadable and prevents
   an exact retry; and
2. after an interruption later in the same transition leaves one complete
   anchored trailing receipt, ordinary idempotent `index()` or `index_many()`
   silently commits that lifecycle receipt, bypassing the required exact
   transition retry and its actor/intent check.

The first defect also prevents retry of an interrupted multi-item bootstrap
when item two stops between its event and anchor writes. Candidate `e9eab8d`
therefore does not meet the Phase 1 atomicity, restart, idempotency, or governed
lifecycle gates.

### R6 scope and immutable baseline

The R6 review re-read the governing Phase 1 task and audits, current integration
handoff, complete preserved R5 handoff, R5-to-R6 repair diff, current store and
tests, source adapters, API and Registry workspace behavior. It verified:

```text
candidate HEAD       e9eab8dd704d4c04d90fff269118a4af21072db9
accepted Phase 0     21339db19357277ca9a9a1ca50107f1a884d7aeb
ServiceFabric gitlink 7632b61d94a966346f95eb6c5bb2a5ea27f3bc14
worktree branch      review/platform-p1-independent-qa-r6
pre-handoff status   clean
```

No implementation, test, source definition, control-plane record, dependency,
runtime data, financial effect, or vendor file was modified in this lane.

### R6-B1 — event-to-anchor interruption loses committed availability

`LocalRegistryStore.transition()` writes the next event at
`packages/risk_registry/src/risk_registry/store.py:648-651`, then writes its
separate anchor at lines `652-655`. `_reconstruct()` requires the number of
anchors to equal the number of events before `_committed_document()` can select
the older catalogue-committed prefix. Consequently, an interruption after the
event installation but before the anchor installation blocks `get()`, `list()`,
and the exact transition retry.

The independent probe wrapped `_write_immutable`, let receipt sequence two
complete its durable write, and then raised `OSError` before the anchor call.
The expected last committed state was candidate with one receipt. The actual
result was:

```text
after_event_before_anchor
  fresh get: GET_BLOCKED RegistryConflict
  registry lifecycle integrity anchor count does not match
  exact retry: unavailable because get could not establish committed state
```

Control probes at the other meaningful boundaries behaved correctly:

| Injected boundary | Fresh committed view | Exact retry | Receipt count |
|---|---|---|---:|
| Before event installation | `candidate` | converged to `validated` | 2 |
| **After event, before anchor** | **blocked** | **blocked** | unavailable |
| After anchor, before snapshot | `candidate` | converged to `validated` | 2 |
| After snapshot, before catalogue | `candidate` | converged to `validated` | 2 |
| After catalogue replacement | `validated` | idempotently returned `validated` | 2 |

The same boundary was injected during the second item of `index_many()`. The
committed catalogue remained empty, so atomic visibility was truthful, but the
batch could not be retried:

```text
batch_event_anchor_failure RAISED second event installed before anchor
batch_visible_after_event_anchor_failure 0
batch_retry_after_event_anchor_failure BLOCKED RegistryConflict
registry lifecycle integrity anchor count does not match
```

**Required repair outcome:** make event-plus-integrity evidence a recoverable
commit unit. A partial event/anchor pair after any file open, write, flush,
`fsync`, chmod, or directory sync failure must not hide the committed prefix.
An identical index or transition retry must deterministically complete or
discard only the uncommitted tail without accepting changed intent or creating
another receipt. Add boundary tests before and after both event and anchor
installation for single index, batch index, and every lifecycle transition.

### R6-B2 — indexing silently commits an interrupted lifecycle transition

After a transition fails before the catalogue update but after its event,
anchor, and derived snapshot are durable, `_committed_document()` correctly
returns only the prior committed prefix. However, `_index_locked()` at
`store.py:443-450` reads the complete reconstructed stream and returns it when
the source observation is unchanged. `index()` then passes that full document
to `_commit_catalog()` at lines `424-432`; `index_many()` does the equivalent.
Neither path proves or retries the pending transition intent.

The explicit R6 probe created exactly this pending validated receipt, confirmed
that the committed view was still candidate with one receipt, and then called
the otherwise idempotent source-index operation before retrying transition:

```text
index
  before=candidate 1
  operation_returned=validated 2
  after=validated 2
  head_advanced=True

index_many
  before=candidate 1
  operation_returned=validated 2
  after=validated 2
  head_advanced=True
```

Thus a bootstrap actor can complete a reviewer-authored lifecycle transition
without presenting the exact transition command, actor, rationale, target,
expected revision, or retry intent. This breaches separation between source
indexing and governed lifecycle mutation even though the trailing receipt bytes
themselves are valid.

**Required repair outcome:** index and bootstrap may commit only an initial
candidate receipt for a previously uncommitted source identity. For an existing
catalogue entry they must compare against the catalogue-committed document, not
adopt any trailing lifecycle receipts. Only `transition()` with an exact matching
pending intent may advance the lifecycle head. Add direct `index()`,
`index_many()`, API bootstrap, changed actor, changed rationale, changed target,
and stale-revision tests while a pending tail exists.

### R5 blocker closure evidence

#### Exact projection anchoring — PASS

R6 catalogue entries contain `projection_digest`, calculated over the exact
serialized `RegistryProjection`. The R5 replacement procedure changed both the
source definition and compatibility digests, removed only the derived snapshot,
and restarted the store:

```text
projection_replacement_get=REJECTED RegistryConflict
registry projection does not match its catalogue anchor
projection_replacement_list=REJECTED RegistryConflict
registry projection does not match its catalogue anchor
```

A coordinated replacement of the projection, receipt, and per-event anchor
while leaving the committed catalogue unchanged was also rejected by the
projection catalogue anchor. The prior local trust limitation remains: an
operating-system owner able to rewrite every record plus the catalogue and its
unkeyed self-digest is outside this local development store's integrity model.

#### Complete trailing-receipt retry — PASS outside R6-B1/B2

When the event and anchor were both durable, R6 exposed only the catalogue
prefix, rejected a non-identical retry, accepted the identical transition retry,
and retained exactly two receipts. When catalogue replacement completed before
an injected reporting failure, the same retry returned the committed transition
without appending receipt three.

This closes R5-B2 for complete event/anchor pairs. It does not cover the event-
only interruption in R6-B1 or the indexing bypass in R6-B2.

### Earlier adversarial areas rechecked

#### Lifecycle stream integrity — PASS

```text
filename_gap REJECTED RegistryConflict
registry lifecycle event filenames must form a contiguous sequence
missing_stream REJECTED RegistryConflict
committed registry lifecycle event stream is missing
recomputed_event REJECTED RegistryConflict
registry lifecycle integrity anchor mismatch
```

Snapshot mismatch, receipt digest, chain, terminal-state, invalid shortcut, and
stale expected-revision tests also remain green.

#### Path and symlink safety — PASS

Root, parent, lock, catalogue, event directory, anchor directory, event file,
and anchor file symlinks were all independently rejected. No tested path wrote
through a symlink or escaped its configured registry root.

#### Source non-duplication and exact relationships — PASS

```text
records=44 kinds=7
agent=4 capability=29 evaluation=1 report=3
dashboard=1 scenario=3 workflow=3
forbidden_projection_keys={}
summary_leaks=[]
nested_definition=REJECTED
repository_commits=[e9eab8dd704d4c04d90fff269118a4af21072db9]
adapter_digest_exact=True
relationships=36 all_resolved_exact=True
```

The recursive probe found no copied grants, schemas, effects, shocks, workflow
topology, model-call counts, prompts, routing, state schemas, or tool latches.
Scenario and workflow summaries remain metadata-only.

#### Comparison, UI/API governance, and effects — PASS

The exact R6 ASGI application returned:

```text
page=200 catalogue=200 records=44
preview_no_write=True bootstrap=200 indexed=44
transition=200 validated
stale_transition=409 unrelated_compare=409
absolute_path_exposed=False registry_root_key=False
kind_specific_effect_fields=0
```

The Registry workspace retains explicit indexing confirmation, bootstrap
preview and consequence copy, server-provided allowed transitions, transition
confirmation, rationale, expected revision, local-publication language, and no
execution or financial-effect action. Registry routes introduce no model,
provider, broker, order, trade, hedge, rebalance, optimization, portfolio
mutation, deployment, or external publication authority.

### R6 automated verification

```bash
PIP_NO_INDEX=1 make verify-platform-phase1 \
  BOOTSTRAP_VENV=/private/tmp/platform-p1-r6-qa.Ff4OMP/venv \
  DAY0_VENV=/Users/lorenzocc/Developer/servicefabric-lab/state/venvs/thesis-sprint
```

Result: **PASS** — environment, repository, exact ServiceFabric pin, package,
diff, and `41 passed in 2.64s`.

```bash
PIP_NO_INDEX=1 make test-application test-architecture \
  DAY0_VENV=/Users/lorenzocc/Developer/servicefabric-lab/state/venvs/thesis-sprint
```

Result: **PASS** — `104 passed in 18.61s` for application tests and
`105 passed in 1.67s` for architecture tests.

`git diff --check` passed before this R6 handoff update.

### R6 browser limitation

The browser environment and sandbox policy are unchanged from the preserved R5
review: the in-app browser runtime had no available instance, localhost socket
binding was denied, and the mandated escalation was rejected. R6 therefore
repeated exact in-process ASGI, static interaction-contract, application, and
architecture verification but does not claim a new independent live-browser
session. The integration handoff's prior successful live browser evidence was
reviewed. This limitation is secondary to R6-B1 and R6-B2.

### R6 acceptance decision and next action

**Do not accept or merge candidate
`e9eab8dd704d4c04d90fff269118a4af21072db9`.** Keep PLATFORM-P1 in progress
and independent QA blocked. Integration should repair R6-B1 and R6-B2 together,
because both arise from the distinction between durable uncommitted tails and
catalogue-committed state. A fresh immutable candidate must pass every boundary
and cross-operation retry probe before Phase 1 can close.

Rollback remains documentation-only for this QA lane. Temporary registries and
the isolated bootstrap environment are non-authoritative; canonical source
definitions, the accepted Phase 0 baseline, and the read-only ServiceFabric pin
remain unchanged.

## R7 independent review

- Exact candidate: `6eed7cae7499c76afa1fe03ac455414b3e7d859c`
- Review worktree: `phase1-independent-qa-r7`
- Verdict: **BLOCKED**
- R5 and R6 history above: preserved and unchanged in meaning

### R7 executive result

R7 closes both exact R6 failure reproductions. A transition interrupted after
its event is durable but before its anchor remains readable at the
catalogue-committed prefix and its exact retry installs the missing anchor.
The same boundary on item two of `index_many()` leaves zero catalogue-visible
items and an exact batch retry converges. Ordinary `index()` and `index_many()`
also no longer adopt a valid uncommitted transition tail: both return the prior
committed lifecycle state, after which the exact transition retry succeeds.
Immutable staging fails without leaving a partial final file.

All declared gates and the cumulative projection, receipt, anchor, catalogue,
filename, restart, batch, path, source, provenance, relationship, comparison,
API, UI, and effect-boundary probes pass. A changed-intent recovery probe for
the initial uncatalogued receipt nevertheless finds one release blocker:

1. after initial `index()` or `index_many()` fails between event and anchor
   installation, a different actor can retry and commit the original actor's
   durable receipt; direct `index()` also accepts a different rationale.

The committed audit record therefore says the original actor completed an
indexing operation that a different actor actually resumed. This violates the
R6 requirement that an uncommitted tail be completed only by an identical retry
without accepting changed intent. Candidate `6eed7ca` does not yet satisfy the
Phase 1 restart, idempotency, or audit-integrity gates.

### R7 scope and immutable baseline

The review inspected the exact R6-to-R7 repair delta, current store and tests,
preserved R5/R6 findings, source adapter, Registry API and workspace, and the
governing Phase 1 workplan and audits. It verified:

```text
candidate HEAD         6eed7cae7499c76afa1fe03ac455414b3e7d859c
accepted Phase 0       21339db19357277ca9a9a1ca50107f1a884d7aeb
ServiceFabric gitlink  7632b61d94a966346f95eb6c5bb2a5ea27f3bc14
worktree branch        review/platform-p1-independent-qa-r7
pre-handoff status     clean
```

No implementation, test, source definition, control-plane record, dependency,
runtime data, financial effect, or vendor file was modified in this lane.

### R7-B1 — changed-intent initial indexing retry is accepted

When a canonical source has a reconstructed receipt stream but no catalogue
entry, `_index_locked()` at
`packages/risk_registry/src/risk_registry/store.py:455-462` materializes the
stream and returns it solely when the source observation matches. It receives
`actor`, `rationale`, and `occurred_at`, but does not compare them with the
durable initial receipt. `index()` then commits that receipt to the catalogue;
`index_many()` follows the same path.

The independent probe interrupted initial indexing immediately after the event
write by failing the anchor write. It then restarted the store and deliberately
retried with a different actor and, for direct indexing, a different rationale:

```text
changed index retry accepted=True
committed receipt actor=original-indexer
committed receipt rationale=original rationale

changed index_many retry accepted=True
committed batch receipt actor=original-bootstrap
```

The new actor is not represented in the committed receipt, while the old actor
is represented as having completed an operation that never returned and whose
publication was completed by another principal. This is not a harmless
idempotent source rediscovery: before catalogue commit there is no public item,
and the durable receipt is the audit evidence for who proposed that item.

**Required repair outcome:** an uncatalogued durable initial receipt must be
completed only by the exact matching indexing intent. At minimum, direct
`index()` must compare actor, rationale, occurrence semantics, source
observation, and receipt purpose; batch bootstrap must compare actor, its fixed
rationale, source set, and receipt purpose. A changed-intent caller must not
publish the old receipt. Add single-item, second-item batch, and API bootstrap
tests that attempt a changed actor and changed rationale before the exact retry.
The exact original retry must still converge without a duplicate receipt.

### Exact R6 blocker closure evidence

#### R6-B1 event-before-anchor interruption — PASS for exact retries

The transition probe allowed receipt sequence two to become durable, failed
before its anchor write, restarted from disk, read the committed state through
both `get()` and `list()`, and then retried exactly:

```text
fresh_get=candidate/1
fresh_list=1 candidate
durable_files=2 events / 1 anchor
exact_retry=validated/2
```

The item-two batch probe left both projections and events on disk but no
catalogue entries. Fresh `list()` returned zero, both fresh `get()` calls
returned `RegistryNotFound`, and the exact retry indexed both items:

```text
fresh_list=0
fresh_get=RegistryNotFound/RegistryNotFound
exact_retry=2
conflicts=0
```

This closes the R6 event-to-anchor availability defect for identical requests.
R7-B1 is the separate changed-intent gap in the initial indexing path.

#### R6-B2 indexing a pending transition — PASS

For both operations, the probe created a complete anchored validated receipt,
failed before catalogue replacement, confirmed the committed candidate prefix,
called indexing with a different bootstrap actor, and then performed the exact
transition retry:

```text
index:
  before=candidate/1 returned=candidate/1 after=candidate/1
  head_advanced=False exact_transition_retry=validated/2

index_many:
  before=candidate/1 returned=candidate/1 after=candidate/1
  head_advanced=False exact_transition_retry=validated/2
```

Source indexing therefore cannot adopt an existing item's uncommitted lifecycle
tail. Transition intent remains checked at `store.py:627-642`.

#### Atomic immutable staging — PASS

An injected file `fsync` failure occurred while staging bytes, before the
exclusive link to the authoritative name. The final path did not exist and the
temporary directory was empty afterward:

```text
atomic staging: final_exists=False temporary_files=0
```

The final immutable name is installed only after complete bytes have been
flushed and synced.

### Cumulative adversarial matrix

#### Integrity, continuity, restart, and batch behavior — PASS outside R7-B1

Independent replacements and corruptions produced:

```text
projection=REJECTED RegistryConflict: projection does not match catalogue anchor
receipt=REJECTED RegistryConflict: lifecycle integrity anchor mismatch
anchor=REJECTED RegistryConflict: lifecycle integrity anchor mismatch
catalog_digest=REJECTED RegistryConflict: catalogue integrity verification failed
catalog_head=REJECTED RegistryConflict: stream does not contain committed head
filename_gap=REJECTED RegistryConflict: filenames must form a contiguous sequence
missing_stream=REJECTED RegistryConflict: committed event stream is missing
```

The focused retry tests also passed for failure before catalogue commit and
failure reported after catalogue replacement. Exact retry retained two
receipts in each case. A preflight conflict and an injected second-projection
write failure both left the batch catalogue unchanged; an identical retry of
the write failure indexed both items. Snapshot replay mismatch, receipt digest,
chain, transition graph, terminal-state, publication eligibility, and stale
expected-revision tests remain green.

#### Path and symlink safety — PASS

Independent probes rejected each tested indirection without writing through it:

```text
root=ValueError        parent=ValueError       lock=OSError
catalog=ValueError     record=ValueError       projection=ValueError
event_file=ValueError  anchor_file=RegistryConflict
records_dir=ValueError event_dir=ValueError    anchor_dir=ValueError
```

#### Source non-duplication and exact provenance — PASS

```text
records=44 kinds=7 unique_references=44
agent=4 capability=29 evaluation=1 report=3
dashboard=1 scenario=3 workflow=3
forbidden_recursive_keys=[] summary_leaks=[]
repository_commits=[6eed7cae7499c76afa1fe03ac455414b3e7d859c]
adapter_digest_exact=True
relationships=36 all_resolved_exact=True
```

Every resolved relationship targets one of the exact 44 references, compatible
projections bind their evaluated source digest to their exact definition
digest, and unrelated stable identities remain non-comparable.

#### API, UI governance, and effect boundaries — PASS

An exact in-process application session returned:

```text
page=200 catalogue=200 records=44
preview_no_write=True bootstrap=200
transition=200 validated stale_transition=409 unrelated_compare=409
absolute_path_exposed=False registry_root_key=False
kind_specific_effect_fields=0
```

Static and application tests confirm explicit bootstrap consequence and
confirmation copy, server-supplied allowed transitions, transition rationale,
expected revision, source drift, local-development publication language, and no
model, provider, broker, order, trade, hedge, rebalance, optimization, portfolio
mutation, deployment, external publication, or other financial-effect control.

### R7 automated verification

```bash
PIP_NO_INDEX=1 make verify-platform-phase1 \
  BOOTSTRAP_VENV=/private/tmp/platform-p1-r6-qa.Ff4OMP/venv \
  DAY0_VENV=/Users/lorenzocc/Developer/servicefabric-lab/state/venvs/thesis-sprint
```

Result: **PASS** — environment, repository, exact ServiceFabric pin, package,
diff, and `45 passed in 2.53s`.

```bash
PIP_NO_INDEX=1 make test-application test-architecture \
  DAY0_VENV=/Users/lorenzocc/Developer/servicefabric-lab/state/venvs/thesis-sprint
```

Result: **PASS** — `104 passed in 17.64s` for application tests and
`105 passed in 1.50s` for architecture tests.

A focused named rerun of catalogue retry, batch atomicity, tamper, continuity,
source, API, comparison, stale-review, and workspace tests passed `22` tests in
`2.19s`. `git diff --check` passed before this handoff update.

### R7 browser limitation

The in-app browser and localhost-bind limitation recorded in R5/R6 remains.
R7 used the exact FastAPI application through an in-process client, plus static
interaction-contract and full application/architecture tests; it does not claim
a new independent live-browser session. This limitation is not the reason for
the R7 verdict.

### R7 acceptance decision and next action

**Do not accept or merge candidate
`6eed7cae7499c76afa1fe03ac455414b3e7d859c`.** Keep PLATFORM-P1 in progress
and independent QA blocked until indexing recovery binds uncatalogued durable
receipts to the exact retry intent. A fresh immutable candidate must reject both
changed-actor paths, reject changed direct-index rationale, preserve zero batch
visibility, and still accept the exact original retry without duplicating a
receipt.

Rollback remains documentation-only for this QA lane. All probe registries were
temporary and non-authoritative. Canonical definitions, the accepted Phase 0
baseline, and the read-only ServiceFabric pin remain unchanged.


## R8 independent review

- Exact candidate: `9ed110dbbb7d8c6cc76c288ebdc06494eeb9ffd0`
- Review worktree: `phase1-independent-qa-r8`
- Verdict: **BLOCKED**
- R5, R6, and R7 history above: preserved and unchanged in meaning

### R8 executive result

R8 closes the direct changed-actor and changed-rationale reproductions from
R7-B1. When the original single index supplied an explicit timestamp, a retry
supplying a different explicit timestamp is also rejected. Every rejected
single retry leaves zero catalogue visibility, and the exact original retry
converges with its original receipt. A changed batch actor is rejected with
zero visibility, while the exact complete batch retry converges.

The complete declared and cumulative matrix otherwise passes. Two related
exactness defects still block acceptance:

1. when the original index supplied an explicit timestamp, a retry that omits
   `occurred_at` treats the omission as a wildcard and adopts the receipt; and
2. an interrupted multi-item batch is not bound to its original membership, so
   a same-actor subset retry can publish one item from the previously atomic
   batch while leaving the other hidden.

Both defects arise because recovery infers one pending operation from per-item
receipts rather than recovering a durable operation-level intent. Candidate
`9ed110d` therefore does not meet the Phase 1 exact-retry, batch-atomicity, and
audit-integrity gates.

### R8 scope and immutable baseline

The review inspected the R7-to-R8 repair delta, current persistence logic and
tests, preserved R5-R7 findings, source adapter, Registry API/workspace, and all
governing Phase 1 materials. It verified:

```text
candidate HEAD         9ed110dbbb7d8c6cc76c288ebdc06494eeb9ffd0
accepted Phase 0       21339db19357277ca9a9a1ca50107f1a884d7aeb
ServiceFabric gitlink  7632b61d94a966346f95eb6c5bb2a5ea27f3bc14
worktree branch        review/platform-p1-independent-qa-r8
pre-handoff status     clean
```

No implementation, test, source definition, control-plane record, dependency,
runtime data, financial effect, or vendor file was modified in this QA lane.

### R7-B1 closure evidence

The single-item probe created one event with no anchor or catalogue entry using
actor `original`, rationale `original rationale`, and explicit timestamp T1.
It restarted from disk and exercised each mismatch before the exact retry:

```text
single_changed_actor=REJECTED visibility=0
single_changed_rationale=REJECTED visibility=0
single_changed_explicit_timestamp(T2)=REJECTED visibility=0
single_exact_retry(T1)=candidate/1 original_receipt_preserved=True
```

The two-item probe interrupted the second item between event and anchor writes.
The changed actor was rejected without adding an anchor, snapshot, or catalogue
visibility; the complete exact retry then indexed both original receipts:

```text
batch_changed_actor=REJECTED visibility=0
batch_exact_retry=2 original_receipts_preserved=True
```

`index_many()` exposes neither custom rationale nor explicit timestamp; it
always supplies the fixed bootstrap rationale and `occurred_at=None`. Direct
single-item tests therefore carry the independently variable rationale and
timestamp coverage. The two defects below concern omission semantics and the
batch request boundary, which the new per-item comparison does not represent.

### R8-B1 — omitted timestamp adopts an explicitly timed receipt

The recovery predicate at
`packages/risk_registry/src/risk_registry/store.py:457-465` checks timestamp
equality only when the retry provides `occurred_at`. If the retry omits the
field, line 462 makes the timestamp predicate true even though the original
request explicitly supplied T1.

The independent probe interrupted that original T1 request before its anchor,
restarted, then made the otherwise identical retry without a timestamp:

```text
single_omitted_original_explicit_timestamp_accepted=True
state=candidate
committed_time=2026-08-03T12:00:00+00:00
```

The retry is not identical: one command supplied a governed timestamp and the
other did not. The store nevertheless publishes the old receipt. The same
wildcard convention exists for interrupted transition recovery, but R8 directly
proves the initial-index path required by this review.

**Required repair outcome:** persist whether the original operation supplied a
timestamp, or canonicalize the request into a complete durable intent before
writing any projection or receipt. An omitted retry must match only an original
omission under the chosen contract; it must not wildcard an explicit value.
Add both explicit-to-omitted and omitted-to-explicit tests as well as unequal
explicit timestamps.

### R8-B2 — subset retry breaks original batch atomicity

`index_many()` at `store.py:694-730` converts only the current call to a tuple.
It does not persist or recover the identity set of the interrupted operation.
Each `_index_locked()` call validates actor, fixed rationale, and the individual
receipt, so a new request containing only one original item looks exact at the
item level.

The independent probe interrupted a two-item batch on item two after its event
became durable. It then retried only item one with the original actor:

```text
batch_subset_retry_accepted=True
visible=1
original_batch_size=2
retry_size=1
```

Before this call, both items were correctly invisible. After it, item one was
catalogue-visible while item two remained an uncommitted tail. A supposedly
atomic bootstrap can therefore be split by changing only retry membership.

**Required repair outcome:** persist an immutable pending-operation record that
binds operation kind, actor, normalized rationale, timestamp semantics, ordered
or canonicalized identity set, and exact source observations before writing any
item. Recovery must compare the entire request with that record. Subset,
superset, duplicate, changed-order if order is material, changed actor, changed
rationale, and changed timestamp retries must not alter visibility; the exact
original batch must still converge without duplicate receipts.

### Cumulative adversarial matrix

#### R5/R6 persistence and recovery closures — PASS

Independent fault injection reconfirmed:

```text
R6-B1 transition: committed_prefix=candidate/1 exact_retry=validated/2
R6-B1 item-two batch: fresh list=0; exact complete retry=2
R6-B2 index: head_advanced=False exact_transition_retry=validated/2
R6-B2 index_many: head_advanced=False exact_transition_retry=validated/2
catalogue post-commit retry=validated/2 idempotent=True
atomic staging: final_exists=False temporary_files=0
```

The focused suite also passes pre-catalogue interruption recovery, catalogue
post-commit idempotence, projection-write batch failure with zero visibility,
preflight conflicts, snapshot reconstruction and mismatch, event/anchor
continuity, lifecycle chains, transition graph, terminal state, publication
eligibility, stale revision, and unrelated comparison rejection.

#### Tamper and filename integrity — PASS

Valid replacement projections remain bound by the catalogue projection digest.
Validly recomputed receipts are rejected by their immutable anchors; altered or
missing committed anchors, missing streams, and filename gaps fail closed.
Additional catalogue probes returned:

```text
catalog_digest=REJECTED RegistryConflict
catalog_head=REJECTED RegistryConflict
```

The first altered an entry without its envelope digest. The second recomputed
the envelope digest around a nonexistent lifecycle head and was rejected because
the stream did not contain that committed head.

#### Path and symlink safety — PASS

Independent probes rejected all tested indirections:

```text
root/parent=ValueError  lock=OSError
catalog=ValueError      record=ValueError      projection=ValueError
event_file=ValueError   anchor_file=RegistryConflict
records_dir=ValueError  event_dir=ValueError    anchor_dir=ValueError
```

No tested path wrote through a symlink or escaped the configured registry root.

#### Source non-duplication, provenance, and relationships — PASS

```text
records=44 unique_references=44 kinds=7
agent=4 capability=29 evaluation=1 report=3
dashboard=1 scenario=3 workflow=3
forbidden_recursive_keys=[]
repository_commit=9ed110dbbb7d8c6cc76c288ebdc06494eeb9ffd0
adapter_digest_exact=True
relationships=36 all_resolved_exact=True
```

Compatible projections bind their evaluated source digest to the exact
definition digest. Scenario and workflow projections remain metadata-only, and
comparison remains limited to versions of one stable identity.

#### API, UI governance, and effect boundaries — PASS

The exact R8 application exercised in process returned:

```text
page=200 catalogue=200 records=44
preview_no_write=True bootstrap=200
transition=200 validated stale_transition=409 unrelated_compare=409
absolute_path_exposed=False registry_root_key=False
kind_specific_effect_fields=0
```

Static and application assertions retain explicit bootstrap consequences and
confirmation, server-supplied transitions, rationale and expected-revision
review controls, source truth/drift, local-development publication language,
and no model, provider, broker, order, trade, hedge, rebalance, optimization,
portfolio mutation, deployment, external publication, or other financial
effect control.

### R8 automated verification

```bash
PIP_NO_INDEX=1 make verify-platform-phase1 \
  BOOTSTRAP_VENV=/private/tmp/platform-p1-r6-qa.Ff4OMP/venv \
  DAY0_VENV=/Users/lorenzocc/Developer/servicefabric-lab/state/venvs/thesis-sprint
```

Result: **PASS** — environment, repository, exact ServiceFabric pin, package,
diff, and `45 passed in 3.32s`.

```bash
PIP_NO_INDEX=1 make test-application test-architecture \
  DAY0_VENV=/Users/lorenzocc/Developer/servicefabric-lab/state/venvs/thesis-sprint
```

Result: **PASS** — `104 passed in 17.64s` for application tests and
`105 passed in 1.52s` for architecture tests.

A named cumulative rerun of recovery, staging, batch, tamper, source, API,
comparison, stale-review, and workspace cases passed `25` tests in `2.35s`.
`git diff --check` passed before this handoff update.

### R8 browser limitation

The in-app browser and localhost-bind limitation preserved in R5-R7 remains.
R8 used the exact FastAPI application through an in-process client, static
interaction-contract assertions, and the full application and architecture
suites. It does not claim a new independent live-browser session. This
limitation is not the reason for the verdict.

### R8 acceptance decision and next action

**Do not accept or merge candidate
`9ed110dbbb7d8c6cc76c288ebdc06494eeb9ffd0`.** Keep PLATFORM-P1 in progress
and independent QA blocked. Recovery must bind every initial write to one
immutable operation-level intent rather than infer intent independently from
each receipt. A fresh immutable candidate must reject timestamp omission and
all changed batch memberships without adding visibility, then accept the exact
original request with the original receipts.

Rollback remains documentation-only for this QA lane. All probe registries were
temporary and non-authoritative. Canonical definitions, the accepted Phase 0
baseline, and the read-only ServiceFabric pin remain unchanged.

## R9 independent review

- Exact candidate: `ae30a75da4c453cec9841154ec56356ec17c80de`
- Review worktree: `phase1-independent-qa-r9`
- Verdict: **BLOCKED**
- R5 through R8 history above: preserved and unchanged in meaning

### R9 executive result

R9 closes both exact R8 blockers with an immutable pending-operation journal.
The journal distinguishes timestamp omission from an explicit value, binds the
single-versus-batch mode, and binds a canonical complete reference set. Changed
actor, rationale, timestamp, subset, superset, and cross-mode retries all fail
without visibility. A reordered complete batch is correctly equivalent to the
same canonical set, and exact original retries preserve their receipts.

Crash-before-intent, crash-after-intent, missing active intent, tampered active
intent, valid stale completed intent, atomic staging, and all cumulative gates
also behave correctly. One release blocker remains: the journal records only
registry references, not the semantic source observations assigned to those
references. After a crash immediately after the journal write but before any
projection write, an otherwise matching retry can substitute a different valid
projection with the same identity and publish it.

Candidate `ae30a75` therefore does not yet meet exact-retry, immutable-source,
or audit-integrity requirements.

### R9 scope and immutable baseline

The review inspected the R8-to-R9 journal delta, persistence code and tests,
all preserved findings, source adapter, Registry API/workspace, and governing
Phase 1 materials. It verified:

```text
candidate HEAD         ae30a75da4c453cec9841154ec56356ec17c80de
accepted Phase 0       21339db19357277ca9a9a1ca50107f1a884d7aeb
ServiceFabric gitlink  7632b61d94a966346f95eb6c5bb2a5ea27f3bc14
worktree branch        review/platform-p1-independent-qa-r9
pre-handoff status     clean
```

No implementation, test, source definition, control-plane record, dependency,
runtime data, financial effect, or vendor file was modified in this QA lane.

### R8-B1/B2 closure evidence

#### Single-item intent and timestamp presence — PASS

The probe interrupted an index with actor `actor`, rationale `timed rationale`,
and explicit T1. Every changed request was independently rejected, and each
rejection left the catalogue empty before the exact retry:

```text
single_omitted_T1=REJECTED visibility=0
single_changed_T2=REJECTED visibility=0
single_changed_actor=REJECTED visibility=0
single_changed_rationale=REJECTED visibility=0
single_exact_retry=candidate/1 original_receipt=True
```

This closes the R8 `None`-as-wildcard defect for initial indexing.

#### Batch set and operation mode — PASS

The probe interrupted a two-item batch between the second event and anchor
writes. It then exercised changed membership and both cross-mode directions:

```text
batch_subset=REJECTED visibility=0
batch_superset=REJECTED visibility=0
single_to_batch=REJECTED visibility=0
batch_to_single=REJECTED visibility=0
batch_reordered_full_set=ACCEPTED canonical_set_match=True visible=2
batch_exact_retry=2 original_receipts=True
```

The journal sorts and deduplicates references, so order is intentionally not
part of batch meaning. Mode, exact set, actor, fixed batch rationale, and
timestamp-presence semantics are part of the operation meaning.

### Pending-intent lifecycle and integrity

#### Crash boundaries — PASS

Failure before the pending-intent link left no journal, projection, event, or
catalogue visibility; the original retry created the journal and candidate.
Failure after the journal link but before `_index_locked()` left one complete
journal and no source data; the original retry converged:

```text
crash_before_intent: visibility=0 journal=0 exact_retry=candidate/1
crash_after_intent:  visibility=0 journal=1 exact_retry=candidate/1
```

The same atomic staging primitive used for projections, events, and anchors is
used for the journal, so a pre-link staging failure leaves no partial final
file.

#### Missing, tampered, and stale intents — PASS

Deleting the active journal after an event became durable caused the retry to
fail with `uncommitted registry data has no matching pending operation intent`.
Changing the actor bytes without changing the journal digest caused integrity
verification to fail. Both cases retained zero visibility:

```text
missing_active_intent=REJECTED visibility=0
tampered_active_intent=REJECTED visibility=0
```

A completed journal remains mode `0400`, does not affect committed reads or
idempotent rediscovery, and does not block a disjoint new index. Two completed
operations produced two immutable stale journals and two visible records. This
is acceptable append-only local history; cleanup or compaction is not required
for Phase 1 correctness.

Pending-directory and pending-file symlinks are independently rejected.

### R9-B1 — journal does not bind the semantic source observation

`_prepare_index_intent()` at
`packages/risk_registry/src/risk_registry/store.py:329-345` records only the
sorted `identity.reference` strings, mode, actor, rationale, and timestamp. It
does not include the projection digest or a normalized semantic-observation
digest. If the process fails after lines 375-380 install that journal but before
`_index_locked()` writes a projection, no other durable record identifies which
projection the original actor intended to index.

The independent probe forced exactly that boundary. The original request used
one valid projection, then failed immediately after the journal was installed.
The retry kept the same reference, actor, rationale, mode, and timestamp
semantics but supplied another valid projection with a different summary,
source digest, definition digest, compatibility digest, and semantic meaning:

```text
journal_only_changed_source_accepted=True
committed_summary='Changed source.'
committed_definition_digest=ffffffff...
```

The retry passed journal comparison because the identity reference was
unchanged, then wrote and catalogued the substituted projection. This bypasses
the store's normal changed-source conflict protection precisely where the
journal is the only durable evidence.

**Required repair outcome:** bind every requested reference to a deterministic
semantic-observation digest in the immutable journal before any projection or
receipt write. The digest should match the store's deliberate idempotency
semantics: discovery time, repository commit, and raw containing-file digest may
be excluded where `_same_source_observation()` excludes them, while exact
definition, adapter, compatibility, identity, summary, lineage, relationships,
contract, tags, and canonicality remain bound. Single and batch retries must
reject any changed mapping with zero visibility. Add journal-only crash tests
for a changed definition, changed metadata, changed adapter, swapped batch
mapping, and exact benign rediscovery fields.

### Cumulative adversarial matrix

#### Persistence, retry, and lifecycle — PASS outside R9-B1

R5/R6/R7/R8 closures remain green:

```text
event-before-anchor committed prefix=candidate/1; exact retry=validated/2
item-two batch failure fresh visibility=0; exact complete retry=2
pending transition + index: head_advanced=False; exact retry=validated/2
pending transition + index_many: head_advanced=False; exact retry=validated/2
catalogue pre-commit retry=validated/2
catalogue post-commit reporting retry=validated/2, receipts=2
atomic staging final_exists=False temporary_files=0
```

Snapshot reconstruction/mismatch, receipt digest and chain, transition graph,
terminal-state, publication eligibility, stale revision, bootstrap preflight
conflict, duplicate request, and second-projection write failure checks pass.

#### Tamper, continuity, and path safety — PASS

Projection replacement, recomputed receipt replacement, altered/missing anchor,
filename gap, missing event stream, catalogue digest, and catalogue-head probes
all fail closed. Root, parent, lock, catalogue, record, projection, event file,
anchor file, pending file, records directory, event directory, anchor directory,
and pending directory indirections are rejected. No tested path wrote through a
symlink or escaped the configured registry root.

#### Source non-duplication, provenance, and relationships — PASS

```text
records=44 unique_references=44 kinds=7
agent=4 capability=29 evaluation=1 report=3
dashboard=1 scenario=3 workflow=3
forbidden_recursive_keys=[]
repository_commit=ae30a75da4c453cec9841154ec56356ec17c80de
adapter_digest_exact=True
relationships=36 all_resolved_exact=True
```

Compatible projections remain tied to their exact definition digest, scenario
and workflow projections remain metadata-only, and version comparison rejects
unrelated stable identities.

#### API, UI governance, and no-effect boundary — PASS

The exact R9 application exercised in process returned:

```text
page=200 catalogue=200 records=44
preview_no_write=True bootstrap=200 transition=200 validated
stale_transition=409 unrelated_compare=409
absolute_path_exposed=False registry_root_key=False
kind_specific_effect_fields=0
```

Static and application tests preserve confirmation and consequence copy,
server-provided transitions, rationale and revision review controls, source
truth/drift, local-development publication language, and no model, provider,
broker, order, trade, hedge, rebalance, optimization, portfolio mutation,
deployment, external publication, or other financial-effect control.

### R9 automated verification

```bash
PIP_NO_INDEX=1 make verify-platform-phase1 \
  BOOTSTRAP_VENV=/private/tmp/platform-p1-r6-qa.Ff4OMP/venv \
  DAY0_VENV=/Users/lorenzocc/Developer/servicefabric-lab/state/venvs/thesis-sprint
```

Result: **PASS** — environment, repository, exact ServiceFabric pin, package,
diff, and `46 passed in 2.90s`.

```bash
PIP_NO_INDEX=1 make test-application test-architecture \
  DAY0_VENV=/Users/lorenzocc/Developer/servicefabric-lab/state/venvs/thesis-sprint
```

Result: **PASS** — `104 passed in 17.29s` for application tests and
`105 passed in 1.49s` for architecture tests.

A named cumulative rerun of recovery, intent, staging, batch, tamper, source,
API, comparison, stale-review, and workspace cases passed `26` tests in
`2.28s`. `git diff --check` passed before this handoff update.

### R9 browser limitation

The in-app browser and localhost-bind limitation preserved in R5-R8 remains.
R9 used the exact FastAPI application through an in-process client, static
interaction-contract assertions, and the full application and architecture
suites. It does not claim a new independent live-browser session. This
limitation is not the reason for the verdict.

### R9 acceptance decision and next action

**Do not accept or merge candidate
`ae30a75da4c453cec9841154ec56356ec17c80de`.** Keep PLATFORM-P1 in progress
and independent QA blocked. Extend the journal from a reference set to an exact
reference-to-semantic-observation mapping. A fresh immutable candidate must
reject changed single and batch projections after a journal-only crash without
creating visibility, while preserving benign rediscovery semantics and exact
original recovery.

Rollback remains documentation-only for this QA lane. All probe registries were
temporary and non-authoritative. Canonical definitions, the accepted Phase 0
baseline, and the read-only ServiceFabric pin remain unchanged.

## R10 independent review

- Exact candidate: `a68ef6fce9d39f5341fa8675c093db2eba95aed6`
- Review worktree: `phase1-independent-qa-r10`
- Verdict: **PASS — ACCEPT**
- R5 through R9 BLOCKED history above: preserved and unchanged in meaning

### R10 executive result

R10 closes the final R9 blocker and passes the complete cumulative Phase 1
adversarial, regression, source-truth, application, architecture, UI, API, and
no-effect review. The pending-operation journal now binds each registry
reference to the same normalized semantic source observation used by ordinary
idempotency checks. A journal-only crash cannot be recovered with a changed
summary, definition, compatibility evaluation, adapter, relationship, lineage,
or batch observation mapping. The exact original observation recovers, while
only explicitly normalized discovery metadata remains safely idempotent.

No release-blocking issue remains on exact candidate `a68ef6f`. The candidate
satisfies the Phase 1 exit gates and is accepted for integration. This review
does not merge it or perform any Phase 2 work.

### R10 scope and immutable baseline

The review inspected the R9-to-R10 diff, full current persistence logic and
tests, all specialist audits and preserved QA history, the Phase 1 plan and
independent-review brief, accepted Phase 0 boundaries, source adapter, Registry
API, and Registry workspace. It verified:

```text
candidate HEAD         a68ef6fce9d39f5341fa8675c093db2eba95aed6
accepted Phase 0       21339db19357277ca9a9a1ca50107f1a884d7aeb
ServiceFabric gitlink  7632b61d94a966346f95eb6c5bb2a5ea27f3bc14
worktree branch        review/platform-p1-independent-qa-r10
pre-handoff status     clean
```

The implementation remains an index over bounded projections and exact source
pointers, not another source of canonical agent, capability, evaluation,
report, dashboard, scenario, or workflow definitions. Mutable data remains
outside Git, lifecycle receipts remain append-only, and local registry
publication grants no deployment, external-publication, or financial-effect
authority.

No implementation, test, source definition, control-plane record, dependency,
runtime data, financial effect, or vendor file was modified in this QA lane.

### R9 blocker closure — semantic observation binding

The review forced failure immediately after the journal was installed and
before any projection bytes were published. It then retried the same registry
identity, actor, rationale, mode, and timestamp semantics with independent
valid semantic substitutions:

```text
changed_summary_definition=REJECTED visibility=0
changed_adapter=REJECTED visibility=0
changed_relationships_and_lineage=REJECTED visibility=0
changed_batch_observation_mapping=REJECTED visibility=0
```

After each rejected single substitution, the exact original projection
recovered as `candidate/1` with the original observation. After the rejected
batch mapping change, the exact original batch recovered both observations.

`_source_observation_digest()` and `_same_source_observation()` use one shared
normalization. The journal maps every sorted reference to that digest before the
first projection write. The mapping binds identity, display metadata, summary,
definition digest, native version, canonicality, adapter, compatibility,
provenance semantics, lineage, source contract, relationships, and tags.

### Volatile metadata normalization — PASS

The intentionally volatile fields are discovery time, repository checkout, and
the raw containing-file digest. A journal-only retry changing only those three
fields produced the same normalized digest and was accepted. This matches
ordinary registry rediscovery semantics:

```text
volatile_only_retry=ACCEPTED
normalized_digest_equal=True
state=candidate/1
```

Adding a changed summary to the same volatile drift changed the normalized
digest and was rejected with zero visibility. The normalization therefore does
not create a general metadata bypass; it excludes only fields deliberately
classified as scan or containing-file noise.

### Operation journal, batch atomicity, and restart behavior

#### Intent fields and mode — PASS

An interrupted explicitly timed single index rejected all non-identical
requests and retained zero visibility before exact recovery:

```text
changed_actor=REJECTED
changed_rationale=REJECTED
omitted_timestamp=REJECTED
changed_timestamp=REJECTED
exact_retry=candidate/1 original_receipt=True
```

An interrupted new two-item batch rejected subset, changed actor, and
batch-to-single retries. The reversed full set matched the canonical source set
and recovered both items. Missing and byte-tampered active journals failed
closed. Completed journals remain read-only, do not obstruct committed reads or
idempotent rediscovery, and do not block a disjoint operation.

#### Mixed committed and new batch — PASS

The probe first committed item one, journaled a batch containing that item and a
new item two, then failed before item two. Only item one remained visible.
Retries using the committed subset, new subset, a superset, or single-index mode
were rejected without changing visibility. The reordered exact full set
recovered item two and returned both records:

```text
mixed_committed_subset=REJECTED visible_only_existing=True
mixed_new_subset=REJECTED visible_only_existing=True
mixed_superset=REJECTED visible_only_existing=True
mixed_single_cross_mode=REJECTED visible_only_existing=True
mixed_exact_reordered_full_set=ACCEPTED visible=2
```

This confirms the active operation is checked before the all-requested-items-
already-committed shortcut, closing both partial and mixed-batch bypasses.

#### Crash boundary matrix — PASS

The complete lifecycle transition boundary matrix returned:

| Injected boundary | Fresh committed state | Exact retry |
|---|---|---|
| Before event installation | `candidate/1` | `validated/2` |
| Event durable, before anchor | `candidate/1` | `validated/2` |
| Anchor durable, before snapshot | `candidate/1` | `validated/2` |
| Snapshot durable, before catalogue | `candidate/1` | `validated/2` |
| Catalogue durable, caller sees failure | `validated/2` | `validated/2` |

For a complete uncommitted transition tail, both ordinary `index()` and
`index_many()` returned the catalogue-committed `candidate/1` prefix and did not
advance the head. The exact transition retry then returned `validated/2`.

Journal failure before its atomic link left no journal or source bytes; exact
retry started cleanly. Failure after the journal link but before projection
publication retained one valid journal and recovered exactly. An injected
staging `fsync` failure left neither a partial final file nor a temporary file.

### Cumulative integrity and safety matrix

#### Immutable source and lifecycle evidence — PASS

Independent adversarial probes reconfirmed:

```text
projection substitution without snapshot=REJECTED RegistryConflict
valid recomputed receipt without snapshot=REJECTED RegistryConflict
event filename gap=REJECTED RegistryConflict
catalogue envelope digest change=REJECTED RegistryConflict
catalogue head substitution with recomputed envelope=REJECTED RegistryConflict
missing committed event stream=REJECTED RegistryConflict
missing/altered committed anchor=REJECTED RegistryConflict
```

Snapshot mismatch, receipt self-digest, append-only chain, transition graph,
terminal state, publication eligibility, stale expected revision, unrelated
comparison, duplicate bootstrap identity, preflight conflict, and second-item
write-failure tests remain green. Batch failures never expose a newly requested
partial set through the catalogue.

#### Path and symlink safety — PASS

Root and parent indirection, lock, catalogue, record, projection, event file,
anchor file, pending-intent file, records directory, event directory, anchor
directory, and pending directory symlinks were rejected. No tested mutation
wrote through a symlink or escaped the configured registry root.

### Source, provenance, comparison, UI, and effect boundaries

#### Source non-duplication and exact provenance — PASS

```text
records=44 unique_references=44 kinds=7
agent=4 capability=29 evaluation=1 report=3
dashboard=1 scenario=3 workflow=3
forbidden_recursive_keys=[] summary_leaks=[]
repository_commit=a68ef6fce9d39f5341fa8675c093db2eba95aed6
adapter_digest_exact=True
relationships=36 all_resolved_exact=True
```

Compatible projections bind their compatibility evaluation to the exact
definition digest. All relationships target exact discovered revisions.
Scenario and workflow projections remain metadata-only; no grants, schemas,
effects, shocks, prompts, routing, topology, state schema, or tool latches are
copied into the registry. Comparison remains limited to versions of one stable
identity.

#### Exact application and no-effect boundary — PASS

The exact R10 application exercised in process returned:

```text
page=200 catalogue=200 records=44
preview_no_write=True bootstrap=200 transition=200 validated
stale_transition=409 unrelated_compare=409
absolute_path_exposed=False registry_root_key=False
kind_specific_effect_fields=0
```

The Registry workspace retains explicit preview and indexing confirmation,
truthful consequence copy, discovered-versus-indexed state, canonical source,
compatibility, provenance, lineage, comparison, server-provided transitions,
rationale, expected revision, source drift, and local-development publication
language. It exposes no model, provider, broker, order, trade, hedge, rebalance,
optimization, portfolio mutation, deployment, external publication, or other
financial-effect action.

### R10 automated verification

```bash
PIP_NO_INDEX=1 make verify-platform-phase1 \
  BOOTSTRAP_VENV=/private/tmp/platform-p1-r6-qa.Ff4OMP/venv \
  DAY0_VENV=/Users/lorenzocc/Developer/servicefabric-lab/state/venvs/thesis-sprint
```

Result: **PASS** — environment, repository, exact ServiceFabric pin, package,
diff, and `48 passed in 3.02s`.

```bash
PIP_NO_INDEX=1 make test-application test-architecture \
  DAY0_VENV=/Users/lorenzocc/Developer/servicefabric-lab/state/venvs/thesis-sprint
```

Result: **PASS** — `104 passed in 18.55s` for application tests and
`105 passed in 1.73s` for architecture tests.

A named cumulative rerun of recovery, journal semantics, staging, mixed and new
batches, tamper, source, API, comparison, stale-review, and workspace cases
passed `28` tests in `2.63s`. `git diff --check` passed before this handoff
update.

### R10 review limitation and bounded residual risks

The in-app browser and localhost-bind limitation preserved in R5-R9 remains.
R10 exercised the exact FastAPI application through an in-process client,
static interaction-contract assertions, and the complete application and
architecture suites. The integration handoff's successful live-browser
evidence was reviewed; R10 does not claim a separate live-browser session.

The local store's digest and read-only-file controls detect accidental and
partial corruption but are not a cryptographic defense against an operating-
system owner who rewrites every mutually consistent file. Completed journal
records are append-only and uncompacted. Both are disclosed local-development
boundaries, not Phase 1 release blockers.

### R10 acceptance decision

**Accept exact candidate
`a68ef6fce9d39f5341fa8675c093db2eba95aed6` for Phase 1 integration.**
Integration may merge only that immutable candidate together with this QA
record, run the final merge gate, and record the resulting accepted Phase 1
commit. Any implementation or test change requires another independent review.

The accepted scope is the Phase 1 local-development registry kernel and
catalogue only. This verdict grants no authority for Phase 2 artifacts, runtime
execution, production publication, external adapters, or financial effects.
All QA registries were temporary and non-authoritative; canonical definitions,
the accepted Phase 0 baseline, and the read-only ServiceFabric pin remain
unchanged.

## R11 acceptance-bookkeeping audit — PASS

R11 independently audits only the acceptance bookkeeping applied after the R10
implementation verdict. The accepted Phase 1 implementation remains exact
candidate `a68ef6fce9d39f5341fa8675c093db2eba95aed6`; bookkeeping commit
`ff28b251b46154bb323d5acb12512990ee1cfe47` is not a replacement implementation
candidate and introduces no runtime behavior.

### R11 bounded-diff and history findings

The exact diff from the accepted implementation candidate to the reviewed
bookkeeping commit contains eight paths only:

```text
config/agent/platform-development/status.json
docs/handoffs/platform-development/phase1-independent-qa.md
docs/handoffs/platform-development/phase1-integration.md
docs/workplans/current.md
docs/workplans/platform-development/phase-1-registry-kernel.md
tests/architecture/test_platform_development_control_plane.py
tests/architecture/test_platform_phase1_control_plane.py
tests/architecture/test_thesis_sprint_control_plane.py
```

The changes are limited to the preserved R10 QA handoff, Phase 1 acceptance
status and documentation, and matching architecture assertions. There are no
code, runtime, API, UI, package, dependency, vendor, or behavioral-test changes,
and no test assertion is weakened.

The status record now distinguishes the Phase 0 accepted candidate
`76651ea8a580832698e99e594581db9c12969dd4`, the accepted Phase 0 integration
baseline `21339db19357277ca9a9a1ca50107f1a884d7aeb`, and the accepted Phase 1
implementation candidate `a68ef6fce9d39f5341fa8675c093db2eba95aed6`.
Those identities agree across the status record, workplans, and handoffs. The
ServiceFabric gitlink remains exactly
`7632b61d94a966346f95eb6c5bb2a5ea27f3bc14`.

The R10 handoff blob is byte-for-byte identical at original QA commit
`52f16f6db49ba653edb23d4c2d2f93327ac5b083`, its integration commit
`e424b727a75919157d3fcfb1300317e6e7fb0176`, and reviewed bookkeeping commit
`ff28b251b46154bb323d5acb12512990ee1cfe47`. R5 through R10 remain in order,
including every prior blocked verdict and the exact R10 acceptance record.

Programme control also remains closed after Phase 1: Phase 1 is accepted,
Phase 0 remains accepted, the prior thesis stream remains deferred, and no
Phase 2 work is activated. The current plan and Phase 1 handoffs explicitly
state that Phase 2 must not start in this workstream.

### R11 automated verification

```bash
PIP_NO_INDEX=1 make verify-platform-phase1 \
  BOOTSTRAP_VENV=/private/tmp/platform-p1-r6-qa.Ff4OMP/venv \
  DAY0_VENV=/Users/lorenzocc/Developer/servicefabric-lab/state/venvs/thesis-sprint
```

Result: **PASS** — environment, repository, exact ServiceFabric pin, package,
diff, and `48 passed in 3.23s`.

```bash
PIP_NO_INDEX=1 make test-application test-architecture \
  DAY0_VENV=/Users/lorenzocc/Developer/servicefabric-lab/state/venvs/thesis-sprint
```

Result: **PASS** — `104 passed in 17.67s` for application tests and
`105 passed in 1.57s` for architecture tests. `git diff --check` also passes.

### R11 verdict

**Accept bookkeeping commit
`ff28b251b46154bb323d5acb12512990ee1cfe47`.** It truthfully records the R10
acceptance of exact Phase 1 implementation candidate
`a68ef6fce9d39f5341fa8675c093db2eba95aed6` without changing that
implementation. The programme remains stopped after Phase 1; this verdict does
not authorize or begin Phase 2.
