"""What a parent can still see, and still not do, once the TV is switched off.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import json
from types import SimpleNamespace
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
    RulesSensor,
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


async def test_the_last_app_is_kept_rather_than_thrown_away(
    hass: HomeAssistant,
) -> None:
    """#91. What were they watching before it went off is worth knowing.

    Not a claim that it is playing: the screen and the reporting entity beside it both
    say the set is not running, which is what makes this readable as the last one.
    """
    app = ActiveAppSensor(asleep(hass))

    assert app.available is True
    assert app.native_value == "Netflix"
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


async def test_the_rules_in_force_are_visible(hass: HomeAssistant) -> None:
    """#73. The TV keeps the rules, so it is the only thing that knows them.

    Without this the daily limit is all Home Assistant can show, because the state
    payload carries that one — and "why did it lock at half past seven" has no answer.
    """
    client = asleep(hass)
    client._handle_rules(
        SimpleNamespace(
            topic=f"{PREFIX}/rules",
            payload=json.dumps(
                {
                    "daily_limit_s": 5400,
                    "days": {"sat": 7200},
                    "windows": [{"id": "school", "from": "16:00", "to": "19:30"}],
                }
            ),
        )
    )

    rules = RulesSensor(client)

    assert rules.native_value == 4, "the revision the TV echoes in its state"
    assert rules.extra_state_attributes["days"] == {"sat": 7200}
    assert rules.extra_state_attributes["windows"][0]["id"] == "school"


async def test_a_rule_this_build_never_heard_of_is_still_shown(
    hass: HomeAssistant,
) -> None:
    """Opaque on purpose: a newer Home Assistant must not watch its own write vanish."""
    client = asleep(hass)
    client._handle_rules(
        SimpleNamespace(
            topic=f"{PREFIX}/rules",
            payload=json.dumps({"daily_limit_s": 60, "bedtime_mood_lighting": "amber"}),
        )
    )

    assert (
        RulesSensor(client).extra_state_attributes["bedtime_mood_lighting"] == "amber"
    )


async def test_rubbish_on_the_rules_topic_keeps_the_last_good_answer(
    hass: HomeAssistant,
) -> None:
    """Showing nothing reads as "enforcing nothing", which is the worse lie."""
    client = asleep(hass)
    good = SimpleNamespace(
        topic=f"{PREFIX}/rules", payload=json.dumps({"daily_limit_s": 60})
    )
    client._handle_rules(good)

    client._handle_rules(SimpleNamespace(topic=f"{PREFIX}/rules", payload="not json"))
    client._handle_rules(SimpleNamespace(topic=f"{PREFIX}/rules", payload="[1, 2, 3]"))

    assert RulesSensor(client).extra_state_attributes == {"daily_limit_s": 60}


async def test_nothing_is_claimed_before_the_rules_arrive(hass: HomeAssistant) -> None:
    """A retained topic that has never been written is not the same as no rules."""
    assert RulesSensor(asleep(hass)).extra_state_attributes is None
