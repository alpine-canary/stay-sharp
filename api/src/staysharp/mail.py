"""Plain-text e-mail through SES in the stage's own Region (eu-central-2), from ``SENDER``.

Used by the sign-in code sender and the inactive-account warning. No HTML, no tracking pixel,
no tracked links. Callers never log the address, the subject's variable parts or the body.
"""

from __future__ import annotations

import os

from staysharp import aws


def ses_send(to: str, subject: str, text: str) -> None:
    aws.sesv2().send_email(
        FromEmailAddress=f"Stay Sharp <{os.environ['SENDER']}>",
        Destination={"ToAddresses": [to]},
        Content={
            "Simple": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": text, "Charset": "UTF-8"}},
            }
        },
    )
