"""Merge an anonymous player id into an account's primary id (task T224, research A4).

Rule (FR-110, FR-112): for each date and level, the first finished daily wins and keeps the
scored slot; the other becomes an unscored replay (or is dropped when that date already has a
replay). Practice attempts and daily practice counts move over. Challenge results recorded
under the anonymous id follow the play, and challenges it created change owner.

Every step is one transaction that puts the new items (only if absent) and deletes the old
ones, so a crash half-way leaves each record either moved or not: running the merge again
finishes the job and a merge that is complete changes nothing.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from botocore.exceptions import ClientError

from staysharp import aws
from staysharp.obs import player_hash
from staysharp.store import plays as plays_store
from staysharp.store import table


@dataclass(frozen=True)
class Merged:
    plays: int
    replays: int


def _items(player_id: str) -> list[dict[str, Any]]:
    return table.query_all(
        {
            "KeyConditionExpression": "PK = :pk",
            "ExpressionAttributeValues": {":pk": {"S": f"P#{player_id}"}},
            "ConsistentRead": True,
        },
        limit=20_000,
    )


def _attributes(item: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in item.items() if k not in ("PK", "SK")}


def _put(key: table.Key, attributes: dict[str, Any]) -> dict[str, Any]:
    return {
        "Put": {
            "TableName": table.table_name(),
            "Item": {**key, **table.serialize(attributes)},
            "ConditionExpression": "attribute_not_exists(PK)",
        }
    }


def _delete(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "Delete": {
            "TableName": table.table_name(),
            "Key": table.key(str(item["PK"]), str(item["SK"])),
        }
    }


def _write(actions: list[dict[str, Any]]) -> bool:
    """``False`` when a put found its target already there (nothing was written)."""
    try:
        aws.dynamodb().transact_write_items(TransactItems=actions)  # type: ignore[arg-type]
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "TransactionCanceledException":
            return False
        raise
    return True


class _Player:
    """One player's plays and answers, read once."""

    def __init__(self, player_id: str, items: list[dict[str, Any]]) -> None:
        self.player_id = player_id
        self.plays: dict[str, dict[str, Any]] = {}
        self.answers: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.practice: list[dict[str, Any]] = []
        self.counts: list[dict[str, Any]] = []
        for item in items:
            sk = str(item["SK"])
            if sk.startswith("PLAY#"):
                self.plays[sk.removeprefix("PLAY#")] = item
            elif sk.startswith("ANS#"):
                play_id = sk.removeprefix("ANS#").rsplit("#", 1)[0]
                self.answers[play_id].append(item)
            elif sk.startswith("PRACOUNT#"):
                self.counts.append(item)
            elif sk.startswith("PRA#"):
                self.practice.append(item)

    def move(self, play_id: str, target: _Player, target_id: str) -> bool:
        """Move a play and its answers under ``target`` as ``target_id``."""
        play = self.plays[play_id]
        mode = target_id.rsplit(".", 1)[1]
        actions = [
            _put(table.play_key(target.player_id, target_id), {**_attributes(play), "mode": mode})
        ]
        moved_answers = []
        for answer in self.answers.get(play_id, []):
            index = int(str(answer["SK"]).rsplit("#", 1)[1])
            moved_answers.append(answer)
            actions.append(
                _put(table.answer_key(target.player_id, target_id, index), _attributes(answer))
            )
        actions.append(_delete(play))
        actions += [_delete(answer) for answer in moved_answers]
        if not _write(actions):
            return False
        target.plays[target_id] = {
            **play,
            "PK": f"P#{target.player_id}",
            "SK": f"PLAY#{target_id}",
            "mode": mode,
        }
        target.answers[target_id] = moved_answers
        del self.plays[play_id]
        self.answers.pop(play_id, None)
        return True

    def drop(self, play_id: str) -> None:
        play = self.plays.pop(play_id)
        answers = self.answers.pop(play_id, [])
        _write([_delete(play)] + [_delete(a) for a in answers])


def _finished(play: dict[str, Any]) -> bool:
    answered = play.get("answered") or set()
    return len(answered) == plays_store.QUESTIONS


