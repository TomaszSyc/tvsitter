"""Pairing pieces of the config flow that can be tested without Home Assistant running.

The flow itself needs a running instance and a TV, but the parts most likely to be wrong
are pure: which broker address a TV is told, what a typed override means, and whether
every refusal the TV can send has something to say to the user.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import voluptuous as vol

from custom_components.tvsitter import config_flow, pairing
from custom_components.tvsitter.broker import (
    BrokerSettings,
    is_unreachable_from_elsewhere,
)

INTEGRATION = Path(__file__).resolve().parent.parent / "custom_components" / "tvsitter"

HA_BROKER = BrokerSettings(
    host="192.0.2.10", port=1883, username="ha-user", password="ha-secret"
)


@pytest.mark.parametrize(
    "host",
    [
        "core-mosquitto",  # what the Mosquitto add-on actually looks like in HA
        "core_mosquitto",
        "localhost",
        "127.0.0.1",
        "::1",
        "addon_abc123_mqtt",
        "hassio",
        "",
        "   ",
    ],
)
def test_addresses_a_tv_cannot_use(host: str) -> None:
    """These resolve inside Home Assistant and nowhere else."""
    assert is_unreachable_from_elsewhere(host)


@pytest.mark.parametrize(
    "host",
    ["192.168.1.10", "10.0.0.5", "mqtt.example.lan", "homeassistant.local", "broker"],
)
def test_addresses_a_tv_can_use(host: str) -> None:
    """A real address, including a bare hostname somebody configured on purpose."""
    assert not is_unreachable_from_elsewhere(host)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("tvsitter/salon", "tvsitter/salon"),
        ("  tvsitter/salon  ", "tvsitter/salon"),
        ("/tvsitter/salon/", "tvsitter/salon"),
        ("tvsitter/+", None),
        ("tvsitter/#", None),
        ("", None),
        ("///", None),
    ],
)
def test_prefix_cleaning(raw: str, expected: str | None) -> None:
    """Wildcards would subscribe to other people's topics; blanks address nothing."""
    assert config_flow._clean_prefix(raw) == expected


def test_broker_defaults_are_used_when_nothing_is_typed() -> None:
    """The common path: the user types a PIN and nothing else."""
    resolved = config_flow._resolve_broker(HA_BROKER, {})
    assert resolved == HA_BROKER


def test_typed_username_takes_the_password_typed_beside_it() -> None:
    """A dedicated account must not be paired with Home Assistant's stored password."""
    resolved = config_flow._resolve_broker(
        HA_BROKER, {"username": "tv-only", "password": "tv-secret"}
    )
    assert resolved is not None
    assert (resolved.username, resolved.password) == ("tv-only", "tv-secret")
    assert resolved.host == HA_BROKER.host


def test_typed_username_with_no_password_stays_empty() -> None:
    """An anonymous broker is a real configuration, so an empty password is honoured."""
    resolved = config_flow._resolve_broker(HA_BROKER, {"username": "tv-only"})
    assert resolved is not None
    assert (resolved.username, resolved.password) == ("tv-only", "")


def test_typed_host_overrides_the_derived_one() -> None:
    """Somebody with a broker elsewhere on the network can say so."""
    resolved = config_flow._resolve_broker(
        HA_BROKER, {"host": "mqtt.example.lan", "port": 8883, "use_tls": True}
    )
    assert resolved is not None
    assert (resolved.host, resolved.port, resolved.use_tls) == (
        "mqtt.example.lan",
        8883,
        True,
    )
    # Credentials still come from Home Assistant, because none were typed.
    assert resolved.username == HA_BROKER.username


def test_no_defaults_and_no_host_means_nothing_to_send() -> None:
    """Better to abort than to pair a TV against an address that is not there."""
    assert config_flow._resolve_broker(None, {}) is None
    assert config_flow._resolve_broker(None, {"username": "someone"}) is None


def test_no_defaults_but_a_typed_host_is_enough() -> None:
    """Filling the section in does not require the MQTT entry to have been readable."""
    resolved = config_flow._resolve_broker(
        None, {"host": "mqtt.example.lan", "username": "tv", "password": "p"}
    )
    assert resolved is not None
    assert resolved.host == "mqtt.example.lan"


