# Day 1 preparation handoff

- Lane: integration authority / preparation
- Branch: `chore/day1-preparation`
- Base: tag `day0-complete` (`a37f45809ddaa838f39f2aeaa9d0a7426fe7be4e`)
- Head: working tree, intentionally uncommitted (no commit/push/merge/tag)

## Changed files

Day 1 status, lane and wave manifests; current workplan; ADRs 0003–0005;
information architecture and screen contracts; portfolio-input and risk-
analysis contracts; provider rights boundary; Day 1 workplans and knowledge
schedule; six lane prompt templates; preparation checker/context scripts;
architecture test; Day 1 workflow; README, AGENTS.md, and Makefile.

## Scope and ownership

1A is the queued human-readable Workbench, 1B is the queued portfolio/data
workspace, and 1C is the queued risk/explainability wave. Lanes and the
domain-analytics -> knowledge -> data -> agents -> experience -> integration
order are explicit in `config/agent/day1/lanes.json` and `waves.json`.

## Tests and evidence

Executed: `make preflight`, `make verify-day0`, `make verify-day1-prep`,
`python3 scripts/day1/check_preparation.py`, `python3 scripts/day1/show_context.py`,
`python3 -m pytest tests/architecture/test_day1_preparation.py -q`, JSON parsing
for every Day 1 record, `git diff --check`, and a clean ServiceFabric submodule.
Evidence is local control-plane output only; no providers or personal portfolios
were accessed.

## Deviations, blockers, limitations

No scope deviation or blocker is known. Day 1 product implementation,
dependencies, PDF export, notebook execution, provider access, and soft QA are
not included. The handoff does not claim supervisor approval.

## Rollback and next action

Revert this preparation change set to `day0-complete`; do not touch the pinned
submodule or Day 0 state. Exact Part 5/6 entry point: review
`codex/prompts/day1/knowledge.md` and `codex/prompts/day1/experience.md` for
`D1-WAVE-1A` after integration accepts the preparation records; then proceed
through the declared order without merging specialist branches.
