"""The parent PIN: hashed here, verified on the TV, never on the wire in the clear.

One file rather than one per platform, unlike the other entity tests, because the
property worth protecting spans all of them: a text entity that holds nothing, a button
that removes what it cannot read, and a sensor that reports that a PIN exists without
reporting the PIN.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from custom_components.tvsitter.binary_sensor import ParentPinSetSensor
from custom_components.tvsitter.button import ClearPinButton
from custom_components.tvsitter.coordinator import TvSitterClient
from custom_components.tvsitter.models import StateSnapshot
from custom_components.tvsitter.parent_pin import hash_pin, is_plausible
from custom_components.tvsitter.text import ParentPinText
from homeassistant.components.text import TextMode
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

PREFIX = "tvsitter/salon"
PIN = "482913"
SALT = "0f1e2d3c4b5a69788796a5b4c3d2e1f0"


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


def test_the_hash_agrees_with_what_the_tv_computes() -> None:
    """The vector pinned on both sides, and the only thing that checks they agree.

    Kotlin derives this with `SecretKeyFactory`, Python with `hashlib`. Nothing else in
    either half would notice the two drifting apart, and the symptom would be a parent
    typing the right PIN into a television that refuses it.
    """
    assert hash_pin(PIN, SALT, iterations=1000)["hash"] == (
        "8de25825f30eff014f53eb11cb0ac52aceadce257d18fac740e3342a13e87ef3"
    )
    assert hash_pin(PIN, SALT, iterations=120_000)["hash"] == (
        "9734df1754755f353cb4f019e4eaaf441b1cc2b826fd45f7f378469e791cb8d0"
    )


def test_the_parameters_travel_with_the_digest() -> None:
    """So the iteration count can be raised without invalidating a PIN in use."""
    hashed = hash_pin(PIN, SALT, iterations=1000)

    assert hashed == {
        "iterations": 1000,
        "salt": SALT,
        "hash": hashed["hash"],
    }


def test_each_pin_gets_its_own_salt() -> None:
    """Two households with the same PIN must not share a hash."""
    first = hash_pin(PIN)
    second = hash_pin(PIN)

    assert len(first["salt"]) == 32
    assert first["salt"] != second["salt"]
    assert first["hash"] != second["hash"]


@pytest.mark.parametrize(
    ("pin", "usable"),
    [
        ("1234", True),
        ("12345678", True),
        ("123", False),
        ("123456789", False),
        ("12a4", False),
        ("", False),
        # Digits by str.isdigit(), but no remote produces them and the TV keypad cannot.
        ("١٢٣٤", False),
    ],
)
def test_only_a_pin_that_could_be_typed_is_accepted(pin: str, usable: bool) -> None:
    """The same range the keypad on the TV enforces."""
    assert is_plausible(pin) is usable


async def test_setting_the_pin_sends_a_hash_and_never_the_pin(
    hass: HomeAssistant,
) -> None:
    """The whole point of hashing here rather than on the TV."""
    client = make_client(hass)
    client.snapshot = snapshot()

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await ParentPinText(client).async_set_value(PIN)

    _hass, topic, payload = publish.call_args.args
    assert topic == f"{PREFIX}/cmd"
    assert PIN not in payload
    sent = json.loads(payload)
    assert sent["op"] == "set_pin"
    assert set(sent["hash"]) == {"iterations", "salt", "hash"}
    assert sent["hash"]["hash"] != PIN


async def test_the_pin_is_never_retained(hass: HomeAssistant) -> None:
    """A retained set_pin would be replayed after every broker restart.

    Which would put the old PIN back over the top of one changed at the television,
    every time the broker bounced — silently, and with nothing to explain it.
    """
    client = make_client(hass)
    client.snapshot = snapshot()

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await ParentPinText(client).async_set_value(PIN)

    assert publish.call_args.kwargs["retain"] is False
    assert publish.call_args.kwargs["qos"] == 1


async def test_the_entity_holds_nothing(hass: HomeAssistant) -> None:
    """Write-only, so the PIN is never in the state machine or the recorder."""
    entity = ParentPinText(make_client(hass))

    assert entity.native_value is None
    assert entity.mode is TextMode.PASSWORD
    assert entity.min == 4
    assert entity.max == 8


async def test_a_pin_nobody_could_type_is_refused_before_it_is_hashed(
    hass: HomeAssistant,
) -> None:
    """Storing a hash of something unusable would lock the TV out of its own keypad."""
    client = make_client(hass)
    client.snapshot = snapshot()

    with (
        patch("homeassistant.components.mqtt.async_publish") as publish,
        pytest.raises(ServiceValidationError),
    ):
        await ParentPinText(client).async_set_value("12")

    publish.assert_not_called()


async def test_clearing_says_null_rather_than_leaving_the_key_out(
    hass: HomeAssistant,
) -> None:
    """The TV refuses a set_pin with no hash key, so this has to be explicit."""
    client = make_client(hass)
    client.snapshot = snapshot(pin_set=True)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await ClearPinButton(client).async_press()

    _hass, _topic, payload = publish.call_args.args
    assert json.loads(payload) == {"op": "set_pin", "hash": None}
    assert publish.call_args.kwargs["retain"] is False


async def test_the_sensor_reports_that_a_pin_exists_and_when_it_changed(
    hass: HomeAssistant,
) -> None:
    """A change made at the TV arrives here as soon as the broker is back."""
    client = make_client(hass)
    client.snapshot = snapshot(
        pin_set=True, pin_changed_at=1787400000000, pin_changed_by="tv"
    )
    sensor = ParentPinSetSensor(client)

    assert sensor.is_on is True
    attributes = sensor.extra_state_attributes
    assert attributes is not None
    assert attributes["changed_by"] == "tv"
    changed_at = dt_util.parse_datetime(attributes["changed_at"])
    assert changed_at is not None
    assert changed_at.timestamp() * 1000 == 1787400000000


async def test_a_television_with_no_pin_says_so(hass: HomeAssistant) -> None:
    """And says nothing about a change that never happened, rather than the epoch."""
    client = make_client(hass)
    client.snapshot = snapshot()
    sensor = ParentPinSetSensor(client)

    assert sensor.is_on is False
    attributes = sensor.extra_state_attributes
    assert attributes is not None
    assert attributes["changed_at"] is None
    assert attributes["changed_by"] is None
