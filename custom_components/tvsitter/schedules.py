"""Turning a Home Assistant schedule helper into the windows the television enforces.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from typing import Any

from .const import WIRE_DAYS

# The helper names its days in full and the rules abbreviate them. Both are fixed
# vocabularies, so this is a lookup rather than a guess.
HELPER_DAYS: dict[str, str] = {
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
    "saturday": "sat",
    "sunday": "sun",
}


def windows_from(schedule: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a schedule helper's weekly blocks into rule windows.

    The helper stores blocks per day and the rules store windows carrying the days
    they apply on: the same weekly grid written down twice. Blocks that share their
    hours merge into one window rather than becoming seven near-identical ones — this
    is a rules object somebody reads when a lock surprises them.

    A whole week of the same block comes out with no `days` key at all, which the engine
    reads as every day and is what the rule actually says.

    Nothing is invented. An empty schedule gives an empty list, and an empty list of
    windows is no restriction rather than a closed week (D27).
    """
    days_by_hours: dict[tuple[str, str], list[str]] = {}
    for helper_day, wire_day in HELPER_DAYS.items():
        for block in schedule.get(helper_day) or []:
            hours = span(block)
            if hours is not None:
                days_by_hours.setdefault(hours, []).append(wire_day)

    windows: list[dict[str, Any]] = []
    for (opens, closes), days in days_by_hours.items():
        window: dict[str, Any] = {
            "id": name_for(opens, closes),
            "from": opens,
            "to": closes,
        }
        if len(days) < len(WIRE_DAYS):
            window["days"] = sorted(days, key=WIRE_DAYS.index)
        windows.append(window)
    return sorted(windows, key=lambda w: (w["from"], w["to"]))


def span(block: Any) -> tuple[str, str] | None:
    """Read one block's hours, or nothing when it is not a block.

    Checked rather than trusted: this is another integration's stored data, reached
    through an action, and a malformed entry must drop a block rather than take the
    whole import down with it.
    """
    if not isinstance(block, dict):
        return None
    opens, closes = shorten(block.get("from")), shorten(block.get("to"))
    return None if opens is None or closes is None else (opens, closes)


def shorten(written: Any) -> str | None:
    """`16:00:00` to `16:00`, and a day's end written as midnight back to its start.

    The helper allows a block running to `24:00:00`, which is not a time anything can
    parse — the engine reads windows as wall-clock and works out the wrapping itself,
    so the end of Monday is simply `00:00`.
    """
    if not isinstance(written, str):
        return None
    parts = written.split(":")
    if len(parts) < 2 or not all(part.isdigit() for part in parts[:2]):
        return None
    hour, minute = int(parts[0]), int(parts[1])
    if hour == 24:
        hour = 0
    return f"{hour:02d}:{minute:02d}" if 0 <= hour < 24 and 0 <= minute < 60 else None


def name_for(opens: str, closes: str) -> str:
    """Name the window so `active_window` means something when the lock goes up."""
    return f"{opens}-{closes}".replace(":", "")
