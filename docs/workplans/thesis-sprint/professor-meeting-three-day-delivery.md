# Professor meeting — three-day delivery plan

- Status: active delivery tracker
- Delivery window: 12–14 August 2026
- Meeting objective: demonstrate a reproducible comparison of three portfolio-risk monitoring architectures and obtain three decisions that fix the thesis direction
- Current estimate: 62% meeting-ready
- Source of truth: this file replaces informal three-day task lists; it does not replace the frozen contracts or retained Run records

## 1. Meeting promise

The demonstration will run the same historical Case through the existing B0,
B1 and A1 architectures, map every treatment into the same
`ArchitectureOutput`, evaluate the outputs consistently, and present the
comparison with its data boundary, limitations, timing, cost and evidence.

The meeting does not require a complete product, final thesis results, a new
ontology, a full Capability Studio, new connectors, or a production investment
decision system.

## 2. Frozen vocabulary and scope

The repository already uses these names. They will not be renamed for the
meeting:

| Name | Meaning |
|---|---|
| B0 | Deterministic reference treatment |
| B1 | Single structured agent treatment |
| A1 | Specialist-agent graph treatment |
| Case | One fixed portfolio, mandate, observation time and eligible information boundary |
| Run | One architecture executing one Case |
| ArchitectureOutput | Common machine-readable result used by evaluation |
| EvaluationRecord | Scores, observations, availability and limitations for one Run |
| Comparison | Matched B0/B1/A1 results for the same Case |

Professor Demo v0.1 is limited to:

- one licensed historical dataset revision;
- one point-in-time-valid portfolio and one registered mandate;
- one primary Case, with at most two additional Cases if already reliable;
- the existing stable capability set only;
- B0, B1 and A1;
- the existing nine-dimension evaluation, while the primary meeting view
  foregrounds detection, severity/risk understanding, evidence, decision,
  latency and cost;
- effect-free recommendations and human review only.

## 3. Non-negotiable reproducibility contract

A demonstration is reproducible when another local execution can reconstruct
the same experimental boundary and produce a comparable result. This requires:

1. immutable references for dataset revision, portfolio snapshot, mandate,
   Case, architecture, capabilities, prompts and evaluation version;
2. content digests for configuration, prompts, data manifests and retained
   outputs;
3. an explicit random seed for deterministic and statistical components;
4. the model route, provider, parameters, token budget, tool limits and cost
   ledger for every generative Run;
5. point-in-time eligibility and missing-data receipts;
6. one command that performs preflight, executes or replays the comparison,
   validates outputs and writes the evidence bundle;
7. a machine-readable manifest plus human-readable Run and evaluation reports;
8. no silent replacement, imputation, fallback or mutation.

Exact byte-for-byte reproduction is required for deterministic artifacts.
Generative B1/A1 outputs are distributionally reproducible: their frozen inputs,
constraints and provenance must be identical, while repeated Runs measure
output variation. A retained verified Run is used as the offline meeting
fallback and is never presented as a fresh model execution.

## 4. Current baseline

Already available:

- the Study → Experiment → Case → Run hierarchy;
- common `ArchitectureOutput` mapping;
- B0, B1 and A1 execution paths;
- experiment wrappers and semantic critic;
- nine-dimensional evaluation with explicit unavailable states;
- processing-time, token and cost ledgers;
- retained matched comparison
  `experiment.baseline-three-20260812-final`;
- corrected B1/A1 structured-output boundaries verified by unsaved regression
  Runs;
- single-Run assurance and runtime reporting.

Known meeting blockers:

- the retained Case retrojects current holdings into 2017 and is therefore an
  apparatus demonstration, not a thesis-valid historical portfolio Case;
- the app does not yet offer one obvious, rehearsed meeting journey;
- evaluation and runtime findings need a concise presentation layer;
- the architecture view and supervisor deck have not been produced;
- one-command reconstruction and fallback rehearsal have not yet been signed
  off.

## 5. Day 1 — Freeze and reproduce

Goal: produce one trustworthy Professor Demo v0.1 boundary and prove that it
can be reconstructed without manual repair.

### 5.1 Experiment lane

- [x] Select one complete historical apparatus Case and disclose that its
  current quantities are retrojected rather than historically constructed.
- [x] Pin the portfolio snapshot, mandate version, dataset revision, event
  boundary, capability versions and B0/B1/A1 versions.
- [x] Freeze the apparatus experiment and evaluation manifests as v0.1.
- [x] Mark independently unavailable labels and outcomes as unavailable rather
  than synthesising them.
- [x] Run preflight and record every missing observation before paid execution.

### 5.2 Reproducibility lane

