# Phase 1 independent QA

- Task: P1-05
- Current review: R5
- Reviewed candidate: `b483e4ea37170b3bff4b67f6a0436e5ad4a1c326`
- Review branch: `review/platform-p1-independent-qa-r5`
- Accepted Phase 0 baseline: `21339db19357277ca9a9a1ca50107f1a884d7aeb`
- Pinned ServiceFabric gitlink: `7632b61d94a966346f95eb6c5bb2a5ea27f3bc14`
- Current verdict: **BLOCKED**
- Repair authority: integration only

## Executive result

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

## Acceptance decision, rollback, and next action

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
