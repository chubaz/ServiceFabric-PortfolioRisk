"""Private-neutral coverage profiling for human-selected Day 4 windows."""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from ..day2 import _load_private_bindings, validate_day2_experiment
from ..day3.contracts import canonical, digest
from ..day3.events import read_events, validate_event_manifest


def _utc(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _neutral_event_counts(
    events: tuple[object, ...],
) -> Counter[str]:
    return Counter(
        event.available_at.astimezone(UTC).date().isoformat()  # type: ignore[attr-defined]
        for event in events
    )


def profile_day4_coverage(
    *,
    day2_experiment_manifest: Path | str,
    event_manifest: Path | str,
    event_dataset: Path | str,
    output: Path | str | None = None,
) -> dict[str, object]:
    """Describe eligible dates without selecting windows or exposing identifiers."""

    manifest, _, catalogue = validate_day2_experiment(day2_experiment_manifest)
    reviewed_events = validate_event_manifest(event_manifest)
    if read_events(event_dataset) != reviewed_events:
        raise ValueError("event dataset differs from reviewed event manifest")
    bindings, portfolios = _load_private_bindings(manifest.portfolios_directory)
    required_prices = max(
        manifest.lookback_returns,
        manifest.minimum_daily_observations,
    ) + 1
    event_counts = _neutral_event_counts(reviewed_events)
    profiles: list[dict[str, object]] = []
    with duckdb.connect(str(catalogue), read_only=True) as connection:
        connection.execute("SET enable_progress_bar = false")
        for portfolio in portfolios:
            permnos = [
                bindings[position.instrument_id]
                for position in portfolio.positions
            ]
            placeholders = ",".join("?" for _ in permnos)
            rows = connection.execute(
                f"""
                SELECT
                  CAST(observed_at AS VARCHAR),
                  CAST(MAX(available_at) AS VARCHAR),
                  COUNT(DISTINCT permno)
                FROM crsp_daily
                WHERE permno IN ({placeholders})
                  AND valuation_price IS NOT NULL
                  AND available_at <= ?
                GROUP BY observed_at
                HAVING COUNT(DISTINCT permno) = ?
                ORDER BY observed_at
                """,
                [*permnos, manifest.as_of, len(permnos)],
            ).fetchall()
            common = [(_utc(observed), _utc(available)) for observed, available, _ in rows]
            eligible: list[dict[str, object]] = []
            for index in range(required_prices - 1, max(required_prices - 1, len(common) - 5)):
                observed, available = common[index]
                review = max(observed, available)
                eligible.append(
                    {
                        "date": observed.date().isoformat(),
                        "review_timestamp": review,
                        "event_count": event_counts[review.date().isoformat()],
                        "has_required_lookback": True,
                        "has_five_future_business_sessions": True,
                    }
                )
            profiles.append(
                {
                    "portfolio_id": portfolio.portfolio_id,
                    "first_eligible_date": (
                        eligible[0]["date"] if eligible else None
                    ),
                    "last_eligible_date": (
                        eligible[-1]["date"] if eligible else None
                    ),
                    "eligible_daily_date_count": len(eligible),
                    "eligible_review_dates": [
                        item["review_timestamp"] for item in eligible
                    ],
                    "dates_with_required_lookback": max(
                        0, len(common) - required_prices + 1
                    ),
                    "dates_with_five_future_business_sessions": max(
                        0, len(common) - 5
                    ),
                    "eligible_window_candidates": eligible,
                    "warnings": (
                        []
                        if eligible
                        else ["no_dates_satisfy_lookback_and_future_horizon"]
                    ),
                }
            )
    body: dict[str, object] = {
        "coverage_version": "1.0",
        "reviewed_day2_experiment_id": manifest.experiment_id,
        "generated_at": manifest.as_of,
        "portfolio_count": len(profiles),
        "required_lookback_returns": manifest.lookback_returns,
        "future_business_sessions": 5,
        "portfolios": profiles,
        "window_selection": "human_required",
        "warnings": [
            "Coverage profiling never selects a window or threshold.",
            "The profile contains private-neutral aliases and derived counts only.",
        ],
        "effects": [],
    }
    body["digest"] = digest(body)
    if output is not None:
        target = Path(output)
        if not target.is_absolute():
            raise ValueError("coverage profile output must be absolute")
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = json.dumps(canonical(body), indent=2, sort_keys=True) + "\n"
        if target.exists() and target.read_text(encoding="utf-8") != payload:
            raise ValueError("immutable coverage profile already exists")
        target.write_text(payload, encoding="utf-8")
        os.chmod(target, 0o600)
    return canonical(body)  # type: ignore[return-value]


def load_coverage_profile(path: Path | str) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = value.pop("digest", None)
    if expected != digest(value):
        raise ValueError("coverage profile digest mismatch")
    value["digest"] = expected
    return value
