# Day 0 Preparation Handoff

- Lane and branch: integration preparation audit, `chore/day0-preparation`
- Base and head: `634601290b09fba0f67463410a4c30a6b13b11f7`
- Changed paths: `scripts/bootstrap/check_repository.sh`; this handoff

## Evidence produced

- The `vendor/servicefabric` gitlink, checked-out `HEAD`, upstream manifest,
  and ADR all identify `7632b61d94a966346f95eb6c5bb2a5ea27f3bc14`.
- `./scripts/bootstrap/check_repository.sh` passed after its tracked-path
  exclusions were extended to cover credential-like filenames, licensed
  provider directories, and local analytical file formats. Reviewed synthetic
  `.parquet`, `.arrow`, and `.feather` fixtures remain permitted only below
  `data/fixtures/synthetic/`.
- `shellcheck scripts/bootstrap/*.sh`, the lane ownership validation, and
  `git diff --check` passed.
- The GitHub workflow runs the same repository checker, then installs and runs
  the ServiceFabric doctor, lints bootstrap scripts, and checks Git whitespace.
- The public repository's most recent `preparation` workflow completed
  successfully (run `29818466716`).
- GitHub confirms that the repository is public and `main` is its default
  branch; it also confirms that `main` is not protected.

## Tests executed

- `make preflight` — passed.
- `make upstream-doctor` — passed.
- `./scripts/bootstrap/check_repository.sh` — passed.
- synthetic fixture boundary check — passed: an alternate index accepts
  `data/fixtures/synthetic/prices.parquet` and rejects
  `data/cache/prices.parquet`.
- `shellcheck scripts/bootstrap/*.sh` — passed.
- lane ownership validation — passed.
- `git diff --check` — passed.

## Blockers

- GitHub reports that `main` is not protected, so the branch-protection
  acceptance check is unmet.
- The `day0-prepared` tag, all six configured Day 0 lane branches, and their
  worktrees are absent. Therefore the worktree plan is structurally valid but
  has not been executed.
- Preparation remains `in_progress` and `docs/workplans/current.md` continues
  to point to D0-PREP. Updating them would incorrectly claim unmet acceptance
  checks had passed.

## Limitations

- No provider APIs, secrets, real financial data, or runtime dependencies were
  accessed or added.
- Remote branch protection remains an external GitHub configuration concern;
  it was inspected but not changed by this audit.

## Rollback

Revert the two changed files to remove the stricter tracked-file validation and
this audit handoff. No submodule, implementation package, tag, worktree, or
remote state was changed.

## Recommended next action

Use an authenticated environment with the required `codex` CLI and permitted
package-index access to run `make preflight`; verify GitHub visibility, branch
protection, and successful CI; then create `day0-prepared` and the six clean
lane worktrees from it before marking D0-PREP complete.
