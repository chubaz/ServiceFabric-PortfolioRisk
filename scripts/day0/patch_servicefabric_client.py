#!/usr/bin/env python3
"""Make the pinned client's unrelated Wave-3 surface lazy in a copied install."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


UPSTREAM_SHA256 = "717bffa027cf3533832bae2e9ced37a387ef41cfcb939a1ba55e289f8ddc8138"


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise SystemExit(f"pinned client patch context count was {source.count(old)}, expected 1")
    return source.replace(old, new, 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    raw = args.source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != UPSTREAM_SHA256:
        raise SystemExit("refusing to patch an unknown ServiceFabric client revision")
    text = raw.decode("utf-8")
    text = replace_once(text, "from .wave3 import Wave3ApplicationService\n", "")
    text = replace_once(
        text,
        '''    if args.command == "apps":
        wave3 = Wave3ApplicationService(context)
        if args.action == "create" and args.template:
''',
        '''    if args.command == "apps":
        if args.action in {"create", "modules", "validate"}:
            from .wave3 import Wave3ApplicationService
            wave3 = Wave3ApplicationService(context)
        if args.action == "create" and args.template:
''',
    )
    text = replace_once(
        text,
        '''        if args.application_id != "text-utility" and not args.revision:
            require_development_workspace(context)
            return 0, "apps-build", {"build": wave3.build(args.application_id), "json_mode": json_mode}
        if args.application_id == "text-utility":
            return 0,"apps-build",{"build":runtime.host.build(args.application_id),"json_mode":json_mode}
''',
        '''        if args.application_id in runtime.host.list_applications():
            return 0, "apps-build", {"build": runtime.host.build(args.application_id), "json_mode": json_mode}
        if not args.revision:
            require_development_workspace(context)
            from .wave3 import Wave3ApplicationService
            return 0, "apps-build", {"build": Wave3ApplicationService(context).build(args.application_id), "json_mode": json_mode}
''',
    )
    invoke_start = text.index("    def invoke_application(self, tool_id: str, arguments: dict[str, object]):")
    invoke_end = text.index("    def invoke_math(self, arguments: dict[str, object]):", invoke_start)
    invoke = text[invoke_start:invoke_end]
    invoke = replace_once(
        invoke,
        "        capability = self.host.describe_capability(tool_id)\n",
        "        capability = self.host.describe_capability(tool_id)\n        canonical_tool_id = str(capability.get(\"canonical_tool_id\", tool_id))\n",
    )
    invoke = replace_once(invoke, '"tool_id":tool_id,', '"tool_id":canonical_tool_id,')
    invoke = replace_once(invoke, "profile = InvocationGovernanceProfile(tool_id,revision", "profile = InvocationGovernanceProfile(canonical_tool_id,revision")
    invoke = replace_once(invoke, "tool_id=tool_id,revision_ref=revision", "tool_id=canonical_tool_id,revision_ref=revision")
    text = text[:invoke_start] + invoke + text[invoke_end:]
    args.source.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
