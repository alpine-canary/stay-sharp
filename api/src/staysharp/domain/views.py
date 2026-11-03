"""The only way a question leaves the server before it is answered (research R1, FR-003).

Built from an explicit allowlist: a field that is not copied here cannot reach the browser, even
if it is added to the stored item later. Field names follow ``QuestionView`` in the contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

VIEW_FIELDS = (
    "index",
    "deck",
    "prompt",
    "code",
    "language",
    "choices",
    "targetSeconds",
    "servedAt",
)


def question_view(
    question: Mapping[str, Any],
    *,
    index: int,
    served_at: str,
    target_seconds: int | None,
) -> dict[str, Any]:
    """Return what the browser may see. ``target_seconds`` is ``None`` for a relaxed play."""
    choices = question.get("choices")
    if not isinstance(choices, list) or len(choices) != 4:
        raise ValueError("a question must have exactly 4 choices")

    view: dict[str, Any] = {
        "index": index,
        "deck": str(question["deck"]),
        "prompt": str(question["prompt"]),
    }
    if question.get("code"):
        view["code"] = str(question["code"])
        if question.get("language"):
            view["language"] = str(question["language"])
    view["choices"] = [{"id": str(c["id"]), "text": str(c["text"])} for c in choices]
    if target_seconds is not None:
        view["targetSeconds"] = int(target_seconds)
    view["servedAt"] = served_at
    return view
