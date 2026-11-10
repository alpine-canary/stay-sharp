"""Plain-text e-mail from ``SENDER``: through SMTP when ``SMTP_HOST`` is set, else through SES.

Used by the sign-in code sender and the inactive-account warning. No HTML, no tracking pixel,
no tracked links. Callers never log the address, the subject's variable parts or the body.

SMTP (the mailbox of ``SENDER`` at the mail host, implicit TLS on port 465) is the way out
while the AWS account is in the SES sandbox; its login is a secret, ``{"username", "password"}``,
named by ``SMTP_SECRET_ID`` and read once per Lambda instance.
"""

from __future__ import annotations

import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from functools import cache

from staysharp import aws

SMTP_PORT = 465
SMTP_TIMEOUT = 8  # seconds; the sender functions have 10 (codes) and 300 (jobs)


def send_mail(to: str, subject: str, text: str) -> None:
    if os.environ.get("SMTP_HOST"):
        smtp_send(to, subject, text)
    else:
        ses_send(to, subject, text)


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


@cache
def smtp_login() -> tuple[str, str]:
    secret = aws.secretsmanager().get_secret_value(SecretId=os.environ["SMTP_SECRET_ID"])
    login = json.loads(secret["SecretString"])
    return str(login["username"]), str(login["password"])


def message(to: str, subject: str, text: str) -> EmailMessage:
    sender = os.environ["SENDER"]
    mail = EmailMessage()
    mail["From"] = formataddr(("Stay Sharp", sender))
    mail["To"] = to
    mail["Subject"] = subject
    mail["Date"] = formatdate(usegmt=True)
    mail["Message-ID"] = make_msgid(domain=sender.rpartition("@")[2])
    mail.set_content(text)
    return mail


def smtp_send(to: str, subject: str, text: str) -> None:
    username, password = smtp_login()
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(
        os.environ["SMTP_HOST"], SMTP_PORT, timeout=SMTP_TIMEOUT, context=context
    ) as smtp:
        smtp.login(username, password)
        smtp.send_message(message(to, subject, text))
