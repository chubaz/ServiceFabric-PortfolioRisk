"""Reviewed Day 3 prompt registry with byte-for-byte digest verification."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from .contracts import PromptReference, bytes_digest

PROMPT_ROOT = Path(__file__).resolve().parents[3] / "prompts" / "day3"
MANIFEST_PATH = PROMPT_ROOT / "prompt-manifest.yaml"


@lru_cache(maxsize=1)
def registry() -> dict[str, dict[str, object]]:
    document = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("version") != "1":
        raise ValueError("invalid Day 3 prompt manifest")
    entries = document.get("prompts")
    if not isinstance(entries, list):
        raise ValueError("Day 3 prompt manifest requires a prompts list")
    result: dict[str, dict[str, object]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Day 3 prompt entry must be an object")
        prompt_id = str(entry["prompt_id"])
        path = PROMPT_ROOT / str(entry["file"])
        if path.parent != PROMPT_ROOT or not path.is_file():
            raise ValueError(f"prompt file is unavailable: {prompt_id}")
        actual = bytes_digest(path.read_bytes())
        if entry.get("sha256") != actual:
            raise ValueError(f"prompt digest mismatch: {prompt_id}")
        required = {
            "version",
            "role",
            "permitted_input_sections",
            "output_schema_version",
            "prohibitions",
            "abstention_rule",
        }
        if not required.issubset(entry):
            raise ValueError(f"prompt metadata is incomplete: {prompt_id}")
        if prompt_id in result:
            raise ValueError(f"duplicate prompt ID: {prompt_id}")
        result[prompt_id] = entry
    return result


def prompt_reference(prompt_id: str) -> PromptReference:
    entry = registry()[prompt_id]
    return PromptReference(
        prompt_id=prompt_id,
        version=str(entry["version"]),
        digest=str(entry["sha256"]),
        role=str(entry["role"]),
    )


def prompt_text(reference: PromptReference) -> str:
    entry = registry()[reference.prompt_id]
    if reference.digest != entry["sha256"]:
        raise ValueError("prompt reference differs from the reviewed registry")
    return (PROMPT_ROOT / str(entry["file"])).read_text(encoding="utf-8")


def prompt_manifest_digest() -> str:
    registry()
    return bytes_digest(MANIFEST_PATH.read_bytes())
