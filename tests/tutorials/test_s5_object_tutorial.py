from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_all_s5_object_tutorials_are_read_only_and_pass() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/thesis/tutorial_s5_objects.py", "all"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"
    assert payload["not_thesis_evidence"] is True
    assert tuple(sorted(payload["sections"])) == (
        "authority",
        "governance",
        "outputs",
        "reproducibility",
        "resources",
        "scientific",
        "world",
    )
    assert payload["sections"]["resources"]["undeclared_capability_allowed"] is False
    assert payload["sections"]["authority"]["supra_agent_enabled"] is False
    assert payload["sections"]["reproducibility"]["repeat_digest_equal"] is True
