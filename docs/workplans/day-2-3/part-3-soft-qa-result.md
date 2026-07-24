# Day 2–3 Part 3 Human-QA Result

- Reviewer: `Human QA reviewer`
- Reviewed at: `2026-07-24T00:00:00Z`
- QA run: `20260724T134653Z`
- Branch: `integration/day2-3`
- Reviewed head: `cd450447117b8324e1e698953fd502df7fa6ef7e`
- Decision: **PASSED**
- Local evidence root: `state/day23/final-qa/20260724T134653Z`
- Part 2 evidence-manifest SHA-256: `9c4a57f9e3a84893fe19323ecd5886fd4a2d9ceaf5328d79c339c28a5410cd84`
- Manual-checklist SHA-256: `f8f9bae93da7056e415db23e3a68d9f4039d6109b5f7e818076e8ba4f379cbc7`

## Automated release gates

- Exact fresh checkout: PASS
- ServiceFabric submodule pin: PASS
- `make verify-d23-current`: PASS
- `make demo-d23-part2`: PASS
- Independent evidence and digest validation: PASS
- `make servicefabric-d23-part2-smoke`: PASS
- ServiceFabric post-stop rejection: PASS
- Process cleanup: PASS
- Manifest and whitespace validation: PASS
- Required GitHub workflows at reviewed head: PASS

## Human workflows reviewed

- Research and personal local-private profiles
- Part 1 datasets, revisions, provenance, freshness, quality, and publication state
- Fixed query manifests, point-in-time filtering, and date-effective crosswalk
- Portfolio-data context and local event availability
- Immutable monitoring policy and four-agent contextual monitoring run
- Evidence-backed draft alert, deterministic replay, and abstention
- One-to-one evaluation methodology and descriptive metrics
- HTML and Markdown reports
- Keyboard, accessibility, responsive presentation, and prohibited-interface boundaries

## Deterministic evaluation reviewed

- True positives: `1`
- False positives: `1`
- False negatives: `1`
- Precision: `0.5`
- Recall: `0.5`
- Replay steps: `3`
- Final replay step: abstained
- Point-in-time rule: `available_at <= as_of`
- Ticker/fuzzy fallback: disabled
- Human review: required
- External effects: none

## Visual evidence

- Saved HTML and API evidence retained; no screenshot file recorded.

## Findings

None recorded. The previously observed missing-run template error was corrected before this decision.

## Accepted limitations

- All deterministic records are fictional synthetic data.
- Evaluation uses a deliberately small labelled sample.
- Precision and recall do not establish predictive or commercial performance.
- Monitoring and replay are explicit foreground actions; there is no scheduler.
- There is no external provider, LLM, arbitrary SQL, notebook execution, fuzzy matching, or look-ahead.
- There is no broker, account, order, trade, hedge, optimization, or automatic rebalance effect.
- Reports are local HTML and Markdown review artifacts.
- This review does not impersonate supervisor approval.

## Release authorization

The reviewer authorizes PR #17 to leave draft status and merge into `main`
after the release-documentation inconsistency is corrected and all required
checks pass on the final head.
