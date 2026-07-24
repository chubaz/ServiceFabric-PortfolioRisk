#!/usr/bin/env python3
"""Stage the Workbench with reviewed synthetic resources for local hosting.

The repository keeps reviewed synthetic observations in the single canonical
``data/fixtures/synthetic`` tree.  ServiceFabric, however, installs a
self-contained application tree and rejects path traversal and symlinks.  This
small, explicit staging boundary copies the allow-listed resources into a
temporary package tree and regenerates its complete source digest manifest.
It is invoked before ``servicefabric apps install``; the staged tree is never
written back into the repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


FIXTURE_NAMES = (
    "crsp_like_daily.csv",
    "compustat_like_annual.csv",
    "crsp_compustat_link.csv",
    "synthetic-outcomes.csv",
)
MANIFEST_NAME = "servicefabric-package.json"


class StagingError(ValueError):
    """The reviewed package staging contract cannot be satisfied."""


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _files(root: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise StagingError(f"symlinks are not permitted in a package tree: {path}")
        if path.is_file() and path.name != MANIFEST_NAME and "__pycache__" not in path.parts:
            files.append(path)
    return tuple(files)


def _canonical_fixtures(source: Path, explicit_root: Path | None) -> Path:
    root = explicit_root or source.parents[1] / "data" / "fixtures" / "synthetic" / "day23"
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise StagingError(f"canonical fixture root is not a directory: {root}")
    return root


def stage_package(
    source: Path,
    output: Path,
    *,
    canonical_fixture_root: Path | None = None,
) -> Path:
    """Create a self-contained, digest-locked package tree at ``output``."""

    source = source.resolve(strict=True)
    if not source.is_dir():
        raise StagingError(f"application source is not a directory: {source}")
    output = output.resolve()
    if output == source or source in output.parents:
        raise StagingError("staging output must not be inside the application source")
    if output.exists():
        raise StagingError(f"staging output already exists: {output}")

    manifest_path = source / MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StagingError("application manifest is unreadable") from error
    if not isinstance(manifest, dict) or manifest.get("application_id") != "portfolio-risk-workbench":
        raise StagingError("staging only supports the reviewed Portfolio Risk Workbench")

    fixture_root = _canonical_fixtures(source, canonical_fixture_root)
    fixtures = []
    for name in FIXTURE_NAMES:
        path = fixture_root / name
        if path.is_symlink() or not path.is_file():
            raise StagingError(f"required canonical fixture is unavailable: {path}")
        fixtures.append((name, path))

    shutil.copytree(
        source,
        output,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )
    for name, source_path in fixtures:
        target = output / "fixtures" / "synthetic" / "day23" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)

    declared = [
        {
            "path": path.relative_to(output).as_posix(),
            "sha256": _digest(path),
        }
        for path in _files(output)
    ]
    manifest["source_files"] = declared
    (output / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--canonical-fixtures", type=Path)
    args = parser.parse_args()
    stage_package(
        args.source,
        args.output,
        canonical_fixture_root=args.canonical_fixtures,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
