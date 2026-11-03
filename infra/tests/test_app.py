from app import STAGES, build_app


def test_app_synthesises_without_credentials() -> None:
    assembly = build_app().synth()
    assert assembly.directory


def test_stages_are_dev_and_prod() -> None:
    assert STAGES == ("dev", "prod")
