# Phase 1 Registry catalogue UI audit

- Status: complete read-only audit
- Lane: P1-02 — registry catalogue UI
- Branch: `feature/platform-p1-registry-ui`
- Programme baseline: `21339db19357277ca9a9a1ca50107f1a884d7aeb`
- Audited head before this handoff: `535c427ad7880582db07a9fa5b1ac9e6409c7230`
- Implementation authority: none; this lane changes only this handoff

## Executive recommendation

Add one **Registry** workspace to the existing Labs shell. It should be a compact master-detail catalogue, not another creation studio and not a file repository. Its default experience is:

1. discover definitions from approved existing source adapters without writing anything;
2. search and inspect those discovered definitions;
3. explicitly preview and index selected definitions into persistent local development storage;
4. inspect source, digest, provenance, compatibility, lineage, and lifecycle receipts;
5. compare indexed versions of the same definition;
6. apply only server-validated lifecycle transitions after a consequence preview.

The workspace must repeat a simple distinction throughout:

```text
Canonical source definition
        ↓ discovered by a read-only adapter
Discovery preview                     no persistence
        ↓ explicit user confirmation
Local registry projection             metadata + pointer + digest
        ↓ validated transition
Append-only lifecycle receipt          source definition remains unchanged
```

An indexed record is not a copied definition, executable installation, artifact, or production deployment. The Registry stores and displays a local development projection. The source remains authoritative.

## Critical terminology

### Three independent states

Never compress these dimensions into one status badge:

| Dimension | Values | Meaning |
|---|---|---|
| Discovery | `Discovered` / `Source unavailable` | Whether an approved adapter found the definition at its canonical source during the latest preview. |
| Index presence | `Discovered only` / `Indexed` | Whether a persistent local registry projection exists. |
| Lifecycle | server-provided values such as `Candidate`, `Validated`, `Published locally`, `Deprecated`, `Retired`, `Archived` | The governed state of an indexed version. It does not exist for a discovered-only item. |

The UI must never show a discovered-only item as `Draft`, `Candidate`, or `Unpublished`; those are lifecycle interpretations that require an indexed record. It must never infer lifecycle from a source path, Git state, test result, or digest.

### Required language

| Concept | Use | Avoid |
|---|---|---|
| Workspace | **Registry** in navigation; **Definition Registry** in the page heading | Capability registry, asset store, marketplace |
| Discovery | **Preview source definitions** | Import, sync, migrate automatically |
| Persistence | **Index in local development registry** | Save agent, install, deploy, publish to production |
| Indexed object | **Registry projection** | Canonical copy, registry-owned definition |
| Publication | **Published locally** and supporting text `Published to the local development registry; not deployed or externally distributed.` | Published, production-ready, live |
| Source change | **Source changed since indexed observation** | Registry out of date, update available |
| Index refresh | **Preview re-indexing** | Overwrite, replace current version |
| Definition kind | Agent, Capability, Evaluation, Report, Dashboard, Scenario, Workflow | Artifact unless it is actually a later artifact-repository object |
| Failure | **Unavailable** or **Failed**, according to the Phase 0 vocabulary | Empty, zero definitions when discovery failed |

There is already a runtime `CapabilityRegistry` used to invoke reviewed capabilities. The new user-facing Definition Registry is a catalogue of definitions across seven kinds. Copy and help text must prevent users from assuming that indexing a capability makes it executable or grants it to an agent.

## Navigation and route

Add the workspace tab after **Agent graph** and before **Simulated cycle**:

```text
Database · Portfolio · Agent · Agent graph · Registry · Simulated cycle · Full experiment
```

Exact route:

```text
?workspace=registry
```

Required navigation behavior:

- `registry` joins the allowed workspace names in initialization and routing.
- Clicking a workspace updates the URL through the History API.
- Browser back/forward restores the visible workspace without adding another history entry.
- The active tab has `aria-current="page"`; inactive tabs omit the attribute rather than using `aria-current="false"`.
- After route changes, focus may remain on the selected navigation button for pointer/keyboard navigation. A direct URL load places normal document reading order at the Registry heading.
- The horizontal mobile tab strip remains scrollable and scrolls the active Registry tab into view without moving keyboard focus unexpectedly.

