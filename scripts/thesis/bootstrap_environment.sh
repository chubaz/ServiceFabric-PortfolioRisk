#!/usr/bin/env bash
set -euo pipefail

repository_root="$(git rev-parse --show-toplevel)"
venv_path="${THESIS_VENV:-$repository_root/.venv-thesis}"
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

"$venv_path/bin/python" -m pip install \
  --require-hashes \
  -r "$repository_root/requirements/thesis.lock"
"$venv_path/bin/python" -m pip check
echo "Thesis Sprint environment ready: $venv_path"
