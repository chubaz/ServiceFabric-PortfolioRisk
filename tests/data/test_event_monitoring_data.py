from datetime import UTC, datetime
from pathlib import Path
import json
import inspect
import os
import socket
import subprocess
import sys

import pytest

from risk_data import (
    CrosswalkRecord,
    CrosswalkSnapshot,
    EntityIdentifier,
    EventDataPlane,
    EventProviderProfile,
    EventQueryRequest,
    LocalEventRecord,
    LocalImportError,
    PublicationRestriction,
    date_effective_mappings_from_crosswalk,
)
from risk_data import cli as risk_data_cli
from risk_domain.monitoring import MonitoringEvidence, MonitoringPolicyVersion
from decimal import Decimal


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "data" / "fixtures" / "synthetic" / "day23"
RETRIEVED_AT = datetime(2026, 7, 1, tzinfo=UTC)


def synthetic_provider() -> EventProviderProfile:
    return EventProviderProfile(
        provider_id="fictional-event-provider",
        display_name="Fictional Event Provider",
        profile="synthetic_local",
        publication_restriction=PublicationRestriction.SYNTHETIC_ONLY,
        synthetic=True,
        private=False,
    )


def preview(plane: EventDataPlane, name: str = "ravenpack-like-events.csv"):
    return plane.preview_event_export(
        (FIXTURES / name).resolve(),
        provider=synthetic_provider(),
        dataset_revision="fictional-event-revision-1",
        mapping_manifest=FIXTURES / f"{name.rsplit('.', 1)[0]}.event-map.json",
        retrieved_at=RETRIEVED_AT,
    )


def confirm(plane: EventDataPlane, item):
    return plane.confirm_event_export(
        item,
        confirm=True,
        preview_digest=item.preview_digest,
        source_digest=item.source.source_digest,
    )


def test_csv_event_preview_confirm_amendment_retraction_and_available_at_query(
    tmp_path: Path,
) -> None:
    plane = EventDataPlane(tmp_path / "event-root")
    item = preview(plane)
    assert item.row_count == 5
    assert any(issue.code == "missing_available_at" for issue in item.issues)
    assert not item.has_blocking_issues

    snapshot = confirm(plane, item)
    states = {record.amendment_state for record in snapshot.records}
    assert states == {"original", "amendment", "retraction"}
    assert all(
        record.supersedes_event_id
        for record in snapshot.records
        if record.amendment_state in {"amendment", "retraction"}
    )
    before = plane.query_events(
        EventQueryRequest(
            snapshot_id=snapshot.snapshot_id,
            as_of=datetime(2026, 6, 29, 10, 6, tzinfo=UTC),
        )
    )
    after = plane.query_events(
        EventQueryRequest(
            snapshot_id=snapshot.snapshot_id,
            as_of=datetime(2026, 7, 1, tzinfo=UTC),
        )
    )
    assert len(before.records) == 1
    assert len(after.records) == 4
    assert any(record.amendment_state == "retraction" for record in after.records)
    assert all(record.available_at <= after.as_of for record in after.records)
    assert any("not substituted" in warning for warning in after.warnings)
    schema_properties = LocalEventRecord.model_json_schema()["properties"]
    assert "local_event_id" in schema_properties
    assert "event_id" not in schema_properties
    assert all("local_event_id" in record.model_dump() for record in snapshot.records)


def test_parquet_event_preview_uses_reviewed_decimal_ranges(tmp_path: Path) -> None:
    item = preview(EventDataPlane(tmp_path / "event-root"), "accern-like-events.parquet")
    assert item.row_count == item.accepted_row_count == 2
    assert not item.issues
    assert all(record.relevance.as_tuple() for record in item.records)
    assert all(record.sentiment.as_tuple() for record in item.records)
    assert all(record.novelty.as_tuple() for record in item.records)


def test_duplicate_source_ids_reject_or_version_deterministically(tmp_path: Path) -> None:
    source = tmp_path / "duplicates.csv"
    header = (FIXTURES / "ravenpack-like-events.csv").read_text(encoding="utf-8").splitlines()[0]
    row = "duplicate-1,fictional-entity-orchid,2026-06-29T09:00:00Z,2026-06-29T09:05:00Z,fictional_notice,0.8,-0.6,0.9,original,,Synthetic fictional text."
    source.write_text(f"{header}\n{row}\n{row}\n", encoding="utf-8")
    plane = EventDataPlane(tmp_path / "event-root")
    rejected = plane.preview_event_export(
        source.resolve(),
        provider=synthetic_provider(),
        dataset_revision="duplicate-revision",
        mapping_manifest=FIXTURES / "ravenpack-like-events.event-map.json",
        retrieved_at=RETRIEVED_AT,
    )
    assert any(
        issue.code == "duplicate_source_event_id" and issue.severity == "blocking"
        for issue in rejected.issues
    )
    with pytest.raises(LocalImportError, match="blocking"):
        confirm(plane, rejected)

    versioned = plane.preview_event_export(
        source.resolve(),
        provider=synthetic_provider(),
        dataset_revision="versioned-revision",
        mapping_manifest=FIXTURES / "accern-like-events.event-map.json",
        retrieved_at=RETRIEVED_AT,
    )
    assert len({record.event_id for record in versioned.records}) == 2
    assert any(
        issue.code == "duplicate_source_event_id_versioned"
        for issue in versioned.issues
    )


