#!/usr/bin/env python3
"""Generate the reviewed deterministic fictional Day 1 Parquet fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


SEED = 20260728
FIXTURE_REVISION = "2026-07-28.2"
MARKET_LIMITATIONS = (
    "Fictional synthetic observation; not a representation of a real market.",
    "No external provider observation or missing value imputation is present.",
)
EVENT_LIMITATIONS = (
    "Fictional synthetic event; not a representation of real news.",
    "Sentiment and relevance are deterministic fixture attributes, not model outputs.",
)
INSTRUMENTS = (
    ("instrument-aurora-tech", Decimal("100.00")),
    ("instrument-cobalt-tech", Decimal("82.00")),
    ("instrument-lantern-fin", Decimal("61.00")),
    ("instrument-marrow-health", Decimal("73.00")),
    ("instrument-pantry-staples", Decimal("49.00")),
    ("instrument-civic-bond", Decimal("101.00")),
    ("instrument-harbor-credit", Decimal("94.00")),
    ("instrument-sunstone-gold", Decimal("76.00")),
)


def business_days(start: date, count: int) -> tuple[date, ...]:
    values: list[date] = []
    current = start
    while len(values) < count:
        if current.weekday() < 5:
            values.append(current)
        current += timedelta(days=1)
    return tuple(values)


def _canonical_value(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _canonical_value(item) for key, item in value.items()}
    return value


def record_digest(row: dict[str, object]) -> str:
    payload = json.dumps(
        _canonical_value(row),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def market_rows() -> list[dict[str, object]]:
    rng = random.Random(SEED)
    days = business_days(date(2024, 1, 2), 130)
    rows: list[dict[str, object]] = []
    for instrument_index, (instrument_id, initial) in enumerate(INSTRUMENTS):
        price = initial
        for ordinal, day in enumerate(days):
            drift = Decimal(instrument_index - 3) * Decimal("0.00007")
            shock = Decimal(rng.randrange(-85, 86)) / Decimal("100000")
            price = (price * (Decimal("1") + drift + shock)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)
            observed = datetime.combine(day, time(16, 0, tzinfo=UTC))
            available = observed + timedelta(minutes=30 + instrument_index)
            warning = instrument_id == "instrument-harbor-credit" and ordinal == 37
            row: dict[str, object] = {
                "instrument_id": instrument_id,
                "timestamp": observed,
                "available_at": available,
                "close": price,
                "adjusted_close": None if warning else price,
                "volume": Decimal(100000 + instrument_index * 11000 + ordinal * 137),
                "currency": "USD",
                "source_id": "synthetic-thesis-market-v1",
                "fixture_revision": FIXTURE_REVISION,
                "units": ("close:USD", "adjusted_close:USD", "volume:shares"),
                "quality_state": "warning" if warning else "complete",
                "limitations": MARKET_LIMITATIONS,
                "synthetic": True,
                "evidence_ref": f"fixture://thesis-day1/market/{instrument_id}/{day.isoformat()}",
            }
            row["content_digest"] = record_digest(row)
            rows.append(row)
    return sorted(rows, key=lambda row: (row["timestamp"], row["instrument_id"]))


def event_rows() -> list[dict[str, object]]:
    days = business_days(date(2024, 1, 8), 24)
    sentiments = ("neutral", "positive", "negative")
    rows: list[dict[str, object]] = []
    for ordinal, day in enumerate(days):
        instrument_id = INSTRUMENTS[ordinal % len(INSTRUMENTS)][0]
        event_time = datetime.combine(day, time(10 + ordinal % 5, 0, tzinfo=UTC))
        delay = timedelta(hours=2 + ordinal % 4)
        if ordinal == 20:
            event_time = datetime(2024, 6, 25, 10, 0, tzinfo=UTC)
            delay = timedelta(days=2, hours=9)  # eligible only after the 27 June 18:00 step
        row = {
            "event_id": f"fictional-event-{ordinal + 1:03d}",
            "event_time": event_time,
            "available_at": event_time + delay,
            "entity_id": f"entity-{instrument_id.removeprefix('instrument-')}",
            "instrument_ids": [instrument_id],
            "headline": f"Fictional operational bulletin {ordinal + 1:03d}",
            "short_text": "Synthetic scenario text describing an invented issuer update for research replay.",
            "sentiment": sentiments[ordinal % len(sentiments)],
            "relevance": Decimal("0.55") + Decimal(ordinal % 5) / Decimal("10"),
            "source_id": "synthetic-thesis-events-v1",
            "fixture_revision": FIXTURE_REVISION,
            "units": ("relevance:unit_interval", "sentiment:categorical"),
            "quality_state": "complete",
            "limitations": EVENT_LIMITATIONS,
            "evidence_ref": f"fixture://thesis-day1/events/fictional-event-{ordinal + 1:03d}",
            "synthetic": True,
        }
        row["content_digest"] = record_digest(row)
        rows.append(row)
    return sorted(rows, key=lambda row: (row["available_at"], row["event_time"], row["event_id"]))


def sha256_file(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def write_fixture(output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    market_path = output / "market.parquet"
    events_path = output / "events.parquet"
    markets = market_rows()
    events = event_rows()
    pq.write_table(pa.Table.from_pylist(markets), market_path, compression="NONE", version="2.6")
    pq.write_table(pa.Table.from_pylist(events), events_path, compression="NONE", version="2.6")
    manifest = {
        "fixture_id": "synthetic-thesis-day1-v1",
        "revision": FIXTURE_REVISION,
        "seed": SEED,
        "synthetic": True,
        "files": {
            "market.parquet": {"sha256": sha256_file(market_path), "row_count": len(markets)},
            "events.parquet": {"sha256": sha256_file(events_path), "row_count": len(events)},
        },
        "limitations": [
            "All instruments, issuers, labels, observations and events are fictional and synthetic.",
            "The fixture is research input, not investment advice or a representation of real markets.",
        ],
    }
    (output / "fixture-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Explicit fixture output directory")
    args = parser.parse_args()
    manifest = write_fixture(args.output.resolve())
    print(f"generated {manifest['files']['market.parquet']['row_count']} market rows and {manifest['files']['events.parquet']['row_count']} events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
