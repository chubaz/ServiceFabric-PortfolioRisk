#!/usr/bin/env bash
set -euo pipefail

repository_root="$(git rev-parse --show-toplevel)"
cd "$repository_root"

expected_sha="$(
  python3 - <<'PY'
import json
from pathlib import Path

manifest = json.loads(
    Path("config/agent/day0/upstream.json").read_text(encoding="utf-8")
)
print(manifest["commit"])
PY
)"

test -d vendor/servicefabric
test -f .gitmodules

actual_sha="$(git -C vendor/servicefabric rev-parse HEAD)"

if [[ "$actual_sha" != "$expected_sha" ]]; then
  echo "ServiceFabric pin mismatch." >&2
  echo "Expected: $expected_sha" >&2
  echo "Actual:   $actual_sha" >&2
  exit 1
fi

submodule_url="$(
  git config \
    -f .gitmodules \
    --get submodule.vendor/servicefabric.url
)"

if [[ "$submodule_url" != "https://github.com/chubaz/ServiceFabric-Public.git" ]]; then
  echo "Unexpected ServiceFabric submodule URL: $submodule_url" >&2
  exit 1
fi

if [[ -n "$(git -C vendor/servicefabric status --porcelain)" ]]; then
  echo "ServiceFabric submodule is dirty." >&2
  git -C vendor/servicefabric status --short
  exit 1
fi

forbidden_tracked="$(
  git ls-files \
    | grep -Ei \
      '(^|/)(\.env(\..*)?|secrets?|credentials?|state|servicefabric-home)(/|$)|\.(pem|key|p12|pfx)$|(^|/)(crsp|compustat|bloomberg|ravenpack|accern)(/|$)|^data/(landing|normalized|curated|snapshots)/' \
    || true
)"

local_data_tracked="$(
  while IFS= read -r tracked_path; do
    case "$tracked_path" in
      *.duckdb|*.duckdb.wal|*.sqlite|*.sqlite3|*.db)
        printf '%s\n' "$tracked_path"
        ;;
      *.parquet|*.arrow|*.feather)
        case "$tracked_path" in
          data/fixtures/synthetic/*) ;;
          *) printf '%s\n' "$tracked_path" ;;
        esac
        ;;
    esac
  done < <(git ls-files)
)"

if [[ -n "$local_data_tracked" ]]; then
  forbidden_tracked="${forbidden_tracked}${forbidden_tracked:+$'\n'}${local_data_tracked}"
fi

if [[ -n "$forbidden_tracked" ]]; then
  echo "Forbidden private or mutable paths are tracked:" >&2
  echo "$forbidden_tracked" >&2
  exit 1
fi

while IFS= read -r -d '' json_file; do
  python3 -m json.tool "$json_file" >/dev/null
done < <(find config -type f -name '*.json' -print0)

git diff --check

echo "Repository check: PASS"
echo "ServiceFabric pin: $actual_sha"