def _finished_at(play: dict[str, Any]) -> dt.datetime:
    """When a finished play ended: its start plus its playing time."""
    started = dt.datetime.fromisoformat(str(play["startedAt"]).replace("Z", "+00:00"))
    return started + dt.timedelta(milliseconds=int(play.get("elapsedMs") or 0))


def _keeps_the_slot(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """True when ``a`` is the daily that keeps the scored slot against ``b``.

    A finished daily beats an unfinished one; of two finished, the first to finish wins (FR-110);
    of two unfinished, the one with more answers (then the earlier start) goes on.
    """
    if _finished(a) != _finished(b):
        return _finished(a)
    if _finished(a):
        return _finished_at(a) < _finished_at(b)
    answered_a, answered_b = len(a.get("answered") or ()), len(b.get("answered") or ())
    if answered_a != answered_b:
        return answered_a > answered_b
    return str(a["startedAt"]) < str(b["startedAt"])


def _replay_id(play_id: str) -> str:
    return play_id.removesuffix(".daily") + ".replay"


def _follow_challenges(play: dict[str, Any], old_hash: str, new_hash: str) -> None:
    started_from = play.get("challengeId")
    if started_from:
        old = table.challenge_result_key(started_from, old_hash)
        found = table.get(old, consistent=True)
        if found is not None:
            new = table.challenge_result_key(started_from, new_hash)
            delete = {"Delete": {"TableName": table.table_name(), "Key": old}}
            if not _write([_put(new, _attributes(found)), delete]):
                _write([delete])  # the primary id already has a result there: keep that one
    created = play.get("createdChallengeId")
    if created:
        try:
            aws.dynamodb().update_item(
                TableName=table.table_name(),
                Key=table.challenge_meta_key(created),
                UpdateExpression="SET ownerHash = :new",
                ConditionExpression="ownerHash = :old",
                ExpressionAttributeValues={":new": {"S": new_hash}, ":old": {"S": old_hash}},
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise


def merge(primary_id: str, anonymous_id: str, now: dt.datetime) -> Merged:
    if primary_id == anonymous_id:
        return Merged(plays=0, replays=0)
    source = _Player(anonymous_id, _items(anonymous_id))
    target = _Player(primary_id, _items(primary_id))
    old_hash, new_hash = player_hash(anonymous_id), player_hash(primary_id)
    moved = replays = 0

    # Dailies first: a demoted daily needs the replay slot before an anonymous replay takes it.
    for play_id in sorted(source.plays, key=lambda p: (not p.endswith(".daily"), p)):
        play = source.plays[play_id]
        _follow_challenges(play, old_hash, new_hash)
        if table.expired(play, now):
            source.drop(play_id)
            continue
        moved += 1
        if play_id.endswith(".daily"):
            existing = target.plays.get(play_id)
            if existing is not None and table.expired(existing, now):
                target.drop(play_id)
                existing = None
            if existing is None:
                source.move(play_id, target, play_id)
                continue
            replays += 1
            # The loser steps down to a replay only next to a finished daily: a replay shows the
            # answers, so beside a daily still open it would be an answer key (C3). Otherwise it
            # is dropped.
            if _keeps_the_slot(play, existing):
                if not (_finished(play) and target.move(play_id, target, _replay_id(play_id))):
                    target.drop(play_id)
                source.move(play_id, target, play_id)
                continue
            if not (_finished(existing) and source.move(play_id, target, _replay_id(play_id))):
                source.drop(play_id)
            continue
        if not source.move(play_id, target, play_id):
            replays += 1
            source.drop(play_id)

    for attempt in source.practice:
        sk = str(attempt["SK"])
        delete = _delete(attempt)
        if not _write([_put(table.key(f"P#{primary_id}", sk), _attributes(attempt)), delete]):
            _write([delete])
    for count in source.counts:
        _write(
            [
                {
                    "Update": {
                        "TableName": table.table_name(),
                        "Key": table.key(f"P#{primary_id}", str(count["SK"])),
                        "UpdateExpression": "ADD n :n SET expiresAt = if_not_exists(expiresAt, :e)",
                        "ExpressionAttributeValues": table.serialize(
                            {":n": count.get("n", 0), ":e": count.get("expiresAt", 0)}
                        ),
                    }
                },
                _delete(count),
            ]
        )
    return Merged(plays=moved, replays=replays)
