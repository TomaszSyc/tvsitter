"""What a parent can still see, and still not do, once the TV is switched off.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from custom_components.tvsitter.binary_sensor import ReportingSensor, ScreenOnSensor
from custom_components.tvsitter.button import ClearLimitButton
from custom_components.tvsitter.coordinator import TvSitterClient
from custom_components.tvsitter.models import StateSnapshot
from custom_components.tvsitter.number import DailyLimitNumber
from custom_components.tvsitter.sensor import (
    ActiveAppSensor,
    RemainingTodaySensor,
    UsedTodaySensor,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

PREFIX = "tvsitter/salon"


def asleep(hass: HomeAssistant) -> TvSitterClient:
    """Build a television that has reported today and is now switched off."""
    client = TvSitterClient(hass, name="TV Salon", topic_prefix=PREFIX)
    client.snapshot = StateSnapshot.from_payload(
        json.dumps(
            {
                "schema": 1,
                "ts": 1,
                "fw": "0.4.2",
                "screen_on": True,
                "locked": False,
                "app_id": "com.netflix.ninja",
                "app_name": "Netflix",
                "used_today_s": 4800,
                "limit_today_s": 5400,
                "remaining_today_s": 600,
                "rules_rev": 4,
            }
        )
    )
    client.available = False
    return client


async def test_the_evening_numbers_survive_the_television(hass: HomeAssistant) -> None:
    """#90, and the whole of it.

    A parent looks at these after the set has been switched off, and a television that
    is not running cannot change how long it was watched for today.
    """
    client = asleep(hass)

    used = UsedTodaySensor(client)
    remaining = RemainingTodaySensor(client)

    assert used.available is True
    assert used.native_value == 4800
    assert remaining.available is True
    assert remaining.native_value == 600


async def test_the_screen_is_off_when_nothing_is_reporting(
    hass: HomeAssistant,
) -> None:
    """It said "on" as it went. Leaving that up all night is the wrong answer."""
    screen = ScreenOnSensor(asleep(hass))

    assert screen.available is True
    assert screen.is_on is False


async def test_the_app_is_unknown_rather_than_the_last_one(
    hass: HomeAssistant,
) -> None:
    """Naming a programme that is not playing is the worse kind of wrong."""
    app = ActiveAppSensor(asleep(hass))

    assert app.available is True
    assert app.native_value is None
    assert app.extra_state_attributes["app_id"] == "com.netflix.ninja"


async def test_reporting_says_what_availability_used_to_say(
    hass: HomeAssistant,
) -> None:
    """The signal is not thrown away, it is given an entity that answers for it."""
    client = asleep(hass)
    reporting = ReportingSensor(client)

    assert reporting.available is True, "'no' is the answer it exists to give"
    assert reporting.is_on is False

    client.available = True
    assert reporting.is_on is True


async def test_a_limit_cannot_be_set_on_a_television_that_is_not_listening(
    hass: HomeAssistant,
) -> None:
    """Commands are never retained, so it would go nowhere and look as if it had not."""
    client = asleep(hass)

    with (
        patch("homeassistant.components.mqtt.async_publish") as publish,
        pytest.raises(ServiceValidationError),
    ):
        await DailyLimitNumber(client).async_set_native_value(30)

    publish.assert_not_called()


async def test_clearing_a_limit_is_refused_the_same_way(hass: HomeAssistant) -> None:
    """Readable is not the same as writable, and this is the line between them."""
    client = asleep(hass)

    with (
        patch("homeassistant.components.mqtt.async_publish") as publish,
        pytest.raises(ServiceValidationError),
    ):
        await ClearLimitButton(client).async_press()

    publish.assert_not_called()


async def test_nothing_is_shown_before_the_first_report(hass: HomeAssistant) -> None:
    """A television that has never said anything has nothing to remember about it."""
    client = TvSitterClient(hass, name="TV Salon", topic_prefix=PREFIX)

    assert UsedTodaySensor(client).available is False
    assert ScreenOnSensor(client).available is False
    assert ReportingSensor(client).available is True
