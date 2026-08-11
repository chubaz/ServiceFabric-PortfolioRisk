# STUDIO-S4 — experiment-run evidence audit

- Status: implementation complete and locally verified; candidate commit pending
- Parent boundary: accepted PLATFORM-P3 Experiment Workspace and PLATFORM-P6 structural correction
- Predecessor: STUDIO-S3 Agent Studio experimental-run evidence
- Verification: `make verify-studio-foundation-s4`
- External financial effects: disabled

## Outcome

Give the Experiment Workspace one reliable process for deciding whether two
retained runs may enter a thesis comparison. The process audits every declared
file through the existing immutable Artifact Repository, identifies intended
and unintended differences, and produces a reviewable acceptance record whose
revision requirements feed the next object-development cycle.

This slice does not add another experiment, run, metric, agent, or storage
object. It composes the existing `ExperimentSet`, retained-run
`ArtifactManifest`, integrity verification, and Studio–Codex skill boundary.

## First visible slice

1. Select two retained run artifacts as baseline and counterfactual.
2. Declare the dimensions intentionally changed by the comparison.
3. Verify the complete file inventory and every content digest before reading
   any result as evidence.
4. Extract a small, explicit comparison key from retained run metadata.
5. Block the pair when an undeclared dimension changed, a required control is
   missing, or either retained bundle fails integrity verification.
6. Distinguish a mechanically comparable pair from a thesis-ready pair. Thesis
   readiness additionally requires explicit research-question, baseline-step,
   information-regime, risk-outcome, and metric-definition identities.
7. Record an acceptance, revision-required, or rejection decision as a retained
   evidence artifact. A later record may supersede it without erasing history.
8. Provide a project-local Codex skill that applies the same gate and never
   silently compares unretained or incomplete folders.

## Comparison contract

- The Artifact Repository is the file-authority boundary. A directory listing
  or browser payload is not proof of bundle completeness.
- Every declared file receives exactly one status: same, changed, left-only,
  or right-only.
- `comparison_id`, scenario, portfolio, as-of boundary, data truth, output
  contract, agent definition, execution mode/model, input, and input provenance
  are comparison dimensions when present.
- Planned variable dimensions are explicit. All other observed changes are
  confounds and block pair comparability.
- Missing thesis-design identities produce `revision_required`; the comparison
  service does not invent them from prose or filenames.
- The gate compares evidence and design identity. It does not calculate effect
  sizes, causal estimands, statistical significance, or declare a winning
  framework.

## Acceptance cycle

```text
retained run pair
  -> integrity and inventory audit
  -> comparison-key gate
  -> acceptance record
  -> isolate failed object or missing design identity
  -> revise in the owning Studio through an approved Studio–Codex brief
  -> rerun and retain
  -> superseding acceptance record
```

An acceptance record names both immutable run artifacts, the comparison
digest, planned variables, blockers, warnings, verdict, reviewer rationale,
and next-revision requirements. `accepted` is denied unless the pair is
thesis-ready at the time the record is created.

## Studio–Codex boundary

The project-local `audit-servicefabric-experiment-run` skill may read retained
run metadata and files through the Artifact Repository, run focused tests, and
write a comparison report only to an explicitly approved output path. It may
not alter run evidence, fabricate missing design identities, register a
candidate, activate an object, change experiment state, merge a worktree, or
publish a finding.

When an acceptance record identifies an object defect, the Experiment
Workspace routes the next revision to that object's owning Studio. The owning
Studio selects its object-building skill and produces a separately approved
Studio–Codex proposal; the audit skill is not an object builder.

## Exit gates

1. A retained run with a missing or changed blob cannot pass the gate.
2. All declared files appear in the comparison result exactly once.
3. Undeclared factor changes block pair comparability.
4. Missing thesis-design identities remain visible and block `accepted`.
5. Acceptance records are immutable evidence artifacts and can form an
   explicit supersession chain.
6. The browser performs no host-path reads and sends no shell command.
7. The project-local skill validates and returns the same comparison semantics
   as the application service.
8. Focused contract, repository, API, and browser tests pass.

### Slice 1 implementation note — 2026-08-10

Implemented the retained-run comparison kernel in `risk_artifacts`, including
complete inventory classification, internal restricted-file verification,
predeclared-variable enforcement, pair-comparable/thesis-ready separation, and
deterministic comparison digests. The Experiment Workspace now exposes one
guided baseline/counterfactual gate and records reviewed outcomes as immutable
evidence artifacts with explicit supersession cycles. The project-local
`audit-servicefabric-experiment-run` skill applies the same kernel and routes
object defects back to their owning Studio without repairing them itself.

Focused contract and application tests pass. A browser fixture verified the
empty state, two-run selection, predeclared agent-definition treatment, the
revision-required result, complete four-file classification, and creation of a
cycle-1 acceptance followed by a visible cycle-2 supersession action. The
fixture correctly remained not thesis-ready because the five explicit
methodology identities were absent.

## Closure record — 2026-08-10

The bounded S4 slice is closed to feature development. Its deterministic gate,
Artifact Repository integration, immutable acceptance/supersession cycle,
Experiment Workspace UI and project-local audit skill satisfy the eight exit
gates above. The focused S4 verification target passed 34 tests plus Python
compilation, JavaScript syntax, manifest-integrity and diff checks. This is the
authoritative local gate. This closure does not claim that the dirty integration worktree is an
immutable or merged candidate; an exact candidate commit remains required
before programme-level acceptance.

No scheduler, experiment worker, metric estimator, causal inference engine or
automatic object repair is admitted by this closure. Those controls remain
unavailable until separately versioned contracts and tests exist.

## Non-goals

- no experiment generator, RCT designer, causal estimator, metric kernel, or
  batch worker;
- no automatic selection of a baseline, counterfactual, or winning system;
- no change to Agent Studio run execution or legacy-run admission;
- no automatic object repair, Registry transition, worktree merge, or external
  publication;
- no historical or licensed-data access outside already retained evidence.
