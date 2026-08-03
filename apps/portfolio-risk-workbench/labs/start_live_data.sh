#!/usr/bin/env bash
set -euo pipefail

prototype_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
search_root="$prototype_dir"
workspace_root=""
while [[ "$search_root" != "/" ]]; do
  if [[ -d "$search_root/private-data/crsp-compustat/raw" ]]; then
    workspace_root="$search_root"
    break
  fi
  search_root="$(dirname -- "$search_root")"
done

if [[ -z "$workspace_root" ]]; then
  echo "Could not locate private-data/crsp-compustat/raw." >&2
  echo "Set PORTFOLIO_RISK_PRIVATE_DATA_ROOT or run from the servicefabric-lab workspace." >&2
  exit 1
fi

python_runtime="${PORTFOLIO_RISK_PYTHON:-$workspace_root/state/venvs/thesis-sprint/bin/python}"
if [[ ! -x "$python_runtime" ]]; then
  echo "Python runtime is unavailable: $python_runtime" >&2
  echo "Set PORTFOLIO_RISK_PYTHON to a Python 3.11 executable with the thesis dependencies." >&2
  exit 1
fi
server_port="${1:-8766}"
repository_root="$(git -C "$prototype_dir" rev-parse --show-toplevel)"
package_paths="$repository_root/packages/risk_domain/src:$repository_root/packages/risk_planning/src:$repository_root/packages/risk_data/src:$repository_root/packages/risk_capabilities/src:$repository_root/packages/risk_agents/src:$repository_root/packages/risk_analytics/src:$repository_root/packages/risk_registry/src:$repository_root/packages/risk_artifacts/src:$repository_root/packages/risk_experiments/src"

PYTHONPATH="$repository_root:$package_paths${PYTHONPATH:+:$PYTHONPATH}" \
  exec "$python_runtime" "$prototype_dir/duckdb_server.py" --port "$server_port"
