"""The lock switch: the one contract rule it could break, and the one it must not obey.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import mock_restore_cache

from custom_components.tvsitter.coordinator import TvSitterClient
from custom_components.tvsitter.models import StateSnapshot
from custom_components.tvsitter.switch import LockSwitch
from homeassistant.core import HomeAssistant, State

PREFIX = "tvsitter/salon"
ENTITY_ID = "switch.tv_salon_lock"


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


def listening(hass: HomeAssistant, *, locked: bool = False) -> TvSitterClient:
    """Build a client whose TV is switched on and reporting."""
    client = make_client(hass)
    client.snapshot = snapshot(locked=locked)
    client.available = True
    return client


async def attached(hass: HomeAssistant, client: TvSitterClient) -> LockSwitch:
    """Wire a switch to the client, without a real platform behind it."""
    switch = LockSwitch(client)
    switch.hass = hass
    switch.entity_id = ENTITY_ID
    with patch.object(LockSwitch, "async_write_ha_state"):
        await switch.async_added_to_hass()
    return switch


def comes_back(client: TvSitterClient, *, locked: bool = False) -> None:
    """Report in again as the TV, availability topic and all."""
    client.snapshot = snapshot(locked=locked)
    client._handle_availability(
        SimpleNamespace(topic=f"{PREFIX}/availability", payload="online")
    )


@pytest.mark.parametrize(
    ("method", "expected"),
    [("async_turn_on", {"op": "lock"}), ("async_turn_off", {"op": "unlock"})],
)
async def test_the_switch_sends_the_command_the_tv_understands(
    hass: HomeAssistant, method: str, expected: dict[str, str]
) -> None:
    """`op` is the discriminator the Kotlin sealed interface is keyed on."""
    switch = LockSwitch(listening(hass, locked=method == "async_turn_off"))

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
    assert LockSwitch(listening(hass, locked=locked)).is_on is locked


async def test_the_switch_admits_it_does_not_know_yet(hass: HomeAssistant) -> None:
    """Before the first payload there is no answer, and `off` would be a guess."""
    assert LockSwitch(make_client(hass)).is_on is None


async def test_the_switch_stays_operable_while_the_tv_is_off(
    hass: HomeAssistant,
) -> None:
    """Unlike every other entity here, and deliberately (#48).

    The moment a parent most wants this control is the moment the television is off, and
    an unavailable entity is one there is nothing to press.
    """
    client = make_client(hass)
    client.available = False

    assert LockSwitch(client).available is True


async def test_locking_a_television_that_is_off_waits_rather_than_vanishing(
    hass: HomeAssistant,
) -> None:
    """Commands are never retained, so there is nowhere for this to sit but here."""
    client = make_client(hass)
    client.snapshot = snapshot(locked=False)
    client.available = False
    switch = await attached(hass, client)

    with (
        patch("homeassistant.components.mqtt.async_publish") as publish,
        patch.object(LockSwitch, "async_write_ha_state"),
    ):
        await switch.async_turn_on()

    publish.assert_not_called()
    assert switch.is_on is True
    assert switch.extra_state_attributes == {"pending": "on"}


async def test_the_intention_goes_out_the_moment_the_tv_reports_in(
    hass: HomeAssistant,
) -> None:
    """The whole point: the lock lands by itself when the television comes back."""
    client = make_client(hass)
    client.snapshot = snapshot(locked=False)
    client.available = False
    switch = await attached(hass, client)

    with patch.object(LockSwitch, "async_write_ha_state"):
        await switch.async_turn_on()

        with patch("homeassistant.components.mqtt.async_publish") as publish:
            comes_back(client)
            await hass.async_block_till_done()

    publish.assert_called_once()
    assert json.loads(publish.call_args.args[2]) == {"op": "lock"}
    # Cleared as it is sent, not when the TV confirms: after this the TV's own reports
    # are the truth again, and a command it declines cannot be resent for ever.
    assert switch.extra_state_attributes is None


async def test_the_intention_is_sent_once(hass: HomeAssistant) -> None:
    """Every state payload runs the listeners; only the first should send anything."""
    client = make_client(hass)
    client.snapshot = snapshot(locked=False)
    client.available = False
    switch = await attached(hass, client)

    with patch.object(LockSwitch, "async_write_ha_state"):
        await switch.async_turn_on()

        with patch("homeassistant.components.mqtt.async_publish") as publish:
            comes_back(client)
            comes_back(client)
            await hass.async_block_till_done()

    publish.assert_called_once()


async def test_an_intention_the_tv_already_agrees_with_is_not_queued(
    hass: HomeAssistant,
) -> None:
    """A stale unlock is not harmless.

    Arriving at a television that woke up locked by its own budget, it sets the daily
    limit aside for the rest of the day — from a switch nobody moved since last night.
    """
    client = make_client(hass)
    client.snapshot = snapshot(locked=False)
    client.available = False
    switch = await attached(hass, client)

    with (
        patch("homeassistant.components.mqtt.async_publish") as publish,
        patch.object(LockSwitch, "async_write_ha_state"),
    ):
        await switch.async_turn_off()

        comes_back(client)
        await hass.async_block_till_done()

    publish.assert_not_called()
    assert switch.extra_state_attributes is None


async def test_an_intention_survives_a_restart_of_home_assistant(
    hass: HomeAssistant,
) -> None:
    """An update at the wrong moment must not quietly drop a decision about tonight."""
    mock_restore_cache(hass, (State(ENTITY_ID, "on", {"pending": "on"}),))

    client = make_client(hass)
    client.available = False
    switch = await attached(hass, client)

    assert switch.is_on is True
    assert switch.extra_state_attributes == {"pending": "on"}
