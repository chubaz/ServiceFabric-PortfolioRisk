"""Day 4 experiment initialization, validation, and immutable plan construction."""
from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from .contracts import (
    ARCHITECTURES,
    AUTHORIZED_MODEL_CALLS,
    PRIMARY_CONTEXTS,
    PRIMARY_MODEL_CALLS,
    PRIMARY_OBSERVATIONS,
    REPEATABILITY_ANCHORS,
    REPEAT_MODEL_CALLS,
    REPEAT_OBSERVATIONS,
    WORKED_EXAMPLE_RULES,
    Day4ExecutionPlan,
    Day4ExperimentManifest,
    Day4Task,
    ExternalArtifactBinding,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]


class Day4ManifestError(ValueError):
    """A Day 4 template, reviewed manifest, or immutable binding is invalid."""


def sha256_file(path: Path | str) -> str:
    source = Path(path)
    hasher = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return f"sha256:{hasher.hexdigest()}"


def sha256_tree(path: Path | str) -> str:
    """Digest a tree from portable relative names and file bytes."""

    root = Path(path)
    hasher = hashlib.sha256()
    files = sorted(item for item in root.rglob("*") if item.is_file())
    for item in files:
        relative = item.relative_to(root).as_posix().encode("utf-8")
        hasher.update(len(relative).to_bytes(8, "big"))
        hasher.update(relative)
        with item.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
    return f"sha256:{hasher.hexdigest()}"


