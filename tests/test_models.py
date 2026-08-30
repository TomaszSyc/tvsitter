"""Payload parsing for the TV Sitter integration.

Mirrors the Kotlin contract tests: the same invariants have to hold on both sides of
the wire, and null-versus-zero is the one most likely to be lost in a rewrite.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import json

import pytest

from custom_components.tvsitter.const import SCHEMA_VERSION
from custom_components.tvsitter.models import StateSnapshot, UnsupportedSchemaError

# Captured from the real device, so these break if either side drifts from the other.
LIVE_PAYLOAD = json.dumps(
    {
        "schema": 1,
        "ts": 1787337982571,
        "fw": "0.1.0-m0",
        "screen_on": True,
        "locked": False,
        "app_id": "com.google.android.apps.tv.launcherx",
        "app_name": "Google TV",
        "used_today_s": 0,
        "remaining_today_s": None,
        "bonus_today_s": 0,
        "per_app": {},
        "active_window": None,
        "rules_rev": 0,
    }
)


def test_parses_a_payload_captured_from_the_device() -> None:
    """The real thing off the wire has to parse field for field."""
    snapshot = StateSnapshot.from_payload(LIVE_PAYLOAD)

    assert snapshot.screen_on is True
    assert snapshot.locked is False
    assert snapshot.app_id == "com.google.android.apps.tv.launcherx"
    assert snapshot.app_name == "Google TV"
    assert snapshot.firmware == "0.1.0-m0"
    assert snapshot.ts == 1787337982571


def test_no_limit_stays_none_and_does_not_become_zero() -> None:
    """Collapsing these two turns an unlimited evening into an instant lock."""
    unlimited = StateSnapshot.from_payload(LIVE_PAYLOAD)
    assert unlimited.remaining_seconds is None

    limited = StateSnapshot.from_payload(
        json.dumps({"ts": 1, "fw": "x", "remaining_today_s": 0})
    )
    assert limited.remaining_seconds == 0


def test_a_newer_schema_is_refused_rather_than_guessed() -> None:
    """Past a schema bump the meaning of existing fields cannot be assumed."""
    payload = json.dumps({"schema": SCHEMA_VERSION + 1, "ts": 1, "fw": "x"})

    with pytest.raises(UnsupportedSchemaError) as raised:
        StateSnapshot.from_payload(payload)

    assert raised.value.found == SCHEMA_VERSION + 1


def test_an_added_field_does_not_break_this_reader() -> None:
    """The other half of the forward-compatibility bargain: unknown keys are ignored."""
    payload = json.dumps(
        {"schema": SCHEMA_VERSION, "ts": 1, "fw": "x", "something_new": 42}
    )

    assert StateSnapshot.from_payload(payload).ts == 1


def test_a_payload_without_a_schema_is_read_as_the_current_one() -> None:
    """An old sender or a hand-written test message means what it says today."""
    snapshot = StateSnapshot.from_payload(
        json.dumps({"ts": 1, "fw": "x", "locked": True})
    )
    assert snapshot.locked is True


def test_missing_counters_default_to_zero_not_to_none() -> None:
    """Counters are totals; absent means nothing has accrued, which is zero."""
    snapshot = StateSnapshot.from_payload(json.dumps({"ts": 1, "fw": "x"}))

    assert snapshot.used_seconds == 0
    assert snapshot.bonus_seconds == 0
    assert snapshot.per_app == {}
    assert snapshot.rules_rev == 0
    # A payload from a TV that predates the PIN reads as having none, not as unknown.
    assert snapshot.pin_set is False
    assert snapshot.pin_changed_at is None
    assert snapshot.pin_changed_by is None


def test_explicit_nulls_in_counters_are_tolerated() -> None:
    """A sender writing null rather than omitting a key must not crash a reader."""
    payload = json.dumps(
        {"ts": 1, "fw": "x", "used_today_s": None, "per_app": None, "rules_rev": None}
    )
    snapshot = StateSnapshot.from_payload(payload)

    assert snapshot.used_seconds == 0
    assert snapshot.per_app == {}


def test_the_pin_fields_are_read_without_the_pin_itself() -> None:
    """What crosses is that a PIN exists, when it changed and where — never the hash."""
    payload = json.dumps(
        {
            "ts": 1,
            "fw": "x",
            "pin_set": True,
            "pin_changed_at": 1787400000000,
            "pin_changed_by": "tv",
        }
    )
    snapshot = StateSnapshot.from_payload(payload)

    assert snapshot.pin_set is True
    assert snapshot.pin_changed_at == 1787400000000
    assert snapshot.pin_changed_by == "tv"


def test_rubbish_is_rejected_loudly() -> None:
    """Anything undecodable has to raise, so the caller can log and move on."""
    with pytest.raises(ValueError):
        StateSnapshot.from_payload("not json at all")


def test_the_exempt_packages_come_through_as_a_tuple() -> None:
    """#130. A frozen dataclass holding a list is frozen in name only."""
    snapshot = StateSnapshot.from_payload(
        json.dumps(
            {
                "schema": 1,
                "ts": 1,
                "exempt_apps": ["app.tvsitter.tv", "com.google.android.tvlauncher"],
            }
        )
    )

    assert snapshot.exempt_apps == ("app.tvsitter.tv", "com.google.android.tvlauncher")


def test_a_television_that_says_nothing_exempts_nothing() -> None:
    """An older build sends no such key: "none known" rather than a promise."""
    snapshot = StateSnapshot.from_payload(json.dumps({"schema": 1, "ts": 1}))

    assert snapshot.exempt_apps == ()
