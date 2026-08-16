from datetime import datetime, timezone

from risk_experiments import (
    AnalysisDefinition, AnalysisSnapshot, ContextRevision, RunClassification,
    rerun_obligations,
)


OLD = "sha256:" + "1" * 64
NEW = "sha256:" + "2" * 64


def _classification(baseline_id: str = "b0") -> RunClassification:
    return RunClassification(
        study_id="thesis-study",
        experiment_id="architecture-comparison",
        fixture_context_digest=OLD,
        case_id="case-20240401",
        baseline_id=baseline_id,
        architecture_reference=f"architecture:{baseline_id}@1.0.0",
        portfolio_mandate_reference="portfolio-mandate:diversified@1.0.0",
        information_regime_reference="information-regime:market-fundamentals-events@1.0.0",
        scenario_reference="scenario:historical-replay@1.0.0",
        evaluation_reference="evaluation:thesis-core@1.0.0",
        repetition=1,
        market_regime_labels=("volatility:high",),
        run_id=f"run-{baseline_id}",
    )


def test_run_classification_has_one_stable_cell_and_keeps_market_labels_outside_it():
    first = _classification()
    second = RunClassification(**{
        **_classification().model_dump(exclude={"classification_digest"}),
        "market_regime_labels": ("volatility:low",),
    })
    assert first.cell_key == second.cell_key
    assert first.classification_digest != second.classification_digest


def test_context_successor_marks_old_cells_for_rerun_without_destroying_old_evidence():
    revision = ContextRevision(
        fixture_context_digest=NEW,
        supersedes_context_digest=OLD,
        changed_dimensions=("information_regime",),
        recorded_at=datetime.now(timezone.utc),
    )
    obligations = rerun_obligations(revision, (_classification("b0"), _classification("b1")))
    assert len(obligations) == 2
    assert {item.reason for item in obligations} == {"context_superseded"}
    assert all(item.status == "required" for item in obligations)


def test_analysis_snapshot_is_immutable_and_reports_partial_coverage():
    analysis = AnalysisDefinition(
        analysis_id="b1-v-b0",
        study_id="thesis-study",
        experiment_id="architecture-comparison",
        name="B1 versus B0",
        analysis_kind="paired_comparison",
        baseline_id="b0",
        treatment_ids=("b1",),
        changed_dimensions=("architecture",),
        outcome_references=("metric:detection-quality@1.0.0",),
        missingness_rule="Report missing paired cases; do not silently drop them.",
    )
    snapshot = AnalysisSnapshot(
        analysis_digest=analysis.analysis_digest,
        fixture_context_digest=OLD,
        run_ids=("run-b0",),
        evaluation_references=("evaluation:thesis-core@1.0.0",),
        status="partial",
        missing_cell_keys=(_classification("b1").cell_key,),
    )
    assert snapshot.snapshot_digest.startswith("sha256:")