This route correction should apply to all existing Labs workspaces rather than creating Registry-only navigation semantics.

## Runtime truth strip

The Registry view uses the existing four-cell Phase 0 truth strip:

| Cell | Exact recommended value |
|---|---|
| Profile | `Development` |
| Data | `Definition metadata · canonical sources remain authoritative` |
| Authority | `Index and lifecycle metadata only · external effects prohibited` |
| Persistence | `Local development registry · survives restart · outside Git · not production publication` |

The truth strip must come from the server-authoritative runtime boundary. It must not be inferred from `?workspace=registry` or local storage.

While the service is unavailable, preserve the existing global failure state and do not claim that indexed records are empty. The page-specific state should say that the registry could not be read.

## Exact page anatomy

```text
┌ Definition Registry ───────────────────────────────────────────────────────┐
│ Find, inspect, and index reusable definitions.              [Status]      │
│ [Local development registry boundary]                 [Preview sources]   │
├ Filters ──────────────────────────────── Results summary ──────────────────┤
│ [Search________________] [Kind ▾] [Index state ▾] [Lifecycle ▾] [Sort ▾]  │
├──────────────────────── Catalogue ──────────────┬──────── Detail ──────────┤
│ ☐ Agent                                          │ Portfolio Event Triage   │
│   Portfolio Event Triage                         │ Agent · 0.1.0             │
│   Discovered only                                │ [Discovered only]         │
│   risk.agent.portfolio_event_triage              │                          │
│                                                   │ Overview                 │
│ ☑ Capability                                     │ Canonical source          │
│   Portfolio exposure                             │ Provenance                │
│   Indexed · Validated                            │ Compatibility / lineage   │
│   portfolio.exposure.summarize                    │ Versions / receipts       │
│                                                   │                          │
│ [Preview indexing (1)]                            │ [Preview index] [Compare] │
└───────────────────────────────────────────────────┴──────────────────────────┘
```

The page uses the existing `.lab-heading`, `.lab-panel`, `.panel-heading`, `.truth-chip`, `.button`, form, and table visual language. Do not introduce a frontend framework, remote asset, new typography family, or visual node canvas.

### Heading

- Eyebrow: `Local development catalogue`
- H1: `Definition Registry`
- Description: `Find, inspect, and index reusable definitions without replacing their canonical sources.`
- Status pill values: `Loading`, `Ready`, `Partial`, `Unavailable`
- Primary action: `Preview source definitions`

Below the heading, show one compact boundary notice:

> Indexing stores metadata, a source pointer, a digest, and lifecycle receipts in the local development registry. It does not copy, run, deploy, or externally publish the definition.

Do not repeat this paragraph on every card.

### Summary row

Show small, text-labelled counts only after a successful response:

- `N discovered`
- `N indexed`
- `N source changes`
- `N unavailable sources`

Unavailable and failed sources are never counted as zero discoveries without an adjacent warning. Counts are derived from server response metadata, not reconstructed from the currently filtered page.

## Filters and selectors

Use one compact toolbar. Every control has a persistent visible label; placeholders are not labels.

| Control | ID / stable test selector | Options and behavior |
|---|---|---|
| Search | `#registry-search` / `registry-search` | Searches display name, stable identifier, kind, tag, and source label. Debounce only network requests; update the result count after the response. |
| Kind | `#registry-kind-filter` / `registry-kind-filter` | `All kinds`, `Agents`, `Capabilities`, `Evaluations`, `Reports`, `Dashboards`, `Scenarios`, `Workflows`. Values/facets come from the server but retain this display order. |
| Index state | `#registry-index-filter` / `registry-index-filter` | `All`, `Discovered only`, `Indexed`. This is not lifecycle. |
| Lifecycle | `#registry-lifecycle-filter` / `registry-lifecycle-filter` | `All lifecycle states`, then server-supported states. Disabled with explanatory text when `Discovered only` is selected. Display `Published locally`, even if the contract value is `published`. |
| Sort | `#registry-sort` / `registry-sort` | `Name A–Z`, `Kind`, `Recently observed`, `Version`. The server owns ordering and tie-breaking. |
| Clear | `#registry-clear-filters` / `registry-clear-filters` | Restores defaults and search focus. Hide or disable when no filter is active. |

