# KP-05: Supervisor Demo Pack and Day 1–3 Backlog

Status: draft; review requested. Implementation status: partial. Draft deadline: T+20h; review deadline: T+24h.

## Supervisor demonstration sequence

1. Load the deterministic YAML catalogue and show KP-00 through KP-05 with T0-relative deadlines, source references, artifact links, implementation status, and immutable review history.
2. Show deterministic dependency traversal for KP-05 and identify its blocking prerequisites. This is planning state, not an authorization to execute work automatically.
3. Resolve deadlines from a supplied timezone-aware T0, then show the review queue, due products, and overdue products. No personal local timestamp is embedded in a seed.
4. Record a sample review decision as a new immutable product value and show that the prior record is unchanged. Review decisions remain tied to their knowledge-product ID.
5. Open the generated [supervisor one-page draft](supervisor-one-page.md), which is rendered from the validated catalogue and lists review-ready products, blockers, requested decisions, and limitations.
6. If the integrated vertical-slice evidence is available, demonstrate only its documented synthetic/local behavior through the canonical runtime. Do not treat a draft finding or alert as investment advice, and do not perform a consequential action.

## Implementation evidence

- `packages/risk_planning/src/risk_planning/models.py`: frozen Pydantic v2 planning records; acyclic dependency validation; supplied-T0 deadline resolution; review queues; immutable review decisions; artifact and thesis-traceability validation.
- `packages/risk_planning/src/risk_planning/catalog.py`: deterministic lexical YAML loading into a validated catalogue.
- `packages/risk_planning/src/risk_planning/render.py`: deterministic source for the supervisor one-page draft.
- `tests/planning/test_catalog.py`: focused checks for seed loading, dependency safety, deadlines, overdue state, review queues/history, artifact links, and traceability.
- `packages/risk_capabilities/src/risk_capabilities/catalog.py` and `packages/risk_agents/src/risk_agents/roles.py`: the finite capability and role-card evidence summarized in KP-04.

## Known limitations

- The supervisor page is a generated draft, not an application approval or operational dashboard.
- No real CRSP, Compustat, WRDS, market-data provider, portfolio account, broker connection, order flow, or external LLM is demonstrated.
- Planning status and a prepared draft do not establish correctness, completeness, data quality, or investment suitability.
- This document makes no claim that soft QA has passed. Soft QA remains an explicit future review activity.
- Dependencies may be intentionally blocked until their prerequisites are approved; this is visible state, not a failure converted to zero.

## Day 1–3 backlog

1. Integrate the approved planning catalogue and generated supervisor view into a canonical ServiceFabric-hosted application route.
2. Add reviewed local-only synthetic ingestion and query-manifest surfaces, retaining quality flags and source provenance.
3. Exercise the capability/agent role cards only through the canonical runtime and add integration evidence for their explainability disclosures.
4. Define and run a supervisor-approved soft-QA plan; record its criteria and outcome separately rather than inferring a pass from focused tests.
5. Design provider access only after legal, rights, credential-reference, storage-zone, and publication reviews; do not enable external access by default.

## Decisions requiring supervisor input

- Are the four role-card grants and prohibited effects sufficient for the intended Day 1–3 review scope?
- Which synthetic scenarios and quality states must the first supervisor-facing display cover?
- What evidence and acceptance criteria define a future soft-QA gate?
- Which backlog item has priority after the current review, acknowledging that none authorizes orders, broker connectivity, rebalancing, licensed-data publication, or investment advice?

## Review gate

Each backlog item requires architecture, safety, and where applicable rights review. The generated one-page representation remains draft until a supervisor explicitly approves a reviewed revision.
