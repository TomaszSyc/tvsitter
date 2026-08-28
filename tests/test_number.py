"""The daily limit entity.

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
        "fw": "0.1.0-m0",
        "screen_on": True,
        "locked": False,
    }
    payload.update(overrides)
    return StateSnapshot.from_payload(json.dumps(payload))


async def test_the_limit_is_read_from_the_tv_in_minutes(hass: HomeAssistant) -> None:
    """The TV keeps the rules, so the TV is what this shows."""
    client = make_client(hass)
    client.snapshot = snapshot(limit_today_s=5400)

    assert DailyLimitNumber(client).native_value == 90


@pytest.mark.parametrize("payload", [{}, {"limit_today_s": None}])
async def test_no_limit_reads_as_nothing_rather_than_zero(
    hass: HomeAssistant, payload: dict[str, object]
) -> None:
    """Zero minutes is a real setting; no limit is not it."""
    client = make_client(hass)
    client.snapshot = snapshot(**payload)

    assert DailyLimitNumber(client).native_value is None


async def test_the_limit_admits_it_does_not_know_before_the_first_payload(
    hass: HomeAssistant,
) -> None:
    """Guessing here would show a limit that is not being enforced."""
    assert DailyLimitNumber(make_client(hass)).native_value is None


async def test_setting_a_limit_sends_minutes_as_seconds(hass: HomeAssistant) -> None:
    """The contract is in seconds; the entity is in minutes because parents are."""
    client = make_client(hass)
    client.snapshot = snapshot(limit_today_s=1800, rules_rev=7)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await DailyLimitNumber(client).async_set_native_value(45)

    _hass, topic, payload = publish.call_args.args
    assert topic == f"{PREFIX}/cmd"
    assert json.loads(payload) == {
        "op": "set_rules",
        "rev": 8,
        "rules": {"daily_limit_s": 2700},
    }


async def test_zero_is_sent_rather_than_treated_as_no_limit(
    hass: HomeAssistant,
) -> None:
    """Nothing at all today is a thing a parent may mean."""
    client = make_client(hass)
    client.snapshot = snapshot(limit_today_s=1800, rules_rev=1)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await DailyLimitNumber(client).async_set_native_value(0)

    _hass, _topic, payload = publish.call_args.args
    assert json.loads(payload)["rules"] == {"daily_limit_s": 0}


async def test_the_revision_starts_at_one_when_the_tv_has_none(
    hass: HomeAssistant,
) -> None:
    """A revision has to move, or neither side can tell whether the rules landed."""
    client = make_client(hass)
    client.snapshot = snapshot()

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await DailyLimitNumber(client).async_set_native_value(30)

    assert json.loads(publish.call_args.args[2])["rev"] == 1


async def test_a_limit_is_never_retained(hass: HomeAssistant) -> None:
    """A retained set_rules would re-impose a limit after every broker restart."""
    client = make_client(hass)
    client.snapshot = snapshot()

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await DailyLimitNumber(client).async_set_native_value(30)

    assert publish.call_args.kwargs["retain"] is False
