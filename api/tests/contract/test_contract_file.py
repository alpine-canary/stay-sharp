"""The contract itself must be a valid OpenAPI 3.1 document."""

from openapi_spec_validator import OpenAPIV31SpecValidator
from openapi_spec_validator.readers import read_from_filename

from tests.contract.conftest import CONTRACT


def test_contract_is_valid_openapi() -> None:
    spec, _ = read_from_filename(str(CONTRACT))
    errors = [f"{list(e.path)}: {e.message}" for e in OpenAPIV31SpecValidator(spec).iter_errors()]
    assert errors == []
