#!/usr/bin/env python3
"""Create or reuse the bounded, source-digested Day 1 ServiceFabric runtime."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from scripts.day0.bootstrap_servicefabric_runtime import (  # noqa: E402
    UPSTREAM_COMMIT,
    dependency_closure,
    digest_inputs,
    digest_tree,
    run,
    servicefabric_projects,
)


LOCAL_PACKAGE_NAMES = (
    "risk_domain",
    "risk_planning",
    "risk_data",
    "risk_capabilities",
    "risk_agents",
    "risk_analytics",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venv", type=Path, required=True)
    args = parser.parse_args()

    upstream = REPOSITORY / "vendor" / "servicefabric"
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=upstream,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != UPSTREAM_COMMIT:
        raise SystemExit(f"unexpected ServiceFabric pin: {head}")
    if subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=upstream,
        check=True,
        capture_output=True,
        text=True,
    ).stdout:
        raise SystemExit("pinned ServiceFabric submodule must remain clean")
    if sys.version_info[:2] != (3, 11):
        raise SystemExit("the ServiceFabric runtime requires Python 3.11")

    venv_path = args.venv.resolve()
    if not (venv_path / "bin" / "python").exists():
        venv_path.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True).create(venv_path)
    python = venv_path / "bin" / "python"
    pip = [str(python), "-m", "pip"]

    manifest = REPOSITORY / "apps" / "portfolio-risk-workbench" / "servicefabric-package.json"
    risk_lock_path = REPOSITORY / "apps" / "portfolio-risk-workbench" / "risk-package-lock.json"
    host_patcher = REPOSITORY / "scripts" / "day0" / "patch_servicefabric_application_host.py"
    client_patcher = REPOSITORY / "scripts" / "day0" / "patch_servicefabric_client.py"
    requirement_lock = REPOSITORY / "requirements" / "day1.lock"
    local_packages = tuple(REPOSITORY / "packages" / name for name in LOCAL_PACKAGE_NAMES)

    risk_lock = json.loads(risk_lock_path.read_text(encoding="utf-8"))
    package_digests = {path.name: digest_tree((path,)) for path in local_packages}
    if risk_lock != {"format": 1, "packages": package_digests}:
        raise SystemExit("risk-package-lock.json does not match reviewed Day 1 package sources")

    stamp = {
        "upstream_commit": head,
        "inputs_digest": digest_inputs(
            (manifest, risk_lock_path, host_patcher, client_patcher, requirement_lock)
        ),
        "local_packages_digest": digest_tree(local_packages),
        "local_packages": list(LOCAL_PACKAGE_NAMES),
    }
    stamp_path = venv_path / ".portfolio-risk-servicefabric-day1-runtime.json"
    installed_stamp = json.loads(stamp_path.read_text(encoding="utf-8")) if stamp_path.exists() else None

    if installed_stamp != stamp:
        run(pip + ["install", "--require-hashes", "-r", str(requirement_lock)], cwd=REPOSITORY)
        run(pip + ["install", "setuptools==80.9.0", "wheel==0.45.1"], cwd=REPOSITORY)
        projects = servicefabric_projects(upstream)
        selected = dependency_closure(projects, "servicefabric-client")
        with tempfile.TemporaryDirectory(prefix="portfolio-risk-day1-host-") as temporary:
            staged_host = Path(temporary) / "application_host"
            staged_client = Path(temporary) / "client"
            shutil.copytree(upstream / "services" / "application_host", staged_host)
            shutil.copytree(upstream / "clients" / "python", staged_client)
            run(
                [str(python), str(host_patcher), str(staged_host / "servicefabric_application_host" / "service.py"), str(manifest)],
                cwd=REPOSITORY,
            )
            run(
                [str(python), str(client_patcher), str(staged_client / "servicefabric_client" / "main.py")],
                cwd=REPOSITORY,
            )
            package_paths = [
                staged_host
                if name == "servicefabric-application-host"
                else staged_client
                if name == "servicefabric-client"
                else projects[name][0]
                for name in selected
            ]
            run(
                pip + ["install", "--no-deps", "--no-build-isolation", "--force-reinstall", *map(str, package_paths)],
                cwd=REPOSITORY,
            )

        # Ordinary wheels plus the digest stamp prevent a running host from
        # importing later working-tree changes. The pinned vendor tree is only
        # copied into the external runtime and is never edited.
        run(
            pip + ["install", "--no-deps", "--no-build-isolation", "--force-reinstall", *map(str, local_packages)],
            cwd=REPOSITORY,
        )
        stamp_path.write_text(json.dumps(stamp, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    run(pip + ["check"], cwd=REPOSITORY)
    print(f"Day 1 ServiceFabric runtime ready: {venv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
