"""Package the API for Lambda (Python 3.13, arm64) with uv, without Docker.

The asset is the ``api/`` folder. Runtime dependencies come from ``api/uv.lock`` (``uv export
--no-dev``) as arm64 manylinux wheels; then the ``staysharp`` package is copied without the
laptop-only ``tools`` folder. Tests skip bundling (context ``aws:cdk:bundling-stacks = []``).
"""

from __future__ import annotations

import shutil
import subprocess  # noqa: S404 - runs uv on files of this repository
import tempfile
from pathlib import Path

import jsii
from aws_cdk import BundlingOptions, DockerImage, ILocalBundling
from aws_cdk import aws_lambda as lambda_

API_DIR = Path(__file__).resolve().parents[2] / "api"
PLATFORM = "aarch64-manylinux_2_28"
# Not shipped to Lambda: laptop tools and caches. The prod asset must also never contain the
# fault-injection module (research R10, W11); it lives outside src/ in api/testing/.
EXCLUDE = shutil.ignore_patterns("__pycache__", "*.pyc", "tools")


@jsii.implements(ILocalBundling)
class UvBundling:
    def try_bundle(self, output_dir: str, *, image: DockerImage, **_: object) -> bool:
        del image
        with tempfile.TemporaryDirectory() as tmp:
            requirements = Path(tmp) / "requirements.txt"
            subprocess.run(  # noqa: S603
                [  # noqa: S607
                    "uv",
                    "export",
                    "--directory",
                    str(API_DIR),
                    "--no-dev",
                    "--no-hashes",
                    "--frozen",
                    "--no-emit-project",
                    "--output-file",
                    str(requirements),
                ],
                check=True,
                capture_output=True,
            )
            subprocess.run(  # noqa: S603
                [  # noqa: S607
                    "uv",
                    "pip",
                    "install",
                    "--requirements",
                    str(requirements),
                    "--target",
                    output_dir,
                    "--python-platform",
                    PLATFORM,
                    "--python-version",
                    "3.13",
                    "--only-binary",
                    ":all:",
                    "--quiet",
                ],
                check=True,
            )
        shutil.copytree(
            API_DIR / "src" / "staysharp",
            Path(output_dir) / "staysharp",
            ignore=EXCLUDE,
            dirs_exist_ok=True,
        )
        return True


def api_code() -> lambda_.Code:
    return lambda_.Code.from_asset(
        str(API_DIR),
        exclude=[".venv", "tests", "**/__pycache__", "dist", ".mypy_cache", ".ruff_cache"],
        bundling=BundlingOptions(
            image=lambda_.Runtime.PYTHON_3_13.bundling_image,
            local=UvBundling(),
            command=["bash", "-c", "echo 'local bundling with uv is required' && exit 1"],
        ),
    )
