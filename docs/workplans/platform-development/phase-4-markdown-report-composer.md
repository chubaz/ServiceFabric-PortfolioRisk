# PLATFORM-P4 — Markdown report composer

- Status: accepted
- Accepted candidate: `7b20ae45be093b3aec1cddc4fb0b05c1194738aa`
- Integration branch: `integration/platform-report-composer`
- Baseline: `19ccf123bd210eae1763f1fd5a332cfd3cb44d72`
- Roadmap: `apps/portfolio-risk-workbench/labs/DEVELOPMENT_ROADMAP.md`
- Verification: `make verify-platform-phase4`

## Outcome

Make concise, evidence-aware Markdown the primary presentation of analytical
agent work without replacing canonical risk calculations, model receipts, or
capability results. A report is a typed, versioned composition artifact whose
sections can be completed iteratively and rendered safely for human review.

## Visible increment

Agent Run Review and the Daily Portfolio Risk Review gain:

1. a readable single-document report with clear outcome and conclusion;
2. nine planned financial sections, each with status, severity and evidence;
3. visible evidence coverage, repetition, length and completeness checks;
4. safe HTML rendered deterministically from restricted Markdown;
5. persisted `report.json`, `review-brief.md`, and `review-brief.html` files;
6. registered chart/table references that remain inert until separately loaded.

The report composer also exposes typed plan, validate and render endpoints so it
can be exercised independently of a full agent run.

## Architecture boundary

- `risk_analytics.reports` remains the calculation/report source where used;
  `risk_reports` is only a narrative composition and validation layer.
- Model text is untrusted input. Raw HTML, links, scripts and event handlers are
  escaped; the browser displays only output from the versioned safe renderer.
- Evidence IDs are retained from canonical capability receipts or supplied
  context. Missing evidence produces a warning and never a fabricated citation.
- Attachments name an existing artifact/file/digest. Reports do not embed or
  execute chart HTML or JavaScript.
- Section revision is immutable and optimistic: it replaces one section only
  when the expected revision matches.
- Reports are human-review artifacts with `effects: []`; publication remains a
  future governed lifecycle operation.

## Tasks

### A — contracts and composition

Implement strict section plans, report sections, attachment references,
validation results and immutable section revisions. Compile the current Agent
Studio presentation into the recommended nine-section financial structure.

### B — validation and safe rendering

Check required sections, evidence existence, repetition and section length.
Render a deliberately small Markdown subset with all model text escaped.

### C — Agent Run Review integration

Persist the envelope, Markdown and safe HTML with each run. Present the report
as one readable document with section navigation and a compact validation bar.
Keep raw inputs, capability calls, model receipts and reviews inspectable.

### D — focused qualification

Run contract, validation, XSS, API, Agent Studio, artifact compatibility and
browser checks. Defer the next exhaustive cross-phase suite until Phase 5.

## Exit gates

1. A default daily review compiles into exactly nine distinct planned sections.
2. Iterative section updates are revision checked and do not append uncontrolled
   prose.
3. Evidence coverage, repetition, length and missing required sections are
   machine-readable and visible.
4. HTML/JavaScript injection remains escaped in every supported Markdown form.
5. Attachments are digest-bound artifact references, never executable payloads.
6. New run folders contain the report envelope, Markdown and safe HTML while
   legacy admission remains fail closed.
7. The Agent Run Review reads as a financial document and retains the complete
   work record underneath.
8. Focused Phase 4 tests pass with external effects disabled.

## Non-goals

- no new risk calculation, model, scenario engine, metric pack or data source;
- no arbitrary HTML, JavaScript, remote assets or model-created dashboard code;
- no report publication lifecycle or decision-card implementation;
- no workflow scheduler, Studio–Codex execution or external integration;
- no portfolio, order, broker, trade, hedge, rebalance or mutation effect;
- no Phase 5 work.
