from aws_cdk import cx_api

from app import STAGES

EXPECTED = {
    "staysharp-account",
    "staysharp-edge",
    *(
        f"staysharp-{stage}-{part}"
        for stage in STAGES
        for part in ("ops", "data", "api", "web", "cdn-alarms")
    ),
}
US_EAST_1 = {"staysharp-edge", *(f"staysharp-{stage}-cdn-alarms" for stage in STAGES)}


def test_stages_are_dev_and_prod() -> None:
    assert STAGES == ("dev", "prod")


def test_app_synthesises_every_stack_without_credentials(assembly: cx_api.CloudAssembly) -> None:
    assert {stack.stack_name for stack in assembly.stacks} == EXPECTED


def test_regions(assembly: cx_api.CloudAssembly) -> None:
    for stack in assembly.stacks:
        expected = "us-east-1" if stack.stack_name in US_EAST_1 else "eu-central-2"
        assert stack.environment.region == expected


def test_no_account_id_is_hard_coded(assembly: cx_api.CloudAssembly) -> None:
    import json
    import re

    for stack in assembly.stacks:
        text = json.dumps(stack.template)
        # Whole tokens only: a hex asset hash can hold 12 digits in a row (it did on 2026-11-05).
        ids = set(re.findall(r"(?<![0-9A-Za-z])[0-9]{12}(?![0-9A-Za-z])", text)) - {"000000000000"}
        assert ids == set(), stack.stack_name
