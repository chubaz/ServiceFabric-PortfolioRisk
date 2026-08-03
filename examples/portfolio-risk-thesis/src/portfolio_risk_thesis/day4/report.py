"""Deterministic, public-safe Day 4 reporting.

The functions in this module deliberately accept plain mappings as well as
Pydantic-style models.  Reporting remains a terminal projection of sealed
evaluation data: it does not calculate labels, execute an architecture, or
make a comparative recommendation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from html import escape
import json
import math
from pathlib import Path
import re
from statistics import median
from typing import Any


ARCHITECTURE_ORDER = ("B0", "B1", "A1")
CHART_FILENAMES = (
    "alert-quality.svg",
    "grounding-abstention.svg",
    "latency-cost.svg",
)
WORKED_EXAMPLE_RULES = (
    "earliest_true_positive_stress_a",
    "earliest_true_positive_stress_b",
    "highest_severity_true_positive_different_portfolio",
    "earliest_false_positive_or_failure",
    "earliest_abstention",
)

_SENSITIVE_KEYS = {
    "architecture_recommendation",
    "credential",
    "credentials",
    "dataset_path",
    "file_path",
    "local_path",
    "model_payload",
    "model_snapshot",
    "private_path",
    "prompt",
    "provider",
    "provider_error",
    "provider_id",
    "provider_identifier",
    "provider_receipts",
    "raw",
    "raw_request",
    "raw_response",
    "rank",
    "ranking",
    "request",
    "response",
    "secret",
    "source_reference",
    "source_path",
    "winner",
    "winner_field",
}
_PATH_PATTERN = re.compile(
    r"(?:(?:file://|/Users/|/home/|/private/|/tmp/|/Volumes/|"
    r"[A-Za-z]:\\\\)[^\s\"'<>]+)"
)
_SECRET_PATTERN = re.compile(
    r"(?i)\b(?:sk-[A-Za-z0-9_-]{12,}|bearer\s+[A-Za-z0-9._~+/-]{12,})\b"
)


def _plain(value: Any) -> Any:
    """Convert model-like values to deterministic JSON-compatible values."""

    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    elif is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_plain(item) for item in value), key=_stable_json)
    if isinstance(value, Enum):
        return _plain(value.value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    return value


def _stable_json(value: Any, *, pretty: bool = False) -> str:
    return json.dumps(
        _plain(value),
        ensure_ascii=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
        allow_nan=False,
    )


def _safe_text(value: Any) -> str:
    text = str(value)
    text = _PATH_PATTERN.sub("[redacted-path]", text)
    return _SECRET_PATTERN.sub("[redacted-secret]", text)


def _markdown_text(value: Any) -> str:
    return (
        escape(_safe_text(value), quote=False)
        .replace("`", "'")
        .replace("|", "\\|")
        .replace("\n", " ")
    )


def sanitize_public_data(value: Any) -> Any:
    """Remove private execution details while retaining aggregate evidence.

    Portfolio values are expected to be the reviewed private-neutral aliases
    required by the Day 4 manifest.  Raw provider material and local paths are
    removed even if they are accidentally included in an input mapping.
    """

    value = _plain(value)
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key in sorted(value):
            normalized_key = key.casefold().replace("-", "_")
            if normalized_key in _SENSITIVE_KEYS or normalized_key.endswith(
                ("_credential", "_secret", "_path")
            ):
                continue
            if normalized_key in {
                "dataset_id",
                "gvkey",
                "model_configuration",
                "permno",
                "provider_receipt",
                "provider_request_id",
                "source_id",
                "source_identifier",
            }:
                continue
            sanitized[key] = sanitize_public_data(value[key])
        return sanitized
    if isinstance(value, list):
        return [sanitize_public_data(item) for item in value]
    if isinstance(value, str):
        return _safe_text(value)
    return value


def _mapping(value: Any) -> dict[str, Any]:
    plain = _plain(value)
    if not isinstance(plain, Mapping):
        raise TypeError("report rows must be mappings or model-like objects")
    return dict(plain)


def _first(row: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return default


def _architecture(row: Mapping[str, Any]) -> str:
    return str(_first(row, "architecture", "architecture_id", default="unknown"))


def _architecture_sort(value: str) -> tuple[int, str]:
    try:
        return (ARCHITECTURE_ORDER.index(value), value)
    except ValueError:
        return (len(ARCHITECTURE_ORDER), value)


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _count(row: Mapping[str, Any], *keys: str) -> int:
    value = _number(_first(row, *keys))
    return int(value) if value is not None else 0


def _rate_from_counts(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _median_present(rows: Sequence[Mapping[str, Any]], *keys: str) -> float | None:
    values = [
        number
        for row in rows
        if (number := _number(_first(row, *keys))) is not None
    ]
    return median(values) if values else None


def _weighted_rate(
    rows: Sequence[Mapping[str, Any]], keys: Sequence[str]
) -> float | None:
    weighted_total = 0.0
    weight = 0
    for row in rows:
        value = _number(_first(row, *keys))
        row_weight = max(_count(row, "total_portfolio_days", "total"), 1)
        if value is not None:
            weighted_total += value * row_weight
            weight += row_weight
    return weighted_total / weight if weight else None


def aggregate_architecture_summary(
    summary: Iterable[Any], *, primary_label_view: str = "event_window"
) -> list[dict[str, Any]]:
    """Consolidate summary rows into one deterministic aggregate per treatment."""

    rows = [_mapping(row) for row in summary]
    primary_rows = [
        row
        for row in rows
        if str(_first(row, "label_view", default=primary_label_view))
        == primary_label_view
    ]
    if primary_rows:
        rows = primary_rows

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_architecture(row), []).append(row)

    aggregates: list[dict[str, Any]] = []
    for architecture in sorted(grouped, key=_architecture_sort):
        architecture_rows = sorted(grouped[architecture], key=_stable_json)
        overall_rows = [
            row
            for row in architecture_rows
            if ("portfolio_id" in row or "window_id" in row)
            and _first(row, "portfolio_id", "portfolio_alias") is None
            and _first(row, "window_id", "window_name") is None
        ]
        if overall_rows:
            architecture_rows = overall_rows
        total = sum(_count(row, "total_portfolio_days", "total") for row in architecture_rows)
        alerts = sum(_count(row, "alerts") for row in architecture_rows)
        abstentions = sum(_count(row, "abstentions") for row in architecture_rows)
        failures = sum(
            _count(row, "execution_failures", "provider_errors")
            for row in architecture_rows
        )
        tp = sum(_count(row, "true_positives", "tp") for row in architecture_rows)
        fp = sum(_count(row, "false_positives", "fp") for row in architecture_rows)
        tn = sum(_count(row, "true_negatives", "tn") for row in architecture_rows)
        fn = sum(_count(row, "false_negatives", "fn") for row in architecture_rows)
        provider_costs = [
            value
            for row in architecture_rows
            if (value := _number(_first(row, "provider_cost", "cost"))) is not None
        ]
        warnings = sorted(
            {
                str(warning)
                for row in architecture_rows
                for warning in _first(row, "warnings", default=[])
            }
        )
        if not provider_costs and any(
            _first(row, "provider_cost", "cost") is None for row in architecture_rows
        ):
            warnings.append("pricing_unavailable")
            warnings = sorted(set(warnings))
        aggregates.append(
            {
                "architecture": architecture,
                "label_view": primary_label_view,
                "total_portfolio_days": total,
                "alerts": alerts,
                "abstentions": abstentions,
                "execution_failures": failures,
                "tp": tp,
                "fp": fp,
                "tn": tn,
                "fn": fn,
                "precision": _rate_from_counts(tp, tp + fp),
                "recall": _rate_from_counts(tp, tp + fn),
                "alerts_per_100_portfolio_days": (
                    alerts * 100 / total if total else None
                ),
                "abstention_rate": _rate_from_counts(abstentions, total),
                "evaluated_coverage": _weighted_rate(
                    architecture_rows, ("evaluated_coverage",)
                ),
                "evidence_reference_coverage": _weighted_rate(
                    architecture_rows,
                    ("evidence_reference_coverage", "evidence_coverage"),
                ),
                "unsupported_claim_rate": _weighted_rate(
                    architecture_rows, ("unsupported_claim_rate",)
                ),
                "critic_pass_rate": _weighted_rate(
                    architecture_rows, ("critic_pass_rate",)
                ),
                "median_event_detection_delay": _median_present(
                    architecture_rows,
                    "median_event_detection_delay_seconds",
                    "median_event_detection_delay",
                    "event_detection_delay",
                ),
                "median_outcome_lead_time": _median_present(
                    architecture_rows,
                    "median_outcome_lead_time_seconds",
                    "median_outcome_lead_time",
                    "outcome_lead_time",
                ),
                "median_latency_ms": _median_present(
                    architecture_rows, "median_latency_ms", "latency_ms"
                ),
                "p95_latency_ms": _median_present(
                    architecture_rows, "p95_latency_ms"
                ),
                "input_tokens": sum(
                    _count(row, "input_tokens") for row in architecture_rows
                ),
                "output_tokens": sum(
                    _count(row, "output_tokens") for row in architecture_rows
                ),
                "provider_cost": sum(provider_costs) if provider_costs else None,
                "warnings": warnings,
            }
        )
    return aggregates


def _fmt(value: Any, *, percent: bool = False, digits: int = 2) -> str:
    number = _number(value)
    if number is None:
        return "not available"
    if percent:
        return f"{number * 100:.{digits}f}%"
    return f"{number:.{digits}f}"


def _markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    def cell(value: Any) -> str:
        return _markdown_text(value)

    lines = [
        "| " + " | ".join(cell(item) for item in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(cell(item) for item in row) + " |" for row in rows)
    return "\n".join(lines)


def render_preliminary_results(
    summary: Iterable[Any],
    repeatability: Iterable[Any] = (),
    metadata: Mapping[str, Any] | None = None,
) -> str:
    """Render aggregate-only preliminary Markdown.

    The result intentionally omits portfolio aliases, local paths, provider
    identity, raw observations, prompts, and responses.
    """

    public_metadata = sanitize_public_data(metadata or {})
    if not isinstance(public_metadata, Mapping):
        public_metadata = {}
    primary_label_view = str(
        public_metadata.get("primary_label_view", "event_window")
    )
    aggregates = aggregate_architecture_summary(
        summary, primary_label_view=primary_label_view
    )
    repeat_rows = [_mapping(row) for row in repeatability]

    counts = {
        "contexts": public_metadata.get(
            "context_count", public_metadata.get("primary_context_count")
        ),
        "primary observations": public_metadata.get("primary_observation_count"),
        "repeat observations": public_metadata.get("repeat_observation_count"),
        "total observations": public_metadata.get("total_observation_count"),
        "labels": public_metadata.get("label_count"),
        "model-call receipts": public_metadata.get(
            "model_call_receipt_count", public_metadata.get("model_call_count")
        ),
    }
    observed_counts = [
        (label, value) for label, value in counts.items() if value is not None
    ]

    lines = [
        "# Day 4 preliminary historical evaluation",
        "",
        "> Research observations only. Human review is required. This material is not "
        "investment advice and authorizes no order, trade, rebalance, or portfolio "
        "mutation.",
        "",
        "## Methodology",
        "",
        "The reviewed historical panel applies B0, B1, and A1 to common point-in-time "
        "contexts. Architecture execution closes before labels are loaded. The "
        f"primary descriptive label view is `{_markdown_text(primary_label_view)}`; "
        "outcome and composite views are sensitivity checks.",
        "",
    ]
    if observed_counts:
        lines.extend(
            [
                "## Observed run coverage",
                "",
                _markdown_table(
                    ("Artifact", "Observed count"),
                    [(label, value) for label, value in observed_counts],
                ),
                "",
            ]
        )

    lines.extend(
        [
            "## Aggregate observations",
            "",
            _markdown_table(
                (
                    "Architecture",
                    "Portfolio-days",
                    "Alerts",
                    "Abstentions",
                    "Execution failures",
                    "Precision",
                    "Recall",
                    "Evidence coverage",
                    "Critic pass",
                ),
                [
                    (
                        row["architecture"],
                        row["total_portfolio_days"],
                        row["alerts"],
                        row["abstentions"],
                        row["execution_failures"],
                        _fmt(row["precision"], percent=True),
                        _fmt(row["recall"], percent=True),
                        _fmt(row["evidence_reference_coverage"], percent=True),
                        _fmt(row["critic_pass_rate"], percent=True),
                    )
                    for row in aggregates
                ],
            ),
            "",
            "Undefined precision or recall is reported as `not available`; missing "
            "observations are not converted to zero.",
            "",
            "## Timeliness and resource observations",
            "",
            _markdown_table(
                (
                    "Architecture",
                    "Median latency (ms)",
                    "Deterministic p95 (ms)",
                    "Input tokens",
                    "Output tokens",
                    "Reviewed-manifest cost",
                    "Warnings",
                ),
                [
                    (
                        row["architecture"],
                        _fmt(row["median_latency_ms"]),
                        _fmt(row["p95_latency_ms"]),
                        row["input_tokens"],
                        row["output_tokens"],
                        _fmt(row["provider_cost"], digits=6),
                        ", ".join(row["warnings"]) or "none",
                    )
                    for row in aggregates
                ],
            ),
            "",
        ]
    )

    if repeat_rows:
        repeat_rows.sort(key=lambda row: _architecture_sort(_architecture(row)))
        lines.extend(
            [
                "## Preliminary repeatability observations",
                "",
                _markdown_table(
                    (
                        "Architecture",
                        "Status agreement",
                        "Severity agreement",
                        "Exact-output agreement",
                        "Position agreement",
                        "Evidence agreement",
                    ),
                    [
                        (
                            _architecture(row),
                            _fmt(
                                _first(
                                    row,
                                    "semantic_status_agreement",
                                    "status_agreement",
                                ),
                                percent=True,
                            ),
                            _fmt(_first(row, "severity_agreement"), percent=True),
                            _fmt(
                                _first(
                                    row,
                                    "exact_semantic_output_digest_agreement",
                                    "exact_output_digest_agreement",
                                ),
                                percent=True,
                            ),
                            _fmt(
                                _first(
                                    row,
                                    "affected_position_jaccard_agreement",
                                    "affected_position_agreement",
                                ),
                                percent=True,
                            ),
                            _fmt(
                                _first(
                                    row,
                                    "evidence_reference_jaccard_agreement",
                                    "evidence_reference_agreement",
                                ),
                                percent=True,
                            ),
                        )
                        for row in repeat_rows
                    ],
                ),
                "",
            ]
        )

    def notes(key: str, defaults: list[str]) -> list[str]:
        value = public_metadata.get(key)
        if value is None:
            return defaults
        if isinstance(value, str):
            return [value]
        if isinstance(value, Sequence):
            return [str(item) for item in value]
        return [str(value)]

    assumptions = notes(
        "assumptions",
        [
            "The reviewed windows and thresholds are fixed before execution.",
            "Private-neutral aliases identify portfolios without exposing account details.",
        ],
    )
    warnings = notes(
        "warnings",
        [
            "This is a small descriptive panel with imperfect preliminary ground truth.",
        ],
    )
    limitations = notes(
        "limitations",
        [
            "Two observations per B1/A1 anchor are only a preliminary agreement check.",
            "The observations do not establish significance, predictive superiority, "
            "investment performance, production readiness, or regulatory compliance.",
        ],
    )
    lines.extend(["## Assumptions", ""])
    lines.extend(f"- {_markdown_text(item)}" for item in assumptions)
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {_markdown_text(item)}" for item in warnings)
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {_markdown_text(item)}" for item in limitations)
    lines.extend(
        [
            "",
            "No comparative conclusion or architecture recommendation is made. "
            "Automated acceptance does not approve the experiment, pull request, "
            "release, or any consequential action.",
            "",
        ]
    )
    return "\n".join(lines)


def _classification(row: Mapping[str, Any]) -> str:
    if bool(_first(row, "execution_failure", default=False)):
        return "execution_failure"
    explicit = str(
        _first(
            row,
            "evaluation_class",
            "classification",
            "observation_class",
            default="",
        )
    ).casefold()
    if explicit:
        return explicit
    status = str(_first(row, "status", "architecture_status", default="")).upper()
    if status in {"REVIEW", "URGENT_REVIEW"}:
        return "alert"
    if status in {"NO_ISSUE"}:
        return "no_alert"
    if status in {"ABSTAIN", "ABSTAINED_AGENT_OUTPUT"}:
        return "abstention"
    if status in {"EXECUTION_FAILURE", "PROVIDER_ERROR", "FAILED"}:
        return "execution_failure"
    return ""


def _positive_label(row: Mapping[str, Any]) -> bool:
    return bool(
        _first(
            row,
            "label_positive",
            "positive_label",
            "event_window_positive",
            default=False,
        )
    )


def _is_tp(row: Mapping[str, Any]) -> bool:
    explicit = _first(row, "is_true_positive", "true_positive")
    return bool(explicit) if explicit is not None else (
        _classification(row) == "alert" and _positive_label(row)
    )


def _is_fp(row: Mapping[str, Any]) -> bool:
    explicit = _first(row, "is_false_positive", "false_positive")
    return bool(explicit) if explicit is not None else (
        _classification(row) == "alert" and not _positive_label(row)
    )


def _window(row: Mapping[str, Any]) -> str:
    return str(_first(row, "window", "window_name", "window_id", default=""))


def _portfolio(row: Mapping[str, Any]) -> str:
    return str(
        _first(row, "portfolio_alias", "portfolio", "portfolio_id", default="")
    )


def _review_date(row: Mapping[str, Any]) -> str:
    return str(
        _first(
            row,
            "review_date",
            "as_of",
            "reviewed_at",
            "timestamp",
            default="",
        )
    )


def _identity(row: Mapping[str, Any]) -> tuple[str, ...]:
    explicit = _first(row, "observation_id", "result_id", "task_id")
    if explicit is not None:
        return (str(explicit),)
    return (
        _architecture(row),
        _portfolio(row),
        _window(row),
        _review_date(row),
        str(_first(row, "repetition", default=0)),
    )


def _chronological_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        _review_date(row),
        _portfolio(row),
        _architecture_sort(_architecture(row)),
        _identity(row),
    )


def _severity_value(row: Mapping[str, Any]) -> int:
    raw_severity = _first(row, "severity", default="")
    numeric_severity = _number(raw_severity)
    if numeric_severity is not None:
        return int(numeric_severity)
    severity = str(raw_severity).upper()
    return {
        "URGENT": 5,
        "CRITICAL": 5,
        "HIGH": 4,
        "MEDIUM": 3,
        "LOW": 2,
        "INFO": 1,
        "NONE": 0,
    }.get(severity, 0)


def _nested_mapping(row: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = row.get(key)
    return dict(value) if isinstance(value, Mapping) else {}


def _flatten_worked_rows(results: Iterable[Any]) -> list[dict[str, Any]]:
    """Flatten PortfolioDayResult-like values while retaining flat-row support."""

    flattened: list[dict[str, Any]] = []
    for result in results:
        row = _mapping(result)
        observations = row.get("observations")
        if isinstance(observations, list):
            key = _nested_mapping(row, "key")
            label = _nested_mapping(row, "label")
            event_window = _nested_mapping(label, "event_window")
            label_positive = bool(event_window.get("positive", False))
            for observation in observations:
                if not isinstance(observation, Mapping):
                    continue
                flat = dict(observation)
                observation_key = _nested_mapping(flat, "key") or key
                flat.setdefault("portfolio_id", observation_key.get("portfolio_id"))
                flat.setdefault("window_id", observation_key.get("window_id"))
                flat.setdefault("as_of", observation_key.get("as_of"))
                flat.setdefault("label_positive", label_positive)
                flat.setdefault("label_digest", label.get("label_digest"))
                flattened.append(flat)
            continue

        key = _nested_mapping(row, "key")
        if key:
            row.setdefault("portfolio_id", key.get("portfolio_id"))
            row.setdefault("window_id", key.get("window_id"))
            row.setdefault("as_of", key.get("as_of"))
        label = _nested_mapping(row, "label")
        event_window = _nested_mapping(label, "event_window")
        if event_window:
            row.setdefault("label_positive", bool(event_window.get("positive", False)))
            row.setdefault("label_digest", label.get("label_digest"))
        flattened.append(row)
    return flattened


def _worked_example(rule: str, row: Mapping[str, Any]) -> dict[str, Any]:
    example = sanitize_public_data(row)
    assert isinstance(example, Mapping)
    return {"selection_rule": rule, "observation": dict(example)}


def select_worked_examples(
    results: Iterable[Any],
    rules: Sequence[str] | None = None,
    *,
    require_minimum_alerts: bool = True,
) -> list[dict[str, Any]]:
    """Apply the reviewed deterministic worked-case rules.

    The architecture identity is a tie-breaker only; cases are never selected
    on the basis of comparative architecture performance.
    """

    selected_rules = tuple(rules or WORKED_EXAMPLE_RULES)
    unknown = set(selected_rules) - set(WORKED_EXAMPLE_RULES)
    if unknown:
        raise ValueError(f"unsupported worked-example rules: {sorted(unknown)}")

    rows = sorted(_flatten_worked_rows(results), key=_chronological_key)
    selected: list[dict[str, Any]] = []
    selected_ids: set[tuple[str, ...]] = set()
    selected_portfolios: set[str] = set()

    def add(rule: str, candidates: Iterable[Mapping[str, Any]]) -> None:
        for candidate in candidates:
            identity = _identity(candidate)
            if identity not in selected_ids:
                selected.append(_worked_example(rule, candidate))
                selected_ids.add(identity)
                selected_portfolios.add(_portfolio(candidate))
                return

    if "earliest_true_positive_stress_a" in selected_rules:
        add(
            "earliest_true_positive_stress_a",
            (row for row in rows if _window(row) == "stress_a" and _is_tp(row)),
        )
    if "earliest_true_positive_stress_b" in selected_rules:
        add(
            "earliest_true_positive_stress_b",
            (row for row in rows if _window(row) == "stress_b" and _is_tp(row)),
        )
    if "highest_severity_true_positive_different_portfolio" in selected_rules:
        true_positives = [row for row in rows if _is_tp(row)]
        different = [
            row
            for row in true_positives
            if _portfolio(row) not in selected_portfolios
        ]
        pool = different or true_positives
        pool.sort(
            key=lambda row: (
                -_severity_value(row),
                *_chronological_key(row),
            )
        )
        add("highest_severity_true_positive_different_portfolio", pool)
    if "earliest_false_positive_or_failure" in selected_rules:
        false_positives = [row for row in rows if _is_fp(row)]
        if false_positives:
            add("earliest_false_positive_or_failure", false_positives)
        else:
            failures = [
                row
                for row in rows
                if _classification(row) == "execution_failure"
                or _first(row, "critic_pass", "critic_passed") is False
            ]
            add("earliest_false_positive_or_failure", failures)
    if "earliest_abstention" in selected_rules:
        add(
            "earliest_abstention",
            (row for row in rows if _classification(row) == "abstention"),
        )

    alert_examples = sum(
        _is_tp(_mapping(example["observation"]))
        for example in selected
    )
    if require_minimum_alerts and alert_examples < 3:
        raise ValueError(
            "worked-example exit criterion failed: fewer than three alert cases"
        )
    if require_minimum_alerts:
        completed_rules = {str(example["selection_rule"]) for example in selected}
        missing_rules = set(selected_rules) - completed_rules
        if missing_rules:
            raise ValueError(
                "worked-example exit criterion failed: required cases unavailable: "
                + ", ".join(sorted(missing_rules))
            )
    return selected


def _svg_chart(
    title: str,
    rows: Sequence[Mapping[str, Any]],
    metrics: Sequence[tuple[str, str, bool]],
) -> str:
    width = 960
    left = 260
    right = 130
    top = 82
    row_height = 34
    height = top + row_height * max(len(rows) * len(metrics), 1) + 58
    plot_width = width - left - right
    palette = {"B0": "#355c7d", "B1": "#2a9d8f", "A1": "#e07a5f"}

    maximums: dict[str, float] = {}
    for key, _, percent in metrics:
        present = [_number(row.get(key)) for row in rows]
        present = [value for value in present if value is not None]
        maximums[key] = 1.0 if percent else max(present or [1.0])
        if maximums[key] <= 0:
            maximums[key] = 1.0

    svg = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
            f'aria-labelledby="title desc">'
        ),
        f'<title id="title">{escape(title)}</title>',
        (
            '<desc id="desc">Descriptive bars by architecture. Missing values '
            "are explicitly marked not available.</desc>"
        ),
        "<style>"
        "text{font-family:system-ui,-apple-system,sans-serif;fill:#17202a}"
        ".heading{font-size:22px;font-weight:700}.label{font-size:13px}"
        ".value{font-size:12px}.axis{stroke:#ccd5df;stroke-width:1}"
        "</style>",
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text class="heading" x="24" y="38">{escape(title)}</text>',
        (
            '<text class="label" x="24" y="60">Preliminary descriptive '
            "observations; human review required.</text>"
        ),
    ]
    y = top
    for row in rows:
        architecture = str(row["architecture"])
        for key, label, percent in metrics:
            value = _number(row.get(key))
            value_label = (
                "not available"
                if value is None
                else (f"{value * 100:.1f}%" if percent else f"{value:.3f}")
            )
            bar_width = (
                0
                if value is None
                else max(0.0, min(value / maximums[key], 1.0)) * plot_width
            )
            svg.extend(
                [
                    (
                        f'<text class="label" x="24" y="{y + 19}">'
                        f"{escape(architecture)} — {escape(label)}</text>"
                    ),
                    (
                        f'<line class="axis" x1="{left}" y1="{y + 16}" '
                        f'x2="{left + plot_width}" y2="{y + 16}"/>'
                    ),
                    (
                        f'<rect x="{left}" y="{y + 5}" width="{bar_width:.2f}" '
                        f'height="20" rx="3" fill="{palette.get(architecture, "#6c757d")}"/>'
                    ),
                    (
                        f'<text class="value" x="{left + plot_width + 12}" '
                        f'y="{y + 20}">{escape(value_label)}</text>'
                    ),
                ]
            )
            y += row_height
    svg.append("</svg>")
    return "\n".join(svg) + "\n"


def _write_idempotent(path: Path, content: str) -> Path:
    """Create an immutable artifact, accepting an identical replay."""

    encoded = content.encode("utf-8")
    if path.exists():
        if path.read_bytes() == encoded:
            return path
        raise FileExistsError(f"refusing to replace immutable artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return path


def render_charts(summary: Iterable[Any], output_dir: str | Path) -> tuple[Path, ...]:
    """Write the three required deterministic, dependency-free SVG charts."""

    rows = aggregate_architecture_summary(summary)
    output = Path(output_dir)
    chart_specs = (
        (
            CHART_FILENAMES[0],
            "Alert quality",
            (
                ("precision", "Precision", True),
                ("recall", "Recall", True),
                (
                    "alerts_per_100_portfolio_days",
                    "Alerts per 100 portfolio-days",
                    False,
                ),
            ),
        ),
        (
            CHART_FILENAMES[1],
            "Grounding and abstention",
            (
                ("evidence_reference_coverage", "Evidence coverage", True),
                ("critic_pass_rate", "Critic pass", True),
                ("abstention_rate", "Abstention rate", True),
                ("unsupported_claim_rate", "Unsupported-claim rate", True),
            ),
        ),
        (
            CHART_FILENAMES[2],
            "Latency and reviewed-manifest cost",
            (
                ("median_latency_ms", "Median latency (ms)", False),
                ("p95_latency_ms", "Deterministic p95 latency (ms)", False),
                ("provider_cost", "Cost", False),
            ),
        ),
    )
    return tuple(
        _write_idempotent(output / filename, _svg_chart(title, rows, metrics))
        for filename, title, metrics in chart_specs
    )


def _dashboard_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    sanitized = sanitize_public_data(data)
    if not isinstance(sanitized, Mapping):
        raise TypeError("dashboard data must be a mapping")
    payload = dict(sanitized)
    contexts = payload.get("portfolio_days", payload.get("contexts", []))
    if not isinstance(contexts, list):
        raise TypeError("dashboard contexts must be a list")
    normalized_contexts: list[Any] = []
    for context in contexts:
        if not isinstance(context, Mapping):
            normalized_contexts.append(context)
            continue
        normalized = dict(context)
        key = _nested_mapping(normalized, "key")
        if key:
            normalized.setdefault("portfolio_alias", key.get("portfolio_id"))
            normalized.setdefault("window", key.get("window_id"))
            normalized.setdefault("review_date", key.get("as_of"))
        normalized_contexts.append(normalized)
    payload["contexts"] = normalized_contexts
    payload.pop("portfolio_days", None)
    return payload


def _script_json(value: Any) -> str:
    return (
        _stable_json(value)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _dashboard_html(payload: Mapping[str, Any]) -> str:
    embedded = _script_json(payload)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Day 4 historical evaluation</title>
  <style>
    :root {{ color-scheme: light; --ink:#17202a; --muted:#5d6d7e;
      --paper:#f4f7f9; --panel:#fff; --line:#d9e2e8; --accent:#276678;
      --warn:#8a5a00; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:var(--paper);
      font:16px/1.5 system-ui,-apple-system,sans-serif; }}
    header,main,footer {{ width:min(1180px,calc(100% - 2rem)); margin:auto; }}
    header {{ padding:2rem 0 1rem; }}
    h1,h2 {{ line-height:1.2; }} h1 {{ margin:.2rem 0; }}
    .boundary {{ border-left:.35rem solid var(--warn); background:#fff8e7;
      padding:.8rem 1rem; }}
    .controls {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr));
      gap:1rem; margin:1rem 0; }}
    label {{ font-weight:650; }} select {{ display:block; width:100%;
      margin-top:.25rem; padding:.6rem; border:1px solid var(--line);
      border-radius:.35rem; background:white; color:var(--ink); }}
    .grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr));
      gap:1rem; }}
    section {{ background:var(--panel); border:1px solid var(--line);
      border-radius:.6rem; padding:1rem; min-width:0; }}
    section h2 {{ margin-top:0; font-size:1.12rem; color:var(--accent); }}
    pre {{ white-space:pre-wrap; overflow-wrap:anywhere; margin:0;
      font:13px/1.45 ui-monospace,SFMono-Regular,monospace; }}
    table {{ width:100%; border-collapse:collapse; }}
    th,td {{ text-align:left; vertical-align:top; padding:.45rem;
      border-bottom:1px solid var(--line); }}
    .wide {{ grid-column:1/-1; }} .muted {{ color:var(--muted); }}
    .decision li {{ margin:.45rem 0; }}
    a {{ color:#155e75; }} footer {{ padding:1.2rem 0 2rem; }}
    @media (max-width:760px) {{ .controls,.grid {{ grid-template-columns:1fr; }}
      .wide {{ grid-column:auto; }} }}
  </style>
</head>
<body>
<header>
  <p class="muted">Thesis Sprint · preliminary historical evaluation</p>
  <h1>Portfolio-risk architecture observations</h1>
  <p class="boundary">Research observations only. Human review is required.
  No order, trade, rebalance, or portfolio mutation is authorized.</p>
</header>
<main>
  <form class="controls" aria-label="Observation filters">
    <label>Portfolio<select id="portfolio"></select></label>
    <label>Window<select id="window"></select></label>
    <label>Review date<select id="review-date"></select></label>
    <label>Architecture<select id="architecture"></select></label>
  </form>
  <p id="empty" class="boundary" hidden>No observation matches these controls.</p>
  <div class="grid" id="content">
    <section><h2>NAV and drawdown context</h2><pre id="nav"></pre></section>
    <section><h2>MetricPack</h2><pre id="metrics"></pre></section>
    <section><h2>Eligible events</h2><pre id="events"></pre></section>
    <section><h2>Deterministic findings</h2><pre id="findings"></pre></section>
    <section class="wide"><h2>Architecture comparison</h2>
      <div id="comparison"></div></section>
    <section class="wide"><h2>Aggregate charts</h2>
      <p><a href="../charts/alert-quality.svg">Alert quality chart</a> ·
      <a href="../charts/grounding-abstention.svg">Grounding and abstention chart</a> ·
      <a href="../charts/latency-cost.svg">Latency and cost chart</a></p>
    </section>
    <section><h2>Critic and evidence detail</h2><pre id="critic"></pre></section>
    <section><h2>Tokens, latency, and cost</h2><pre id="resources"></pre></section>
    <section class="wide decision"><h2>Human decision options</h2>
      <ul><li>Accept the observation for further research review.</li>
      <li>Request evidence or critic review before interpretation.</li>
      <li>Reject the preliminary observation without changing labels or thresholds.</li>
      </ul>
      <p>Every option is effect-free and requires an explicit human decision.</p>
    </section>
    <section class="wide"><h2>Methodology, assumptions, warnings, and limitations</h2>
      <pre id="notes"></pre></section>
  </div>
  <p><a href="../preliminary-results.md" download>Export preliminary Markdown</a></p>
</main>
<footer class="muted">Static offline artifact · embedded CSS, JavaScript, and data</footer>
<script id="day4-data" type="application/json">{embedded}</script>
<script>
(() => {{
  "use strict";
  const data = JSON.parse(document.getElementById("day4-data").textContent);
  const contexts = Array.isArray(data.contexts) ? data.contexts : [];
  const ids = ["portfolio","window","review-date","architecture"];
  const controls = Object.fromEntries(ids.map(id => [id,document.getElementById(id)]));
  const first = (obj, keys, fallback="") => {{
    for (const key of keys) if (obj && obj[key] !== undefined && obj[key] !== null)
      return obj[key];
    return fallback;
  }};
  const field = {{
    portfolio:c => String(first(c,["portfolio_alias","portfolio","portfolio_id"])),
    window:c => String(first(c,["window","window_name","window_id"])),
    "review-date":c => String(first(c,["review_date","as_of","reviewed_at"])),
  }};
  const results = c => Array.isArray(first(c,["architecture_results","observations"],[]))
    ? first(c,["architecture_results","observations"],[]) : [];
  const architecture = r => String(first(r,["architecture","architecture_id"]));
  const values = id => {{
    if (id === "architecture") return [...new Set(contexts.flatMap(c => results(c).map(architecture)))];
    return [...new Set(contexts.map(field[id]))];
  }};
  const architectureOrder = a => ({{B0:0,B1:1,A1:2}})[a] ?? 99;
  for (const id of ids) {{
    const sorted = values(id).filter(Boolean).sort((a,b) =>
      id === "architecture" ? architectureOrder(a)-architectureOrder(b) || a.localeCompare(b)
      : a.localeCompare(b));
    controls[id].replaceChildren(...sorted.map(value => {{
      const option=document.createElement("option"); option.value=value;
      option.textContent=value; return option;
    }}));
    controls[id].addEventListener("change",render);
  }}
  const show = (id,value) => {{
    document.getElementById(id).textContent =
      typeof value === "string" ? value : JSON.stringify(value ?? "not available",null,2);
  }};
  const table = rows => {{
    const keys=["architecture","status","severity","classification"];
    const t=document.createElement("table");
    const head=document.createElement("tr");
    for (const key of keys) {{ const th=document.createElement("th"); th.textContent=key; head.append(th); }}
    const thead=document.createElement("thead"); thead.append(head); t.append(thead);
    const body=document.createElement("tbody");
    for (const row of rows) {{ const tr=document.createElement("tr");
      for (const key of keys) {{ const td=document.createElement("td");
        td.textContent=String(first(row,[key,key === "architecture" ? "architecture_id" : key],"not available"));
        tr.append(td); }} body.append(tr); }}
    t.append(body); return t;
  }};
  function render() {{
    const context=contexts.find(c => ["portfolio","window","review-date"].every(
      id => field[id](c) === controls[id].value));
    const selected=context ? results(context).find(r => architecture(r) === controls.architecture.value) : null;
    document.getElementById("empty").hidden=Boolean(context && selected);
    document.getElementById("content").hidden=!context;
    if (!context) return;
    show("nav", first(context,["nav_drawdown_context","nav_and_drawdown","nav"]));
    show("metrics", first(context,["metric_pack","metrics"]));
    show("events", first(context,["eligible_events","events"],[]));
    show("findings", first(context,["deterministic_findings","findings"],[]));
    const comparison=document.getElementById("comparison"); comparison.replaceChildren(table(results(context)));
    show("critic", selected ? {{
      critic:first(selected,["critic","critic_result"]),
      evidence:first(selected,["evidence_references","evidence_refs"],[])
    }} : "not available");
    show("resources", selected ? {{
      input_tokens:first(selected,["input_tokens"]),
      output_tokens:first(selected,["output_tokens"]),
      latency_ms:first(selected,["latency_ms","median_latency_ms"]),
      cost:first(selected,["provider_cost","cost"]),
      warnings:first(selected,["warnings"],[])
    }} : "not available");
    show("notes",{{
      methodology:data.methodology ?? "Point-in-time execution precedes label evaluation.",
      assumptions:data.assumptions ?? [],
      warnings:data.warnings ?? [],
      limitations:data.limitations ?? []
    }});
  }}
  render();
}})();
</script>
</body>
</html>
"""


