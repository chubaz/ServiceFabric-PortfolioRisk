#!/usr/bin/env bash
set -euo pipefail

repository_root="$(git rev-parse --show-toplevel)"
runtime_venv="${SERVICEFABRIC_RUNTIME_VENV:?SERVICEFABRIC_RUNTIME_VENV is required}"
: "${SERVICEFABRIC_HOME:?SERVICEFABRIC_HOME is required}"
: "${PORTFOLIO_RISK_DATA_ROOT:?PORTFOLIO_RISK_DATA_ROOT is required}"
export SERVICEFABRIC_HOME PORTFOLIO_RISK_DATA_ROOT

"$repository_root/scripts/day0/bootstrap_servicefabric_runtime.py" --venv "$runtime_venv"
servicefabric="$runtime_venv/bin/servicefabric"

cleanup() {
  "$servicefabric" apps stop portfolio-risk-workbench >/dev/null 2>&1 || true
  "$servicefabric" apps stop text-utility >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM
cleanup

"$servicefabric" init

# Preserve the pinned upstream acceptance journey as the first runtime gate.
"$servicefabric" apps install "$repository_root/vendor/servicefabric/examples/text-utility"
"$servicefabric" apps build text-utility
"$servicefabric" apps start text-utility
"$servicefabric" apps status text-utility
"$servicefabric" apps resources text-utility
"$servicefabric" tools describe text.count_words
"$servicefabric" call text.count_words --input '{"text":"ServiceFabric validates Text Utility before Portfolio Risk."}'
"$servicefabric" apps stop text-utility
if "$servicefabric" call text.count_words --input '{"text":"must not execute"}'; then
  echo "Text Utility capability unexpectedly executed after stop" >&2
  exit 1
fi

"$servicefabric" apps install "$repository_root/apps/portfolio-risk-workbench"
"$servicefabric" apps build portfolio-risk-workbench
"$servicefabric" apps start portfolio-risk-workbench
"$servicefabric" apps status portfolio-risk-workbench
"$servicefabric" apps resources portfolio-risk-workbench
"$servicefabric" tools describe risk.workbench.status
"$servicefabric" call risk.workbench.status --input '{}'
"$servicefabric" call portfolio.exposure.summarize --input '{}'
"$servicefabric" call market.anomaly.detect --input '{}'
"$servicefabric" call alert.draft.synthesize --input '{}'
"$servicefabric" apps stop portfolio-risk-workbench
if "$servicefabric" call risk.workbench.status --input '{}'; then
  echo "Portfolio Risk capability unexpectedly executed after stop" >&2
  exit 1
fi

echo "ServiceFabric Portfolio Risk smoke: PASS"
