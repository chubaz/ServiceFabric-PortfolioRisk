#!/usr/bin/env bash
# Guided, fail-closed local workflow for the human-authorized Day 3 steps.
set -euo pipefail

repository_root="$(git rev-parse --show-toplevel)"
cd "$repository_root"

thesis_venv="${THESIS_VENV:-$repository_root/.venv-thesis}"
export THESIS_VENV="$thesis_venv"
python_bin="$thesis_venv/bin/python"
package_paths="$repository_root/packages/risk_domain/src:$repository_root/packages/risk_planning/src:$repository_root/packages/risk_data/src:$repository_root/packages/risk_capabilities/src:$repository_root/packages/risk_agents/src:$repository_root/packages/risk_analytics/src:$repository_root/examples/portfolio-risk-thesis/src"

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

if [[ "$repository_root" == */worktrees/thesis-sprint/* ]]; then
  default_workspace_root="${repository_root%%/worktrees/thesis-sprint/*}"
else
  default_workspace_root="$repository_root"
fi
workspace_root="$(path_or_default "${THESIS_WORKSPACE_ROOT:-}" "$default_workspace_root")"
private_root="$(path_or_default "${THESIS_PRIVATE_ROOT:-}" "$workspace_root/private-data")"
day2_output_root="$(path_or_default "${THESIS_DAY2_OUTPUT_ROOT:-}" "$private_root/crsp-compustat/thesis-results")"
real_config_root="$(path_or_default "${THESIS_REAL_CONFIG_ROOT:-}" "$private_root/crsp-compustat/config")"
event_root="$(path_or_default "${THESIS_DAY3_EVENT_ROOT:-}" "$private_root/thesis-events")"
model_root="$(path_or_default "${THESIS_DAY3_MODEL_ROOT:-}" "$private_root/thesis-model")"

if [[ -f "$real_config_root/thesis-experiment-v2.yaml" ]]; then
  default_real_experiment="$real_config_root/thesis-experiment-v2.yaml"
else
  default_real_experiment="$real_config_root/thesis-experiment.yaml"
fi

export THESIS_REAL_EXPERIMENT_MANIFEST="$(path_or_default "${THESIS_REAL_EXPERIMENT_MANIFEST:-}" "$default_real_experiment")"
export THESIS_DAY3_EVENT_MANIFEST="$(path_or_default "${THESIS_DAY3_EVENT_MANIFEST:-}" "$event_root/day3-event-manifest.yaml")"
export THESIS_DAY3_EVENT_DATASET="$(path_or_default "${THESIS_DAY3_EVENT_DATASET:-}" "$event_root/day3-events.parquet")"
export THESIS_DAY3_MODEL_CONFIG="$(path_or_default "${THESIS_DAY3_MODEL_CONFIG:-}" "$model_root/day3-model-config.yaml")"
export THESIS_DAY3_EXPOSURES="$(path_or_default "${THESIS_DAY3_EXPOSURES:-}" "$model_root/day3-exposures.yaml")"
export THESIS_DAY3_EXPERIMENT_MANIFEST="$(path_or_default "${THESIS_DAY3_EXPERIMENT_MANIFEST:-}" "$model_root/day3-experiment.yaml")"
export THESIS_DAY3_OUTPUT_ROOT="$(path_or_default "${THESIS_DAY3_OUTPUT_ROOT:-}" "$day2_output_root")"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

require_path() {
  local variable_name="$1"
  local kind="$2"
  local value="${!variable_name:-}"
  [[ -n "$value" ]] || fail "set $variable_name"
  [[ "$value" = /* ]] || fail "$variable_name must be absolute"
  [[ "$kind" != file || -f "$value" ]] || fail "$variable_name must identify a file"
  [[ "$kind" != directory || -d "$value" ]] || fail "$variable_name must identify a directory"
}

prompt_for_directory() {
  local variable_name="$1"
  local description="$2"
  local value="${!variable_name:-}"
  while [[ ! -d "$value" || "$value" != /* ]]; do
    echo "$description"
    read -r -p "Absolute directory: " value
  done
  printf -v "$variable_name" '%s' "$value"
  export "$variable_name"
}

choose_day2_run() {
  local candidate
  local required
  local complete
  local selection
  local index
  local configured_run="${THESIS_DAY2_RUN_DIR:-}"
  local -a candidates=()

  if [[ -n "$configured_run" && "$configured_run" = /* && -d "$configured_run" ]]; then
    return
  fi
  if [[ -n "$configured_run" ]]; then
    echo "Ignoring unavailable THESIS_DAY2_RUN_DIR: $configured_run"
    unset THESIS_DAY2_RUN_DIR
  fi

  shopt -s nullglob
  for candidate in "$day2_output_root"/day2_*; do
    [[ -d "$candidate" ]] || continue
    complete=true
    for required in \
      morning-metric-packs.json \
      deterministic-findings.json \
      kernel-decisions.json \
      evidence-manifest.json
    do
      [[ -f "$candidate/$required" ]] || complete=false
    done
    [[ "$complete" == true ]] && candidates+=("$candidate")
  done
  shopt -u nullglob

  if [[ "${#candidates[@]}" -eq 1 ]]; then
    export THESIS_DAY2_RUN_DIR="${candidates[0]}"
    echo "Using the only complete Day 2 run: $THESIS_DAY2_RUN_DIR"
    return
  fi

  if [[ "${#candidates[@]}" -gt 1 ]]; then
    echo "Choose the accepted Day 2 evidence run:"
    index=1
    for candidate in "${candidates[@]}"; do
      printf '  %d) %s\n' "$index" "$candidate"
      index=$((index + 1))
    done
    while true; do
      read -r -p "Selection [1-${#candidates[@]}]: " selection
      if [[ "$selection" =~ ^[0-9]+$ ]] \
        && (( selection >= 1 && selection <= ${#candidates[@]} ))
      then
        export THESIS_DAY2_RUN_DIR="${candidates[$((selection - 1))]}"
        return
      fi
      echo "Enter a number from 1 to ${#candidates[@]}."
    done
  fi

  prompt_for_directory \
    THESIS_DAY2_RUN_DIR \
    "No complete Day 2 run was found beneath $day2_output_root."
}

choose_portfolio() {
  local selection
  local index
  local portfolio_id
  local configured_portfolio="${THESIS_DAY3_PORTFOLIO_ID:-}"
  local -a portfolio_ids=()

  while IFS= read -r portfolio_id; do
    [[ -n "$portfolio_id" ]] && portfolio_ids+=("$portfolio_id")
  done < <(
    "$python_bin" - "$THESIS_DAY2_RUN_DIR/morning-metric-packs.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    packs = json.load(source)
for portfolio_id in sorted({str(pack["portfolio_id"]) for pack in packs}):
    print(portfolio_id)
PY
  )

  [[ "${#portfolio_ids[@]}" -gt 0 ]] || fail "the Day 2 run contains no portfolios"
  if [[ -n "$configured_portfolio" ]]; then
    for portfolio_id in "${portfolio_ids[@]}"; do
      if [[ "$configured_portfolio" == "$portfolio_id" ]]; then
        return
      fi
    done
    echo "Ignoring unavailable THESIS_DAY3_PORTFOLIO_ID: $configured_portfolio"
    unset THESIS_DAY3_PORTFOLIO_ID
  fi
  if [[ "${#portfolio_ids[@]}" -eq 1 ]]; then
    export THESIS_DAY3_PORTFOLIO_ID="${portfolio_ids[0]}"
    echo "Using the only Day 2 portfolio: $THESIS_DAY3_PORTFOLIO_ID"
    return
  fi

  echo "Choose the one portfolio for the Day 3 comparison:"
  index=1
  for portfolio_id in "${portfolio_ids[@]}"; do
    printf '  %d) %s\n' "$index" "$portfolio_id"
    index=$((index + 1))
  done
  while true; do
    read -r -p "Selection [1-${#portfolio_ids[@]}]: " selection
    if [[ "$selection" =~ ^[0-9]+$ ]] \
      && (( selection >= 1 && selection <= ${#portfolio_ids[@]} ))
    then
      export THESIS_DAY3_PORTFOLIO_ID="${portfolio_ids[$((selection - 1))]}"
      return
    fi
    echo "Enter a number from 1 to ${#portfolio_ids[@]}."
  done
}

review_file() {
  local filename="$1"
  local description="$2"
  local created="$3"
  local answer

  echo "$description"
  if [[ "$created" == true ]]; then
    read -r -p "Press Enter to open your editor, or Ctrl-C to stop: "
    "${EDITOR:-vi}" "$filename"
    return
  fi
  read -r -p "Reopen the existing file for review? [y/N]: " answer
  if [[ "$answer" == "y" || "$answer" == "Y" ]]; then
    "${EDITOR:-vi}" "$filename"
  fi
}

echo "Day 3 interactive assistant — private data and model calls remain local."
[[ -x "$python_bin" ]] || fail "Thesis Python is unavailable at $python_bin; run make thesis-env first"
PYTHONPATH="$repository_root:$package_paths" \
  "$python_bin" -m portfolio_risk_thesis.cli --help >/dev/null

require_path THESIS_DAY3_EVENT_MANIFEST any
require_path THESIS_DAY3_EVENT_DATASET any
require_path THESIS_DAY3_MODEL_CONFIG any
require_path THESIS_DAY3_EXPOSURES any
require_path THESIS_DAY3_EXPERIMENT_MANIFEST any
require_path THESIS_DAY3_OUTPUT_ROOT any
for private_directory in \
  "$(dirname "$THESIS_DAY3_EVENT_MANIFEST")" \
  "$(dirname "$THESIS_DAY3_EVENT_DATASET")" \
  "$(dirname "$THESIS_DAY3_MODEL_CONFIG")" \
  "$(dirname "$THESIS_DAY3_EXPOSURES")" \
  "$(dirname "$THESIS_DAY3_EXPERIMENT_MANIFEST")" \
  "$THESIS_DAY3_OUTPUT_ROOT"
do
  if [[ ! -d "$private_directory" ]]; then
    mkdir -p "$private_directory"
    chmod 700 "$private_directory"
  fi
done

event_manifest_created=false
if [[ -e "$THESIS_DAY3_EVENT_MANIFEST" ]] \
  && PYTHONPATH="$repository_root:$package_paths" "$python_bin" - "$THESIS_DAY3_EVENT_MANIFEST" <<'PY'
import sys
from portfolio_risk_thesis.day3.events import validate_event_manifest

events = validate_event_manifest(sys.argv[1])
raise SystemExit(
    0
    if len(events) == 20
    and all(event.profile == "synthetic_curated" for event in events)
    and all(event.event_id.startswith("fictional-event-") for event in events)
    else 1
)
PY
then
  superseded_manifest="$THESIS_DAY3_EVENT_MANIFEST.superseded-$(date -u +%Y%m%dT%H%M%SZ)"
  mv "$THESIS_DAY3_EVENT_MANIFEST" "$superseded_manifest"
  echo "Archived the generic fictional starter: $superseded_manifest"
fi
if [[ ! -e "$THESIS_DAY3_EVENT_MANIFEST" ]]; then
  cp \
    "$repository_root/data/fixtures/public/thesis-day3/event-manifest.json" \
    "$THESIS_DAY3_EVENT_MANIFEST"
  chmod 600 "$THESIS_DAY3_EVENT_MANIFEST"
  echo "Initialized 20 reviewed historical events from the fixed 2024-10-04 through 2024-12-31 evidence window."
  event_manifest_created=true
fi

review_file \
  "$THESIS_DAY3_EVENT_MANIFEST" \
  "Review curated point-in-time events. Do not add outcome labels or licensed article text." \
  "$event_manifest_created"

if [[ -e "$THESIS_DAY3_EVENT_DATASET" ]] \
  && ! PYTHONPATH="$repository_root:$package_paths" "$python_bin" -m portfolio_risk_thesis.cli validate-day3-events \
    --manifest "$THESIS_DAY3_EVENT_MANIFEST" \
    --dataset "$THESIS_DAY3_EVENT_DATASET" >/dev/null 2>&1
then
  superseded_dataset="$THESIS_DAY3_EVENT_DATASET.superseded-$(date -u +%Y%m%dT%H%M%SZ)"
  mv "$THESIS_DAY3_EVENT_DATASET" "$superseded_dataset"
  echo "Archived the superseded event dataset: $superseded_dataset"
fi
PYTHONPATH="$repository_root:$package_paths" "$python_bin" -m portfolio_risk_thesis.cli materialize-day3-events --manifest "$THESIS_DAY3_EVENT_MANIFEST" --output "$THESIS_DAY3_EVENT_DATASET"
PYTHONPATH="$repository_root:$package_paths" "$python_bin" -m portfolio_risk_thesis.cli validate-day3-events --manifest "$THESIS_DAY3_EVENT_MANIFEST" --dataset "$THESIS_DAY3_EVENT_DATASET"
event_count="$(
  PYTHONPATH="$repository_root:$package_paths" "$python_bin" - "$THESIS_DAY3_EVENT_MANIFEST" <<'PY'
import sys
from portfolio_risk_thesis.day3.events import validate_event_manifest

print(len(validate_event_manifest(sys.argv[1])))
PY
)"
if (( event_count < 20 || event_count > 50 )); then
  fail "the reviewed Day 3 event manifest must contain 20-50 events; found $event_count"
fi

choose_day2_run
choose_portfolio

exposures_created=false
if [[ ! -e "$THESIS_DAY3_EXPOSURES" ]]; then
  exposure_evidence_ref="$(
    "$python_bin" - "$THESIS_DAY2_RUN_DIR/morning-metric-packs.json" "$THESIS_DAY3_PORTFOLIO_ID" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    packs = json.load(source)
pack = next(value for value in packs if value["portfolio_id"] == sys.argv[2])
print(
    next(
        (
            reference
            for reference in pack["evidence"]
            if reference.startswith("portfolio-receipt:")
        ),
        pack["evidence"][0],
    )
)
PY
  )"
  cat > "$THESIS_DAY3_EXPOSURES" <<EOF
- position_alias: position-001
  weight: "0.20"
  evidence_refs:
    - "$exposure_evidence_ref"
- position_alias: position-002
  weight: "0.20"
  evidence_refs:
    - "$exposure_evidence_ref"
- position_alias: position-003
  weight: "0.20"
  evidence_refs:
    - "$exposure_evidence_ref"
- position_alias: position-004
  weight: "0.20"
  evidence_refs:
    - "$exposure_evidence_ref"
- position_alias: position-005
  weight: "0.20"
  evidence_refs:
    - "$exposure_evidence_ref"
EOF
  chmod 600 "$THESIS_DAY3_EXPOSURES"
  exposures_created=true
fi
review_file \
  "$THESIS_DAY3_EXPOSURES" \
  "Review private-neutral exposure aliases; do not use PERMNO, GVKEY, or security identifiers." \
  "$exposures_created"
PYTHONPATH="$repository_root:$package_paths" "$python_bin" - "$THESIS_DAY3_EXPOSURES" <<'PY'
import sys
import yaml
from portfolio_risk_thesis.day3.contracts import PositionExposure

with open(sys.argv[1], encoding="utf-8") as source:
    document = yaml.safe_load(source)
if not isinstance(document, list) or not 5 <= len(document) <= 8:
    raise SystemExit("ERROR: reviewed exposure context must contain 5-8 positions")
for value in document:
    PositionExposure.model_validate(value)
PY
exposure_confirmation="${THESIS_DAY3_EXPOSURES_CONFIRMED:-}"
if [[ "$exposure_confirmation" != "REVIEWED_EXPOSURES" ]]; then
  read -r -p "Type REVIEWED_EXPOSURES to confirm aliases, weights, membership, and evidence: " exposure_confirmation
fi
[[ "$exposure_confirmation" == "REVIEWED_EXPOSURES" ]] \
  || fail "reviewed exposure confirmation is required"

if [[ ! -e "$THESIS_DAY3_MODEL_CONFIG" ]]; then
  model_snapshot="${THESIS_DAY3_MODEL_SNAPSHOT:-}"
  if [[ -z "$model_snapshot" ]]; then
    read -r -p "Explicit dated OpenAI model snapshot (for example gpt-4.1-mini-2025-04-14): " model_snapshot
  fi
  [[ -n "$model_snapshot" ]] || fail "explicit snapshot is required"
  cat > "$THESIS_DAY3_MODEL_CONFIG" <<EOF
provider_id: openai_responses
model_id: "$model_snapshot"
model_snapshot: "$model_snapshot"
prompt_manifest_digest: "sha256:$(shasum -a 256 examples/portfolio-risk-thesis/prompts/day3/prompt-manifest.yaml | awk '{print $1}')"
temperature: "0"
temperature_supported: true
maximum_output_tokens: 1600
timeout_seconds: 90
retry_count: 1
store: false
tools: []
response_schema_version: v1
EOF
  chmod 600 "$THESIS_DAY3_MODEL_CONFIG"
fi

read -r configured_model_snapshot configured_output_limit < <(
  "$python_bin" - "$THESIS_DAY3_MODEL_CONFIG" <<'PY'
import sys
import yaml

with open(sys.argv[1], encoding="utf-8") as source:
    configuration = yaml.safe_load(source)
print(
    str(configuration.get("model_snapshot", "")),
    int(configuration.get("maximum_output_tokens", 0)),
)
PY
)
if [[ "$configured_model_snapshot" == gpt-5.* ]] \
  && (( configured_output_limit < 4096 ))
then
  revised_model_config="$(
    "$python_bin" - "$THESIS_DAY3_MODEL_CONFIG" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
print(path.with_name(f"{path.stem}-output-4096{path.suffix}"))
PY
  )"
  if [[ -f "$revised_model_config" ]] \
    && "$python_bin" - "$THESIS_DAY3_MODEL_CONFIG" "$revised_model_config" <<'PY'
import sys
import yaml

with open(sys.argv[1], encoding="utf-8") as source:
    original = yaml.safe_load(source)
with open(sys.argv[2], encoding="utf-8") as source:
    revised = yaml.safe_load(source)
expected = dict(original)
expected["maximum_output_tokens"] = 4096
raise SystemExit(0 if revised == expected else 1)
PY
  then
    export THESIS_DAY3_MODEL_CONFIG="$revised_model_config"
    echo "Using the previously reviewed 4,096-token model-config revision."
  else
    [[ ! -e "$revised_model_config" ]] \
      || fail "existing 4,096-token model-config revision differs from the expected content"
    echo "The strict Day 3 JSON schema needs a 4,096-token output ceiling for GPT-5."
    echo "This raises the ceiling from $configured_output_limit; billing remains based on tokens actually used."
    output_limit_confirmation="${THESIS_DAY3_OUTPUT_LIMIT_CONFIRMED:-}"
    if [[ "$output_limit_confirmation" != "INCREASE_OUTPUT_LIMIT" ]]; then
      read -r -p "Type INCREASE_OUTPUT_LIMIT to create a reviewed model-config revision: " output_limit_confirmation
    fi
    [[ "$output_limit_confirmation" == "INCREASE_OUTPUT_LIMIT" ]] \
      || fail "the GPT-5 structured-output ceiling must be increased before the paid run"
    cp "$THESIS_DAY3_MODEL_CONFIG" "$revised_model_config"
    "$python_bin" - "$revised_model_config" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").splitlines()
updated = [
    "maximum_output_tokens: 4096"
    if line.startswith("maximum_output_tokens:")
    else line
    for line in lines
]
path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY
    chmod 600 "$revised_model_config"
    export THESIS_DAY3_MODEL_CONFIG="$revised_model_config"
    echo "Created reviewed model-config revision with maximum_output_tokens 4096."
  fi
fi

set +e
prepare_result="$(
  PYTHONPATH="$repository_root:$package_paths" "$python_bin" -m portfolio_risk_thesis.cli prepare-day3-experiment \
    --day2-run-directory "$THESIS_DAY2_RUN_DIR" \
    --event-manifest "$THESIS_DAY3_EVENT_MANIFEST" \
    --event-dataset "$THESIS_DAY3_EVENT_DATASET" \
    --model-config "$THESIS_DAY3_MODEL_CONFIG" \
    --portfolio-id "$THESIS_DAY3_PORTFOLIO_ID" \
    --exposures "$THESIS_DAY3_EXPOSURES" \
    --output "$THESIS_DAY3_EXPERIMENT_MANIFEST" 2>&1
)"
prepare_status=$?
set -e
if (( prepare_status != 0 )) \
  && [[ "$prepare_result" == *"immutable Day 3 experiment manifest already exists with different content"* ]]
then
  binding_revision="$(
    "$python_bin" - \
      "$THESIS_DAY2_RUN_DIR" \
      "$THESIS_DAY3_EVENT_MANIFEST" \
      "$THESIS_DAY3_EVENT_DATASET" \
      "$THESIS_DAY3_MODEL_CONFIG" \
      "$THESIS_DAY3_EXPOSURES" \
      "$THESIS_DAY3_PORTFOLIO_ID" <<'PY'
import hashlib
from pathlib import Path
import sys

digest = hashlib.sha256()
for value in sys.argv[1:6]:
    path = Path(value)
    digest.update(str(path.resolve()).encode())
    digest.update(b"\0")
    if path.is_file():
        digest.update(path.read_bytes())
    digest.update(b"\0")
digest.update(sys.argv[6].encode())
print(digest.hexdigest()[:16])
PY
  )"
  THESIS_DAY3_EXPERIMENT_MANIFEST="$(
    "$python_bin" - "$THESIS_DAY3_EXPERIMENT_MANIFEST" "$binding_revision" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
print(path.with_name(f"{path.stem}-{sys.argv[2]}{path.suffix}"))
PY
  )"
  export THESIS_DAY3_EXPERIMENT_MANIFEST
  echo "Preserving the existing immutable experiment manifest."
  echo "Using experiment-manifest revision: $THESIS_DAY3_EXPERIMENT_MANIFEST"
  prepare_result="$(
    PYTHONPATH="$repository_root:$package_paths" "$python_bin" -m portfolio_risk_thesis.cli prepare-day3-experiment \
      --day2-run-directory "$THESIS_DAY2_RUN_DIR" \
      --event-manifest "$THESIS_DAY3_EVENT_MANIFEST" \
      --event-dataset "$THESIS_DAY3_EVENT_DATASET" \
      --model-config "$THESIS_DAY3_MODEL_CONFIG" \
      --portfolio-id "$THESIS_DAY3_PORTFOLIO_ID" \
      --exposures "$THESIS_DAY3_EXPOSURES" \
      --output "$THESIS_DAY3_EXPERIMENT_MANIFEST"
  )"
  prepare_status=0
fi
if (( prepare_status != 0 )); then
  echo "$prepare_result" >&2
  exit "$prepare_status"
fi
echo "$prepare_result"
PYTHONPATH="$repository_root:$package_paths" "$python_bin" -m portfolio_risk_thesis.cli validate-day3 --experiment-manifest "$THESIS_DAY3_EXPERIMENT_MANIFEST"

read -r -p "Run the paid OpenAI experiment now? Type RUN_OPENAI to continue: " consent
[[ "$consent" == "RUN_OPENAI" ]] || { echo "Stopped before any external model call."; exit 0; }
if ! security find-generic-password -a "$USER" -s servicefabric-thesis-openai -w >/dev/null 2>&1; then
  read -r -s -p "OpenAI API key (stored only in your Keychain): " temporary_key
  printf '\n'
  [[ -n "$temporary_key" ]] || fail "an OpenAI API key is required for the authorized real run"
  security add-generic-password -U -a "$USER" -s servicefabric-thesis-openai -w "$temporary_key"
  unset temporary_key
fi
openai_key="$(security find-generic-password -a "$USER" -s servicefabric-thesis-openai -w)"
export OPENAI_API_KEY="$openai_key"
unset openai_key
[[ -n "$OPENAI_API_KEY" ]] || fail "Keychain item is unavailable"
trap 'unset OPENAI_API_KEY' EXIT
while true; do
  set +e
  run_result="$(
    PYTHONPATH="$repository_root:$package_paths" "$python_bin" -m portfolio_risk_thesis.cli run-day3 \
      --experiment-manifest "$THESIS_DAY3_EXPERIMENT_MANIFEST" \
      --provider openai_responses \
      --output-root "$THESIS_DAY3_OUTPUT_ROOT" 2>&1
  )"
  run_status=$?
  set -e
  if (( run_status == 0 )); then
    break
  fi
  echo "$run_result" >&2
  if [[ "$run_result" == *insufficient_quota* ]]; then
    echo "OpenAI rejected the call because this API project has no available quota."
    echo "Add billing or credits at: https://platform.openai.com/settings/organization/billing/overview"
    read -r -p "After quota is available, type RETRY_OPENAI to retry; press Enter to stop: " retry_consent
    [[ "$retry_consent" == "RETRY_OPENAI" ]] || exit "$run_status"
    continue
  fi
  exit "$run_status"
done
echo "$run_result"
run_id="$(
  printf '%s\n' "$run_result" \
    | "$python_bin" -c 'import json,sys; print(json.load(sys.stdin)["run_id"])'
)"
export THESIS_DAY3_RUN_DIR="$THESIS_DAY3_OUTPUT_ROOT/$run_id"
PYTHONPATH="$repository_root:$package_paths" "$python_bin" -m portfolio_risk_thesis.cli inspect-day3-comparison \
  --run-directory "$THESIS_DAY3_RUN_DIR"
echo "Running the formal Day 3 public and local evidence gates."
make verify-thesis-day3-real
unset OPENAI_API_KEY
trap - EXIT
echo "Day 3 local model run and formal gate completed: $THESIS_DAY3_RUN_DIR"
