"""Command-line entry points for bounded local data workflows."""

from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import ingest_synthetic


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m risk_data.cli")
    subcommands = parser.add_subparsers(dest="command", required=True)
    ingest = subcommands.add_parser("ingest-synthetic", help="write deterministic synthetic artifacts")
    ingest.add_argument("--output", type=Path, required=True, metavar="ROOT")
    args = parser.parse_args()
    if args.command == "ingest-synthetic":
        result = ingest_synthetic(args.output)
        print(result.snapshot_manifest)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
