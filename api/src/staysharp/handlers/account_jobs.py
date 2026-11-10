"""Hourly account job (tasks T233, T243; research A7, A8).

- Finish deletions left ``deleting`` for more than 10 minutes (a request that failed half-way
  and was never retried). Then emit ``StuckAccountDeletions``: those still not finished an hour
  after they were asked. The alarm fires at 1.
- Inactive accounts (FR-120, T243): warn at 23 months, delete at 24 (store/inactive.py), and
  remove sign-ups never confirmed after 7 days, so no unused e-mail address is kept.

Any error is raised after the other accounts were tried: the invocation fails and the error
alarm tells the maintainer.
"""

from __future__ import annotations

import datetime as dt
import os
from collections.abc import Callable
from typing import Any

from staysharp import clock, config
from staysharp.handlers.account_delete import delete_user
from staysharp.mail import send_mail
from staysharp.metrics import emit
from staysharp.obs import account_hash, logger, metrics
from staysharp.store import deletion, inactive

RETRY_AFTER = dt.timedelta(minutes=10)
STUCK_AFTER = dt.timedelta(hours=1)


def finish_deletions(now: dt.datetime, remove_user: deletion.DeleteUser) -> dict[str, int]:
    failures = 0
    finished = 0
    for sub, _since in deletion.stuck(now, RETRY_AFTER):
        try:
            deletion.delete_account(sub, now, remove_user)
            finished += 1
        except Exception as error:  # noqa: BLE001 - try the others, then report
            failures += 1
            logger.warning(
                "deletion still failing",
                extra={"account_hash": account_hash(sub), "error_type": type(error).__name__},
            )
    stuck = len(deletion.stuck(now, STUCK_AFTER))
    emit("StuckAccountDeletions", stuck)
    return {"finished": finished, "failed": failures, "stuck": stuck}


def _fake_on() -> bool:
    return config.stage() == "local" and os.environ.get("FAKE_COGNITO") == "1"


def email_of() -> inactive.EmailOf:
    if _fake_on():
        from testing import fake_cognito

        return fake_cognito.email_of
    return inactive.cognito_email_of(os.environ["USER_POOL_ID"])


def unconfirmed() -> Callable[[], list[tuple[str, dt.datetime]]]:
    if _fake_on():
        return list
    return inactive.cognito_unconfirmed(os.environ["USER_POOL_ID"])


def run() -> dict[str, int]:
    now = clock.now()
    remove_user = delete_user()
    result = finish_deletions(now, remove_user)
    idle = inactive.run(now, send=send_mail, email_of=email_of(), delete_user=remove_user)
    idle["unconfirmed"] = inactive.remove_unconfirmed(now, unconfirmed(), remove_user)
    emit("InactiveAccountsWarned", idle["warned"])
    emit("InactiveAccountsDeleted", idle["deleted"])
    result = {
        **result,
        "inactive_warned": idle["warned"],
        "inactive_deleted": idle["deleted"],
        "inactive_failed": idle["failed"],
        "unconfirmed_removed": idle["unconfirmed"],
    }
    logger.info("account job done", extra=result)
    failures = result["failed"] + result["inactive_failed"]
    if failures:
        raise RuntimeError(f"{failures} account steps still failing")
    return result


@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, int]:
    del event, context
    metrics.set_default_dimensions(Stage=config.stage())
    return run()