def test_private_licensed_event_text_is_redacted_from_default_query_and_public_evidence(
    tmp_path: Path,
) -> None:
    source = tmp_path / "licensed.csv"
    source.write_text(
        (FIXTURES / "ravenpack-like-events.csv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    provider = EventProviderProfile(
        provider_id="fictional-private-provider",
        display_name="Fictional Private Provider",
        profile="licensed_local",
        publication_restriction=PublicationRestriction.NO_PUBLICATION,
        synthetic=False,
        private=True,
    )
    plane = EventDataPlane(tmp_path / "event-root")
    item = plane.preview_event_export(
        source.resolve(),
        provider=provider,
        dataset_revision="private-revision-1",
        mapping_manifest=FIXTURES / "ravenpack-like-events.event-map.json",
        retrieved_at=RETRIEVED_AT,
    )
    snapshot = confirm(plane, item)
    assert any(record.event_text for record in snapshot.records)
    result = plane.query_events(
        EventQueryRequest(
            snapshot_id=snapshot.snapshot_id,
            as_of=datetime(2026, 7, 1, tzinfo=UTC),
        )
    )
    assert all(record.event_text is None for record in result.records)
    assert "Synthetic fictional event text" not in str(snapshot.public_evidence)
    assert any("redacted" in warning for warning in result.warnings)


def test_event_workflow_has_no_network_behavior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def prohibited(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("network attempted")

    monkeypatch.setattr(socket, "socket", prohibited)
    plane = EventDataPlane(tmp_path / "event-root")
    snapshot = confirm(plane, preview(plane))
    assert plane.query_events(
        EventQueryRequest(
            snapshot_id=snapshot.snapshot_id,
            as_of=datetime(2026, 7, 1, tzinfo=UTC),
        )
    ).records


def test_part2_cli_exposes_all_local_commands_and_validates_fixed_policy(
    tmp_path: Path,
) -> None:
    environment = os.environ | {
        "PYTHONPATH": os.pathsep.join(
            (
                str(ROOT),
                str(ROOT / "packages" / "risk_domain" / "src"),
                str(ROOT / "packages" / "risk_data" / "src"),
            )
        )
    }
    help_result = subprocess.run(
        [sys.executable, "-m", "risk_data.cli", "--help"],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    for command in (
        "preview-event-export",
        "confirm-event-export",
        "create-data-context",
        "validate-monitoring-policy",
        "run-monitoring",
        "run-replay",
        "evaluate-replay",
        "render-monitoring-report",
    ):
        assert command in help_result.stdout

    policy = MonitoringPolicyVersion(
        policy_id="fictional-cli-policy",
        version=1,
        daily_percentage_move_threshold=Decimal("0.05"),
        concentration_threshold=Decimal("0.40"),
        event_relevance_minimum=Decimal("0.60"),
        negative_sentiment_threshold=Decimal("-0.50"),
        stale_data_maximum_age_seconds=86400,
        cadence="manual",
        cadence_metadata="Explicit invocation only.",
        reviewed_by="fictional-human-reviewer",
        reviewed_at=RETRIEVED_AT,
        evidence=(
            MonitoringEvidence(
                evidence_id="fictional-cli-evidence",
                reference="fixture://synthetic/cli",
                digest="sha256:" + "5" * 64,
            ),
        ),
    )
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(policy.model_dump(mode="json"), sort_keys=True),
        encoding="utf-8",
    )
    validated = subprocess.run(
        [
            sys.executable,
            "-m",
            "risk_data.cli",
            "validate-monitoring-policy",
            "--policy",
            str(policy_path),
        ],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(validated.stdout)["revision"] == policy.revision


def test_monitoring_cli_execution_paths_use_registered_capabilities() -> None:
    source = inspect.getsource(risk_data_cli.main)
    for capability_id in (
        "portfolio.data_context.create",
        "monitoring.replay",
        "monitoring.evaluate",
        "monitoring.report.render",
    ):
        assert f'"{capability_id}"' in source
    assert "invoke_contextual_monitoring_workflow" in source
    assert "create_portfolio_data_context(request)" not in source
    assert "run_contextual_monitoring(request)" not in source
    assert "evaluate_replay(" not in source
    assert "render_monitoring_report(request)" not in source


def test_part1_crosswalk_adapter_preserves_explicit_dates_primary_rule_and_entities() -> None:
    crosswalk = CrosswalkSnapshot(
        snapshot_id="fictional-crosswalk-snapshot",
        records=(
            CrosswalkRecord(
                source_identifier=EntityIdentifier(
                    entity_id="fictional-company-orchid",
                    identifier_type="gvkey",
                    identifier_value="990001",
                ),
                target_identifier=EntityIdentifier(
                    entity_id="fictional-security-orchid",
                    identifier_type="permno",
                    identifier_value="910001",
                ),
                effective_from=datetime(2020, 1, 1, tzinfo=UTC).date(),
                effective_to=None,
                open_ended=True,
                observed_at=datetime(2020, 1, 1, tzinfo=UTC).date(),
                available_at=datetime(2020, 1, 2, tzinfo=UTC),
                link_type="fictional_link",
                link_primary="P",
            ),
        ),
        overlap_policy="reject",
        source_digest="sha256:" + "6" * 64,
    )
    mappings = date_effective_mappings_from_crosswalk(crosswalk)

    assert mappings[0].source_instrument_id == "fictional-security-orchid"
    assert mappings[0].target_entity_id == "fictional-security-orchid"
    assert mappings[0].fundamental_entity_id == "fictional-company-orchid"
    assert mappings[0].open_ended
    assert mappings[0].reviewed_primary
