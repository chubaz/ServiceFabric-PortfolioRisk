#!/usr/bin/env bash
set -euo pipefail

repository_root="$(git rev-parse --show-toplevel)"
runtime_venv="${DAY23_SERVICEFABRIC_RUNTIME_VENV:?DAY23_SERVICEFABRIC_RUNTIME_VENV is required}"
servicefabric_home_base="${DAY23_SERVICEFABRIC_HOME:?DAY23_SERVICEFABRIC_HOME is required}"
data_root_base="${PORTFOLIO_RISK_DATA_ROOT:?PORTFOLIO_RISK_DATA_ROOT is required}"
manifest_digest="$(sha256sum "$repository_root/apps/portfolio-risk-workbench/servicefabric-package.json" | awk '{print $1}')"
SERVICEFABRIC_HOME="$servicefabric_home_base/$manifest_digest"
PORTFOLIO_RISK_DATA_ROOT="$data_root_base/day23-phase1/data-plane"
export SERVICEFABRIC_HOME PORTFOLIO_RISK_DATA_ROOT

"$repository_root/scripts/day1/bootstrap_servicefabric_runtime.py" --venv "$runtime_venv"
servicefabric="$runtime_venv/bin/servicefabric"
python="$runtime_venv/bin/python"

cleanup() {
  "$servicefabric" apps stop portfolio-risk-workbench >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM
cleanup

effect_free_call() {
  local tool_id="$1"
  local input="$2"
  local output
  output="$("$servicefabric" call "$tool_id" --input "$input")"
  printf '%s\n' "$output"
  SERVICEFABRIC_CALL_OUTPUT="$output" EXPECTED_CAPABILITY_ID="$tool_id" "$python" -c '
import json
import os

rendered = os.environ["SERVICEFABRIC_CALL_OUTPUT"]
expected = os.environ["EXPECTED_CAPABILITY_ID"]
candidate = next(
    (line.split(" -> ", 1)[1] for line in rendered.splitlines() if " -> {" in line),
    None,
)
if candidate is None:
    raise SystemExit("ServiceFabric call output did not contain a JSON result")
payload = json.loads(candidate)
if payload.get("capability_id") != expected:
    raise SystemExit(f"unexpected capability response: {payload.get('capability_id')}")
if payload.get("effects") != []:
    raise SystemExit(f"capability returned non-empty or missing effects: {payload.get('effects')}")
if expected == "data.provider.catalog":
    providers = payload.get("data", {}).get("providers", [])
    external = [item for item in providers if item.get("provider_class") == "Network-disabled provider"]
    if len(external) != 6 or any(
        item.get("network_state") != "disabled" or item.get("access_state") != "disabled"
        for item in external
    ):
        raise SystemExit("external provider network state is not explicitly disabled")
elif expected == "data.import.preview":
    data = payload.get("data", {})
    if not data.get("confirmable") or data.get("dataset", {}).get("dataset_kind") != "daily_market":
        raise SystemExit("hosted synthetic import preview was not valid")
elif expected == "data.dataset.list":
    if not payload.get("data", {}).get("snapshots"):
        raise SystemExit("hosted dataset catalogue did not expose immutable snapshots")
elif expected == "data.query.fixed":
    data = payload.get("data", {})
    if data.get("manifest_id") != "security-master" or not data.get("rows"):
        raise SystemExit("hosted fixed query did not return the reviewed security master")
'
}

"$servicefabric" init
"$servicefabric" apps install "$repository_root/apps/portfolio-risk-workbench"
"$servicefabric" apps build portfolio-risk-workbench
"$servicefabric" apps start portfolio-risk-workbench
"$servicefabric" apps status portfolio-risk-workbench
"$servicefabric" apps resources portfolio-risk-workbench

preview_input='{"content":"permno,date,available_at,prc,ret,shrout,vol,cusip,ticker,currency\n910001,2026-06-29,2026-06-29T21:00:00Z,-40.00,0.0100,1000000,125000,99100010,NOVA,USD\n","filename":"servicefabric-crsp-like.csv","provider_profile":"synthetic_local","provider_id":"fictional-local-provider","provider_name":"Fictional Local Provider","dataset_id":"servicefabric-synthetic-daily-market","dataset_kind":"daily_market","dataset_description":"Explicitly synthetic hosted Phase 1 preview","revision_id":"revision-2026-07-22","rights_state":"reviewed_synthetic","publication_restriction":"synthetic_only","workbench_profile":"research","retrieved_at":"2026-07-22T10:00:00Z"}'
fixed_query_input='{"manifest_id":"security-master","parameters":{},"limit":100}'

for tool_id in \
  data.provider.catalog \
  data.import.preview \
  data.dataset.list \
  data.query.fixed
do
  "$servicefabric" tools describe "$tool_id"
  case "$tool_id" in
    data.import.preview) effect_free_call "$tool_id" "$preview_input" ;;
    data.query.fixed) effect_free_call "$tool_id" "$fixed_query_input" ;;
    *) effect_free_call "$tool_id" '{}' ;;
  esac
done

application_record="$SERVICEFABRIC_HOME/hosted-applications/portfolio-risk-workbench/application.json"
process_identity="$("$python" -c '
import json
import sys
record = json.load(open(sys.argv[1], encoding="utf-8"))
print(str(record.get("pid")) + ":" + str(record.get("process_start_ticks")))
' "$application_record")"

"$servicefabric" apps stop portfolio-risk-workbench
if "$servicefabric" call data.dataset.list --input '{}'; then
  echo "D23 Phase 1 capability unexpectedly executed after Workbench stop" >&2
  exit 1
fi

"$python" -c '
import json
import os
import sys
from pathlib import Path

record_path = Path(sys.argv[1])
pid_text, ticks_text = sys.argv[2].split(":", 1)
record = json.loads(record_path.read_text(encoding="utf-8"))
if record.get("state") != "stopped" or record.get("pid") is not None:
    raise SystemExit("Workbench process record was not cleaned up after stop")
pid = int(pid_text)
stat = Path(f"/proc/{pid}/stat")
if stat.exists():
    current_ticks = stat.read_text(encoding="utf-8").split()[21]
    if current_ticks == ticks_text:
        raise SystemExit("Workbench process remains alive after stop")
' "$application_record" "$process_identity"

echo "ServiceFabric Portfolio Risk D23 Phase 1 local smoke: PASS"
