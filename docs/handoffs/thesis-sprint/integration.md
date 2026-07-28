# Thesis Sprint integration handoff — Day 1 activation

## Lane and branch

- Lane: `integration`
- Branch: `integration/thesis-experiment`
- Base: `day23-complete` (`2c4a163`)
- Head: uncommitted working tree
- Lifecycle: `THESIS-D1` in progress; later days and soft QA queued

## Changed paths

- `.github/workflows/thesis-sprint.yml`
- `AGENTS.md`
- `Makefile`
- `config/agent/thesis-sprint/lanes.json`
- `config/agent/thesis-sprint/status.json`
- `docs/architecture/adr/0006-thesis-experiment-runtime.md`
- `docs/contracts/thesis-experiment-v0.1.md`
- `docs/handoffs/thesis-sprint/day1.md`
- `docs/handoffs/thesis-sprint/integration.md`
- `docs/workplans/current.md`
- `docs/workplans/thesis-sprint/day-1-data-portfolios-replay.md`
- `docs/workplans/thesis-sprint/day-2-metrics-decision-kernel.md`
- `docs/workplans/thesis-sprint/day-3-agent-architectures.md`
- `docs/workplans/thesis-sprint/day-4-experiment-results.md`
- `scripts/thesis/bootstrap_environment.sh`
- `scripts/thesis/check_lane_paths.py`
- `tests/architecture/test_day1_preparation.py`
- `tests/architecture/test_day23_control_plane.py`
- `tests/architecture/test_thesis_sprint_control_plane.py`

No application, package, connector, schema, fixture, requirement, historical
lifecycle, or `vendor/servicefabric/**` path changed.

## Tests executed

- `make preflight`: PASS.
- `make test-thesis-control`: PASS (`16 passed`).
- `make test-architecture`: PASS (`78 passed`).
- `make verify-d23-current`: PASS, including Day 0, historical Day 1, D23
  Part 1 and Part 2, manifests, lane checks, and whitespace gates.
- `make verify-thesis-current`: PASS, including the complete D23 baseline,
  `15` thesis control tests, and explicit notices that Day 1 implementation,
  integration, and journey tests do not yet exist.
- JSON validation, Python compilation, shell syntax, and Make dry-run checks:
  PASS.
- `git diff --check`: PASS.
- `git -C vendor/servicefabric status --short`: clean.
- `make -n verify-thesis-day1
  THESIS_DAY1_LANE_BASE=control-plane-sha
  THESIS_DAY1_LANE_HEAD=specialist-sha`: confirmed the lane checker receives
  only the explicit control-plane-to-candidate range.

## Evidence produced

The control-plane diff and test output are the only activation evidence. No
experiment observation, replay, metric, architecture, or result artifact is
produced.

## Deviations

Two historical architecture tests now verify completed Day 1 and D23 records
without requiring the global current-workplan pointer to remain permanently on
an old programme. The historical Day 1 preparation script is left unchanged;
`verify-day1` skips only its obsolete current-pointer coupling when a
`THESIS-*` workplan is active, after the full historical regression tests have
passed.

Review correction: the eventual Day 1 lane gate no longer compares
`day23-complete..HEAD` against the specialist allowlist. It automatically
resolves the commit that introduced the Thesis Sprint control plane and
requires the exact specialist candidate head, excluding both activation and
later integration-owned changes.

## Blockers

None.

## Limitations

Day 1 implementation does not yet exist. The full Day 1 verification and demo
remain unavailable until the specialist supplies the required tests, fixture
digest validator, fixtures, and demo.

## Rollback

Revert only the uncommitted Thesis Sprint activation paths. Preserve the
completed historical lifecycle records, tag `day23-complete`, and the pinned
`vendor/servicefabric` tree.

## Recommended next action

Review and commit this activation, then start `feature/thesis-day1` from that
reviewed control-plane commit using the specialist entry point in the active
workplan. At acceptance, pass the exact recorded specialist head as
`THESIS_DAY1_LANE_HEAD`; the gate automatically resolves the control-plane
addition commit as the lane base.
