from aws_cdk import cx_api

from app import STAGES

EXPECTED = {
    "staysharp-account",
    "staysharp-edge",
    *(f"staysharp-{stage}-{part}" for stage in STAGES for part in ("ops", "data", "api", "web")),
}


def test_stages_are_dev_and_prod() -> None:
    assert STAGES == ("dev", "prod")


def test_app_synthesises_every_stack_without_credentials(assembly: cx_api.CloudAssembly) -> None:
    assert {stack.stack_name for stack in assembly.stacks} == EXPECTED


def test_regions(assembly: cx_api.CloudAssembly) -> None:
    for stack in assembly.stacks:
        expected = "us-east-1" if stack.stack_name == "staysharp-edge" else "eu-central-2"
        assert stack.environment.region == expected


def test_no_account_id_is_hard_coded(assembly: cx_api.CloudAssembly) -> None:
    import json
    import re

    for stack in assembly.stacks:
        text = json.dumps(stack.template)
        ids = set(re.findall(r"(?<![0-9])[0-9]{12}(?![0-9])", text)) - {"000000000000"}
        assert ids == set(), stack.stack_name
