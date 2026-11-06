"""Check that the Pydantic models match the API contract (fails CI on drift).

For every object schema in ``components.schemas`` of the contract, the Pydantic model with the
same name in ``staysharp.domain.models`` must expose exactly the same fields (by alias). Schemas
without a model are listed; while ``staysharp.domain.models`` does not exist yet (before task
T025) the check reports that and passes.

Usage: uv run python scripts/gen_models.py [path/to/openapi.yaml [module]]
(the accounts contract: ``... specs/002-accounts/contracts/accounts.openapi.yaml
staysharp.domain.accounts``; names not found there are looked up in ``staysharp.domain.models``)
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONTRACT = (
    Path(__file__).resolve().parents[2] / "specs" / "001-m1-web-app" / "contracts" / "openapi.yaml"
)


def contract_fields(contract: dict[str, Any]) -> dict[str, set[str]]:
    schemas: dict[str, Any] = contract.get("components", {}).get("schemas", {})
    return {
        name: set(schema.get("properties", {}))
        for name, schema in schemas.items()
        if schema.get("type") == "object"
    }


def model_fields(module: Any, name: str) -> set[str] | None:
    model = getattr(module, name, None)
    if model is None or not hasattr(model, "model_fields"):
        return None
    return {field.alias or key for key, field in model.model_fields.items()}


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_CONTRACT
    expected = contract_fields(yaml.safe_load(path.read_text(encoding="utf-8")))
    try:
        base = importlib.import_module("staysharp.domain.models")
    except ModuleNotFoundError:
        print(f"staysharp.domain.models not written yet; {len(expected)} schemas to cover")
        return 0
    module = importlib.import_module(argv[2]) if len(argv) > 2 else base

    drift = 0
    for name, fields in sorted(expected.items()):
        actual = model_fields(module, name)
        if actual is None and module is not base:
            actual = model_fields(base, name)
        if actual is None:
            print(f"missing model: {name}")
            drift += 1
        elif actual != fields:
            print(
                f"drift in {name}: only in contract {sorted(fields - actual)}, "
                f"only in model {sorted(actual - fields)}"
            )
            drift += 1
    print(f"{len(expected)} schemas checked, {drift} with drift")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