def render_dashboard(data: Mapping[str, Any], output_dir: str | Path) -> Path:
    """Write a self-contained semantic HTML dashboard and its audit data JSON."""

    payload = _dashboard_payload(data)
    output = Path(output_dir)
    _write_idempotent(
        output / "dashboard-data.json", _stable_json(payload, pretty=True) + "\n"
    )
    return _write_idempotent(output / "index.html", _dashboard_html(payload))


def write_day4_reports(
    output_dir: str | Path,
    *,
    summary: Iterable[Any],
    repeatability: Iterable[Any],
    results: Iterable[Any],
    dashboard_data: Mapping[str, Any],
    metadata: Mapping[str, Any] | None = None,
    worked_example_rules: Sequence[str] | None = None,
) -> dict[str, Path]:
    """Write the complete Day 4 reporting layer beneath an immutable run."""

    root = Path(output_dir)
    summary_rows = list(summary)
    repeatability_rows = list(repeatability)
    result_rows = list(results)
    examples = select_worked_examples(
        result_rows, worked_example_rules, require_minimum_alerts=True
    )
    markdown = render_preliminary_results(
        summary_rows, repeatability_rows, metadata
    )
    paths: dict[str, Path] = {
        "preliminary_results": _write_idempotent(
            root / "preliminary-results.md", markdown
        )
    }
    for path in render_charts(summary_rows, root / "charts"):
        paths[path.stem.replace("-", "_")] = path
    for index, example in enumerate(examples, start=1):
        rule = str(example["selection_rule"]).replace("_", "-")
        path = _write_idempotent(
            root / "worked-examples" / f"{index:02d}-{rule}.json",
            _stable_json(example, pretty=True) + "\n",
        )
        paths[f"worked_example_{index}"] = path
    paths["dashboard"] = render_dashboard(dashboard_data, root / "dashboard")
    paths["dashboard_data"] = root / "dashboard" / "dashboard-data.json"
    return paths