Do not add owner, tags, compatibility, date-range, or source-adapter filters in the first visible increment. Those can follow observed use rather than crowding the default toolbar.

The filter state should be serializable in query parameters only if the integration lane can do so consistently. At minimum, preserve `workspace=registry`. Do not store filter policy in the registry.

## Catalogue result item

Use a compact vertical result list rather than a seven-column table or card mosaic. Definition names and status differences need more horizontal room than decorative tiles provide.

Each result is an `<article>` with two separate interactions:

1. a labelled checkbox for batch indexing selection;
2. a button/link that selects the item and opens its detail.

Do not put a checkbox inside a button.

### Information hierarchy

Always visible:

1. plain-language kind;
2. display name;
3. stable canonical identifier and definition version;
4. index-presence badge;
5. lifecycle badge when indexed;
6. one-line purpose or source summary.

Visible when relevant:

- `Source changed` warning;
- `Source unavailable` error;
- compatibility warning count;
- validation warning count.

Not shown on the card:

- full digest;
- full filesystem path;
- raw manifest;
- full lineage graph;
- lifecycle history;
- report/run files.

For discovered-only items, exact helper copy is:

> Found at its canonical source. No persistent registry projection exists yet.

For indexed items:

> Local metadata projection. The canonical source remains authoritative.

Batch checkboxes are enabled only for definitions the server marks indexable. Already indexed unchanged items and unavailable sources are not selectable. Their disabled reason is available as visible text or an accessible description.

## Detail panel

The detail panel opens with the first item after a successful list response, or the user's selected item. Its heading shows:

- display name;
- kind and definition version;
- stable identifier;
- discovered/indexed and lifecycle badges;
- one concise purpose statement.

Use four semantic sections. They may be a simple vertical disclosure list; tabs are acceptable only if implemented with complete tab semantics and keyboard behavior.

### 1. Overview

Show:

- definition kind;
- canonical identifier;
- definition version or immutable revision;
- index presence;
- lifecycle state, if indexed;
- source adapter label;
- latest source-observation time;
- compatibility summary;
- lineage summary;
- validation/warning summary.

Primary actions are contextual:

- discovered only: `Preview index`;
- indexed and unchanged: `Compare versions`, `Change lifecycle`;
- indexed with changed source digest: `Preview re-indexing`, `Compare source observations`, `Change lifecycle`;
- unavailable: `Retry source preview`; no index action.

### 2. Source and provenance

Show separately:

- source type;
- repository-relative source locator or other rights-safe canonical locator;
- source definition version;
- full content digest with an explicit `Copy digest` button;
- source observation time;
- discovery adapter and adapter version;
- index receipt identity and index time, if indexed;
- creator/creation method only when supplied by authoritative provenance;
- warnings and source availability.

`View source definition` may load a read-only preview only through the approved source adapter. It must not become an arbitrary local-file reader. Label it:

> Read-only current-source preview; this content is not stored by the registry.

Never expose credentials, licensed rows, absolute private paths, or unreviewed arbitrary files.

### 3. Compatibility and lineage

Compatibility is a readable list grouped as:

- requires;
- provides;
- known compatible versions;
- incompatibilities or unresolved checks.

Lineage is a readable edge list:

```text
This workflow uses Agent Blueprint 0.2.0
This dashboard reads Report Contract 1.1.0
This version supersedes 0.1.0
```

Each linked indexed record opens in the same Registry detail panel. A target not yet indexed is labelled `Source reference only`. Do not render a graph canvas in Phase 1.

Empty copy:

- `No compatibility declarations were supplied by the canonical source.`
- `No lineage relationships are indexed for this version.`

These statements mean unavailable metadata, not universal compatibility or absence of real-world dependencies.

### 4. Versions and lifecycle receipts

List indexed versions newest first, showing:

