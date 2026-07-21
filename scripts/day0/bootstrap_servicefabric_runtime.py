#!/usr/bin/env python3
"""Create or reuse the external, pinned ServiceFabric smoke-test runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import venv
from pathlib import Path


UPSTREAM_COMMIT = "7632b61d94a966346f95eb6c5bb2a5ea27f3bc14"


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def run(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def servicefabric_projects(upstream: Path) -> dict[str, tuple[Path, tuple[str, ...]]]:
    projects: dict[str, tuple[Path, tuple[str, ...]]] = {}
    for pyproject in upstream.rglob("pyproject.toml"):
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        project = data.get("project", {})
        if "name" in project:
            projects[normalized(project["name"])] = (pyproject.parent, tuple(project.get("dependencies", ())))
    return projects


def dependency_closure(projects: dict[str, tuple[Path, tuple[str, ...]]], root: str) -> tuple[str, ...]:
    pending = [normalized(root)]
    selected: set[str] = set()
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        if name not in projects:
            raise SystemExit(f"pinned upstream package is missing: {name}")
        selected.add(name)
        for requirement in projects[name][1]:
            match = re.match(r"[A-Za-z0-9_.-]+", requirement)
            if match and normalized(match.group()) in projects:
                pending.append(normalized(match.group()))
    return tuple(sorted(selected))


def digest_inputs(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def digest_tree(paths: tuple[Path, ...]) -> str:
    """Digest local package sources so a rebuilt runtime has reviewed inputs."""
    digest = hashlib.sha256()
    for path in paths:
        for file in sorted(path.rglob("*")):
            relative = file.relative_to(path)
            if (
                not file.is_file()
                or "__pycache__" in relative.parts
                or any(part.endswith(".egg-info") for part in relative.parts)
                or relative.parts[0] in {"build", "dist", ".pytest_cache"}
                or relative.suffix == ".pyc"
            ):
                continue
            digest.update(path.name.encode())
            digest.update(relative.as_posix().encode())
            digest.update(file.read_bytes())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venv", type=Path, required=True)
    args = parser.parse_args()

    repository = Path(__file__).resolve().parents[2]
    upstream = repository / "vendor" / "servicefabric"
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=upstream,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != UPSTREAM_COMMIT:
        raise SystemExit(f"unexpected ServiceFabric pin: {head}")
    if subprocess.run(["git", "status", "--porcelain"], cwd=upstream, check=True, capture_output=True, text=True).stdout:
        raise SystemExit("pinned ServiceFabric submodule must remain clean")
    if sys.version_info[:2] != (3, 11):
        raise SystemExit("the ServiceFabric runtime requires Python 3.11")

    venv_path = args.venv.resolve()
    if not (venv_path / "bin" / "python").exists():
        venv_path.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True).create(venv_path)
    python = venv_path / "bin" / "python"
    pip = [str(python), "-m", "pip"]

    manifest = repository / "apps" / "portfolio-risk-workbench" / "servicefabric-package.json"
    host_patcher = repository / "scripts" / "day0" / "patch_servicefabric_application_host.py"
    client_patcher = repository / "scripts" / "day0" / "patch_servicefabric_client.py"
    local_packages = tuple(
        repository / "packages" / name
        for name in ("risk_domain", "risk_planning", "risk_data", "risk_capabilities", "risk_agents")
    )
    risk_lock_path = repository / "apps" / "portfolio-risk-workbench" / "risk-package-lock.json"
    risk_lock = json.loads(risk_lock_path.read_text(encoding="utf-8"))
    package_digests = {path.name: digest_tree((path,)) for path in local_packages}
    if risk_lock != {"format": 1, "packages": package_digests}:
        raise SystemExit("risk-package-lock.json does not match reviewed local package sources")
    stamp_inputs = (manifest, risk_lock_path, host_patcher, client_patcher, repository / "requirements" / "day0.lock")
    stamp = {
        "upstream_commit": head,
        "inputs_digest": digest_inputs(stamp_inputs),
        "local_packages_digest": digest_tree(local_packages),
    }
    stamp_path = venv_path / ".portfolio-risk-servicefabric-runtime.json"
    installed_stamp = json.loads(stamp_path.read_text(encoding="utf-8")) if stamp_path.exists() else None

    if installed_stamp != stamp:
        run(pip + ["install", "--require-hashes", "-r", str(repository / "requirements" / "day0.lock")], cwd=repository)
        run(pip + ["install", "setuptools==80.9.0", "wheel==0.45.1"], cwd=repository)
        projects = servicefabric_projects(upstream)
        selected = dependency_closure(projects, "servicefabric-client")
        with tempfile.TemporaryDirectory(prefix="portfolio-risk-host-") as temporary:
            staged_host = Path(temporary) / "application_host"
            staged_client = Path(temporary) / "client"
            shutil.copytree(upstream / "services" / "application_host", staged_host)
            shutil.copytree(upstream / "clients" / "python", staged_client)
            run(
                [str(python), str(host_patcher), str(staged_host / "servicefabric_application_host" / "service.py"), str(manifest)],
                cwd=repository,
            )
            run(
                [str(python), str(client_patcher), str(staged_client / "servicefabric_client" / "main.py")],
                cwd=repository,
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
                cwd=repository,
            )
        stamp_path.write_text(json.dumps(stamp, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        # Do not use editable installs here: the hosted application must not
        # import later, unreviewed working-tree edits after it has been built.
        # The source digest above makes a deliberate bootstrap rebuild
        # deterministic and records the reviewed package input set.
        run(
            pip
            + [
                "install",
                "--no-deps",
                "--no-build-isolation",
                "--force-reinstall",
                *map(str, local_packages),
            ],
            cwd=repository,
        )
    run(pip + ["check"], cwd=repository)
    print(f"ServiceFabric runtime ready: {venv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