def test_pair_schema_accepts_a_filled_in_form() -> None:
    """Guards the sectioned schema, which is the part that cannot be eyeballed."""
    schema = config_flow._pair_schema("tvsitter/salon", HA_BROKER)
    validated = schema(
        {
            "pin": "927745",
            "topic_prefix": "tvsitter/salon",
            "broker": {
                "host": "192.0.2.10",
                "port": 1883,
                "username": "",
                "password": "",
                "use_tls": False,
            },
        }
    )
    assert validated["pin"] == "927745"
    assert validated["broker"]["host"] == "192.0.2.10"


def test_pair_schema_defaults_the_broker_section_from_home_assistant() -> None:
    """The address a TV can reach is pre-filled, so the common path needs no typing."""
    schema = config_flow._pair_schema("tvsitter/salon", HA_BROKER)
    validated = schema(
        {"pin": "927745", "topic_prefix": "tvsitter/salon", "broker": {}}
    )
    assert validated["broker"]["host"] == HA_BROKER.host
    assert validated["broker"]["port"] == HA_BROKER.port
    # Never pre-filled: nobody has to read it back, and the flow reads it itself.
    assert validated["broker"]["password"] == ""


def test_pair_schema_still_requires_a_pin() -> None:
    """The PIN is the whole point of the step."""
    schema = config_flow._pair_schema("tvsitter/salon", HA_BROKER)
    with pytest.raises(vol.Invalid):
        schema({"topic_prefix": "tvsitter/salon", "broker": {}})


def test_pair_response_is_read_the_way_the_tv_writes_it() -> None:
    """Field names come from PairResponse's @SerialName annotations, not from Python."""
    accepted = pairing.PairResult.from_payload(
        json.loads('{"ok":true,"device_id":"dd17356d","name":"Salon"}')
    )
    assert (accepted.ok, accepted.device_id, accepted.name) == (
        True,
        "dd17356d",
        "Salon",
    )

    refused = pairing.PairResult.from_payload(
        json.loads('{"ok":false,"error":"wrong_pin","attempts_remaining":3}')
    )
    assert (refused.ok, refused.error, refused.attempts_remaining) == (
        False,
        "wrong_pin",
        3,
    )


def _flow_strings(filename: str) -> dict:
    if filename == "strings.json":
        path = INTEGRATION / filename
    else:
        path = INTEGRATION / "translations" / filename
    return json.loads(path.read_text(encoding="utf-8"))["config"]


@pytest.mark.parametrize("filename", ["strings.json", "en.json", "pl.json"])
def test_every_refusal_has_something_to_say(filename: str) -> None:
    """A missing key renders as `wrong_pin` on screen, which helps nobody.

    The failure mode this catches is real: the TV can refuse in six different ways, and
    each one has to reach the user as a sentence.
    """
    errors = _flow_strings(filename)["error"]
    from_the_tv = {
        value
        for name, value in vars(pairing).items()
        if name.startswith("ERROR_") and isinstance(value, str)
    }
    expected = from_the_tv | {"wrong_pin_attempts", "unknown", "invalid_topic_prefix"}

    assert expected <= set(errors), (
        f"{filename} is missing {sorted(expected - set(errors))}"
    )


@pytest.mark.parametrize("filename", ["strings.json", "en.json", "pl.json"])
def test_every_abort_has_something_to_say(filename: str) -> None:
    """Same for the reasons the flow gives up on its own."""
    aborts = set(_flow_strings(filename)["abort"])
    expected = {
        "already_configured",
        "already_paired",
        "not_tvsitter",
        "no_broker",
        "mqtt_unavailable",
    }

    assert expected <= aborts, f"{filename} is missing {sorted(expected - aborts)}"


def test_attempts_placeholder_is_present_where_it_is_used() -> None:
    """The counted variant is useless without the count, and raises if it is absent."""
    for filename in ("strings.json", "en.json", "pl.json"):
        message = _flow_strings(filename)["error"]["wrong_pin_attempts"]
        assert "{attempts}" in message, filename
