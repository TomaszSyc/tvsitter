"""Lifting the limit.

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
from homeassistant.core import HomeAssistant

PREFIX = "tvsitter/salon"


def make_client(hass: HomeAssistant) -> TvSitterClient:
    """Build a client with nothing subscribed; these tests only publish."""
    return TvSitterClient(hass, name="TV Salon", topic_prefix=PREFIX)


def snapshot(**overrides: object) -> StateSnapshot:
    """Build a state payload of the shape the TV sends."""
    payload: dict[str, object] = {
        "schema": 1,
        "ts": 1,
        "fw": "0.2.0",
        "screen_on": True,
        "locked": False,
    }
    payload.update(overrides)
    return StateSnapshot.from_payload(json.dumps(payload))


async def test_pressing_it_names_the_limit_and_nothing_else(
    hass: HomeAssistant,
) -> None:
    """Null removes exactly one rule.

    Sending the whole rules object would mean knowing every rule in force, which this
    cannot; sending an empty object would change nothing, because set_rules merges.
    """
    client = make_client(hass)
    client.snapshot = snapshot(limit_today_s=1800, rules_rev=4)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await ClearLimitButton(client).async_press()

    _hass, topic, payload = publish.call_args.args
    assert topic == f"{PREFIX}/cmd"
    assert json.loads(payload) == {
        "op": "set_rules",
        "rev": 5,
        "rules": {"daily_limit_s": None},
    }


async def test_it_does_not_send_an_empty_rules_object(hass: HomeAssistant) -> None:
    """The trap this button was written to avoid.

    Under merge semantics an empty object is a no-op, so a button that sent one would
    look like it worked and change nothing.
    """
    client = make_client(hass)
    client.snapshot = snapshot(limit_today_s=1800, rules_rev=1)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await ClearLimitButton(client).async_press()

    assert json.loads(publish.call_args.args[2])["rules"] != {}


async def test_the_revision_moves_so_the_tv_does_not_ignore_it(
    hass: HomeAssistant,
) -> None:
    """The TV refuses a revision it has already seen, so this has to be higher."""
    client = make_client(hass)
    client.snapshot = snapshot(rules_rev=12)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await ClearLimitButton(client).async_press()

    assert json.loads(publish.call_args.args[2])["rev"] == 13


async def test_clearing_is_never_retained(hass: HomeAssistant) -> None:
    """A retained rules change would be replayed after every broker restart."""
    client = make_client(hass)
    client.snapshot = snapshot()

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await ClearLimitButton(client).async_press()

    assert publish.call_args.kwargs["retain"] is False