- definition version;
- digest abbreviation plus full-copy control;
- lifecycle state;
- observed/indexed time;
- source-change indicator;
- `Compare` action.

Below the versions, show append-only lifecycle receipts with prior state, resulting state, server-recorded actor, timestamp, note/reason, and receipt identifier. Never label a transition as a human approval unless the receipt identifies a human approver under the accepted contract.

Raw registry projection JSON may remain under a closed `Developer details` disclosure. Raw JSON is not the primary presentation.

## Discovery and explicit indexing flow

### Preview sources

`Preview source definitions` is read-only. It refreshes discovery observations in the response but creates no persistent registry record unless the contracts lane explicitly defines an append-only discovery observation as persistence. The UI must follow the final contract and truthfully describe that behavior.

Interaction:

1. Set the page region to `aria-busy=true`.
2. Keep existing indexed results visible but visibly stale while refreshing.
3. Announce `Previewing approved definition sources.`
4. Replace results only after a successful response.
5. On partial success, retain successful items and show each unavailable adapter/source separately.
6. Do not auto-select or auto-index new discoveries.

### Index preview

The user selects one or more discovered definitions and activates `Preview indexing (N)`. The server returns the proposed registry projections and all validation outcomes. The UI does not construct canonical IDs, digests, versions, compatibility, or lineage.

Use a native dialog with:

- selected definition count and names;
- source locator and digest per definition;
- whether the operation creates a new index record, observes an unchanged source, or proposes a new immutable version/observation;
- validation warnings and blocked items;
- exact persistence boundary;
- `Cancel` and `Index N definitions` actions.

Exact consequence copy:

> This writes local development registry metadata and append-only receipts outside Git. Canonical source definitions are not copied or changed. Nothing is deployed, executed, or externally published.

Only server-confirmed indexable items can be submitted. If a mixed preview contains blocked items, list them separately and make the confirm count unambiguous.

### Index result

Do not optimistically mark items indexed. After a successful response:

- announce the confirmed indexed/unchanged/blocked counts;
- refresh the selected records from the server;
- select the first newly indexed item;
- show its index receipt;
- preserve filters and scroll position where practical.

If indexing fails:

> Indexing failed. No success is assumed. Existing registry records and source definitions were not changed by this interface.

If the API reports a partial commit, show each receipt and failure exactly; do not collapse it into success. Atomic all-or-none behavior is preferable for a batch unless the accepted contract explicitly defines per-item receipts.

## Lifecycle transition interaction

Do not use an editable lifecycle dropdown directly on cards. A transition is a governed state change with an append-only receipt.

`Change lifecycle` opens a native dialog populated from the server-provided allowed transitions for that exact indexed version.

Dialog contents:

1. definition name, kind, ID, and version;
2. current lifecycle state;
3. one choice among server-allowed target states;
4. readable meaning and consequence of the selected state;
5. required note/reason when the contract requires it;
6. immutable-source and no-deployment boundary;
7. `Cancel` and an explicit confirmation such as `Move to Validated`.

Required publication copy:

> Published locally means available as a reusable definition in this development registry. It does not deploy code, distribute an artifact, grant a capability, or create financial authority.

Required archive copy:

> Archive hides an eligible non-published registry version from the default catalogue. It does not delete its canonical source or lifecycle receipts.

The UI submits the current record revision/ETag supplied by the server. On conflict:

> Lifecycle changed since this dialog opened. Review the current state before trying again.

Never update the badge before the server returns the accepted transition and receipt. Failed transitions use:

> Lifecycle unchanged. The transition was not accepted.

Phase 1 has no delete button, bulk lifecycle transition, rollback, source edit, Git commit, deployment, or execution action.

## Version comparison

`Compare versions` opens an inline comparison region or native dialog. Prefer an inline region on desktop so the source/detail context remains visible; use a full-width dialog on mobile.

Selectors:

- `From version`: an indexed version of the currently selected stable identity;
- `To version`: another indexed version of the same stable identity and kind.

Default to the selected version and its closest prior indexed version. Do not compare unrelated definitions through these selectors; lineage links handle related but distinct identities.

The comparison presents:

