"""Parsing of the payloads described in docs/mqtt-contract.md.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any

from .const import SCHEMA_VERSION


class UnsupportedSchemaError(ValueError):
    """Raised when a payload declares a schema newer than this build understands."""

    def __init__(self, found: int) -> None:
        """Record which schema was found."""
        super().__init__(
            f"payload schema {found} is newer than supported {SCHEMA_VERSION}"
        )
        self.found = found


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    """One `<prefix>/state` payload.

    `remaining_seconds` is None for "no limit", which is a different thing from zero.
    Collapsing the two would turn an unlimited evening into an instant lock.
    """

    ts: int
    firmware: str
    screen_on: bool
    locked: bool
    app_id: str | None = None
    app_name: str | None = None
    used_seconds: int = 0
    limit_seconds: int | None = None
    remaining_seconds: int | None = None
    bonus_seconds: int = 0
    per_app: dict[str, int] = field(default_factory=dict)
    active_window: str | None = None
    rules_rev: int = 0

    @classmethod
    def from_payload(cls, payload: str) -> StateSnapshot:
        """Parse a payload, refusing anything from a newer schema.

        Unknown keys are ignored so that adding a field does not break this reader,
        which is the other half of the same forward-compatibility bargain.
        """
        data: dict[str, Any] = json.loads(payload)
        schema = data.get("schema", SCHEMA_VERSION)
        if isinstance(schema, int) and schema > SCHEMA_VERSION:
            raise UnsupportedSchemaError(schema)

        return cls(
            ts=int(data.get("ts", 0)),
            firmware=str(data.get("fw", "")),
            screen_on=bool(data.get("screen_on", False)),
            locked=bool(data.get("locked", False)),
            app_id=data.get("app_id"),
            app_name=data.get("app_name"),
            used_seconds=int(data.get("used_today_s") or 0),
            limit_seconds=data.get("limit_today_s"),
            remaining_seconds=data.get("remaining_today_s"),
            bonus_seconds=int(data.get("bonus_today_s") or 0),
            per_app=dict(data.get("per_app") or {}),
            active_window=data.get("active_window"),
            rules_rev=int(data.get("rules_rev") or 0),
        )
