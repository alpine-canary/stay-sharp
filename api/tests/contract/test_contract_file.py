"""The contracts themselves must be valid OpenAPI 3.1 documents."""

from pathlib import Path

import pytest
from openapi_spec_validator import OpenAPIV31SpecValidator
from openapi_spec_validator.readers import read_from_filename

from tests.contract.conftest import ACCOUNTS_CONTRACT, CONTRACT


@pytest.mark.parametrize("contract", [CONTRACT, ACCOUNTS_CONTRACT], ids=lambda p: p.name)
def test_contract_is_valid_openapi(contract: Path) -> None:
    spec, _ = read_from_filename(str(contract))
    validator = OpenAPIV31SpecValidator(spec, base_uri=contract.as_uri())
    errors = [f"{list(e.path)}: {e.message}" for e in validator.iter_errors()]
    assert errors == []
