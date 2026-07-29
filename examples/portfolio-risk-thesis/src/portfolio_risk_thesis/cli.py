"""Local commands for validating and replaying the synthetic Day 1 experiment."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .adapters import HistoricalEventDataAdapter, HistoricalMarketDataAdapter
from .manifests import load_dataset_manifest, load_experiment
from .portfolio import (
    SnapshotBuilder,
    load_portfolios,
    materialize_real_portfolios,
    prepare_real_selection_interactive,
    validate_materialized_real_portfolios,
)
from .replay import ReplayChannel, ReplayClock, ReplayStepResult


EXAMPLE_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = EXAMPLE_ROOT.parents[1]
DEFAULT_DATASET_MANIFEST = EXAMPLE_ROOT / "data" / "dataset_manifest.yaml"
DEFAULT_PORTFOLIOS = EXAMPLE_ROOT / "portfolios"
DEFAULT_EXPERIMENT = EXAMPLE_ROOT / "experiments" / "day1_smoke.yaml"


def replay_results(
    dataset_manifest: Path = DEFAULT_DATASET_MANIFEST,
    portfolios_directory: Path = DEFAULT_PORTFOLIOS,
    experiment_manifest: Path = DEFAULT_EXPERIMENT,
) -> dict[str, tuple[ReplayStepResult, ...]]:
    market_metadata, event_metadata = load_dataset_manifest(dataset_manifest)
    market = HistoricalMarketDataAdapter(market_metadata)
    events = HistoricalEventDataAdapter(event_metadata)
    results: dict[str, tuple[ReplayStepResult, ...]] = {}
    for portfolio in load_portfolios(portfolios_directory):
        specification = load_experiment(experiment_manifest, portfolio.portfolio_id)
        if specification.dataset_revision != market_metadata.revision:
            raise ValueError("experiment and dataset revisions do not match")
        clock = ReplayClock(specification, specification.review_time)
        results[portfolio.portfolio_id] = ReplayChannel(market, events, SnapshotBuilder()).replay(
            clock, specification, portfolio
        )
    return results


def _external_output_root(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("output root must be an explicit absolute path")
    resolved = path.resolve(strict=False)
    configured_value = os.environ.get("THESIS_DATA_ROOT")
    if not configured_value:
        raise argparse.ArgumentTypeError("THESIS_DATA_ROOT must be configured before writing output")
    configured = Path(configured_value)
    if not configured.is_absolute():
        raise argparse.ArgumentTypeError("THESIS_DATA_ROOT must be an absolute path")
    configured = configured.resolve(strict=False)
    if configured == REPOSITORY_ROOT or REPOSITORY_ROOT in configured.parents:
        raise argparse.ArgumentTypeError("THESIS_DATA_ROOT must remain outside Git")
    if resolved != configured and configured not in resolved.parents:
        raise argparse.ArgumentTypeError("output root must be beneath THESIS_DATA_ROOT")
    return resolved


def _shared_paths(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dataset-manifest", type=Path, default=DEFAULT_DATASET_MANIFEST, help="Dataset manifest to validate and use")
    parser.add_argument("--portfolios-directory", type=Path, default=DEFAULT_PORTFOLIOS, help="Directory containing reviewed portfolio YAML")
    parser.add_argument("--experiment-manifest", type=Path, default=DEFAULT_EXPERIMENT, help="Reviewed Day 1 experiment manifest")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate-data", help="Validate source schemas, digests, metadata and synthetic disclosure")
    validate.add_argument("--dataset-manifest", type=Path, default=DEFAULT_DATASET_MANIFEST)

    portfolios = commands.add_parser("list-portfolios", help="List the three reviewed fixed-quantity portfolios")
    portfolios.add_argument("--portfolios-directory", type=Path, default=DEFAULT_PORTFOLIOS)

    replay = commands.add_parser("replay-day1", help="Run the five-day deterministic replay for all portfolios")
    _shared_paths(replay)
    replay.add_argument("--output-root", type=_external_output_root, help="Optional explicit external root for a compact summary")

    inspect = commands.add_parser("inspect-step", help="Inspect one compact replay-step summary")
    _shared_paths(inspect)
    inspect.add_argument("--portfolio-id", default="diversified", help="Reviewed portfolio ID")
    inspect.add_argument("--ordinal", type=int, default=0, help="Zero-based replay-step ordinal")

    initialize_real = commands.add_parser(
        "init-real-portfolios",
        help="validate and materialize an already reviewed real-portfolio selection",
    )
    initialize_real.add_argument(
        "--candidate-artifact", type=Path, required=True
    )
    initialize_real.add_argument("--selection", type=Path, required=True)
    initialize_real.add_argument(
        "--output-directory", type=Path, required=True
    )

    validate_real = commands.add_parser(
        "validate-real-portfolios",
        help="verify immutable materialized real-portfolio definitions and receipt",
    )
    validate_real.add_argument(
        "--portfolios-directory", type=Path, required=True
    )
    validate_real.add_argument("--receipt", type=Path, required=True)
    prepare_real = commands.add_parser(
        "prepare-real-selection",
        help="interactively author and validate a human-reviewed private selection",
    )
    prepare_real.add_argument("--candidate-artifact", type=Path, required=True)
    prepare_real.add_argument("--selection", type=Path, required=True)
    return parser


def _summary(results: dict[str, tuple[ReplayStepResult, ...]]) -> dict[str, object]:
    return {
        "synthetic": True,
        "human_review_required": True,
        "portfolios": {
            portfolio_id: {
                "run_id": steps[0].step.run_id,
                "steps": len(steps),
                "final_nav": str(steps[-1].snapshot.exposure_snapshot.nav),
                "effects": [],
            }
            for portfolio_id, steps in sorted(results.items())
        },
        "limitations": [
            "Synthetic research evidence only; not investment advice.",
            "No network, provider, broker, order, trade, rebalance or portfolio mutation effect.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-data":
            market, events = load_dataset_manifest(args.dataset_manifest)
            HistoricalMarketDataAdapter(market)
            HistoricalEventDataAdapter(events)
            print(f"validated synthetic revision {market.revision}: {market.row_counts[0]} market rows, {events.row_counts[0]} events")
        elif args.command == "list-portfolios":
            for portfolio in load_portfolios(args.portfolios_directory):
                print(f"{portfolio.portfolio_id}: {len(portfolio.positions)} fixed positions, {len(portfolio.cash)} cash balance")
        elif args.command == "replay-day1":
            results = replay_results(args.dataset_manifest, args.portfolios_directory, args.experiment_manifest)
            summary = _summary(results)
            if args.output_root is not None:
                args.output_root.mkdir(parents=True, exist_ok=True)
                output = args.output_root / "day1-replay-summary.json"
                output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                print(f"wrote compact synthetic replay summary to {output}")
            for portfolio_id, item in summary["portfolios"].items():
                print(f"{portfolio_id}: {item['steps']} steps; final NAV {item['final_nav']}; run {item['run_id'][:23]}...")
        elif args.command == "inspect-step":
            results = replay_results(args.dataset_manifest, args.portfolios_directory, args.experiment_manifest)
            if args.portfolio_id not in results:
                raise ValueError(f"unknown portfolio: {args.portfolio_id}")
            steps = results[args.portfolio_id]
            if args.ordinal < 0 or args.ordinal >= len(steps):
                raise ValueError(f"ordinal must be between 0 and {len(steps) - 1}")
            item = steps[args.ordinal]
            print(
                f"{args.portfolio_id} step {item.step.ordinal} as_of={item.step.as_of.isoformat()} "
                f"new_market={len(item.step.newly_eligible_market_records)} "
                f"new_events={len(item.step.newly_eligible_event_records)} "
                f"latest_prices={len(item.step.latest_eligible_market_records)} "
                f"NAV={item.snapshot.exposure_snapshot.nav}"
            )
        elif args.command == "init-real-portfolios":
            receipt = materialize_real_portfolios(
                candidate_artifact_path=args.candidate_artifact,
                selection_path=args.selection,
                output_directory=args.output_directory,
            )
            print(
                json.dumps(
                    {
                        "receipt_id": receipt.receipt_id,
                        "selection_id": receipt.selection_id,
                        "portfolio_count": receipt.portfolio_count,
                        "effects": 0,
                    },
                    sort_keys=True,
                )
            )
        elif args.command == "validate-real-portfolios":
            receipt = validate_materialized_real_portfolios(
                portfolios_directory=args.portfolios_directory,
                receipt_path=args.receipt,
            )
            print(
                json.dumps(
                    {
                        "receipt_id": receipt.receipt_id,
                        "selection_id": receipt.selection_id,
                        "portfolio_count": receipt.portfolio_count,
                        "validated": True,
                        "effects": 0,
                    },
                    sort_keys=True,
                )
            )
        elif args.command == "prepare-real-selection":
            prepare_real_selection_interactive(
                candidate_artifact_path=args.candidate_artifact,
                selection_path=args.selection,
            )
        return 0
    except Exception as error:  # command boundary: concise error and non-zero status
        parser.exit(1, f"{args.command} failed: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
