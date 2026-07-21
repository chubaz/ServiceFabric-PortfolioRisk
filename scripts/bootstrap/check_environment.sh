#!/usr/bin/env bash
set -euo pipefail

required_commands=(
  bash
  codex
  curl
  gh
  git
  jq
  make
  python3
  shellcheck
  tmux
)

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

gh auth status --hostname github.com >/dev/null
codex --version
git --version
shellcheck --version | sed -n '1,2p'

echo "Environment check: PASS"
