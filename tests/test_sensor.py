"""The readings: what they say, and what they say when the TV has not.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.tvsitter.coordinator import TvSitterClient
from custom_components.tvsitter.models import StateSnapshot
from custom_components.tvsitter.sensor import (
    AppUsageSensor,
    BonusTodaySensor,
    LastReportedSensor,
    LimitTodaySensor,
    RemainingTodaySensor,
    UsedTodaySensor,
)
from homeassistant.components.sensor import SensorStateClass
from homeassistant.core import HomeAssistant

PREFIX = "tvsitter/salon"


def make_client(hass: HomeAssistant, **overrides: object) -> TvSitterClient:
    """Build a client holding one state payload of the shape the TV sends."""
    client = TvSitterClient(hass, name="TV Salon", topic_prefix=PREFIX)
    payload: dict[str, object] = {
        "schema": 1,
        "ts": 1787490000000,
        "fw": "0.4.18",
        "screen_on": True,
        "locked": False,
        "used_today_s": 4800,
        "limit_today_s": 5400,
        "remaining_today_s": 600,
        "bonus_today_s": 900,
    }
    payload.update(overrides)
    client.snapshot = StateSnapshot.from_payload(json.dumps(payload))
    client.available = True
    return client


async def test_the_day_reads_back(hass: HomeAssistant) -> None:
    """Four numbers, and each answers a different question."""
    client = make_client(hass)

    assert UsedTodaySensor(client).native_value == 4800
    assert RemainingTodaySensor(client).native_value == 600
    assert BonusTodaySensor(client).native_value == 900
    assert LimitTodaySensor(client).native_value == 5400


async def test_used_and_bonus_are_total_increasing(hass: HomeAssistant) -> None:
    """Both reset at 04:00 rather than climbing for ever, which is what this means.

    Without it a graph of the month is a sawtooth read as real drops in viewing.
    """
    client = make_client(hass)

    assert UsedTodaySensor(client).state_class is SensorStateClass.TOTAL_INCREASING
    assert BonusTodaySensor(client).state_class is SensorStateClass.TOTAL_INCREASING


async def test_no_limit_is_nothing_rather_than_zero(hass: HomeAssistant) -> None:
    """Zero is a real setting — no viewing today — so it cannot double as "none set"."""
    client = make_client(hass, limit_today_s=None, remaining_today_s=None)

    assert LimitTodaySensor(client).native_value is None
    assert RemainingTodaySensor(client).native_value is None


async def test_a_limit_of_zero_is_still_a_limit(hass: HomeAssistant) -> None:
    """The other half of the same distinction, and the one easy to lose."""
    client = make_client(hass, limit_today_s=0, remaining_today_s=0)

    assert LimitTodaySensor(client).native_value == 0
    assert RemainingTodaySensor(client).native_value == 0


async def test_how_old_the_numbers_are(hass: HomeAssistant) -> None:
    """A retained payload shows numbers whether or not anything is still running."""
    reported = LastReportedSensor(make_client(hass)).native_value

    assert reported is not None
    assert reported.timestamp() == pytest.approx(1787490000)


async def test_a_television_that_has_never_reported_says_nothing(
    hass: HomeAssistant,
) -> None:
    """Rather than zero, which would read as a day with no television in it."""
    client = TvSitterClient(hass, name="TV Salon", topic_prefix=PREFIX)

    assert UsedTodaySensor(client).native_value is None
    assert BonusTodaySensor(client).native_value is None
    assert LastReportedSensor(client).native_value is None


async def test_the_firmware_is_on_the_device(hass: HomeAssistant) -> None:
    """Which build is on that television is the first thing a report needs."""
    assert UsedTodaySensor(make_client(hass)).device_info["sw_version"] == "0.4.18"


def test_every_entity_name_is_translated() -> None:
    """A missing key shows as "TV Salon Bonus_today" and nobody notices for months.

    Keys, not names: the whole point of the Polish file is that the names differ.
    """
    package = Path("custom_components/tvsitter")

    def keys(document: dict) -> set[str]:
        return {
            f"{platform}.{key}"
            for platform, entities in document["entity"].items()
            for key in entities
        }

    expected = keys(json.loads((package / "strings.json").read_text()))
    for language in ("en", "pl"):
        translations = package / "translations" / f"{language}.json"
        assert keys(json.loads(translations.read_text())) == expected, language


def apps(hass: HomeAssistant, per_app: dict[str, int], names: dict[str, str]):
    """Build a client whose TV has charged time to some packages."""
    return make_client(hass, per_app=per_app, per_app_names=names)


async def test_an_app_is_named_by_the_television(hass: HomeAssistant) -> None:
    """#82. The labels live on the set and nowhere else.

    Without them a graph of what a child watches is a graph of package ids.
    """
    client = apps(hass, {"com.netflix.ninja": 890}, {"com.netflix.ninja": "Netflix"})

    sensor = AppUsageSensor(client, "com.netflix.ninja")

    assert sensor.name == "Netflix"
    assert sensor.native_value == 890
    assert sensor.state_class is SensorStateClass.TOTAL_INCREASING


async def test_an_app_without_a_label_keeps_its_package_id(
    hass: HomeAssistant,
) -> None:
    """An id on a graph beats a row that is not there."""
    client = apps(hass, {"com.mystery.app": 60}, {})

    assert AppUsageSensor(client, "com.mystery.app").name == "com.mystery.app"


async def test_a_label_arriving_later_fixes_the_name(hass: HomeAssistant) -> None:
    """Read on every update rather than fixed at creation."""
    client = apps(hass, {"com.netflix.ninja": 60}, {})
    sensor = AppUsageSensor(client, "com.netflix.ninja")

    client.snapshot = apps(
        hass, {"com.netflix.ninja": 120}, {"com.netflix.ninja": "Netflix"}
    ).snapshot

    assert sensor.name == "Netflix"


async def test_a_day_that_rolled_over_reads_zero_rather_than_unknown(
    hass: HomeAssistant,
) -> None:
    """It resets with the budget day, which is not the same as having no answer."""
    client = apps(hass, {}, {})

    assert AppUsageSensor(client, "com.netflix.ninja").native_value == 0


async def test_an_app_on_a_television_that_has_not_reported_says_nothing(
    hass: HomeAssistant,
) -> None:
    """Zero here would claim a day with no television in it."""
    client = TvSitterClient(hass, name="TV Salon", topic_prefix=PREFIX)

    assert AppUsageSensor(client, "com.netflix.ninja").native_value is None
