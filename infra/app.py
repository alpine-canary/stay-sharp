"""Stay Sharp CDK app.

Stages ``dev`` and ``prod`` live in one AWS account dedicated to the project (constitution 1.0.1).
The account is never written here: it comes from the SSO profile at deploy time
(``CDK_DEFAULT_ACCOUNT``). Stacks are added from Phase 2 on (tasks T018 to T045).
"""

import aws_cdk as cdk

REGION = "eu-central-2"
EDGE_REGION = "us-east-1"
STAGES = ("dev", "prod")


def build_app() -> cdk.App:
    app = cdk.App()
    cdk.Tags.of(app).add("project", "stay-sharp")
    return app


if __name__ == "__main__":
    build_app().synth()
