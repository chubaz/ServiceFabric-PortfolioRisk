#!/usr/bin/env bash
set -euo pipefail

repository_root="$(git rev-parse --show-toplevel)"
runtime_venv="${DAY23_SERVICEFABRIC_RUNTIME_VENV:?DAY23_SERVICEFABRIC_RUNTIME_VENV is required}"
servicefabric_home_base="${DAY23_SERVICEFABRIC_HOME:?DAY23_SERVICEFABRIC_HOME is required}"
data_root_base="${PORTFOLIO_RISK_DATA_ROOT:?PORTFOLIO_RISK_DATA_ROOT is required}"
stage_dir="$(mktemp -d "${TMPDIR:-/tmp}/servicefabric-d23-part2.XXXXXX")"
staged_package="$stage_dir/portfolio-risk-workbench"
stage_python="${DAY23_STAGE_PYTHON:-python3}"
"$stage_python" "$repository_root/apps/portfolio-risk-workbench/stage_package.py" \
  --source "$repository_root/apps/portfolio-risk-workbench" \
  --output "$staged_package" \
  --canonical-fixtures "$repository_root/data/fixtures/synthetic/day23"
"$stage_python" "$repository_root/scripts/day0/update_manifest_hashes.py" \
  "$staged_package/servicefabric-package.json" --check
manifest_digest="$(sha256sum "$staged_package/servicefabric-package.json" | awk '{print $1}')"
upstream_commit_before="$(git -C "$repository_root/vendor/servicefabric" rev-parse HEAD)"
upstream_status_before="$(git -C "$repository_root/vendor/servicefabric" status --porcelain)"
SERVICEFABRIC_HOME="$servicefabric_home_base/part2/$manifest_digest"
PORTFOLIO_RISK_DATA_ROOT="$data_root_base/day23-part2-state/servicefabric/$manifest_digest"
export SERVICEFABRIC_HOME PORTFOLIO_RISK_DATA_ROOT

servicefabric="$runtime_venv/bin/servicefabric"
python="$runtime_venv/bin/python"

cleanup() {
  "$servicefabric" apps stop portfolio-risk-workbench >/dev/null 2>&1 || true
  "$servicefabric" apps stop text-utility >/dev/null 2>&1 || true
  if [[ "${1:-}" == "remove" ]]; then
    rm -rf "$stage_dir"
  fi
}
trap 'cleanup remove' EXIT INT TERM
cleanup

"$repository_root/scripts/day23/bootstrap_staged_servicefabric_runtime.py" \
  --venv "$runtime_venv" \
  --manifest "$staged_package/servicefabric-package.json"

effect_free_call() {
  local tool_id="$1"
  local output
  output="$("$servicefabric" call "$tool_id" --input '{}')"
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
actual = payload.get("capability_id")
effects = payload.get("effects")
if actual != expected:
    raise SystemExit(f"unexpected capability response: {actual}")
if effects != []:
    raise SystemExit(f"capability returned non-empty or missing effects: {effects}")
if payload.get("human_review_required") is not True:
    raise SystemExit("Part 2 capability did not retain explicit human review")
data = payload.get("data")
if expected == "portfolio.data_context.create":
    if not data or data.get("blocked") or not data.get("mapping_coverage", {}).get("complete"):
        raise SystemExit("hosted portfolio data context was not complete")
elif expected == "events.query.as_of":
    if payload.get("status") != "stopped":
        raise SystemExit("empty hosted event selection did not truthfully stop")
elif expected == "monitoring.policy.evaluate":
    if not data or data.get("effects") != []:
        raise SystemExit("hosted monitoring policy evaluation was not effect-free")
elif expected == "monitoring.run.contextual":
    if not data or len(data.get("four_agent_timeline", [])) != 4:
        raise SystemExit("hosted contextual run did not preserve all four agents")
elif expected == "monitoring.replay":
    if not data or not data.get("steps"):
        raise SystemExit("hosted deterministic replay returned no steps")
elif expected == "monitoring.evaluate":
    if not data or data.get("effects") != [] or "methodology" not in data:
        raise SystemExit("hosted monitoring evaluation was incomplete")
elif expected == "monitoring.report.render":
    if not data or not data.get("markdown") or not data.get("html"):
        raise SystemExit("hosted monitoring report did not include Markdown and HTML")
'
}

"$servicefabric" init

# The pinned upstream Text Utility baseline is the first smoke gate.
"$servicefabric" apps install "$repository_root/vendor/servicefabric/examples/text-utility"
"$servicefabric" apps build text-utility
"$servicefabric" apps start text-utility
"$servicefabric" apps status text-utility
"$servicefabric" apps resources text-utility
"$servicefabric" tools describe text.count_words
"$servicefabric" call text.count_words --input '{"text":"ServiceFabric validates Text Utility before the Day 2-3 Part 2 Workbench."}'
"$servicefabric" apps stop text-utility
if "$servicefabric" call text.count_words --input '{"text":"must not execute"}'; then
  echo "Text Utility capability unexpectedly executed after stop" >&2
  exit 1
fi

"$servicefabric" apps install "$staged_package"
"$servicefabric" apps build portfolio-risk-workbench
"$servicefabric" apps start portfolio-risk-workbench
"$servicefabric" apps status portfolio-risk-workbench
"$servicefabric" apps resources portfolio-risk-workbench

for tool_id in \
  portfolio.data_context.create \
  events.query.as_of \
  monitoring.policy.evaluate \
  monitoring.run.contextual \
  monitoring.replay \
  monitoring.evaluate \
  monitoring.report.render
do
  "$servicefabric" tools describe "$tool_id"
  effect_free_call "$tool_id"
done

application_record="$SERVICEFABRIC_HOME/hosted-applications/portfolio-risk-workbench/application.json"
process_identity="$("$python" -c '
import json
import sys
record = json.load(open(sys.argv[1], encoding="utf-8"))
print(str(record.get("pid")) + ":" + str(record.get("process_start_ticks")))
' "$application_record")"

"$servicefabric" apps stop portfolio-risk-workbench
if "$servicefabric" call monitoring.evaluate --input '{}'; then
  echo "D23 Part 2 capability unexpectedly executed after Workbench stop" >&2
  exit 1
fi

"$python" -c '
import json
import sys
from pathlib import Path

record_path = Path(sys.argv[1])
pid_text, ticks_text = sys.argv[2].split(":", 1)
record = json.loads(record_path.read_text(encoding="utf-8"))
if record.get("state") != "stopped" or record.get("pid") is not None:
    raise SystemExit("Workbench process record was not cleaned up after stop")
pid = int(pid_text)
stat = Path(f"/proc/{pid}/stat")
if stat.exists() and stat.read_text(encoding="utf-8").split()[21] == ticks_text:
    raise SystemExit("Workbench process remains alive after stop")
' "$application_record" "$process_identity"

upstream_commit_after="$(git -C "$repository_root/vendor/servicefabric" rev-parse HEAD)"
upstream_status_after="$(git -C "$repository_root/vendor/servicefabric" status --porcelain)"
if [[ "$upstream_commit_after" != "$upstream_commit_before" ]] ||
  [[ "$upstream_status_after" != "$upstream_status_before" ]]; then
  echo "Part 2 smoke modified the pinned upstream ServiceFabric tree" >&2
  exit 1
fi

echo "ServiceFabric Portfolio Risk D23 Part 2 local smoke: PASS"
