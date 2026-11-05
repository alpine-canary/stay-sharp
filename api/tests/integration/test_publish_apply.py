"""Publish apply against DynamoDB Local (T086, FR-024, FR-027, R4, S7).

All-or-nothing per batch: everything is checked before the first write, writes go in
transactions of at most 100 items with each day's items in one transaction, and a rerun after a
failure finishes the job without duplicates. Edits write version n+1 and never touch player
items. Today and past days cannot change. Choice ids are random at the first publish and kept.
"""

from __future__ import annotations

import copy
import datetime as dt
import random
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from botocore.exceptions import ClientError

from staysharp import aws
from staysharp.domain.models import DECKS, DailySet, Question
from staysharp.publish import apply, validate
from staysharp.publish.validate import Authored, Content
from staysharp.store import table as store
from staysharp.tools.content import fixture_choice_id

pytestmark = pytest.mark.integration

VALID = Path(__file__).resolve().parents[1] / "fixtures" / "publish" / "valid"
LAUNCH = dt.date(2026, 11, 1)
BEFORE = dt.date(2026, 11, 30)  # the day before the first scheduled day
NOW = dt.datetime(2026, 11, 30, 9, 0, tzinfo=dt.UTC)


def content() -> Content:
    loaded = validate.load(VALID)
    return Content(
        [Authored(copy.deepcopy(q.data), q.path) for q in loaded.questions],
        [Authored(copy.deepcopy(s.data), s.path) for s in loaded.schedules],
    )


def question(c: Content, qid: str) -> dict[str, Any]:
    return next(q.data for q in c.questions if q.data["id"] == qid)


def schedule(c: Content, level: str) -> dict[str, Any]:
    return next(s.data for s in c.schedules if s.data["level"] == level)


def run(c: Content, *, today: dt.date = BEFORE, seed: int = 1) -> apply.Plan:
    return apply.publish(c, today=today, launch=LAUNCH, now=NOW, rng=random.Random(seed))


def everything(name: str) -> dict[tuple[str, str], dict[str, Any]]:
    items: dict[tuple[str, str], dict[str, Any]] = {}
    start: Any = None
    while True:
        kwargs: dict[str, Any] = {"TableName": name}
        if start:
            kwargs["ExclusiveStartKey"] = start
        page = aws.dynamodb().scan(**kwargs)
        for raw in page["Items"]:
            item = store.deserialize(raw)
            items[(item["PK"], item["SK"])] = item
        start = page.get("LastEvaluatedKey")
        if not start:
            return items


def stored_question(qid: str, version: int) -> Question:
    item = store.get(store.question_key(qid, version))
    assert item is not None
    return Question.model_validate({k: v for k, v in item.items() if k not in ("PK", "SK")})


def stored_set(day: dt.date, level: str) -> DailySet:
    item = store.get(store.daily_key(day, level))  # type: ignore[arg-type]
    assert item is not None
    return DailySet.model_validate({k: v for k, v in item.items() if k not in ("PK", "SK")})


# --- A first publish --------------------------------------------------------------------------


def test_first_publish_writes_questions_sets_pool_and_stock(table: str) -> None:
    plan = run(content())
    items = everything(table)
    kinds = Counter(pk.split("#")[0] for pk, _ in items)
    # 20 scheduled + 1 sample; the unscheduled draft is skipped.
    assert kinds == {"Q": 21, "DAILY": 4, "POOL": 20, "STOCK": 4}
    assert ("Q#sen_fail_draft", "V#1") not in items
    assert plan.skipped_drafts == 1

    senior = stored_set(dt.date(2026, 12, 1), "senior")
    assert senior.game_number == 31
    assert [i.deck for i in senior.items] == list(DECKS["senior"])
    assert [i.target_seconds for i in senior.items] == [60, 45, 45, 20, 30]
    assert all(i.version == 1 for i in senior.items)
    assert senior.published_at is not None
    assert ("POOL#senior#news", "2026-12-02#sen_news_birch") in items
    assert ("STOCK#starter", "2026-12-02") in items