1. definition version, digest, source locator, observed time, and lifecycle side by side;
2. a concise change summary supplied by the server;
3. added/removed/changed compatibility declarations;
4. added/removed lineage edges;
5. validation and source-drift warnings;
6. a closed raw projection-diff disclosure for developers.

Lifecycle changes must be visually separated from source-definition changes. A different registry lifecycle receipt does not mean the canonical definition content changed. Conversely, a different source digest must not be described as a semantic change unless an approved adapter provides that interpretation.

Empty state:

> No second indexed version is available for comparison. Index another version or inspect the current source observation.

Comparison is read-only and has no `Accept`, `Merge`, `Restore`, or `Deploy` action.

## Empty, loading, partial, and error states

| State | Heading | Exact supporting copy | Actions |
|---|---|---|---|
| Initial loading | `Loading local registry…` | `Reading indexed projections and approved source adapters.` | None |
| Registry empty before discovery | `No definitions have been previewed` | `Preview approved source definitions. This is read-only and will not index anything.` | `Preview source definitions` |
| Discovered, none indexed | `Definitions found. Nothing is indexed yet.` | `Inspect a definition, then preview and explicitly confirm local development indexing.` | Select items; `Preview indexing` |
| Filter has no matches | `No definitions match these filters` | `Clear one or more filters. Indexed records have not been removed.` | `Clear filters` |
| Source adapters return none successfully | `No source definitions discovered` | `The approved adapters completed successfully but found no eligible definitions.` | `Preview again` |
| Partial discovery | `Some sources are unavailable` | `Successful source previews remain visible. Unavailable sources are not counted as empty.` | `Review unavailable sources`, `Retry` |
| Registry service unavailable | `Registry unavailable` | `The local service did not respond. No index or lifecycle change is assumed.` | `Retry` |
| Index preview blocked | `Selection cannot be indexed` | `Review the validation results. Nothing has been written.` | `Back to selection` |
| Index failure | `Indexing failed` | `No success is assumed. Refresh before retrying.` | `Refresh`, `Retry preview` |
| Transition failure | `Lifecycle unchanged` | `The transition was not accepted. Review the current record and receipt/error.` | `Refresh record` |
| Comparison unavailable | `No comparable version` | `This identity has only one indexed version.` | Close comparison |

Errors should include a safe request/receipt identifier where available, not a raw stack trace or private filesystem path.

## Responsive behavior

### Wide: above 1180 px

- One compact filter toolbar across the page.
- Catalogue/detail grid: `minmax(330px, .75fr) minmax(0, 1.25fr)`.
- Result list has its own bounded scroll only when needed; the selected item stays visible.
- Detail may be sticky below the header and truth strip only if its full content remains reachable without nested-scroll traps.

### Medium: 761–1180 px

- Filters wrap to two rows.
- Catalogue/detail grid becomes approximately `minmax(280px, .8fr) minmax(0, 1.2fr)` until it no longer fits.
- Long source identifiers wrap; action buttons wrap without overlapping badges.
- Comparison stacks the metadata summary but retains clearly labelled From/To columns for changed fields.

### Narrow: 760 px and below

- One column: heading, boundary, filters, result list, detail.
- Selecting a result moves/scrolls to the detail heading and provides a `Back to results` control.
- Filter controls become one or two full-width columns; the primary action is full width.
- Batch action uses a non-obscuring sticky footer only while at least one item is selected; otherwise no fixed footer.
- The version comparison uses a full-width dialog or sequential From/To blocks.
- Digest and identifiers wrap anywhere; never force whole-page horizontal scrolling.
- The global truth strip remains visible in its existing two-by-two layout.

Do not hide provenance, lifecycle, the local-publication qualification, or external-effect boundary at smaller widths.

## Accessibility behavior

