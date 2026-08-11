"""Application adapter for the bounded P8 effect-free run-trace host."""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from typing import Any

from risk_artifacts import (
    ArtifactKind, ArtifactManifest, DataTruthClass, PreviewMode,
    PublicationState, RetentionClass, RightsState, SourceRevision, file_manifest,
)
from risk_experiments import LocalFixtureContextStore, build_effect_free_trace

from artifact_repository import artifact_store, record_payload
from fixture_context_runtime import fixture_store


TRACE_FILE = "run-trace.json"
FIXTURE_DIGEST = "sha256:2b2c347ecafa775853aad88f49b7565263726c17c61850d22e1b789d984761d9"


def run_trace_payload() -> dict[str, Any]:
    records = [
        record_payload(record)
        for record in artifact_store().list()
        if record.manifest.creation_method == "experiment-kernel.effect-free-run-trace"
    ]
    return {
        "traces": records,
        "boundary": {
            "execution": "foreground deterministic trace only",
            "scheduler": "not implemented",
            "labels_accessed": False,
            "metric_calculated": False,
            "external_effects": "disabled",
        },
    }


def create_calibration_run_trace(*, actor: str) -> dict[str, Any]:
    # A trace can only begin from a previously resolved, persisted context.
    context = fixture_store().get(FIXTURE_DIGEST)
    created_at = datetime.now(timezone.utc).replace(microsecond=0)
    trace_id = "fixture-trace-" + hashlib.sha256(
        f"{context.fixture_context_digest}|{actor}|{created_at.isoformat()}".encode()
    ).hexdigest()[:24]
    trace = build_effect_free_trace(context, created_at=created_at, trace_id=trace_id)
    raw = (json.dumps(trace.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode("utf-8")
    file = file_manifest(
        path=TRACE_FILE, content=raw, media_type="application/json",
        role="effect_free_run_trace", preview_mode=PreviewMode.ESCAPED_TEXT,
        download_allowed=False, sensitive=False,
    )
    manifest = ArtifactManifest(
        artifact_id=trace.trace_id,
        title="Calibration fixture · effect-free run trace",
        kind=ArtifactKind.RETAINED_RUN,
        created_at=trace.created_at,
        created_by=actor,
        creation_method="experiment-kernel.effect-free-run-trace",
        run_id=trace.trace_id,
        experiment_id=None,
        data_truth=DataTruthClass.REVIEWED_SYNTHETIC,
        rights=RightsState.INTERNAL,
        rights_policy_id="rights.repository-reviewed-synthetic.v1",
        publication=PublicationState.RESTRICTED,
        retention=RetentionClass.RUN_RETAINED,
        entry_file=TRACE_FILE,
        files=(file,), total_size_bytes=len(raw),
        source_revisions=(
            SourceRevision(kind="fixture_context", source_id="calibration-agent-vs-b0", revision="1.0.0", digest=context.fixture_context_digest),
            SourceRevision(kind="run_trace", source_id=trace.trace_id, revision="1.0.0", digest=trace.trace_digest or ""),
        ),
        approvals=(context.acceptance.reference,),
        restrictions=tuple(sorted(("apparatus_calibration_only", "human_review_required", "no_labels", "no_metric", "no_thesis_inference"))),
        source_manifest_digest=context.sources.manifest_digest,
    )
    record = artifact_store().admit(
        manifest, {TRACE_FILE: raw}, actor=actor,
        rationale="Retained bounded effect-free trace from an already resolved calibration Fixture Context.",
    )
    value = record_payload(record)
    value["trace"] = trace.model_dump(mode="json")
    return value
