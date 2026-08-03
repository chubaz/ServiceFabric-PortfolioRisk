#!/usr/bin/env bash
# Non-interactive execution of an already reviewed and prepared Day 3 manifest.
set -euo pipefail

repository_root="$(git rev-parse --show-toplevel)"
cd "$repository_root"

path_or_default() {
  local configured="${1:-}"
  local fallback="$2"
  case "$configured" in
    ""|/absolute|/absolute/*|/path/to|/path/to/*)
      printf '%s\n' "$fallback"
      ;;
    *)
      printf '%s\n' "$configured"
      ;;
  esac
}

thesis_venv="${THESIS_VENV:-$repository_root/.venv-thesis}"
python_bin="$thesis_venv/bin/python"
package_paths="$repository_root/packages/risk_domain/src:$repository_root/packages/risk_planning/src:$repository_root/packages/risk_data/src:$repository_root/packages/risk_capabilities/src:$repository_root/packages/risk_agents/src:$repository_root/packages/risk_analytics/src:$repository_root/examples/portfolio-risk-thesis/src"
if [[ "$repository_root" == */worktrees/thesis-sprint/* ]]; then
  workspace_root="${repository_root%%/worktrees/thesis-sprint/*}"
else
  workspace_root="$repository_root"
fi
private_root="$(path_or_default "${THESIS_PRIVATE_ROOT:-}" "$workspace_root/private-data")"
model_root="$(path_or_default "${THESIS_DAY3_MODEL_ROOT:-}" "$private_root/thesis-model")"
output_root="$(path_or_default "${THESIS_DAY3_OUTPUT_ROOT:-}" "$private_root/crsp-compustat/thesis-results")"
manifest="$(path_or_default "${THESIS_DAY3_EXPERIMENT_MANIFEST:-${1:-}}" "")"

[[ -x "$python_bin" ]] \
  || { echo "ERROR: Thesis Python is unavailable at $python_bin" >&2; exit 1; }
if [[ -n "$manifest" && ( "$manifest" != /* || ! -f "$manifest" ) ]]; then
  echo "Ignoring unavailable THESIS_DAY3_EXPERIMENT_MANIFEST: $manifest"
  manifest=""
fi
if [[ -z "$manifest" ]]; then
  manifest="$(
    "$python_bin" - "$model_root" <<'PY'
from pathlib import Path
import hashlib
import sys
import yaml

candidates = []
for path in sorted(Path(sys.argv[1]).glob("day3-experiment*.yaml")):
    try:
        experiment = yaml.safe_load(path.read_text(encoding="utf-8"))
        config = Path(experiment["model_config"])
        digest = "sha256:" + hashlib.sha256(config.read_bytes()).hexdigest()
        configuration = yaml.safe_load(config.read_text(encoding="utf-8"))
    except (KeyError, OSError, TypeError, yaml.YAMLError):
        continue
    if (
        experiment.get("model_config_digest") == digest
        and configuration.get("provider_id") == "openai_responses"
        and int(configuration.get("maximum_output_tokens", 0)) >= 4096
    ):
        candidates.append(path)
if len(candidates) != 1:
    raise SystemExit(
        "ERROR: set THESIS_DAY3_EXPERIMENT_MANIFEST; expected exactly one "
        f"validated 4,096-token candidate, found {len(candidates)}"
    )
print(candidates[0])
PY
  )"
fi
[[ "$manifest" = /* && -f "$manifest" ]] \
  || { echo "ERROR: Day 3 experiment manifest must be an existing absolute file" >&2; exit 1; }
[[ "$output_root" = /* ]] \
  || { echo "ERROR: Day 3 output root must be absolute" >&2; exit 1; }
if [[ ! -d "$output_root" ]]; then
  mkdir -p "$output_root"
  chmod 700 "$output_root"
fi

PYTHONPATH="$repository_root:$package_paths" "$python_bin" \
  -m portfolio_risk_thesis.cli validate-day3 \
  --experiment-manifest "$manifest"
if [[ "${THESIS_DAY3_VALIDATE_ONLY:-0}" == "1" ]]; then
  echo "Day 3 direct-run validation passed; no external model call made."
  exit 0
fi

openai_key="$(security find-generic-password -a "$USER" -s servicefabric-thesis-openai -w)"
export OPENAI_API_KEY="$openai_key"
unset openai_key
[[ -n "$OPENAI_API_KEY" ]] \
  || { echo "ERROR: Keychain item servicefabric-thesis-openai is unavailable" >&2; exit 1; }
trap 'unset OPENAI_API_KEY' EXIT

run_result="$(
  PYTHONPATH="$repository_root:$package_paths" "$python_bin" \
    -m portfolio_risk_thesis.cli run-day3 \
    --experiment-manifest "$manifest" \
    --provider openai_responses \
    --output-root "$output_root"
)"
echo "$run_result"
run_id="$(
  printf '%s\n' "$run_result" \
    | "$python_bin" -c 'import json,sys; print(json.load(sys.stdin)["run_id"])'
)"
run_directory="$output_root/$run_id"
PYTHONPATH="$repository_root:$package_paths" "$python_bin" \
  -m portfolio_risk_thesis.cli validate-day3-run \
  --run-directory "$run_directory" \
  --require-successful-provider
PYTHONPATH="$repository_root:$package_paths" "$python_bin" \
  -m portfolio_risk_thesis.cli inspect-day3-comparison \
  --run-directory "$run_directory"
echo "Day 3 direct paid run completed: $run_directory"
