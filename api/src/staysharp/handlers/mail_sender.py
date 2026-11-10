"""Cognito's custom e-mail sender: sign-in codes leave from Zurich (research A2).

A user pool in eu-central-2 may only send through SES in Frankfurt or London. To keep every
e-mail address and code in Switzerland, Cognito hands each code, encrypted with the stage's KMS
key, to this function in eu-central-2, which decrypts it and sends it from
``stay-sharp@lumineth.com`` (infra/stacks/auth_stack.py): with SES in eu-central-2, or through
the mailbox's SMTP server while the account is in the SES sandbox (staysharp.mail).

Only the trigger source is logged: never the address, the code or the encrypted code. At most
5 codes an hour and 10 a day go to one address, 300 an hour in all (store/mail_limits.py).
"""

from __future__ import annotations

import base64
import logging
import os
from collections.abc import Callable
from functools import cache
from typing import Any

from staysharp import clock
from staysharp.mail import send_mail
from staysharp.obs import logger
from staysharp.store import mail_limits

SUBJECT = "Your Stay Sharp code"
# Sources that carry a code we send. Cognito also calls for password resets, invitations and
# take-over notices, which this pool never uses (no password, no admin-created users).
CODE_SOURCES = frozenset(
    {
        "CustomEmailSender_SignUp",
        "CustomEmailSender_ResendCode",
        "CustomEmailSender_Authentication",
        "CustomEmailSender_UpdateUserAttribute",
        "CustomEmailSender_VerifyUserAttribute",
    }
)

# The Encryption SDK logs each decryption at INFO; keep only its warnings.
logging.getLogger("aws_encryption_sdk").setLevel(logging.WARNING)


class SendFailed(Exception):
    """Sending failed. Carries no message: AWS errors can quote the address."""


Decrypt = Callable[[str], str]
Send = Callable[[str, str, str], None]


def body(code: str) -> str:
    return (
        f"Your Stay Sharp code is {code}.\n\n"
        "Type it on the page where you asked for it.\n\n"
        "If you did not ask for a code, you can ignore this e-mail.\n"
    )


@cache
def kms_decrypt() -> Decrypt:
    """The Encryption SDK, bound to the stage's key (only this function ships it)."""
    import aws_encryption_sdk  # type: ignore[import-untyped]  # noqa: PLC0415 - mailer only
    from aws_encryption_sdk.identifiers import (  # type: ignore[import-untyped]  # noqa: PLC0415
        CommitmentPolicy,
    )

    client = aws_encryption_sdk.EncryptionSDKClient(
        commitment_policy=CommitmentPolicy.REQUIRE_ENCRYPT_ALLOW_DECRYPT
    )
    provider = aws_encryption_sdk.StrictAwsKmsMasterKeyProvider(key_ids=[os.environ["KEY_ARN"]])

    def decrypt(encrypted: str) -> str:
        plaintext, _ = client.decrypt(source=base64.b64decode(encrypted), key_provider=provider)
        return bytes(plaintext).decode()

    return decrypt


def _no_limit(_address: str) -> bool:
    return True


def send_code(
    event: dict[str, Any], decrypt: Decrypt, send: Send, allow: Callable[[str], bool] = _no_limit
) -> bool:
    """Send the code of one Cognito event. ``False`` when there is nothing to send, or when the
    address or the whole service is over its limit (store/mail_limits.py)."""
    source = str(event.get("triggerSource", ""))
    request = event.get("request") or {}
    encrypted = request.get("code")
    email = (request.get("userAttributes") or {}).get("email")
    if source not in CODE_SOURCES or not encrypted or not email:
        logger.info("sign-in e-mail skipped", extra={"trigger_source": source})
        return False
    if not allow(email):
        # Not raised: Cognito would retry. The player can ask for a new code later.
        logger.warning("sign-in e-mail limited", extra={"trigger_source": source})
        return False
    try:
        send(email, SUBJECT, body(decrypt(encrypted)))
    except Exception as error:
        # Logged and raised without the AWS message, which can quote the address. Cognito then
        # answers the player with an error and they can ask for a new code.
        logger.error(
            "sign-in e-mail failed",
            extra={"trigger_source": source, "error_type": type(error).__name__},
        )
        raise SendFailed from None
    logger.info("sign-in e-mail sent", extra={"trigger_source": source})
    return True


@logger.inject_lambda_context(log_event=False, clear_state=True)
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:  # noqa: ARG001
    logger.remove_keys(["function_arn"])
    send_code(
        event, kms_decrypt(), send_mail, lambda address: mail_limits.allow(address, clock.now())
    )
    return event
