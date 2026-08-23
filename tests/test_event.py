"""Asking for more time, and answering it.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from custom_components.tvsitter.coordinator import TvSitterClient
from custom_components.tvsitter.event import TimeRequestEvent
from custom_components.tvsitter.models import StateSnapshot
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

PREFIX = "tvsitter/salon"
REQUEST_ID = "8f14e45f"


def make_client(hass: HomeAssistant) -> TvSitterClient:
    """Build a client with nothing subscribed; the arrivals are handed to it by hand."""
    return TvSitterClient(hass, name="TV Salon", topic_prefix=PREFIX)


def snapshot(**overrides: object) -> StateSnapshot:
    """Build a state payload of the shape the TV sends."""
    payload: dict[str, object] = {
        "schema": 1,
        "ts": 1,
        "fw": "0.2.0",
        "screen_on": True,
        "locked": True,
    }
    payload.update(overrides)
    return StateSnapshot.from_payload(json.dumps(payload))


def arriving(**overrides: Any) -> SimpleNamespace:
    """One `<prefix>/request` message, as the subscription hands it over."""
    payload: dict[str, Any] = {
        "schema": 1,
        "id": REQUEST_ID,
        "kind": "more_time",
        "app_id": "com.netflix.ninja",
        "app_name": "Netflix",
        "asked_minutes": 15,
        "ts": 1787400000000,
    }
    payload.update(overrides)
    return SimpleNamespace(
        topic=f"{PREFIX}/request", payload=json.dumps(payload), qos=1, retain=False
    )


async def listening(hass: HomeAssistant, client: TvSitterClient) -> TimeRequestEvent:
    """Wire an event entity to the client, with no real Home Assistant behind it."""
    entity = TimeRequestEvent(client)
    entity.hass = hass
    await entity.async_added_to_hass()
    return entity


async def test_a_request_from_the_tv_becomes_an_event(hass: HomeAssistant) -> None:
    """The whole point: an automation triggers on the child asking."""
    client = make_client(hass)
    client.snapshot = snapshot(app_id="com.netflix.ninja", app_name="Netflix")
    entity = await listening(hass, client)

    with patch.object(TimeRequestEvent, "async_write_ha_state"):
        client._handle_request(arriving())

    attributes = entity.state_attributes
    assert attributes["event_type"] == "more_time"
    assert attributes["id"] == REQUEST_ID
    assert attributes["asked_minutes"] == 15
    assert attributes["app_id"] == "com.netflix.ninja"
    assert attributes["app_name"] == "Netflix"


async def test_two_identical_requests_are_two_events(hass: HomeAssistant) -> None:
    """Why this is an event and not a sensor holding the last request.

    A state that does not change is not a trigger, and a child asking twice half an hour
    apart has asked twice.
    """
    client = make_client(hass)
    client.snapshot = snapshot()
    entity = await listening(hass, client)

    with patch.object(TimeRequestEvent, "async_write_ha_state"):
        client._handle_request(arriving())
        first = entity.state
        client._handle_request(arriving())

    assert entity.state != first


async def test_the_request_names_the_app_itself(hass: HomeAssistant) -> None:
    """The TV resolved that name at the moment of asking, so it wins."""
    client = make_client(hass)
    client.snapshot = snapshot(
        app_id="com.google.android.youtube.tv", app_name="YouTube"
    )
    entity = await listening(hass, client)

    with patch.object(TimeRequestEvent, "async_write_ha_state"):
        client._handle_request(arriving(app_id="com.netflix.ninja", app_name="Netflix"))

    assert entity.state_attributes["app_id"] == "com.netflix.ninja"
    assert entity.state_attributes["app_name"] == "Netflix"


async def test_without_a_name_the_two_have_to_agree(hass: HomeAssistant) -> None:
    """An older TV sends no name, and the wrong programme is worse than none."""
    client = make_client(hass)
    client.snapshot = snapshot(
        app_id="com.google.android.youtube.tv", app_name="YouTube"
    )
    entity = await listening(hass, client)

    with patch.object(TimeRequestEvent, "async_write_ha_state"):
        client._handle_request(arriving(app_id="com.netflix.ninja", app_name=None))

    assert entity.state_attributes["app_name"] is None


async def test_a_kind_this_build_does_not_know_is_ignored(hass: HomeAssistant) -> None:
    """A newer TV must not take the subscription down with an exception."""
    client = make_client(hass)
    client.snapshot = snapshot()
    entity = await listening(hass, client)

    with patch.object(TimeRequestEvent, "async_write_ha_state"):
        client._handle_request(arriving(kind="something_else"))

    assert entity.state is None


async def test_a_request_with_no_id_is_dropped(hass: HomeAssistant) -> None:
    """An answer is addressed to an id, so a request without one cannot be answered."""
    client = make_client(hass)
    client.snapshot = snapshot()
    entity = await listening(hass, client)

    with patch.object(TimeRequestEvent, "async_write_ha_state"):
        client._handle_request(arriving(id=""))

    assert entity.state is None
    assert client.last_request is None


async def test_granting_answers_the_request_by_id(hass: HomeAssistant) -> None:
    """The id matters: the TV ignores an answer to a request it has already settled."""
    client = make_client(hass)
    client.snapshot = snapshot()
    entity = await listening(hass, client)

    with patch.object(TimeRequestEvent, "async_write_ha_state"):
        client._handle_request(arriving())

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await entity.async_grant_time(minutes=15)

    _hass, topic, payload = publish.call_args.args
    assert topic == f"{PREFIX}/cmd"
    assert json.loads(payload) == {
        "op": "grant",
        "req_id": REQUEST_ID,
        "minutes": 15,
    }
    assert publish.call_args.kwargs["retain"] is False
    assert publish.call_args.kwargs["qos"] == 1


async def test_an_explicit_id_wins_over_the_last_one(hass: HomeAssistant) -> None:
    """A blueprint answers the notification it was tagged with, not the newest one."""
    client = make_client(hass)
    client.snapshot = snapshot()
    entity = await listening(hass, client)

    with patch.object(TimeRequestEvent, "async_write_ha_state"):
        client._handle_request(arriving())
        client._handle_request(arriving(id="deadbeef"))

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await entity.async_grant_time(minutes=30, req_id=REQUEST_ID)

    assert json.loads(publish.call_args.args[2])["req_id"] == REQUEST_ID


async def test_refusing_sends_a_refusal(hass: HomeAssistant) -> None:
    """Silence leaves the child watching a screen that says nothing happened."""
    client = make_client(hass)
    client.snapshot = snapshot()
    entity = await listening(hass, client)

    with patch.object(TimeRequestEvent, "async_write_ha_state"):
        client._handle_request(arriving())

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await entity.async_deny_time()

    assert json.loads(publish.call_args.args[2]) == {
        "op": "deny",
        "req_id": REQUEST_ID,
    }


async def test_answering_nothing_says_so_rather_than_publishing(
    hass: HomeAssistant,
) -> None:
    """A grant with no request to attach it to would be a bonus nobody asked for."""
    client = make_client(hass)
    client.snapshot = snapshot()
    entity = await listening(hass, client)

    with (
        patch("homeassistant.components.mqtt.async_publish") as publish,
        pytest.raises(ServiceValidationError),
    ):
        await entity.async_grant_time(minutes=15)

    publish.assert_not_called()
