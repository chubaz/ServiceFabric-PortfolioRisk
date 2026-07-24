#!/usr/bin/env bash
set -euo pipefail

repository_root="$(git rev-parse --show-toplevel)"
venv_path="${DAY23_VENV:-$repository_root/.venv-day23}"
python_bin="${PYTHON_BIN:-python3.11}"

if ! command -v "$python_bin" >/dev/null 2>&1; then
  echo "Python 3.11 is required; unable to find $python_bin." >&2
  exit 1
fi
"$python_bin" - <<'PY'
import sys
if sys.version_info[:2] != (3, 11):
    raise SystemExit(f"Python 3.11 is required; found {sys.version.split()[0]}.")
PY

if [[ ! -x "$venv_path/bin/python" ]]; then
  "$python_bin" -m venv "$venv_path"
fi
"$venv_path/bin/python" -m pip install --require-hashes -r "$repository_root/requirements/day1.lock"
"$venv_path/bin/python" -m pip check
echo "Day 2–3 environment ready: $venv_path"
