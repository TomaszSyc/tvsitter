"""Parsing of the payloads described in docs/mqtt-contract.md.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any

from .const import KIND_MORE_TIME, SCHEMA_VERSION


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
    per_app_names: dict[str, str] = field(default_factory=dict)
    active_window: str | None = None
    lock_reason: str | None = None
    until_seconds: int | None = None
    rules_rev: int = 0
    pin_set: bool = False
    pin_changed_at: int | None = None
    pin_changed_by: str | None = None

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
            per_app_names=dict(data.get("per_app_names") or {}),
            active_window=data.get("active_window"),
            lock_reason=data.get("lock_reason"),
            until_seconds=data.get("until_s"),
            rules_rev=int(data.get("rules_rev") or 0),
            pin_set=bool(data.get("pin_set", False)),
            pin_changed_at=data.get("pin_changed_at"),
            pin_changed_by=data.get("pin_changed_by"),
        )


@dataclass(frozen=True, slots=True)
class TimeRequest:
    """One `<prefix>/request` payload: a child asking for more time.

    Not retained on the wire, so one that arrives while Home Assistant is restarting is
    simply gone. That is the right trade — a retained request would be asked again after
    every broker restart, and a parent would be answering a question from last week.
    """

    id: str
    asked_minutes: int
    kind: str = KIND_MORE_TIME
    app_id: str | None = None
    app_name: str | None = None
    ts: int = 0

    @classmethod
    def from_payload(cls, payload: str) -> TimeRequest:
        """Parse a request, refusing anything from a newer schema.

        An empty `id` is refused rather than tolerated: the id is what an answer is
        addressed to, so a request without one could be granted twice or not at all.
        """
        data: dict[str, Any] = json.loads(payload)
        schema = data.get("schema", SCHEMA_VERSION)
        if isinstance(schema, int) and schema > SCHEMA_VERSION:
            raise UnsupportedSchemaError(schema)

        request_id = str(data.get("id") or "").strip()
        if not request_id:
            raise ValueError("a request without an id cannot be answered")

        return cls(
            id=request_id,
            asked_minutes=int(data.get("asked_minutes") or 0),
            kind=str(data.get("kind") or KIND_MORE_TIME),
            app_id=data.get("app_id"),
            app_name=data.get("app_name"),
            ts=int(data.get("ts") or 0),
        )


@dataclass(frozen=True, slots=True)
class DaySummary:
    """One budget day, closed, as the television describes it on its way out.

    Retained, and only ever the last one: the archive belongs to whoever is
    listening. This
    exists so a sentence can be said about a day that is over — "yesterday: 2 h
    14 of 2 h 30"
    — without a recorder query, and so a Home Assistant that was down at four in
    the morning
    still learns what happened.
    """

    day: str
    used_seconds: int
    limit_seconds: int | None = None
    bonus_seconds: int = 0
    granted_seconds: int = 0
    lock_count: int = 0
    per_app: dict[str, int] = field(default_factory=dict)
    per_app_names: dict[str, str] = field(default_factory=dict)
    requests: dict[str, int] = field(default_factory=dict)
    ts: int = 0

    @classmethod
    def from_payload(cls, payload: str) -> DaySummary:
        """Parse a day summary, refusing anything from a newer schema."""
        data: dict[str, Any] = json.loads(payload)
        schema = data.get("schema", SCHEMA_VERSION)
        if isinstance(schema, int) and schema > SCHEMA_VERSION:
            raise UnsupportedSchemaError(schema)

        day = str(data.get("day") or "").strip()
        if not day:
            raise ValueError("a day summary without a day is about nothing")

        return cls(
            day=day,
            used_seconds=int(data.get("used_s") or 0),
            limit_seconds=data.get("limit_s"),
            bonus_seconds=int(data.get("bonus_s") or 0),
            granted_seconds=int(data.get("granted_s") or 0),
            lock_count=int(data.get("lock_count") or 0),
            per_app=dict(data.get("per_app") or {}),
            per_app_names=dict(data.get("per_app_names") or {}),
            requests=dict(data.get("requests") or {}),
            ts=int(data.get("ts") or 0),
        )


@dataclass(frozen=True, slots=True)
class Alert:
    """Something a parent should hear about, that no state field can carry.

    A counter in retained state rewrites the payload on every wrong keypress and
    still cannot
    say when it happened. This is a moment, so it arrives like a request rather
    than a value.
    """

    id: str
    kind: str
    ts: int = 0
    detail: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: str) -> Alert:
        """Parse an alert, refusing anything from a newer schema."""
        data: dict[str, Any] = json.loads(payload)
        schema = data.get("schema", SCHEMA_VERSION)
        if isinstance(schema, int) and schema > SCHEMA_VERSION:
            raise UnsupportedSchemaError(schema)

        alert_id = str(data.get("id") or "").strip()
        kind = str(data.get("kind") or "").strip()
        if not alert_id or not kind:
            raise ValueError("an alert needs an id and a kind")

        return cls(
            id=alert_id,
            kind=kind,
            ts=int(data.get("ts") or 0),
            detail=dict(data.get("detail") or {}),
        )
