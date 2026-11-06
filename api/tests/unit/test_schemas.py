"""The packaged progress schema is the contract's, byte for byte (T202)."""

from pathlib import Path

from staysharp.publish import validate

ACCOUNTS = Path(__file__).resolve().parents[3] / "specs" / "002-accounts" / "contracts"


def test_the_packaged_progress_schema_matches_the_contract() -> None:
    name = "progress.schema.json"
    assert validate.schema_text(name) == (ACCOUNTS / name).read_text(encoding="utf-8")
