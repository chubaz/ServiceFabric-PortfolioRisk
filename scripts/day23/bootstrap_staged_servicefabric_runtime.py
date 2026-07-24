#!/usr/bin/env python3
"""Bootstrap the pinned ServiceFabric runtime against a staged app manifest.

The shared Day 1 bootstrap establishes the pinned runtime and local package
set from the repository manifest. Part 2 then supplies an ephemeral,
self-contained Workbench package whose manifest must also be embedded in the
reviewed host. This adapter rebuilds only the copied application-host package
from the read-only pinned upstream tree and installs that reviewed host into
the already bootstrapped runtime.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
HOST_PACKAGE_NAME = "servicefabric-application-host"

if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))


def run(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venv", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    manifest = args.manifest.resolve(strict=True)
    package_root = manifest.parent
    package = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(package, dict) or package.get("application_id") != "portfolio-risk-workbench":
        raise SystemExit("staged manifest is not the reviewed Portfolio Risk Workbench")
    if not (package_root / "app.py").is_file():
        raise SystemExit("staged Workbench package is missing app.py")

    venv_path = args.venv.resolve(strict=True)
    python = venv_path / "bin" / "python"
    if not python.is_file():
        raise SystemExit(f"ServiceFabric runtime Python is unavailable: {python}")

    # Preserve the normal pinned runtime and package-lock checks. The staged
    # host replacement below is deliberately performed after it.
    run(
        [
            str(python),
            str(REPOSITORY / "scripts/day1/bootstrap_servicefabric_runtime.py"),
            "--venv",
            str(venv_path),
        ],
        cwd=REPOSITORY,
    )

    from scripts.day0.bootstrap_servicefabric_runtime import servicefabric_projects

    upstream = REPOSITORY / "vendor" / "servicefabric"
    projects = servicefabric_projects(upstream)
    try:
        host_source = projects[HOST_PACKAGE_NAME][0]
    except KeyError as error:
        raise SystemExit("pinned ServiceFabric application-host package is missing") from error

    host_patcher = REPOSITORY / "scripts/day0/patch_servicefabric_application_host.py"
    with tempfile.TemporaryDirectory(prefix="portfolio-risk-d23-staged-host-") as temporary:
        staged_host = Path(temporary) / "application_host"
        shutil.copytree(host_source, staged_host)
        run(
            [
                str(python),
                str(host_patcher),
                str(staged_host / "servicefabric_application_host" / "service.py"),
                str(manifest),
            ],
            cwd=REPOSITORY,
        )
        run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--no-build-isolation",
                "--force-reinstall",
                str(staged_host),
            ],
            cwd=REPOSITORY,
        )

    run([str(python), "-m", "pip", "check"], cwd=REPOSITORY)
    print(f"ServiceFabric staged-manifest runtime ready: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
