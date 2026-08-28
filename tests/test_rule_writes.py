"""Writing rules: the revision, and why one place owns it.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import json
from unittest.mock import patch

from custom_components.tvsitter.button import ClearLimitButton
from custom_components.tvsitter.coordinator import TvSitterClient
from custom_components.tvsitter.models import StateSnapshot
from custom_components.tvsitter.number import DailyLimitNumber
from homeassistant.core import HomeAssistant

PREFIX = "tvsitter/salon"


def make_client(hass: HomeAssistant) -> TvSitterClient:
    """Build a client with nothing subscribed; these tests only publish.

    Marked as listening, because that is what these tests are about. Writing to a
    television that is not is refused on purpose (#90), and has its own tests.
    """
    client = TvSitterClient(hass, name="TV Salon", topic_prefix=PREFIX)
    client.available = True
    return client


def snapshot(**overrides: object) -> StateSnapshot:
    """Build a state payload of the shape the TV sends."""
    payload: dict[str, object] = {
        "schema": 1,
        "ts": 1,
        "fw": "0.4.1",
        "screen_on": True,
        "locked": False,
    }
    payload.update(overrides)
    return StateSnapshot.from_payload(json.dumps(payload))


def revisions(publish: object) -> list[int]:
    """Pull the revision out of every command that went out."""
    return [json.loads(call.args[2])["rev"] for call in publish.call_args_list]


async def test_two_changes_in_a_row_do_not_share_a_revision(
    hass: HomeAssistant,
) -> None:
    """#72. The TV ignores a revision no higher than the one it has.

    A parent moving the limit and then clearing it, both before the TV has had a chance
    to republish, used to compute the same number twice — and the second was dropped on
    arrival with nothing said anywhere.
    """
    client = make_client(hass)
    client.snapshot = snapshot(rules_rev=7)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await DailyLimitNumber(client).async_set_native_value(45)
        await ClearLimitButton(client).async_press()

    assert revisions(publish) == [8, 9]


async def test_a_burst_from_one_control_keeps_climbing(hass: HomeAssistant) -> None:
    """No round trip to wait for, so it cannot be waited for."""
    client = make_client(hass)
    client.snapshot = snapshot(rules_rev=3)
    number = DailyLimitNumber(client)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        for minutes in (30, 45, 60):
            await number.async_set_native_value(minutes)

    assert revisions(publish) == [4, 5, 6]


async def test_the_television_wins_when_it_is_ahead(hass: HomeAssistant) -> None:
    """Something else has been writing rules, or Home Assistant has restarted.

    Carrying on from our own count would send a revision the TV has already passed,
    which it would ignore — the failure this exists to prevent, one step along.
    """
    client = make_client(hass)
    client.snapshot = snapshot(rules_rev=2)
    number = DailyLimitNumber(client)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await number.async_set_native_value(30)
        client.snapshot = snapshot(rules_rev=20)
        await number.async_set_native_value(45)

    assert revisions(publish) == [3, 21]


async def test_a_television_that_has_never_reported_starts_at_one(
    hass: HomeAssistant,
) -> None:
    """Zero would be ignored: it is not higher than the zero a fresh TV holds."""
    client = make_client(hass)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await client.async_set_rules({"daily_limit_s": 600})
        await client.async_set_rules({"daily_limit_s": None})

    assert revisions(publish) == [1, 2]


async def test_clearing_a_limit_names_one_key_and_nothing_else(
    hass: HomeAssistant,
) -> None:
    """set_rules merges, so naming one key with null removes exactly that rule."""
    client = make_client(hass)
    client.snapshot = snapshot(rules_rev=1)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await ClearLimitButton(client).async_press()

    payload = json.loads(publish.call_args.args[2])
    assert payload == {"op": "set_rules", "rev": 2, "rules": {"daily_limit_s": None}}
    assert publish.call_args.kwargs["retain"] is False
    assert publish.call_args.kwargs["qos"] == 1
