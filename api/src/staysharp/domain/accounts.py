"""Account request and response models (specs/002-accounts/contracts/accounts.openapi.yaml).

Same rules as ``domain/models.py``: strict, camelCase on the wire, and the fields of each model
match the contract schema of the same name (``scripts/gen_models.py``).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from staysharp.domain.models import Strict


class Me(Strict):
    primary_player_id: str
    display_name: str | None = None
    created_at: str


class MeUpdate(Strict):
    display_name: str | None


class Adopt(Strict):
    adult: Literal[True]


class Merged(Strict):
    plays: int = Field(ge=0)
    replays: int = Field(ge=0)


class Adopted(Strict):
    primary_player_id: str
    created: bool
    merged: Merged


class Progress(Strict):
    version: int = Field(ge=0)
    body: dict[str, Any]