1. Use a `<section id="lab-registry" aria-labelledby="lab-registry-title">` consistent with existing Labs pages.
2. The result count is a polite status region. The entire result list is not live; large list replacement should not be narrated item by item.
3. Loading regions use `aria-busy`; error summaries receive focus only after a user-triggered failed action.
4. Each result article has a unique accessible name containing display name, kind, version, index presence, and lifecycle.
5. Batch selection is a `<fieldset>` with a visually available legend such as `Select definitions to index`.
6. Disabled index checkboxes have a programmatic and visible reason.
7. Status badges include text and never rely on teal, amber, or coral alone.
8. All generic buttons, links, summaries, checkboxes, filters, result selectors, dialog controls, and copy buttons need a visible `:focus-visible` style. The current Labs stylesheet only provides a specialized focus rule for the Agent help button; the Registry increment should add the general rule without regressing existing pages.
9. Native dialogs preserve focus, close on Escape, and return focus to the opening control. Initial focus should be on the dialog heading or Cancel, not the confirm action for lifecycle changes.
10. If detail sections are tabs, implement arrow-key navigation, `role=tab`, `aria-selected`, `aria-controls`, and associated `tabpanel`. Simple headings/disclosures are safer for the first increment.
11. Source code and raw JSON previews have an accessible name and keyboard-scrollable container.
12. Truncated visual text must have an adjacent accessible full value or copy action; do not rely on `title` alone.
13. Minimum interactive target height remains the existing 40 px button standard. Critical status/provenance copy should not use the current 7–8 px microtype.

## Stable selectors for implementation and tests

Use stable `data-testid` values in addition to semantic HTML. Dynamic identity belongs in `data-registry-id`, never in CSS classes or text matching.

| Purpose | Selector |
|---|---|
| Workspace navigation | `[data-testid="registry-tab"]` |
| Page root | `[data-testid="registry-workspace"]` |
| Page status | `[data-testid="registry-status"]` |
| Boundary notice | `[data-testid="registry-boundary"]` |
| Preview sources | `[data-testid="registry-preview-sources"]` |
| Summary | `[data-testid="registry-summary"]` |
| Search | `[data-testid="registry-search"]` |
| Kind filter | `[data-testid="registry-kind-filter"]` |
| Index filter | `[data-testid="registry-index-filter"]` |
| Lifecycle filter | `[data-testid="registry-lifecycle-filter"]` |
| Sort | `[data-testid="registry-sort"]` |
| Clear filters | `[data-testid="registry-clear-filters"]` |
| Results and count | `[data-testid="registry-results"]`, `[data-testid="registry-result-count"]` |
| Result item | `[data-testid="registry-item"][data-registry-id]` |
| Item selector | `[data-testid="registry-item-select"][data-registry-id]` |
| Detail opener | `[data-testid="registry-item-open"][data-registry-id]` |
| Detail | `[data-testid="registry-detail"]` |
| Source preview | `[data-testid="registry-source-preview"]` |
| Batch preview | `[data-testid="registry-preview-index"]` |
| Index dialog/confirm | `[data-testid="registry-index-dialog"]`, `[data-testid="registry-index-confirm"]` |
| Version compare | `[data-testid="registry-compare-open"]`, `[data-testid="registry-version-from"]`, `[data-testid="registry-version-to"]`, `[data-testid="registry-diff"]` |
| Lifecycle dialog | `[data-testid="registry-transition-dialog"]` |
| Lifecycle target/note | `[data-testid="registry-transition-target"]`, `[data-testid="registry-transition-note"]` |
| Lifecycle confirm | `[data-testid="registry-transition-confirm"]` |
| Receipt list | `[data-testid="registry-receipts"]` |
| Empty/error state | `[data-testid="registry-empty"]`, `[data-testid="registry-error"]` |

Tests should prefer roles, labels, and accessible names for user behavior. These selectors are escape hatches for dynamic catalogue state and stable architecture assertions.

## Minimum UI-facing service contract

The UI should consume view models from the integration-owned Registry API. It must not rebuild registry semantics in JavaScript. Each list/detail response needs enough information to render:

- stable registry record identity, if indexed;
- canonical definition identity and kind;
- display name and short purpose;
- definition version/revision;
- discovered/indexed state;
- lifecycle label/value only when indexed;
- source adapter, safe source locator, source observation time, and source availability;
- content digest and source-change comparison;
- indexability plus blocked reason;
- warning/error state;
- compatibility and lineage summaries;
- allowed lifecycle transitions and current concurrency revision;
- relevant receipt identities.

