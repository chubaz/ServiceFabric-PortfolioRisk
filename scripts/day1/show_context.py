#!/usr/bin/env python3
"""Print concise Day 1 preparation context for a lane supervisor."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for relative in ("config/agent/day1/status.json", "config/agent/day1/waves.json", "config/agent/day1/lanes.json"):
    print(f"== {relative} ==")
    payload = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    if relative.endswith("status.json"):
        print(json.dumps(payload, indent=2))
    elif relative.endswith("waves.json"):
        for wave in payload["waves"]:
            print(f"{wave['id']}: {wave['objective']} | depends_on={','.join(wave['depends_on']) or 'none'} | lanes={','.join(wave['lanes'])}")
            print(f"  acceptance: {'; '.join(wave['acceptance_gates'])}")
        print(f"integration order: {' -> '.join(payload['integration_order'])}")
    else:
        for lane, record in payload["lanes"].items():
            print(f"{lane}: branch={record['branch']} handoff={next(item for item in record['allowed_files'] if item.startswith('docs/handoffs/'))}")
