import json
from pathlib import Path

from risk_domain.schema_export import write_schema_snapshot


def test_schema_generation_is_reproducible(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    write_schema_snapshot(generated)
    committed = Path(__file__).resolve().parents[2] / "schemas" / "risk" / "v0.1"

    assert {path.name: path.read_bytes() for path in generated.iterdir()} == {path.name: path.read_bytes() for path in committed.iterdir()}


def test_review_only_schemas_expose_no_order_payload_fields() -> None:
    schema_dir = Path(__file__).resolve().parents[2] / "schemas" / "risk" / "v0.1"
    for filename in ("alert-draft.schema.json", "decision-point.schema.json", "agent-run.schema.json", "risk-finding.schema.json"):
        schema = json.loads((schema_dir / filename).read_text(encoding="utf-8"))
        properties = schema.get("properties", {})
        assert not {"order", "order_payload", "orders"}.intersection(properties)


def test_evidence_required_contracts_encode_non_empty_arrays() -> None:
    schema_dir = Path(__file__).resolve().parents[2] / "schemas" / "risk" / "v0.1"
    required_fields = {
        "news-event.schema.json": ("evidence_references",),
        "risk-finding.schema.json": ("snapshot_references", "evidence_references"),
        "agent-run.schema.json": ("evidence_references",),
    }
    for filename, fields in required_fields.items():
        schema = json.loads((schema_dir / filename).read_text(encoding="utf-8"))
        for field in fields:
            assert schema["properties"][field]["minItems"] == 1
