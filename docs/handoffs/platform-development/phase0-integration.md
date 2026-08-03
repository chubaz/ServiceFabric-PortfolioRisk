# Phase 0 integration handoff — synthesis candidate

- Lane: integration
- Branch: `integration/platform-development`
- Baseline: `81660bd3d4be9c8fb6725e5836e7821f9947eb17`
- Lifecycle: `PLATFORM-P0`, synthesis wave active
- Pull request: #20 (draft)

## Lifecycle and accepted audit evidence

The prior thesis stream was closed honestly before this workstream began: PR #18
merged to `main` after all required checks passed, the optional 270-call panel
and human scientific QA remain not run, and no research-ranking claim was made.

The three Phase 0 audit candidates were ancestry- and exact-path-validated,
read in full, and accepted into integration:

| Lane | Integration commit | Accepted result |
|---|---|---|
| canonical decisions | `e3acab1` | Twenty P0/Before-v1 decisions normalized; sixteen accepted and four modified; canonical reuse boundary recorded |
| storage and runtime | `29e2147` | Twenty-five Labs endpoints and five persistence models classified; ServiceFabric registry/artifact projections preferred |
| UI, profiles, and policy | `6883427` | Four-part truth disclosure and evidence-to-effect terminology specified; development controls require server enforcement |

## Canonical synthesis

1. ServiceFabric generic registry, invocation, result, evidence, artifact, and
   operation contracts remain the reusable infrastructure.
2. PortfolioRisk retains domain semantics for portfolio context, mandate,
   Environment Risk Context, findings, decision proposals, decisions, and
   simulated PortfolioEvents.
3. Adapters and projections connect those layers. Phase 0 does not introduce a
   second generic run, registry, artifact, or context object.
4. The visible lifecycle uses strict language:
   evidence -> finding -> decision proposal -> decision -> effect.
5. Development, experimental, and production meanings must not be inferred from
   styling or route names; the server supplies an explicit operating boundary.

## Visible increment

The Labs shell now presents an always-visible truth strip with four independent
dimensions:

- operating profile;
- data origin and point-in-time qualification;
- authority and external-effect boundary;
- persistence and publication state.

The strip is a server-defined response projection, not a new domain object. It
distinguishes licensed historical data from synthetic behavior fixtures and
explains mixed simulated-cycle inputs. Agent test folders are explicitly
temporary and deletable rather than published registry assets.

The isolated Agent run no longer releases a review checkpoint by default. When
the user deliberately enables the effect-free test-harness release, receipts
record `test_harness`, `human_approval: false`, the development profile,
findings/proposals-only authority, no external effects, and the persistence
class. UI copy no longer describes this as human approval or auto-clearance.

The first independent QA review (`aa9ce2c`, preserved in integration as
`96d610f`) returned **FAIL** and was not overridden. Its three bounded findings
have been corrected for a fresh review:

- a threshold crossing now creates an immutable decision proposal; an
  identified human resolver creates a separate decision and a separate
  consequence receipt, all with empty portfolio/external effects;
- code-defined Agent scenarios are now `synthetic_behavior_sample` throughout
  input preview, source context, run result, and saved manifest, with
  `reviewed_fixture: false`;
- the integration lane grant now explicitly includes the application and
  application-test paths already assigned by P0-04, and an architecture test
  validates the actual visible-synthesis commit against that grant.

## Verification evidence

- Python compilation for the changed runtime modules: PASS.
- `node --check apps/portfolio-risk-workbench/labs/labs.js`: PASS.
- focused application and architecture tests: 14 passed.
- `make verify-platform-phase0`: PASS, 25 tests.
- `make test-application`: PASS, 95 tests.
- `make test-architecture`: PASS, 100 tests.
- `make verify-thesis-current`: PASS after GitHub Actions exposed and the
  candidate corrected a squash-merge-era Day 1 lane-ancestry assertion. The
  historical regression suite still runs; obsolete specialist-range validation
  runs only while the Thesis programme owns the active pointer.
- package manifest hashes refreshed and checked: PASS.
- `git diff --check`: PASS.
- fresh local service on port 8878: health, catalogue, portfolios, agent runs,
  and agent runtime endpoints returned successfully.
- Agent input-preview API returned `synthetic_behavior_sample`,
  `reviewed_fixture: false`, and a `synthetic://` source reference.
- in-app browser desktop inspection: PASS.
- 740px responsive inspection: four cells visible in a two-by-two grid.
- amended Agent/cycle inspection: corrected truth values, simulated report
  title, proposal label, consequence-aware resolution actions, and default-off
  checkpoint verified.

## Unresolved decisions and latest safe point

These remain decision-register items rather than hidden implementation choices:

- minimum mandatory proposal core (`DEC-002`): before Decision v1;
- D4 experimental substitution boundary (`DEC-013`): before automated
  experimental decisions;
- supra-agent substitution and veto policy (`DEC-014`): before automated
  experimental decisions;
- typed versus bounded agent-built ERC content (`ERC-027`): before ERC v1;
- placement of the portfolio-applied environment layer: before Overall Context
  v1;
- cross-experiment ERC ancestry: before multi-experiment execution;
- final `OperatingProfile` naming: before reusable registry publication.

No unresolved item blocks this disclosure-only Phase 0 increment. All do block
the corresponding downstream authority or persistence surface.

## Deviations and limitations

The roadmap remains directional rather than exhaustive. Phase 0 also owns CI
continuity, decision normalization, vertical-slice regression safety, and
visible provenance/profile boundaries. This candidate does not create mandate,
ERC, decision, registry, Studio-Codex, adapter, or experimental execution
features; it establishes the boundary those later slices must respect.

The development workbench still contains legacy browser-local drafts. The truth
strip discloses that state; it does not silently promote them to governed assets.

## Rollback

Revert the Phase 0 synthesis commit. The merged `main` baseline, accepted audit
handoffs, and deferred Thesis Sprint record remain intact. No licensed data or
saved local run is mutated by the increment.

## Next action

Commit and push the bounded correction, fast-forward the independent QA
worktree, and run a fresh P0-05 review. Move the active wave to acceptance only
after a new PASS handoff is validated; do not mark the draft pull request ready
before that gate.
