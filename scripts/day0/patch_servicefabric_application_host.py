#!/usr/bin/env python3
"""Apply the reviewed Portfolio Risk overlay to a copied pinned AP-01A host."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from pprint import pformat


UPSTREAM_SHA256 = "1cf5c44bc82242ac4a0eab9c11fc017603ea26c73c93536326570cff9bb03780"


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise SystemExit(f"pinned host patch context count was {source.count(old)}, expected 1")
    return source.replace(old, new, 1)


def patch_host(source_path: Path, manifest_path: Path) -> None:
    raw = source_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != UPSTREAM_SHA256:
        raise SystemExit("refusing to patch an unknown ServiceFabric application host revision")
    text = raw.decode("utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    application_id = manifest["application_id"]
    if application_id != "portfolio-risk-workbench":
        raise SystemExit("the runtime overlay only reviews portfolio-risk-workbench")

    package_start = text.index("_REVIEWED_PACKAGE = {")
    capability_start = text.index("\n\n_CAPABILITIES = {", package_start)
    text_utility_literal = text[package_start + len("_REVIEWED_PACKAGE = ") : capability_start]
    reviewed = (
        "_REVIEWED_PACKAGES = {\n"
        f"    \"text-utility\": {text_utility_literal},\n"
        f"    {application_id!r}: {pformat(manifest, sort_dicts=False, width=100)},\n"
        "}"
    )
    text = text[:package_start] + reviewed + text[capability_start:]

    descriptors = []
    for item in manifest["capabilities"]:
        namespace, remainder = item["tool_id"].split(".", 1)
        canonical_tool_id = namespace + "." + remainder.replace(".", "_")
        descriptors.append(
            f'''    {item["tool_id"]!r}: {{
        "tool_id": {item["tool_id"]!r},
        "canonical_tool_id": {canonical_tool_id!r},
        "revision": {manifest["version"]!r},
        "application_id": {application_id!r},
        "description": "Reviewed synthetic Portfolio Risk Workbench capability.",
        "permission_id": "text-inspect",
        "path": {item["path"]!r},
        "effects": ("none",),
    }},'''
        )
    text = replace_once(
        text,
        "\n}\n\n\nclass ApplicationHostError",
        "\n" + "\n".join(descriptors) + "\n}\n\n\nclass ApplicationHostError",
    )
    text = replace_once(
        text,
        '''    def _directory(self, application_id: str) -> Path:
        if application_id != "text-utility":
            raise ApplicationHostError(f"application '{application_id}' is not installed")
        return self.root / application_id
''',
        '''    def _directory(self, application_id: str) -> Path:
        if application_id not in _REVIEWED_PACKAGES:
            raise ApplicationHostError(f"application '{application_id}' is not installed")
        return self.root / application_id
''',
    )
    text = replace_once(
        text,
        '''    @staticmethod
    def _validate_package(package: object) -> dict[str, object]:
        if package != _REVIEWED_PACKAGE:
            raise ApplicationHostError("package is not an approved AP-01A FastAPI package")
        return dict(package)
''',
        '''    @staticmethod
    def _validate_package(package: object) -> dict[str, object]:
        if not isinstance(package, dict):
            raise ApplicationHostError("package is not an approved FastAPI package")
        reviewed = _REVIEWED_PACKAGES.get(str(package.get("application_id")))
        if package != reviewed:
            raise ApplicationHostError("package is not an approved FastAPI package")
        return dict(package)
''',
    )
    install_start = text.index("    def install(self, source: Path) -> dict[str, object]:")
    build_start = text.index("    def build(self, application_id: str) -> dict[str, object]:", install_start)
    generic_install = '''    def install(self, source: Path) -> dict[str, object]:
        try:
            source = source.resolve(strict=True)
        except OSError as error:
            raise ApplicationHostError("package source is unavailable") from error
        if not source.is_dir():
            raise ApplicationHostError("package source must be a directory")
        try:
            package = self._validate_package(
                json.loads((source / "servicefabric-package.json").read_text(encoding="utf-8"))
            )
            self._validate_source(source, package)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ApplicationHostError("package manifest is unreadable") from error
        application_id = str(package["application_id"])
        with self._lock(application_id):
            directory = self.root / application_id
            installed = not directory.exists()
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / "source"
            if installed:
                shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                record: dict[str, object] = {
                    "application_id": application_id,
                    "package": package,
                    "state": "installed",
                    "restart_count": 0,
                    "request_count": 0,
                }
            else:
                record = self._record(application_id)
                if package != record.get("package"):
                    raise ApplicationHostError("installed package differs from the reviewed package")
            _atomic(directory / "application.json", record)
        return {"application_id": application_id, "installed": installed, "state": record["state"]}

'''
    text = text[:install_start] + generic_install + text[build_start:]
    text = text.replace('"name": "Text Utility 1.0.0",', '"name": f"{application_id} {record[\'package\'][\'version\']}",', 1)
    text = text.replace('"source_manifest_ref": "text-utility-source",', '"source_manifest_ref": f"{application_id}-source",', 1)

    capabilities_start = text.index("    def capabilities(self) -> tuple[dict[str, object], ...]:")
    describe_start = text.index("    def describe_capability(self, tool_id: str)", capabilities_start)
    generic_capabilities = '''    def capabilities(self) -> tuple[dict[str, object], ...]:
        available: list[dict[str, object]] = []
        for application_id in self.list_applications():
            record = self._record(application_id)
            self._validate_package(record.get("package"))
            available.extend(
                dict(item)
                for item in _CAPABILITIES.values()
                if item["application_id"] == application_id
            )
        return tuple(sorted(available, key=lambda item: str(item["tool_id"])))

'''
    text = text[:capabilities_start] + generic_capabilities + text[describe_start:]
    text = replace_once(
        text,
        '''    @staticmethod
    def _validate_arguments(arguments: object) -> dict[str, object]:
        if not isinstance(arguments, dict) or set(arguments) != {"text"}:
            raise ApplicationHostError("application capability input is invalid")
        text = arguments.get("text")
        if not isinstance(text, str) or not text or len(text) > MAX_ARGUMENT_TEXT:
            raise ApplicationHostError("application capability input is invalid")
        return arguments
''',
        '''    @staticmethod
    def _validate_arguments(arguments: object) -> dict[str, object]:
        if not isinstance(arguments, dict):
            raise ApplicationHostError("application capability input is invalid")
        if len(json.dumps(arguments, sort_keys=True)) > MAX_ARGUMENT_TEXT:
            raise ApplicationHostError("application capability input is invalid")
        return arguments
''',
    )
    invoke_start = text.index("    def invoke(self, tool_id: str, arguments: dict[str, object])")
    logs_start = text.index("    def logs(self, application_id: str", invoke_start)
    invoke = text[invoke_start:logs_start]
    invoke = invoke.replace("        arguments = self._validate_arguments(arguments)\n", "        arguments = self._validate_arguments(arguments)\n        application_id = str(descriptor[\"application_id\"])\n", 1)
    invoke = invoke.replace('self._directory("text-utility")', "self._directory(application_id)")
    invoke = invoke.replace('self._lock("text-utility")', "self._lock(application_id)")
    invoke = invoke.replace('self._record("text-utility")', "self._record(application_id)")
    invoke = invoke.replace('self.controller.store.load("text-utility", "text-utility")', "self.controller.store.load(application_id, application_id)")
    invoke = invoke.replace("application 'text-utility' is unavailable", "application '{application_id}' is unavailable")
    invoke = invoke.replace('ApplicationHostError("application \'{application_id}\' is unavailable")', 'ApplicationHostError(f"application \'{application_id}\' is unavailable")')
    text = text[:invoke_start] + invoke + text[logs_start:]

    source_path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    patch_host(args.source, args.manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