- [x] Add one professor-demo command that preflights, runs, verifies and retains
  the comparison; rendering and retained reload are supplied by the same app.
- [x] Write a run manifest containing environment, Git revision, data and
  definition digests, seed, prompts, model route and budgets.
- [x] Write comparison JSON, Run reports, EvaluationRecords and a
  digest inventory into one immutable evidence bundle.
- [x] Verify the Saved results repository reloads the retained Experiment and Comparison.
- [x] Document licensed-data requirements and the offline retained-Run fallback.

Day 1 retained result:

- comparison: `counterfactual-analysis:experiment-professor-demo-v0.1:aefee03b407937daee11`;
- completed Runs: 3/3;
- critical defects: 0;
- total bounded model cost: $0.009972;
- gate record: `docs/thesis/professor-demo-day1-gate.md`.

### 5.3 Acceptance gate

Day 1 passes only when:

- one command reconstructs the same Case boundary;
- B0, B1 and A1 receive the same eligible information;
- all three produce valid `ArchitectureOutput` records;
- the evaluation declares unavailable evidence honestly;
- the Comparison can be saved, restarted, reloaded and verified by digest;
- no material preflight error remains hidden.

End-of-day deliverables:

- Professor Demo v0.1 manifest;
- one verified retained comparison;
- reproducibility manifest and command;
- one-page experiment specification;
- Day 1 gate record.

## 6. Day 2 — Make the experiment easy to understand

Goal: a professor can operate or follow the demonstration without learning the
internal platform vocabulary.

### 6.1 Demonstration journey

The primary path must contain five visible steps:

1. **Case** — portfolio, mandate, date, data status and missing observations.
2. **Compare** — B0, B1 and A1 with the same inputs and capabilities.
3. **Run** — live progress, processing pause, capability/model activity and cost.
4. **Results** — material findings, evidence, decisions and architecture
   differences.
5. **Quality** — whether the Run is valid, what was unavailable and what can be
   concluded.

### 6.2 Presentation lane

- [ ] Remove nonessential controls and internal terminology from the primary
  journey; retain technical receipts behind disclosure controls.
- [ ] Establish one consistent typography, spacing, status and number-formatting
  system.
- [ ] Present findings before technical metrics.
- [ ] Give every evaluation dimension a plain-language question, value, status,
  evidence basis and limitation.
- [ ] Add a concise comparison table and a small number of decision-useful
  charts only.
- [ ] Separate experiment success from architecture quality.
- [ ] Render the Run report, evaluation report and improvement log as readable
  Markdown/HTML with downloadable machine-readable files.
- [ ] Make real, licensed, synthetic, simulated and missing data unmistakable.

### 6.3 Reliability lane

- [ ] Test a live B0/B1/A1 execution from the browser.
- [ ] Test retained-run playback without provider access.
- [ ] Test refresh, server restart, saved Experiment load and Comparison load.
- [ ] Test narrow and wide screens and the exact meeting browser.
- [ ] Add actionable empty, loading and failure states.
- [ ] Record screenshots and a two-minute fallback walkthrough.

### 6.4 Acceptance gate

Day 2 passes only when:

- the five-step journey completes without a developer explaining navigation;
- the Run’s validity and the architecture’s quality cannot be confused;
- every visible number has a definition and unit;
- critical limitations appear next to the affected result;
- the live path and retained fallback both work after restart;
- no failed request, clipped content, overlap or unreadable text remains in the
  meeting path.

End-of-day deliverables:

- polished experiment journey;
- retained demo comparison and fallback;
- human-readable evaluation and runtime reports;
- browser QA record and screenshots;
- five-minute rehearsal script.

## 7. Day 3 — Explain the system and the research programme

Goal: show what exists, how it works, what is planned, and what the supervisor
must decide.

### 7.1 Live architecture diagram

Build one interactive view generated from a versioned architecture manifest,
not a manually maintained drawing.

Required levels:

1. **Thesis view** — research question, common Case, three architectures,
   common output, evaluation and comparison.
2. **Execution view** — data boundary, capabilities, wrappers, agents/graph,
   semantic critic, `ArchitectureOutput` and evaluation.
3. **Component view** — definition/version, implementation status, evidence,
   dependencies and owning source paths.

Every component is marked as:

- completed and demonstrated;
- implemented but not demonstrated;
- planned for the thesis;
- potential post-thesis feature;
- open research question.

The diagram must support filtering, zoom/drill-down, an explanatory detail
panel, direct links to the relevant app view or documentation, and an
as-of/build identifier. Adding a component to the manifest must update the
diagram without editing its layout code.

### 7.2 Supervisor deck

Target: 8–10 slides.

