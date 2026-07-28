#!/usr/bin/env python3
"""Run the bounded Day 1 replay and write only a compact external summary."""

from __future__ import annotations

import argparse
from pathlib import Path

from portfolio_risk_thesis.cli import main as cli_main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True, help="Explicit output root outside Git")
    args = parser.parse_args()
    return cli_main(["replay-day1", "--output-root", str(args.data_root.resolve())])


if __name__ == "__main__":
    raise SystemExit(main())
