"""The lock switch: the one contract rule it could break, and the one it must not obey.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from datetime import timedelta
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import mock_restore_cache

from custom_components.tvsitter.coordinator import TvSitterClient
from custom_components.tvsitter.models import StateSnapshot
from custom_components.tvsitter.switch import (
    ATTR_PENDING,
    ATTR_PENDING_UNTIL,
    PENDING_UNLOCK_TTL,
    LockSwitch,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

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


async def test_locking_one_that_is_already_locked_is_not_queued(
    hass: HomeAssistant,
) -> None:
    """It is already up, and it cannot go further up."""
    client = make_client(hass)
    client.snapshot = snapshot(locked=True)
    client.available = False
    switch = await attached(hass, client)

    with (
        patch("homeassistant.components.mqtt.async_publish") as publish,
        patch.object(LockSwitch, "async_write_ha_state"),
    ):
        await switch.async_turn_on()

        comes_back(client, locked=True)
        await hass.async_block_till_done()

    publish.assert_not_called()
    assert switch.extra_state_attributes is None


async def test_unlocking_one_that_went_to_sleep_unlocked_is_still_queued(
    hass: HomeAssistant,
) -> None:
    """#89, and the point of the whole deadline.

    A television asleep and unlocked very often wakes up locked, by its own budget or by
    a lock restored from before the reboot. A parent pressing unlock a minute before
    switching it on is asking about that lock, not about the state it went to sleep in.
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

    publish.assert_not_called()
    assert switch.is_on is False
    assert switch.extra_state_attributes[ATTR_PENDING] == "off"
    assert switch.extra_state_attributes[ATTR_PENDING_UNTIL] is not None


async def test_the_waiting_unlock_lands_on_a_television_that_woke_up_locked(
    hass: HomeAssistant,
) -> None:
    """The lock the parent was actually asking about."""
    client = make_client(hass)
    client.snapshot = snapshot(locked=False)
    client.available = False
    switch = await attached(hass, client)

    with patch.object(LockSwitch, "async_write_ha_state"):
        await switch.async_turn_off()

        with patch("homeassistant.components.mqtt.async_publish") as publish:
            comes_back(client, locked=True)
            await hass.async_block_till_done()

    assert json.loads(publish.call_args.args[2]) == {"op": "unlock"}
    assert switch.extra_state_attributes is None


async def test_a_television_that_woke_up_unlocked_is_left_alone(
    hass: HomeAssistant,
) -> None:
    """Sending it anyway sets the daily limit aside for a lock that never appeared."""
    client = make_client(hass)
    client.snapshot = snapshot(locked=False)
    client.available = False
    switch = await attached(hass, client)

    with patch.object(LockSwitch, "async_write_ha_state"):
        await switch.async_turn_off()

        with patch("homeassistant.components.mqtt.async_publish") as publish:
            comes_back(client, locked=False)
            await hass.async_block_till_done()

    publish.assert_not_called()
    assert switch.extra_state_attributes is None


async def test_an_unlock_nobody_followed_through_on_lapses(
    hass: HomeAssistant,
) -> None:
    """The other half of #89.

    One pressed and forgotten last night must not hand over this evening the moment the
    television is switched on.
    """
    client = make_client(hass)
    client.snapshot = snapshot(locked=False)
    client.available = False
    switch = await attached(hass, client)

    with patch.object(LockSwitch, "async_write_ha_state"):
        await switch.async_turn_off()

        later = dt_util.utcnow() + PENDING_UNLOCK_TTL + timedelta(seconds=1)
        with (
            patch("homeassistant.components.mqtt.async_publish") as publish,
            patch(
                "custom_components.tvsitter.switch.dt_util.utcnow", return_value=later
            ),
        ):
            assert switch.extra_state_attributes is None, "and it says so first"
            comes_back(client, locked=True)
            await hass.async_block_till_done()

    publish.assert_not_called()


async def test_a_waiting_lock_never_lapses(hass: HomeAssistant) -> None:
    """The asymmetry is the point: a late lock can be lifted, a late unlock cannot."""
    client = make_client(hass)
    client.snapshot = snapshot(locked=False)
    client.available = False
    switch = await attached(hass, client)

    with patch.object(LockSwitch, "async_write_ha_state"):
        await switch.async_turn_on()

        assert switch.extra_state_attributes == {ATTR_PENDING: "on"}
        later = dt_util.utcnow() + timedelta(days=1)
        with (
            patch("homeassistant.components.mqtt.async_publish") as publish,
            patch(
                "custom_components.tvsitter.switch.dt_util.utcnow", return_value=later
            ),
        ):
            comes_back(client, locked=False)
            await hass.async_block_till_done()

    assert json.loads(publish.call_args.args[2]) == {"op": "lock"}


async def test_a_restored_unlock_without_a_deadline_is_dropped(
    hass: HomeAssistant,
) -> None:
    """From a build that had none. Honouring it for ever is the case being prevented."""
    mock_restore_cache(hass, (State(ENTITY_ID, "off", {"pending": "off"}),))

    client = make_client(hass)
    client.snapshot = snapshot(locked=True)
    client.available = False
    switch = await attached(hass, client)

    assert switch.extra_state_attributes is None
    assert switch.is_on is True, "back to what the TV last said"


async def test_a_restored_unlock_keeps_the_deadline_it_was_given(
    hass: HomeAssistant,
) -> None:
    """A restart in the middle of those fifteen minutes is not a decision to forget."""
    deadline = (dt_util.utcnow() + timedelta(minutes=10)).isoformat()
    mock_restore_cache(
        hass,
        (State(ENTITY_ID, "off", {"pending": "off", "pending_until": deadline}),),
    )

    client = make_client(hass)
    client.snapshot = snapshot(locked=True)
    client.available = False
    switch = await attached(hass, client)

    assert switch.is_on is False
    assert switch.extra_state_attributes[ATTR_PENDING] == "off"


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