1. Thesis question and intended contribution.
2. Why a controlled architecture comparison is necessary.
3. Implemented system and live architecture diagram.
4. Professor Demo v0.1 experimental contract.
5. B0 versus B1 versus A1.
6. Demonstration results and limitations.
7. Experimental programme from the first Case to repeated studies.
8. Implemented, next, potential and deferred features.
9. Three supervisor decisions.
10. Optional appendix: reproducibility and technical evidence.

The deck must distinguish demonstrated facts, preliminary apparatus results,
planned thesis work and post-thesis ideas.

### 7.3 Experimental programme slide

Show the cumulative progression:

```text
Validated apparatus
  → point-in-time Cases and independent labels
  → repeated architecture Runs
  → information and capability treatments
  → robustness and regime tests
  → decision counterfactuals and regret
  → thesis evaluation and sensitivity analysis
```

### 7.4 Three decisions requested from the supervisor

1. **Contribution** — Is the thesis contribution correctly framed as the design
   and empirical comparison of portfolio-risk monitoring architectures, with
   ServiceFabric as the experimental apparatus?
2. **Method** — Is a historical matched experiment using fixed Cases, common
   capabilities, B0/B1/A1 and common evaluation a valid method for answering
   the research question?
3. **Scope** — Should the thesis primarily evaluate alert and risk-analysis
   quality and architecture differences, leaving portfolio-decision regret and
   advanced scenarios as a secondary extension?

Each decision slide must show the recommendation, alternatives, consequence of
each choice and the immediate work it unlocks.

### 7.5 Final acceptance gate

Day 3 passes only when:

- the live demo completes twice from a fresh application start;
- retained fallback playback completes without network or model access;
- the architecture diagram agrees with the versioned manifest;
- every slide claim links to an implementation, retained result or clearly
  labelled plan;
- the evidence bundle verifies by digest;
- the three requested decisions are answerable in the meeting;
- presentation files, screenshots, manifests and results are copied to one
  dated, read-only meeting bundle.

## 8. Work that can run in parallel

Only non-conflicting lanes should run concurrently:

| Lane | Can run alongside | Must wait for |
|---|---|---|
| Point-in-time Case and manifest | reproducibility command | nothing |
| Reproducibility command and evidence inventory | Case selection | stable contract names |
| UI visual system and report renderer | Case work | current result schemas |
| Browser QA automation | report/UI implementation | stable meeting route |
| Architecture manifest and diagram shell | Day 2 UI polish | frozen vocabulary |
| Slide narrative and decision framing | diagram implementation | frozen meeting promise |
| Final screenshots and numerical results | nothing | accepted retained comparison |

Do not parallelise changes to the same experiment runtime, route or result
schema. Merge each lane only after its focused tests pass.

## 9. Explicit deferrals

Until the meeting bundle is accepted, do not start:

- new Studios or broad Studio UX redesign;
- RavenPack production integration;
- new MCP/API/provider families;
- advanced event teacher/student models;
- copulas, diffusion models or new scenario engines;
- portfolio mutation or external effects;
- a complete live dashboard product;
- a new domain object or alternative experimental hierarchy;
- large-scale paid experiment batches.

These remain visible in the architecture diagram as planned, potential or
post-thesis items.

## 10. Tracker

| Checkpoint | Status | Evidence | Blocking issue |
|---|---|---|---|
| Scope and vocabulary frozen | complete | this plan; existing contracts | none |
| Existing B0/B1/A1 apparatus inspected | complete | baseline handoff | retained Case is not point-in-time valid |
| B1/A1 semantic-output correction | complete | focused regression tests | paid matched rerun not retained |
| Professor Demo v0.1 Case and manifest | not started | — | point-in-time portfolio choice |
| One-command reproducibility | not started | — | manifest not frozen |
| Save/restart/reload verification | partial | registry and Run persistence exist | meeting path not rehearsed |
| Polished five-step demo journey | not started | — | Day 1 boundary |
| Evaluation and runtime presentation | partial | raw reports exist | presentation layer |
| Retained offline fallback | partial | retained comparison exists | fallback UI rehearsal |
| Interactive architecture diagram | not started | — | architecture manifest |
| Supervisor deck | not started | — | final comparison and screenshots |
| Two successful final rehearsals | not started | — | all prior gates |
| Read-only meeting evidence bundle | not started | — | all prior gates |

## 11. Progress calculation

Progress is the proportion of the 13 tracker checkpoints marked complete.
Partial checkpoints count as one half. The estimate at the top of this file is
updated only after evidence exists; activity without a verified deliverable
does not increase it.

## 12. Next action

Freeze Professor Demo v0.1 by selecting the point-in-time-valid Case and writing
its complete reproducibility manifest. No UI or slide claim should be finalised
before that boundary is accepted.