def _load_mapping(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise Day4ManifestError(f"unable to load Day 4 manifest {path}: {error}") from error
    if not isinstance(value, dict):
        raise Day4ManifestError("Day 4 experiment manifest must contain a mapping")
    return value


def _binding_path(binding: ExternalArtifactBinding, manifest_path: Path) -> Path:
    path = Path(binding.path)
    if binding.scope == "repository_fixture":
        path = REPOSITORY_ROOT / path
    try:
        return path.resolve(strict=True)
    except OSError as error:
        raise Day4ManifestError(f"bound Day 4 input is missing: {path}") from error


def validate_input_bindings(
    manifest: Day4ExperimentManifest,
    manifest_path: Path | str,
) -> dict[str, Path]:
    source = Path(manifest_path).resolve()
    resolved: dict[str, Path] = {}
    for name, binding in manifest.inputs:
        path = _binding_path(binding, source)
        if binding.kind == "file" and not path.is_file():
            raise Day4ManifestError(f"bound input must be a file: {name}")
        if binding.kind == "tree" and not path.is_dir():
            raise Day4ManifestError(f"bound input must be a directory: {name}")
        actual = sha256_tree(path) if binding.kind == "tree" else sha256_file(path)
        if actual != binding.digest:
            raise Day4ManifestError(
                f"bound input digest mismatch for {name}: "
                f"expected {binding.digest}, got {actual}"
            )
        resolved[name] = path
    return resolved


def _date_strings(values: object) -> set[str]:
    if not isinstance(values, (tuple, list, set)):
        return set()
    return {str(value) for value in values}


def _candidate_dates(values: object) -> set[str]:
    if isinstance(values, Mapping):
        dates: set[str] = set()
        for key, value in values.items():
            if isinstance(value, bool):
                if value:
                    dates.add(str(key))
            elif isinstance(value, Mapping):
                eligible = all(
                    bool(value.get(flag, True))
                    for flag in (
                        "has_required_lookback",
                        "has_five_future_business_sessions",
                        "eligible",
                    )
                )
                candidate = value.get(
                    "as_of",
                    value.get(
                        "review_timestamp",
                        value.get("review_date", value.get("date", key)),
                    ),
                )
                if eligible:
                    dates.add(str(candidate))
            elif isinstance(value, (str, int)):
                dates.add(str(value))
        return dates
    if isinstance(values, (tuple, list, set)):
        dates = set()
        for value in values:
            if isinstance(value, Mapping):
                eligible = all(
                    bool(value.get(flag, True))
                    for flag in (
                        "has_required_lookback",
                        "has_five_future_business_sessions",
                        "eligible",
                    )
                )
                candidate = value.get(
                    "as_of",
                    value.get(
                        "review_timestamp",
                        value.get("review_date", value.get("date")),
                    ),
                )
                if candidate is not None and eligible:
                    dates.add(str(candidate))
            else:
                dates.add(str(value))
        return dates
    return set()


def _coverage_by_portfolio(coverage: Mapping[str, object]) -> dict[str, set[str]]:
    """Accept the strict profiler shape and small compatible test projections."""

    raw = coverage.get("portfolios", coverage.get("coverage", coverage))
    rows: list[tuple[str, Mapping[str, object]]] = []
    if isinstance(raw, Mapping):
        rows = [
            (str(alias), value)
            for alias, value in raw.items()
            if isinstance(value, Mapping)
        ]
    elif isinstance(raw, list):
        for value in raw:
            if not isinstance(value, Mapping):
                continue
            alias = value.get("portfolio_id", value.get("portfolio_alias"))
            if alias is not None:
                rows.append((str(alias), value))

    result: dict[str, set[str]] = {}
    for alias, row in rows:
        explicit = _date_strings(
            row.get("eligible_review_dates", row.get("eligible_dates", ()))
        )
        candidates = _candidate_dates(row.get("eligible_window_candidates", ()))
        prior = _date_strings(
            row.get("dates_with_required_lookback", row.get("lookback_dates", ()))
        )
        future = _date_strings(
            row.get(
                "dates_with_five_future_business_sessions",
                row.get("future_session_dates", ()),
            )
        )
        candidates = explicit or candidates or prior
        if future:
            candidates = candidates.intersection(future)
        result[alias] = candidates
    return result


def validate_day4_manifest(
    manifest: Day4ExperimentManifest,
    *,
    coverage: Mapping[str, object] | Path | str | None = None,
    require_reviewed: bool = True,
) -> Day4ExperimentManifest:
    if require_reviewed and not manifest.reviewed:
        raise Day4ManifestError("Day 4 experiment manifest has not been reviewed")
    if len(manifest.portfolio_day_keys()) != PRIMARY_CONTEXTS:
        raise Day4ManifestError("reviewed manifest must define exactly 45 contexts")
    if len(manifest.portfolio_day_keys()) * len(ARCHITECTURES) != PRIMARY_OBSERVATIONS:
        raise Day4ManifestError("reviewed manifest must define exactly 135 primary results")
    if len(manifest.repeatability.anchors) != REPEATABILITY_ANCHORS:
        raise Day4ManifestError("reviewed manifest must define exactly nine anchors")
    if (
        len(manifest.repeatability.anchors)
        * len(manifest.repeatability.architectures)
        * manifest.repeatability.additional_repetitions
        != REPEAT_OBSERVATIONS
    ):
        raise Day4ManifestError("reviewed manifest must define exactly 18 repeat results")
    if estimate_model_calls(manifest) != AUTHORIZED_MODEL_CALLS:
        raise Day4ManifestError("reviewed plan must authorize exactly 270 model calls")

    if coverage is not None:
        document: Mapping[str, object]
        if isinstance(coverage, (str, Path)):
            try:
                value = yaml.safe_load(Path(coverage).read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError) as error:
                raise Day4ManifestError(f"unable to load coverage profile: {error}") from error
            if not isinstance(value, dict):
                raise Day4ManifestError("coverage profile must contain an object")
            document = value
        else:
            document = coverage
        eligible = _coverage_by_portfolio(document)
        if set(eligible) != set(manifest.portfolios):
            raise Day4ManifestError("coverage profile does not cover exactly the manifest portfolios")
        for key in manifest.portfolio_day_keys():
            as_of = key.as_of.isoformat().replace("+00:00", "Z")
            accepted = eligible[key.portfolio_id]
            accepted_dates = {value[:10] for value in accepted}
            if as_of not in accepted and as_of[:10] not in accepted_dates:
                raise Day4ManifestError(
                    f"review date lacks required prior/future coverage: "
                    f"{key.portfolio_id} {as_of}"
                )
    return manifest


def load_day4_manifest(
    path: Path | str,
    *,
    coverage: Mapping[str, object] | Path | str | None = None,
    require_reviewed: bool = True,
    verify_bindings: bool = True,
) -> Day4ExperimentManifest:
    source = Path(path).resolve(strict=True)
    try:
        manifest = Day4ExperimentManifest.model_validate(_load_mapping(source))
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, Day4ManifestError):
            raise
        raise Day4ManifestError(f"invalid Day 4 experiment manifest: {error}") from error
    validate_day4_manifest(
        manifest,
        coverage=coverage,
        require_reviewed=require_reviewed,
    )
    if verify_bindings:
        resolved = validate_input_bindings(manifest, source)
        model_document = _load_mapping(resolved["day3_model_config"])
        model_value = model_document.get("provider", model_document)
        if manifest.model.model_dump(mode="python") != manifest.model.__class__.model_validate(
            model_value
        ).model_dump(mode="python"):
            raise Day4ManifestError(
                "embedded model configuration differs from the reviewed Day 3 binding"
            )
        if manifest.pricing is not None:
            pricing_document = _load_mapping(resolved["pricing_manifest"])
            pricing_value = pricing_document.get("pricing", pricing_document)
            if (
                manifest.pricing.model_dump(mode="python")
                != manifest.pricing.__class__.model_validate(pricing_value).model_dump(
                    mode="python"
                )
            ):
                raise Day4ManifestError(
                    "embedded pricing snapshot differs from its reviewed binding"
                )
        bound_coverage = coverage
        if bound_coverage is None:
            bound_coverage = resolved["coverage_profile"]
        validate_day4_manifest(
            manifest,
            coverage=bound_coverage,
            require_reviewed=require_reviewed,
        )
    return manifest