def test_choice_ids_are_random_at_first_publish_and_kept_on_rerun(table: str) -> None:
    run(content(), seed=1)
    first = stored_question("sen_spot_amber", 1)
    ids = [c.id for c in first.choices]
    assert ids != [fixture_choice_id("sen_spot_amber", i) for i in range(4)]
    assert first.choice_order is not None and sorted(first.choice_order) == sorted(ids)

    before = everything(table)
    again = run(content(), seed=2)
    assert again.questions == [] and again.days == []
    assert everything(table) == before


def test_publish_is_refused_whole_and_writes_nothing(table: str) -> None:
    c = content()
    question(c, "sen_spot_amber")["answer"]["lines"] = [99]
    with pytest.raises(apply.Refused) as refused:
        run(c)
    assert any(p.id == "sen_spot_amber" for p in refused.value.problems)
    assert everything(table) == {}


# --- Edits ------------------------------------------------------------------------------------


def test_an_edit_writes_the_next_version_and_never_touches_grades(table: str) -> None:
    run(content())
    grade = {"PK": "P#player", "SK": "ANS#2026-12-01.senior.daily#2", "grade": 1, "qid": "x"}
    aws.dynamodb().put_item(TableName=table, Item=table_serialize(grade))
    v1 = stored_question("sen_fail_birch", 1)

    c = content()
    question(c, "sen_fail_birch")["explanation"] = "A corrected explanation for this fixture."
    question(c, "sen_fail_birch")["change_reason"] = "typo in the explanation"
    plan = run(c)

    assert [(q.qid, q.version) for q in plan.questions] == [("sen_fail_birch", 2)]
    v2 = stored_question("sen_fail_birch", 2)
    assert stored_question("sen_fail_birch", 1) == v1
    assert [c.id for c in v2.choices] == [c.id for c in v1.choices]
    assert v2.answer_choice_id == v1.answer_choice_id
    assert v2.change_reason == "typo in the explanation"
    assert v2.published_at == NOW
    # The future set that uses it now points at version 2.
    assert stored_set(dt.date(2026, 12, 2), "senior").items[2].version == 2
    # Player items are never written by publish.
    item = table_get(table, "P#player", "ANS#2026-12-01.senior.daily#2")
    assert item["grade"] == 1


def test_an_edit_without_a_change_reason_is_refused(table: str) -> None:
    run(content())
    c = content()
    question(c, "sen_fail_birch")["prompt"] = "A new prompt with no reason given for the edit."
    with pytest.raises(apply.Refused) as refused:
        run(c)
    assert [p.id for p in refused.value.problems] == ["sen_fail_birch"]
    assert store.get(store.question_key("sen_fail_birch", 2)) is None


def test_approval_metadata_alone_is_not_a_new_version(table: str) -> None:
    run(content())
    c = content()
    question(c, "sen_fail_birch")["approved_at"] = "2026-11-05T08:00:00Z"
    assert run(c).questions == []


# --- Today and past days ----------------------------------------------------------------------


def _swap_news(c: Content) -> None:
    twin = copy.deepcopy(question(c, "sen_news_birch"))
    twin["id"] = "sen_news_cedar"
    c.questions.append(Authored(twin, "questions/senior/sen_news_cedar.yaml"))
    schedule(c, "senior")["days"]["2026-12-01"][4] = "sen_news_cedar"


def test_today_cannot_change(table: str) -> None:
    run(content())
    c = content()
    _swap_news(c)
    before = everything(table)
    with pytest.raises(apply.Refused) as refused:
        run(c, today=dt.date(2026, 12, 1))
    assert any(
        p.id == "senior 2026-12-01" and "today or a past day" in p.reason
        for p in refused.value.problems
    )
    assert everything(table) == before


def test_a_past_day_never_published_cannot_be_added(table: str) -> None:
    with pytest.raises(apply.Refused) as refused:
        run(content(), today=dt.date(2026, 12, 1))
    assert {p.id for p in refused.value.problems} == {"senior 2026-12-01", "starter 2026-12-01"}


def test_an_unchanged_past_day_is_accepted_and_left_alone(table: str) -> None:
    run(content())
    before = stored_set(dt.date(2026, 12, 1), "senior")
    c = content()
    question(c, "sen_spot_amber")["explanation"] = "Edited after its day: a new version only."
    question(c, "sen_spot_amber")["change_reason"] = "clearer explanation"
    plan = run(c, today=dt.date(2026, 12, 2))
    assert [(q.qid, q.version) for q in plan.questions] == [("sen_spot_amber", 2)]
    assert stored_set(dt.date(2026, 12, 1), "senior") == before  # still version 1


