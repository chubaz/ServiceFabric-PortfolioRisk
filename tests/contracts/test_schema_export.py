from pathlib import Path

from risk_domain.schema_export import write_schema_snapshot


def test_schema_generation_is_reproducible(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    write_schema_snapshot(generated)
    committed = Path(__file__).resolve().parents[2] / "schemas" / "risk" / "v0.1"

    assert {path.name: path.read_bytes() for path in generated.iterdir()} == {path.name: path.read_bytes() for path in committed.iterdir()}
