"""The lock switch, and the one contract rule it could break.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from custom_components.tvsitter.coordinator import TvSitterClient
from custom_components.tvsitter.models import StateSnapshot
from custom_components.tvsitter.switch import LockSwitch
from homeassistant.core import HomeAssistant

PREFIX = "tvsitter/salon"


def make_client(hass: HomeAssistant) -> TvSitterClient:
    """Build a client with nothing subscribed; these tests only publish."""
    return TvSitterClient(hass, name="TV Salon", topic_prefix=PREFIX)


def snapshot(*, locked: bool) -> StateSnapshot:
    """Build a state payload of the shape the TV sends."""
    return StateSnapshot.from_payload(
        json.dumps(
            {
                "schema": 1,
                "ts": 1,
                "fw": "0.1.0-m0",
                "screen_on": True,
                "locked": locked,
            }
        )
    )


@pytest.mark.parametrize(
    ("method", "expected"),
    [("async_turn_on", {"op": "lock"}), ("async_turn_off", {"op": "unlock"})],
)
async def test_the_switch_sends_the_command_the_tv_understands(
    hass: HomeAssistant, method: str, expected: dict[str, str]
) -> None:
    """`op` is the discriminator the Kotlin sealed interface is keyed on."""
    switch = LockSwitch(make_client(hass))

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await getattr(switch, method)()

    publish.assert_called_once()
    _hass, topic, payload = publish.call_args.args
    assert topic == f"{PREFIX}/cmd"
    assert json.loads(payload) == expected


async def test_a_command_is_never_retained(hass: HomeAssistant) -> None:
    """The rule that matters most in docs/mqtt-contract.md.

    A retained `lock` would be replayed to the TV after every broker restart, locking a
    television nobody asked to lock — and it would keep doing it.
    """
    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await make_client(hass).async_send({"op": "lock"})

    assert publish.call_args.kwargs["retain"] is False
    assert publish.call_args.kwargs["qos"] == 1


@pytest.mark.parametrize("locked", [True, False])
async def test_the_switch_reads_the_tv_rather_than_its_own_wishes(
    hass: HomeAssistant, locked: bool
) -> None:
    """State comes from the TV's own payload, never from what was last commanded."""
    client = make_client(hass)
    client.snapshot = snapshot(locked=locked)

    assert LockSwitch(client).is_on is locked


async def test_the_switch_admits_it_does_not_know_yet(hass: HomeAssistant) -> None:
    """Before the first payload there is no answer, and `off` would be a guess."""
    assert LockSwitch(make_client(hass)).is_on is None
