from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pydantic import ValidationError
import pytest

from risk_analytics import (
    AssociationEdge,
    PathObservation,
    StudyDirection,
    build_label_study,
)


START = datetime(2015, 1, 1, tzinfo=UTC)


def observations(scope: str, returns: tuple[str, ...]) -> tuple[PathObservation, ...]:
    price = Decimal("100")
    rows = []
    for index, value in enumerate(returns):
        result = Decimal(value)
        price *= Decimal("1") + result
        rows.append(PathObservation(
            scope_id=scope,
            observed_at=START + timedelta(days=index),
            available_at=START + timedelta(days=index, hours=1),
            total_return=result,
            valuation_price=price,
            evidence_id=f"market-{scope}-{index}",
        ))
    return tuple(rows)


def test_study_is_reproducible_proposal_only_and_covers_required_horizons() -> None:
    target = observations("alpha", tuple(["0.002"] * 12 + ["-0.08", "-0.04", "-0.02"] + ["0.01"] * 20))
    peers = target + observations("beta", tuple(["0.001"] * 12 + ["-0.02", "-0.01", "-0.01"] + ["0.004"] * 20))
    parameters = dict(
        unit_id="signal-review-alpha",
        scope_id="alpha",
        signal_time=START + timedelta(days=12),
        direction=StudyDirection.DOWNSIDE,
        dataset_snapshot_id="licensed-crsp-v1",
        retrospective_cutoff=START + timedelta(days=34),
        observations=target,
        peer_observations=peers,
    )
    first = build_label_study(**parameters)
    second = build_label_study(**parameters)

    assert first == second
    assert first.annotation_status == "proposal_only"
    assert first.gold_case_created is False
    assert [item.horizon_sessions for item in first.severity_observations] == [1, 5, 20]
    assert {item.kind.value for item in first.interval_proposals} >= {"punctual", "drawdown"}
    assert first.maximum_adverse_excursion_basis_points > 0
    assert first.group_context.member_count == 2
    assert first.group_context.adverse_breadth == Decimal("1")
    assert all(item.proposal_digest for item in first.interval_proposals)


def test_upside_and_censored_paths_remain_representable() -> None:
    target = observations("alpha", tuple(["0"] * 10 + ["0.12"] + ["0.01"] * 5))
    study = build_label_study(
        unit_id="signal-review-upside",
        scope_id="alpha",
        signal_time=START + timedelta(days=10),
        direction=StudyDirection.UPSIDE,
        dataset_snapshot_id="licensed-crsp-v1",
        retrospective_cutoff=START + timedelta(days=15),
        observations=target,
        peer_observations=target,
    )
    assert study.severity_observations[0].directional_impact_basis_points >= 0
    assert any(item.censored for item in study.interval_proposals)
    assert any(not item.complete_horizon for item in study.severity_observations)


def test_associations_are_explicit_noncausal_edges_and_do_not_merge_paths() -> None:
    target = observations("alpha", tuple(["0"] * 8 + ["-0.1"] + ["0"] * 8))
    edge = AssociationEdge(
        related_unit_id="signal-review-beta",
        edge_type="synchronised_group_move",
        distance_sessions=0,
        direction_agrees=True,
        association_score=Decimal("0.65"),
    )
    study = build_label_study(
        unit_id="signal-review-alpha",
        scope_id="alpha",
        signal_time=START + timedelta(days=8),
        direction=StudyDirection.DOWNSIDE,
        dataset_snapshot_id="licensed-crsp-v1",
        retrospective_cutoff=START + timedelta(days=16),
        observations=target,
        peer_observations=target,
        association_edges=(edge,),
    )
    assert study.association_edges == (edge,)
    assert edge.causal_claim is False
    assert all(item.observed_at <= study.retrospective_cutoff for item in study.path)
    payload = study.model_dump(mode="python")
    payload["path"] = (*payload["path"], {**payload["path"][-1], "observed_at": START + timedelta(days=30)})
    payload.pop("study_digest")
    with pytest.raises(ValidationError, match="retrospective cutoff"):
        type(study).model_validate(payload)
