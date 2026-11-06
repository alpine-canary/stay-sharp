"""Hourly account job (tasks T233, T243; research A7, A8).

- Finish deletions left ``deleting`` for more than 10 minutes (a request that failed half-way
  and was never retried). Then emit ``StuckAccountDeletions``: those still not finished an hour
  after they were asked. The alarm fires at 1.
- Inactive accounts (FR-120) come with task T243.

Any error is raised after the other accounts were tried: the invocation fails and the error
alarm tells the maintainer.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from staysharp import clock, config
from staysharp.handlers.account_delete import delete_user
from staysharp.metrics import emit
from staysharp.obs import account_hash, logger, metrics
from staysharp.store import deletion

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


def run() -> dict[str, int]:
    result = finish_deletions(clock.now(), delete_user())
    logger.info("account job done", extra=result)
    if result["failed"]:
        raise RuntimeError(f"{result['failed']} account deletions still failing")
    return result


@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, int]:
    del event, context
    metrics.set_default_dimensions(Stage=config.stage())
    return run()