def estimate_model_calls(manifest: Day4ExperimentManifest) -> int:
    primary = len(manifest.portfolio_day_keys()) * (0 + 1 + 4)
    repeats = (
        len(manifest.repeatability.anchors)
        * manifest.repeatability.additional_repetitions
        * (1 + 4)
    )
    if primary != PRIMARY_MODEL_CALLS or repeats != REPEAT_MODEL_CALLS:
        raise Day4ManifestError("manifest differs from the frozen 225 + 45 call plan")
    return primary + repeats


def validate_authorized_model_calls(
    manifest: Day4ExperimentManifest,
    authorized_model_calls: int,
) -> int:
    expected = estimate_model_calls(manifest)
    if authorized_model_calls != expected:
        raise Day4ManifestError(
            f"authorized model calls must exactly equal the reviewed plan ({expected})"
        )
    if manifest.maximum_authorized_model_calls != expected:
        raise Day4ManifestError("manifest authorization differs from its computed plan")
    return expected


def build_execution_plan(
    manifest: Day4ExperimentManifest,
    context_digests: Mapping[str, str],
) -> Day4ExecutionPlan:
    validate_day4_manifest(manifest)
    keys = manifest.portfolio_day_keys()
    expected_keys = {key.key_digest for key in keys}
    if set(context_digests) != expected_keys:
        raise Day4ManifestError("context digests must cover exactly the 45 portfolio-day keys")

    common = {
        "experiment_digest": manifest.manifest_digest,
        "model_snapshot": manifest.model.model_snapshot,
        "prompt_manifest_digest": manifest.model.prompt_manifest_digest,
    }
    tasks: list[Day4Task] = []
    for key in keys:
        for architecture_id in ARCHITECTURES:
            tasks.append(
                Day4Task(
                    **common,
                    key=key,
                    architecture_id=architecture_id,
                    repetition=0,
                    context_digest=context_digests[key.key_digest],
                    expected_model_calls={"B0": 0, "B1": 1, "A1": 4}[architecture_id],
                )
            )
    for anchor in manifest.repeatability.anchors:
        for architecture_id in manifest.repeatability.architectures:
            tasks.append(
                Day4Task(
                    **common,
                    key=anchor,
                    architecture_id=architecture_id,
                    repetition=1,
                    context_digest=context_digests[anchor.key_digest],
                    expected_model_calls={"B1": 1, "A1": 4}[architecture_id],
                )
            )
    return Day4ExecutionPlan(
        experiment_digest=manifest.manifest_digest,
        contexts=keys,
        tasks=tuple(tasks),
    )


def _input_binding(
    path: Path | str,
    *,
    kind: str,
    scope: str,
    repository_root: Path,
) -> dict[str, str]:
    source = Path(path)
    resolved = (
        (repository_root / source).resolve(strict=True)
        if not source.is_absolute()
        else source.resolve(strict=True)
    )
    if scope == "repository_fixture":
        try:
            stored = (
                source.as_posix()
                if not source.is_absolute()
                else resolved.relative_to(repository_root).as_posix()
            )
        except ValueError as error:
            raise Day4ManifestError(
                "synthetic fixture bindings must be beneath the manifest directory"
            ) from error
    else:
        stored = str(resolved)
    actual = sha256_tree(resolved) if kind == "tree" else sha256_file(resolved)
    return {"path": stored, "digest": actual, "kind": kind, "scope": scope}


