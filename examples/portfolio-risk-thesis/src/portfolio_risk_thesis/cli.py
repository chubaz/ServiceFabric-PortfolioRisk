"""Local commands for validating and replaying the synthetic Day 1 experiment."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import yaml

from .adapters import HistoricalEventDataAdapter, HistoricalMarketDataAdapter
from .day2 import (
    prepare_day2_experiment,
    run_day2_experiment,
    validate_day2_experiment,
)
from .manifests import load_dataset_manifest, load_experiment
from .portfolio import (
    SnapshotBuilder,
    load_portfolios,
    materialize_real_portfolios,
    prepare_real_selection_interactive,
    validate_materialized_real_portfolios,
)
from .replay import ReplayChannel, ReplayClock, ReplayStepResult
from .day3.events import initialize_event_template, materialize_events, read_events, validate_event_manifest
from .day3.contracts import PositionExposure
from .day3.experiment import (
    load_bundle,
    prepare_experiment,
    run_fixture_experiment,
    run_openai_experiment,
)
from .day3.runner import validate_run


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


def _utc_argument(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "timestamp must be an explicit UTC ISO timestamp"
        ) from error
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
        or parsed.utcoffset().total_seconds() != 0
    ):
        raise argparse.ArgumentTypeError(
            "timestamp must be an explicit UTC ISO timestamp"
        )
    return parsed.astimezone(UTC)


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
    prepare_real.add_argument(
        "--show-all-candidates",
        action="store_true",
        help="Show historical candidates outside the Day 2 latest-data cohort",
    )
    prepare_real.add_argument(
        "--uniform-quantity",
        help="Explicit positive integer quantity to apply to every reviewed position",
    )
    prepare_real.add_argument(
        "--uniform-cash-amount",
        help="Explicit USD cash amount to apply to every reviewed portfolio",
    )

    prepare_day2 = commands.add_parser(
        "prepare-day2-experiment",
        help="bind reviewed private sources and portfolios to a Day 2 experiment",
    )
    prepare_day2.add_argument("--source-manifest", type=Path, required=True)
    prepare_day2.add_argument("--data-root", type=Path, required=True)
    prepare_day2.add_argument("--portfolios-directory", type=Path, required=True)
    prepare_day2.add_argument("--experiment-manifest", type=Path, required=True)
    prepare_day2.add_argument(
        "--reviewer-id",
        help="Optional override; defaults to the validated portfolio receipt reviewer",
    )
    prepare_day2.add_argument(
        "--reviewed-at",
        type=_utc_argument,
        help="Optional override; defaults to the validated portfolio receipt review time",
    )
    prepare_day2.add_argument(
        "--as-of",
        type=_utc_argument,
        help="Optional override; defaults to the validated portfolio receipt as_of",
    )

    validate_day2 = commands.add_parser(
        "validate-day2",
        help="validate the reviewed private Day 2 experiment and immutable inputs",
    )
    validate_day2.add_argument("--experiment-manifest", type=Path, required=True)

    run_day2 = commands.add_parser(
        "run-day2",
        help="run the deterministic Morning MetricPack and decision kernel",
    )
    run_day2.add_argument("--experiment-manifest", type=Path, required=True)
    run_day2.add_argument("--output-root", type=_external_output_root, required=True)

    init_events = commands.add_parser("init-day3-events", help="write an external reviewed curated-event template")
    init_events.add_argument("--output", type=Path, required=True)
    materialize_events_command = commands.add_parser("materialize-day3-events", help="materialize reviewed events to immutable Parquet")
    materialize_events_command.add_argument("--manifest", type=Path, required=True)
    materialize_events_command.add_argument("--output", type=Path, required=True)
    validate_events = commands.add_parser("validate-day3-events", help="validate curated event manifest and Parquet")
    validate_events.add_argument("--manifest", type=Path, required=True)
    validate_events.add_argument("--dataset", type=Path, required=True)
    prepare_day3 = commands.add_parser("prepare-day3-experiment", help="bind immutable Day 2 evidence, reviewed events and model configuration")
    prepare_day3.add_argument("--day2-run-directory", type=Path, required=True)
    prepare_day3.add_argument("--event-manifest", type=Path, required=True)
    prepare_day3.add_argument("--event-dataset", type=Path, required=True)
    prepare_day3.add_argument("--model-config", type=Path, required=True)
    prepare_day3.add_argument("--portfolio-id", required=True)
    prepare_day3.add_argument("--exposures", type=Path, required=True, help="External YAML list of private-neutral exposure aliases")
    prepare_day3.add_argument("--output", type=Path, required=True)
    validate_day3 = commands.add_parser("validate-day3", help="validate a Day 3 experiment without calling a model")
    validate_day3.add_argument("--experiment-manifest", type=Path, required=True)
    run_day3 = commands.add_parser("run-day3", help="run the explicitly selected Day 3 provider")
    run_day3.add_argument("--experiment-manifest", type=Path, required=True)
    run_day3.add_argument("--provider", choices=("fixture", "openai_responses"), required=True)
    run_day3.add_argument("--allow-fixture-provider", action="store_true")
    run_day3.add_argument("--fixture-responses", type=Path)
    run_day3.add_argument("--output-root", type=Path, required=True)
    inspect_day3 = commands.add_parser("inspect-day3-comparison", help="print a compact Day 3 comparison")
    inspect_day3.add_argument("--run-directory", type=Path, required=True)
    verify_day3_run = commands.add_parser("validate-day3-run", help="validate immutable Day 3 evidence and frozen treatment controls")
    verify_day3_run.add_argument("--run-directory", type=Path, required=True)
    verify_day3_run.add_argument("--require-successful-provider", action="store_true")
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
                show_all_candidates=args.show_all_candidates,
                uniform_quantity=args.uniform_quantity,
                uniform_cash_amount=args.uniform_cash_amount,
            )
        elif args.command == "prepare-day2-experiment":
            prepare_day2_experiment(
                source_manifest_path=args.source_manifest,
                data_root=args.data_root,
                portfolios_directory=args.portfolios_directory,
                experiment_manifest_path=args.experiment_manifest,
                reviewer_id=args.reviewer_id,
                reviewed_at=args.reviewed_at,
                as_of=args.as_of,
            )
            print(
                json.dumps(
                    {
                        "experiment_id": (
                            "portfolio-risk-architecture-comparison-v1-day2"
                        ),
                        "reviewed": True,
                        "effects": 0,
                    },
                    sort_keys=True,
                )
            )
        elif args.command == "validate-day2":
            manifest, receipt, _ = validate_day2_experiment(
                args.experiment_manifest
            )
            print(
                json.dumps(
                    {
                        "experiment_id": manifest.experiment_id,
                        "portfolio_count": receipt.portfolio_count,
                        "dataset_mode": manifest.dataset_mode,
                        "validated": True,
                        "effects": 0,
                    },
                    sort_keys=True,
                )
            )
        elif args.command == "run-day2":
            output = run_day2_experiment(
                experiment_manifest_path=args.experiment_manifest,
                output_root=args.output_root,
            )
        elif args.command == "init-day3-events":
            output = initialize_event_template(args.output)
            print(json.dumps({"initialized": True, "filename": output.name, "effects": 0}, sort_keys=True))
        elif args.command == "materialize-day3-events":
            output = materialize_events(args.manifest, args.output)
            print(json.dumps({"materialized": True, "filename": output.name, "effects": 0}, sort_keys=True))
        elif args.command == "validate-day3-events":
            manifest = validate_event_manifest(args.manifest)
            dataset = read_events(args.dataset)
            if manifest != dataset:
                raise ValueError("event dataset does not exactly match reviewed manifest")
            print(json.dumps({"validated": True, "event_count": len(manifest), "effects": 0}, sort_keys=True))
        elif args.command == "prepare-day3-experiment":
            raw_exposures = yaml.safe_load(args.exposures.read_text(encoding="utf-8"))
            if not isinstance(raw_exposures, list):
                raise ValueError("exposures file must be a YAML list")
            output = prepare_experiment(day2_run_directory=args.day2_run_directory, event_manifest=args.event_manifest, event_dataset=args.event_dataset, model_config=args.model_config, portfolio_id=args.portfolio_id, exposures=tuple(PositionExposure.model_validate(value) for value in raw_exposures), output=args.output)
            print(json.dumps({"prepared": True, "filename": output.name, "effects": 0}, sort_keys=True))
        elif args.command == "validate-day3":
            bundle, configuration = load_bundle(args.experiment_manifest)
            print(json.dumps({"validated": True, "context_digest": bundle.context_digest, "provider": configuration.provider_id, "effects": 0}, sort_keys=True))
        elif args.command == "run-day3":
            if args.provider == "fixture":
                if not args.allow_fixture_provider:
                    raise ValueError("fixture provider requires --allow-fixture-provider")
                if args.fixture_responses is None:
                    raise ValueError("fixture provider requires --fixture-responses")
                response_document = json.loads(
                    args.fixture_responses.read_text(encoding="utf-8")
                )
                responses = {
                    (
                        str(item["architecture_id"]),
                        str(item["role_id"]),
                        str(item["prompt_digest"]),
                        str(item["context_digest"]),
                    ): item["output"]
                    for item in response_document["responses"]
                }
                output = run_fixture_experiment(
                    args.experiment_manifest,
                    args.output_root,
                    responses,
                )
            else:
                output = run_openai_experiment(args.experiment_manifest, args.output_root)
            print(json.dumps({"completed": True, "run_id": output.name, "effects": 0}, sort_keys=True))
        elif args.command == "inspect-day3-comparison":
            comparison = json.loads((args.run_directory / "architecture-comparison.json").read_text(encoding="utf-8"))
            for item in comparison["architectures"]:
                print(
                    f"{item['architecture_id']} status={item['status']} "
                    f"critic_passed={item['critic_passed']} "
                    f"unsupported_claims={item['unsupported_claim_count']} "
                    f"evidence_coverage={item['evidence_reference_coverage']} "
                    f"model_calls={item['model_calls']} "
                    f"input_tokens={item['input_tokens']} "
                    f"output_tokens={item['output_tokens']} "
                    f"latency_ms={item['latency_ms']} effects={item['effects']}"
                )
            print(f"context_digest={comparison['context_digest']}")
            print(
                json.dumps(
                    {
                        "run_id": args.run_directory.name,
                        "completed": True,
                        "effects": 0,
                    },
                    sort_keys=True,
                )
            )
        elif args.command == "validate-day3-run":
            comparison = validate_run(
                args.run_directory,
                require_successful_provider=args.require_successful_provider,
            )
            print(
                json.dumps(
                    {
                        "validated": True,
                        "context_digest": comparison.context_digest,
                        "model_calls": {
                            run.architecture_id: len(run.receipts)
                            for run in comparison.runs
                        },
                        "effects": 0,
                    },
                    sort_keys=True,
                )
            )
        return 0
    except Exception as error:  # command boundary: concise error and non-zero status
        parser.exit(1, f"{args.command} failed: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
