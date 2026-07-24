from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_PIN = "7632b61d94a966346f95eb6c5bb2a5ea27f3bc14"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout


def tracked_files() -> list[str]:
    return [path for path in git("ls-files").splitlines() if path]


def test_servicefabric_submodule_is_pinned() -> None:
    upstream = json.loads((ROOT / "config/agent/day0/upstream.json").read_text())
    assert upstream["commit"] == EXPECTED_PIN
    gitlink = git("ls-tree", "HEAD", "vendor/servicefabric").split()
    assert gitlink[:3] == ["160000", "commit", EXPECTED_PIN]
    assert git("-C", "vendor/servicefabric", "rev-parse", "HEAD").strip() == EXPECTED_PIN


def test_worktree_does_not_modify_servicefabric() -> None:
    assert not git("diff", "--name-only", "--", "vendor/servicefabric").splitlines()
    assert not git("diff", "--cached", "--name-only", "--", "vendor/servicefabric").splitlines()
    assert not git("-C", "vendor/servicefabric", "status", "--porcelain").strip()


def test_package_ownership_is_disjoint_and_has_one_specialist_handoff() -> None:
    manifest = json.loads((ROOT / "config/agent/day0/lanes.json").read_text())
    lanes = manifest["lanes"]
    assert manifest["integration_order"] == [
        "domain",
        "planning",
        "data",
        "agents",
        "application",
        "integration",
    ]
    handoffs = {
        "domain": "docs/handoffs/day-0/domain.md",
        "planning": "docs/handoffs/day-0/planning.md",
        "data": "docs/handoffs/day-0/data.md",
        "application": "docs/handoffs/day-0/application.md",
        "agents": "docs/handoffs/day-0/agents.md",
    }
    specialist_paths: list[str] = []
    for lane, handoff in handoffs.items():
        allowed = lanes[lane]["allowed_paths"]
        assert allowed.count(handoff) == 1
        assert [path for path in allowed if path.startswith("docs/handoffs/")] == [handoff]
        specialist_paths.extend(path for path in allowed if path != handoff)
    assert len(specialist_paths) == len(set(specialist_paths))


@pytest.mark.parametrize(
    "forbidden",
    [
        re.compile(r"(^|/)(crsp|compustat|bloomberg|ravenpack|accern)(/|$)", re.I),
        re.compile(r"^data/(landing|normalized|curated|snapshots)/"),
        re.compile(r"\.(duckdb|sqlite3?|db|arrow|feather)$", re.I),
    ],
)
def test_provider_and_mutable_data_paths_are_not_tracked(forbidden: re.Pattern[str]) -> None:
    assert not [path for path in tracked_files() if forbidden.search(path)]


def test_only_reviewed_synthetic_part2_parquet_fixture_is_tracked() -> None:
    tracked_parquet = {
        path for path in tracked_files() if Path(path).suffix.lower() == ".parquet"
    }
    assert tracked_parquet == {
        "data/fixtures/synthetic/day23/accern-like-events.parquet"
    }


def test_reviewed_synthetic_fixtures_have_one_canonical_tracked_root() -> None:
    synthetic_fixture_paths = {
        path
        for path in tracked_files()
        if path.startswith("fixtures/synthetic/")
        or "/fixtures/synthetic/" in path
    }
    assert synthetic_fixture_paths
    assert all(
        path.startswith("data/fixtures/synthetic/")
        for path in synthetic_fixture_paths
    )


def test_no_broker_or_order_execution_package_exists() -> None:
    prohibited = re.compile(r"(^|/)(broker|brokers|orders?|order_execution|trading)(/|$)", re.I)
    assert not [path for path in tracked_files() if prohibited.search(path)]


def test_no_secret_literals_are_tracked() -> None:
    patterns = [
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
        re.compile(r"sk-[A-Za-z0-9]{20,}"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ]
    matches: list[str] = []
    for relative in tracked_files():
        path = ROOT / relative
        if path.is_symlink() or not path.is_file():
            continue
        content = path.read_bytes()
        if b"\0" in content:
            continue
        text = content.decode("utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in patterns):
            matches.append(relative)
    assert not matches