def init_day4_experiment(
    output: Path | str,
    *,
    experiment_id: str,
    portfolios: tuple[str, str, str],
    coverage_profile: Path | str,
    day2_experiment_manifest: Path | str,
    day3_event_manifest: Path | str,
    day3_event_dataset: Path | str,
    day3_model_config: Path | str,
    day3_acceptance_run: Path | str,
    pricing_manifest: Path | str,
    profile: str = "real",
) -> Path:
    """Write a deliberately unreviewed immutable template without selecting evidence."""

    if len(portfolios) != 3 or len(set(portfolios)) != 3:
        raise Day4ManifestError("a Day 4 template requires three explicit portfolio aliases")
    if profile not in {"real", "synthetic_fixture"}:
        raise Day4ManifestError("profile must be real or synthetic_fixture")
    target = Path(output)
    if not target.is_absolute():
        target = target.resolve()
    scope = "repository_fixture" if profile == "synthetic_fixture" else "external"
    binding_args = {"scope": scope, "repository_root": REPOSITORY_ROOT}
    inputs = {
        "coverage_profile": _input_binding(coverage_profile, kind="file", **binding_args),
        "day2_experiment_manifest": _input_binding(
            day2_experiment_manifest, kind="file", **binding_args
        ),
        "day3_event_manifest": _input_binding(
            day3_event_manifest, kind="file", **binding_args
        ),
        "day3_event_dataset": _input_binding(
            day3_event_dataset, kind="file", **binding_args
        ),
        "day3_model_config": _input_binding(
            day3_model_config, kind="file", **binding_args
        ),
        "day3_acceptance_run": _input_binding(
            day3_acceptance_run, kind="tree", **binding_args
        ),
        "pricing_manifest": _input_binding(pricing_manifest, kind="file", **binding_args),
    }
    payload = {
        "version": "1",
        "profile": profile,
        "experiment_id": experiment_id,
        "reviewed": False,
        "reviewer": None,
        "portfolios": list(portfolios),
        "inputs": inputs,
        "window_set": {
            "windows": [
                {
                    "window_id": window_id,
                    "kind": "control" if window_id == "control" else "stress",
                    "rationale": "TODO: human-reviewed rationale",
                    "review_dates": [
                        "TODO: human-reviewed UTC daily-close timestamp"
                    ] * 5,
                    "trigger_available_at": (
                        None
                        if window_id == "control"
                        else "TODO: reviewed trigger availability in UTC"
                    ),
                    "relevant_portfolios": [],
                }
                for window_id in ("stress_a", "stress_b", "control")
            ]
        },
        "architectures": list(ARCHITECTURES),
        "label_policy": {
            "future_business_sessions": 5,
            "future_portfolio_drawdown_threshold": "TODO",
            "future_realized_volatility_threshold": "TODO",
            "worst_position_loss_threshold": "TODO",
            "material_event_enabled": "TODO",
            "matching_lookback_business_days": "TODO",
            "primary_label_view": "event_window",
            "sensitivity_label_views": ["outcome", "composite"],
        },
        "repeatability": {
            "anchors": [
                {
                    "portfolio_id": portfolio,
                    "window_id": window_id,
                    "as_of": "TODO: one reviewed window date",
                }
                for portfolio in portfolios
                for window_id in ("stress_a", "stress_b", "control")
            ],
            "architectures": ["B1", "A1"],
            "additional_repetitions": 1,
            "expected_additional_observations": 18,
            "expected_additional_model_calls": 45,
        },
        "model": {"TODO": "human-reviewed Day 3 model configuration"},
        "pricing": {"TODO": "human-reviewed external pricing snapshot"},
        "maximum_authorized_model_calls": 270,
        "worked_example_rules": list(WORKED_EXAMPLE_RULES),
        "human_review_required": True,
        "effects": [],
        "limitations": [
            "Two observations per anchor are a preliminary agreement measure only."
        ],
    }
    document = yaml.safe_dump(payload, sort_keys=False)
    if target.exists():
        if target.read_text(encoding="utf-8") == document:
            return target
        raise Day4ManifestError("immutable Day 4 template already exists with different content")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.write_text(document, encoding="utf-8")
    target.chmod(0o600)
    return target


# Stable public aliases used by CLI and runner integration.
load_experiment_manifest = load_day4_manifest
estimate_day4_calls = estimate_model_calls
initialize_day4_experiment = init_day4_experiment
