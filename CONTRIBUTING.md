# Contributing

## Branching

All changes after the initial bootstrap use pull requests.

- `main` is the reviewed integration baseline.
- `integration/day0` owns cross-lane acceptance.
- Specialist branches own only their documented paths.

## Required checks

Before opening a pull request:

```bash
make preflight
git diff --check
git status --short