Facet counts, allowed transitions, comparison summaries, source-drift decisions, and validation outcomes must come from the server. The browser can format and filter already returned display data, but it must not invent missing domain semantics.

Recommended API interaction shapes, subject to the contracts audit:

```text
GET  registry catalogue + facets
POST source preview / discovery
GET  one projection + source/provenance/versions/receipts
POST index preview
POST confirmed indexing
GET  version comparison
POST lifecycle transition with current revision
```

The UI must remain resilient if the final endpoints differ. Behavior and truthful states matter more than these illustrative route names.

## Focused test plan

### Static/architecture assertions

1. `registry` exists in the navigation, route allowlist, and runtime truth views.
2. The Registry truth strip says Development, canonical sources authoritative, metadata-only authority, external effects prohibited, persistent local storage outside Git, and not production publication.
3. Primary Registry copy contains `index`/`indexed`, not `import`, `install`, or unqualified `publish`.
4. The initial seven kinds are present in the required order.
5. Stable selectors above exist.
6. No delete, deploy, execute, run, broker, order, trade, hedge, rebalance, portfolio mutation, Studio–Codex, or arbitrary-file control is introduced.
7. Generic `:focus-visible` support exists.

### Application/API tests

1. A successful source preview creates no indexed record without explicit confirmation.
2. A discovered-only response renders no lifecycle state.
3. Explicit indexing updates the list only from the server response and displays an index receipt.
4. Restarting the local service retains indexed projections.
5. A source digest change renders `Source changed since indexed observation`; it does not silently overwrite or claim semantic change.
6. A failed/unavailable adapter is not reported as zero definitions.
7. Search and every filter produce server-consistent result/facet counts.
8. Detail shows a rights-safe source pointer, full digest, provenance, compatibility, lineage, and receipt history without embedding the source payload in the registry response.
9. Version compare rejects different stable identities and separates lifecycle-only changes from source changes.
10. Transition choices exactly match server-allowed transitions.
11. A successful transition displays the append-only receipt and refreshed state.
12. A stale revision receives a conflict message and does not optimistically alter the lifecycle badge.
13. `Published locally` always includes its no-deployment qualification.

### Interaction/accessibility tests

1. `?workspace=registry` loads the Registry and marks only its tab current.
2. Tab clicks, browser back, and browser forward preserve URL and visible workspace.
3. Search, filters, result selection, batch selection, detail disclosures, comparison, and dialogs work by keyboard.
4. Focus returns correctly after cancel/confirm; a user-triggered error summary receives focus.
5. Loading and result-count updates are announced once without reading the entire list.
6. All badges retain text meaning without color.
7. At 760 px and below, filters, cards, detail, identifiers, dialogs, and compare output do not overlap or cause whole-page horizontal scrolling.
8. Registry tab and truth strip remain discoverable in the mobile header.

### Regression

Run at minimum:

```bash
pytest tests/application/test_labs_runtime.py
pytest tests/application/test_workbench.py
pytest tests/architecture/test_platform_development_control_plane.py
pytest tests/architecture/test_platform_phase1_control_plane.py
pytest tests/application/test_registry_api.py
pytest tests/registry
make verify-platform-phase1
```

The Registry increment must not change behavior in Database, Portfolio, Agent, Agent graph, Simulated cycle, or Full experiment beyond the shared navigation/history and generic focus improvements.

## Risks and mitigations