def test_a_future_day_can_change_and_its_old_pool_entry_goes(table: str) -> None:
    run(content())
    c = content()
    _swap_news(c)
    run(c)
    items = everything(table)
    assert ("POOL#senior#news", "2026-12-01#sen_news_cedar") in items
    assert ("POOL#senior#news", "2026-12-01#sen_news_amber") not in items
    assert stored_set(dt.date(2026, 12, 1), "senior").items[4].qid == "sen_news_cedar"


# --- Large batches, failures and fairness -----------------------------------------------------


def big(days: int) -> Content:
    """``days`` days per level, each with five fresh copies of the fixture questions."""
    base = content()
    questions: list[Authored] = []
    schedules: list[Authored] = []
    for s in base.schedules:
        level = s.data["level"]
        first = s.data["days"]["2026-12-01"]
        new_days: dict[str, list[str]] = {}
        for n in range(days):
            day = (dt.date(2026, 12, 1) + dt.timedelta(days=n)).isoformat()
            qids = []
            for qid in first:
                twin = copy.deepcopy(question(base, qid))
                twin["id"] = f"{qid}_n{n:03d}"
                questions.append(Authored(twin, f"{twin['id']}.yaml"))
                qids.append(twin["id"])
            new_days[day] = qids
        schedules.append(Authored({**copy.deepcopy(s.data), "days": new_days}, s.path))
    return Content(questions, schedules)


class Recorder:
    """Wraps the real client: records transaction sizes, can fail the n-th transaction."""

    def __init__(self, real: Any, fail_at: int | None = None) -> None:
        self.real = real
        self.fail_at = fail_at
        self.sizes: list[int] = []

    def transact_write_items(self, **kwargs: Any) -> Any:
        self.sizes.append(len(kwargs["TransactItems"]))
        if self.fail_at is not None and len(self.sizes) == self.fail_at:
            raise ClientError(
                {"Error": {"Code": "InternalServerError", "Message": "injected"}},
                "TransactWriteItems",
            )
        return self.real.transact_write_items(**kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.real, name)


def test_transactions_hold_at_most_100_items_and_never_split_a_day(
    table: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = Recorder(aws.dynamodb())
    monkeypatch.setattr(aws, "dynamodb", lambda: recorder)
    plan = run(big(40))
    assert len(plan.questions) == 400 + 1
    assert max(recorder.sizes) <= 100
    assert sum(recorder.sizes) == 401 + 80 * (1 + 1 + 5)
    # Questions first (5 transactions), then whole days of 7 items each.
    assert recorder.sizes[:5] == [100, 100, 100, 100, 1]
    assert all(size % 7 == 0 for size in recorder.sizes[5:])


def test_a_failed_write_stops_and_a_rerun_finishes_the_job(
    table: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = aws.dynamodb()
    monkeypatch.setattr(aws, "dynamodb", lambda: Recorder(real, fail_at=3))
    with pytest.raises(apply.WriteFailed):
        run(big(30))
    partial = everything(table)
    assert not any(pk.startswith("DAILY#") for pk, _ in partial)  # no set before its questions

    monkeypatch.setattr(aws, "dynamodb", lambda: real)
    run(big(30), seed=7)
    items = everything(table)
    kinds = Counter(pk.split("#")[0] for pk, _ in items)
    assert kinds == {"Q": 301, "DAILY": 60, "POOL": 300, "STOCK": 60}
    # Questions written before the failure kept their first ids (no version 2 from the rerun).
    assert not any(sk == "V#2" for _, sk in items)


def test_correct_positions_are_roughly_uniform(table: str) -> None:
    plan = run(big(40))
    positions = Counter(
        [c.id for c in q.choices].index(q.answer_choice_id) for q in plan.questions
    )
    assert set(positions) == {0, 1, 2, 3}
    assert max(positions.values()) - min(positions.values()) <= 1


# --- Helpers ----------------------------------------------------------------------------------


def table_serialize(item: dict[str, Any]) -> dict[str, Any]:
    return store.serialize(item)


def table_get(name: str, pk: str, sk: str) -> dict[str, Any]:
    del name
    item = store.get(store.key(pk, sk))
    assert item is not None
    return item
