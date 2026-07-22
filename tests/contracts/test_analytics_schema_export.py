import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "risk_analytics" / "src"))

from risk_analytics.schema_export import write_schema_snapshot


def test_analytics_schema_generation_is_reproducible(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    write_schema_snapshot(generated)
    committed = ROOT / "schemas" / "risk" / "analytics" / "v0.1"
    assert {path.name: path.read_bytes() for path in generated.iterdir()} == {
        path.name: path.read_bytes() for path in committed.iterdir()
    }


def test_analytics_schemas_have_no_advice_optimization_or_effect_fields() -> None:
    schema_dir = ROOT / "schemas" / "risk" / "analytics" / "v0.1"
    prohibited = {"advice", "optimization", "recommendation", "effect", "effects", "order", "trade", "rebalance", "hedge"}
    for path in schema_dir.glob("*.schema.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        names: set[str] = set()

        def collect(value: object) -> None:
            if isinstance(value, dict):
                properties = value.get("properties")
                if isinstance(properties, dict):
                    names.update(properties)
                for item in value.values():
                    collect(item)
            elif isinstance(value, list):
                for item in value:
                    collect(item)

        collect(schema)
        assert not prohibited.intersection(names), path.name
