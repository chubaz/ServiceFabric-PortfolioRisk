#!/usr/bin/env bash
set -euo pipefail

required_commands=(
  bash
  curl
  gh
  git
  jq
  make
  python3
  shellcheck
)

# Codex and tmux support the local agent workflow but are not needed by the
# repository verification targets executed on GitHub-hosted runners.
if [[ "${GITHUB_ACTIONS:-}" != "true" ]]; then
  required_commands+=(codex tmux)
fi

for command_name in "${required_commands[@]}"; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    exit 1
  fi
done

python3 - <<'PY'
import sys

if sys.version_info < (3, 11):
    raise SystemExit(
        "Python 3.11 or newer is required; "
        f"found {sys.version.split()[0]}"
    )
print(f"Python: {sys.version.split()[0]}")
PY

if ! gh auth status --hostname github.com >/dev/null 2>&1; then
  if [[ "${DAY0_REQUIRE_GITHUB_AUTH:-0}" == "1" ]]; then
    echo "GitHub CLI authentication is required but unavailable." >&2
    exit 1
  fi
  echo "WARNING: GitHub CLI authentication is unavailable; offline Day 0 checks will continue." >&2
fi
if [[ "${GITHUB_ACTIONS:-}" != "true" ]]; then
  codex --version
fi
git --version
shellcheck --version | sed -n '1,2p'

echo "Environment check: PASS"