| Risk | Consequence | Required mitigation |
|---|---|---|
| Confusing Definition Registry with the capability execution registry | User assumes indexed capability is runnable or granted | Use `Definition Registry`; say indexing does not execute or grant. |
| Treating discovery as persistence | Silent writes and false sense of durability | Discovery is read-only; explicit index preview and confirmation. |
| Treating lifecycle as index presence | Discovered records appear governed | No lifecycle badge until indexed. |
| Unqualified `Published` | User assumes production deployment | Render `Published locally` with no-deployment qualification everywhere. |
| Browser constructs identities or transitions | UI diverges from canonical contracts | Server supplies IDs, validations, facets, allowed transitions, diffs, and receipts. |
| Source change silently overwrites projection | Loss of immutable observation and auditability | Show drift; require preview; let server create the accepted immutable observation/version. |
| Digest dominates the card | Catalogue repeats the prior SHA-only UX problem | Put name/purpose/kind/state first; digest in provenance detail. |
| Raw JSON dominates the page | Poor comprehension | Readable detail first; raw projection under Developer details. |
| Registry becomes an artifact repository | Phase 2 scope leaks into Phase 1 | No run files, reports, datasets, downloads, deletion, or retention controls. |
| Lifecycle action feels consequence-free | Accidental governance change | Native dialog, consequence copy, explicit target label, receipt, concurrency check. |
| Seven tabs crowd mobile header | Registry becomes undiscoverable | Scrollable nav, active tab scroll-into-view, visible focus, no hidden truth strip. |
| Missing source looks empty | False completeness | Separate `unavailable`/`failed` states and successful-result counts. |

## Evidence inspected

- `AGENTS.md`
- `docs/workplans/current.md`
- `docs/workplans/platform-development/phase-1-registry-kernel.md`
- `docs/workplans/platform-development/phase-1/TASK-02-CATALOGUE-UI.md`
- `config/agent/platform-development/phase1-lanes.json`
- `docs/handoffs/platform-development/phase0-ui-policy.md`
- `apps/portfolio-risk-workbench/labs/index.html`
- `apps/portfolio-risk-workbench/labs/labs.js`
- `apps/portfolio-risk-workbench/labs/styles.css`
- `apps/portfolio-risk-workbench/labs/duckdb_server.py`
- `apps/portfolio-risk-workbench/labs/DEVELOPMENT_ROADMAP.md`, especially sections 4 and 11
- `tests/application/test_labs_runtime.py`
- `tests/application/test_workbench.py`
- `tests/architecture/test_platform_development_control_plane.py`
- `tests/architecture/test_platform_phase1_control_plane.py`

## Validation executed

- `python3 -m pytest tests/architecture/test_platform_phase1_control_plane.py -q` — PASS, 5 tests.
- `git diff --check` — PASS before candidate commit.
- Lane path review — PASS; this handoff is the only changed path.
- `make preflight` — BLOCKED after its environment check passed; see the pin mismatch below.

An initial `python -m pytest ...` invocation could not run because this shell has no `python` alias. Re-running the same focused test through `python3` passed.

## Deviations, blockers, and limitations

- `make preflight` did not reach a green repository baseline. Environment validation passed, then the ServiceFabric pin check reported expected `7632b61d94a966346f95eb6c5bb2a5ea27f3bc14` and actual `535c427ad7880582db07a9fa5b1ac9e6409c7230`. This lane did not change pins or repository state.
- This was a source, style, interaction, and test audit. No Registry contract or API implementation was available in this lane, so illustrative API routes and lifecycle examples must be reconciled with P1-01 before implementation.
- Browser visual automation was not necessary for the bounded read-only audit. Existing DOM, CSS, runtime truth, and tests were treated as implementation evidence.
- Exact source line references may shift during integration.

## Rollback

This lane adds only `docs/handoffs/platform-development/phase1-catalogue-ui.md`. Rollback is deletion of that file. No application, registry, source definition, test, runtime, or persistence state is affected.

## Recommended integration sequence

1. Reconcile this UI behavior with the accepted P1-01 registry and lifecycle contract and P1-03 source-adapter inventory.
2. Add the server-owned Registry runtime view and read-only catalogue/discovery API.
3. Add the Registry tab, route, boundary copy, list/detail shell, and all empty/error states.
4. Add explicit index preview/confirmation and receipt rendering.
5. Add detail provenance, compatibility, lineage, versions, and source-drift states.
6. Add read-only comparison and validated lifecycle-transition dialogs.
7. Add route/history, generic focus, responsive, and accessibility tests.
8. Run focused Registry tests, all Labs regressions, Phase 1 verification, and independent QA.

The first implementation should remain compact. A user should understand what exists, where it comes from, whether it is indexed, what changed, and what a lifecycle action means without encountering a creation form or raw manifest first.
