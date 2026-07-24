# Day 2–3 Phase 1 data-experience handoff

- Lane: `experience`
- Branch: `feature/day2-data-experience`
- Base: `day1-complete` (`627a08b`)
- Head: working tree based on `7b4ae37`; no commit or push was requested or created

## Changed paths

- `apps/portfolio-risk-workbench/**`
- `tests/application/test_workbench.py`
- `docs/handoffs/day-2-3/experience.md`

No root dependency, Makefile, CI, shared control-plane, another specialist
package, or `vendor/servicefabric/**` path was changed.

## Delivered

- Human-readable `/data` overview plus governed import, preview, immutable
  snapshot list/detail, crosswalk, fixed-query catalogue, and bounded query
  screens.
- Browser-safe CSV/Parquet byte upload with a 1,000,000-byte parser and service
  limit, no filesystem-path input, explicit rights/publication selection,
  digest plus checkbox confirmation, no default landing retention, and a
  visible CLI boundary for larger files.
- A narrow Workbench adapter over the integrated `ResearchDataPlane`; parsing,
  mapping, units, transformations, point-in-time eligibility, quality,
  crosswalk construction, and fixed query execution remain package-owned.
- APIs for previews/confirmation, immutable datasets, crosswalks, reviewed
  manifests, fixed queries, and snapshot quality. Browser/API projections omit
  absolute source, normalized, curated, manifest, quality, and evidence paths.
- Provider presentation that distinguishes reviewed synthetic local input,
  locally licensed exports requiring explicit review, and network-disabled
  providers without enablement or credential-entry controls.
- Effect-free `data.provider.catalog`, `data.import.preview`,
  `data.dataset.list`, and `data.query.fixed` action routes with rights,
  network, human-review, and limitation disclosures.
- Packaged copies of the three integrated reviewed mapping catalogues for the
  hosted Workbench; tests require byte-for-byte equality with data-owned
  sources.
- Updated application source declarations/hashes and the integrated
  `risk_data` source digest in `risk-package-lock.json`.

## Tests executed

- `make preflight` — PASS (the first sandboxed attempt could not download
  pinned dependencies; the approved network-enabled retry passed)
- Focused Phase 1 application tests — PASS, 5 tests
- `make test-d23-experience` — PASS, 81 tests
- `make test-application` — PASS, 81 tests
- Application manifest declaration/hash check — PASS
- `git diff --check` — PASS

## Evidence produced

- Application tests cover semantic HTML, CSV preview, invalid schema, licensed
  rights requirement, explicit digest/checkbox confirmation, immutable
  snapshot response, crosswalk rendering, point-in-time `as_of`, warning and
  blocking missing availability, maximum result size, absence of SQL/provider
  enablement/filesystem-path inputs, no network access, prohibited effect-route
  absence, preserved JSON APIs, effect-free actions, catalogue equality, and
  complete manifest declarations/hashes.
- Confirmed imports write only package-owned immutable local data-plane
  artifacts. Browser staging is outside Git; invalid preview bytes and
  successfully confirmed bytes are removed, and raw landing retention remains
  false.

## Deviations

- None from Phase 1 scope. No portfolio mapping or analytics was added for the
  new research datasets.

## Review defects resolved

- Licensed imports are rejected by the public research profile, hidden from
  its import controls and snapshot lists, and rendered with private-profile
  disclosures on direct preview, dataset, crosswalk, and query links.
- Staging identity now covers the complete preview request, preventing cleanup
  collisions between equal bytes carrying different dataset, mapping, rights,
  publication, or profile metadata.
- Cached idempotent confirmation removes source bytes recreated by an exact
  re-upload before returning the immutable prior receipt.
- Structured query forms carry an explicit reviewed identifier type so
  `entity_id`, `permno`, `gvkey`, and `dataset_id` are not collapsed to the
  first manifest parameter.
- Research storage failures use a bounded message in HTML and JSON/action
  responses and never render an absolute server path.

## Blockers

- None.

## Limitations

- Browser imports are capped at 1,000,000 bytes; the reviewed local CLI is the
  intended large-file path.
- Confirmable browser previews require temporary local byte staging until
  confirmation. Abandoned-preview expiry and multi-writer locking are deferred.
- The integrated immutable snapshot contract does not expose exact observed or
  availability ranges. The detail screen states that absence explicitly and
  does not inspect Parquet or infer values in the application.
- Provider network access, arbitrary SQL, notebook execution, credentials,
  broker connectivity, orders, trades, rebalancing, and public licensed-row
  reporting remain unavailable.

## Rollback

Revert the Workbench application, application-test, and this exact handoff
changes. External immutable research snapshots remain local owner-controlled
artifacts; rollback does not edit or overwrite them.

## Recommended next action

Integration should review the browser staging lifecycle and API projections,
confirm the packaged mapping catalogues match the accepted data-platform
revision, then run `make verify-d23-phase1` before accepting a candidate
commit.
