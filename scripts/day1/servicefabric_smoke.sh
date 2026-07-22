#!/usr/bin/env bash
set -euo pipefail

repository_root="$(git rev-parse --show-toplevel)"
runtime_venv="${SERVICEFABRIC_RUNTIME_VENV:?SERVICEFABRIC_RUNTIME_VENV is required}"
: "${SERVICEFABRIC_HOME:?SERVICEFABRIC_HOME is required}"
: "${PORTFOLIO_RISK_DATA_ROOT:?PORTFOLIO_RISK_DATA_ROOT is required}"
manifest_digest="$(sha256sum "$repository_root/apps/portfolio-risk-workbench/servicefabric-package.json" | awk '{print $1}')"
SERVICEFABRIC_HOME="$SERVICEFABRIC_HOME/$manifest_digest"
export SERVICEFABRIC_HOME PORTFOLIO_RISK_DATA_ROOT

"$repository_root/scripts/day1/bootstrap_servicefabric_runtime.py" --venv "$runtime_venv"
servicefabric="$runtime_venv/bin/servicefabric"
python="$runtime_venv/bin/python"

cleanup() {
  "$servicefabric" apps stop portfolio-risk-workbench >/dev/null 2>&1 || true
  "$servicefabric" apps stop text-utility >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM
cleanup

effect_free_call() {
  local tool_id="$1"
  local output
  output="$("$servicefabric" call "$tool_id" --input '{}')"
  printf '%s\n' "$output"
  SERVICEFABRIC_CALL_OUTPUT="$output" "$python" -c '
import json
import os

rendered = os.environ["SERVICEFABRIC_CALL_OUTPUT"]
candidate = next(
    (line.split(" -> ", 1)[1] for line in rendered.splitlines() if " -> {" in line),
    None,
)
if candidate is None:
    raise SystemExit("ServiceFabric call output did not contain a JSON result")
payload = json.loads(candidate)
effects = payload.get("effects")
if effects != []:
    raise SystemExit(f"capability returned non-empty or missing effects: {effects}")
'
}

"$servicefabric" init

# The original pinned Text Utility journey remains the first acceptance gate.
"$servicefabric" apps install "$repository_root/vendor/servicefabric/examples/text-utility"
"$servicefabric" apps build text-utility
"$servicefabric" apps start text-utility
"$servicefabric" apps status text-utility
"$servicefabric" apps resources text-utility
"$servicefabric" tools describe text.count_words
"$servicefabric" call text.count_words --input '{"text":"ServiceFabric validates Text Utility before the Day 1 Workbench."}'
"$servicefabric" apps stop text-utility
if "$servicefabric" call text.count_words --input '{"text":"must not execute"}'; then
  echo "Text Utility capability unexpectedly executed after stop" >&2
  exit 1
fi

"$servicefabric" apps install "$repository_root/apps/portfolio-risk-workbench"
"$servicefabric" apps build portfolio-risk-workbench
"$servicefabric" apps start portfolio-risk-workbench
"$servicefabric" apps status portfolio-risk-workbench
resources_output="$("$servicefabric" apps resources portfolio-risk-workbench)"
printf '%s\n' "$resources_output"
runtime_application="$SERVICEFABRIC_HOME/hosted-applications/portfolio-risk-workbench/runtime"
"$python" -c '
import hashlib
import json
import sys
from pathlib import Path

runtime = Path(sys.argv[1])
manifest = json.loads((runtime / "servicefabric-package.json").read_text(encoding="utf-8"))
declared = {item["path"]: item["sha256"] for item in manifest["source_files"]}
required = {"templates/dashboard.html", "templates/risk.html", "static/workbench.css"}
if not required <= declared.keys():
    raise SystemExit("semantic HTML/CSS resources are absent from the built manifest")
for relative, expected in declared.items():
    path = runtime / relative
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit(f"built resource is absent or has the wrong digest: {relative}")
' "$runtime_application"

for tool_id in \
  portfolio.input.preview \
  provider.catalog.list \
  risk.volatility.annualized \
  risk.var.historical \
  risk.scenario.evaluate \
  risk.report.render
do
  "$servicefabric" tools describe "$tool_id"
  effect_free_call "$tool_id"
done

"$servicefabric" apps stop portfolio-risk-workbench
if "$servicefabric" call risk.volatility.annualized --input '{}'; then
  echo "Day 1 capability unexpectedly executed after Workbench stop" >&2
  exit 1
fi

echo "ServiceFabric Portfolio Risk Day 1 smoke: PASS"
