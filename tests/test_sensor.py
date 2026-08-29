"""The readings: what they say, and what they say when the TV has not.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from datetime import timedelta
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from custom_components.tvsitter.const import QUIET_AFTER_SECONDS
from custom_components.tvsitter.coordinator import TvSitterClient
from custom_components.tvsitter.models import StateSnapshot
from custom_components.tvsitter.sensor import (
    AppUsageSensor,
    BonusTodaySensor,
    LastReportedSensor,
    LimitTodaySensor,
    RemainingTodaySensor,
    UsedTodaySensor,
    UsedYesterdaySensor,
)
from homeassistant.components.sensor import SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

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


DAY = json.dumps(
    {
        "schema": 1,
        "day": "2026-08-28",
        "used_s": 8040,
        "limit_s": 9000,
        "bonus_s": 900,
        "granted_s": 900,
        "lock_count": 2,
        "per_app": {"com.netflix.ninja": 3600},
        "per_app_names": {"com.netflix.ninja": "Netflix"},
        "requests": {"asked": 3, "granted": 1, "denied": 1, "expired": 1},
        "ts": 1787490000000,
    }
)


def yesterday(hass: HomeAssistant, payload: str = DAY) -> TvSitterClient:
    """Build a client that has heard one closed day."""
    client = make_client(hass)
    client._handle_day(SimpleNamespace(topic=f"{PREFIX}/day", payload=payload))
    return client


async def test_yesterday_can_be_said_in_one_sentence(hass: HomeAssistant) -> None:
    """#81. The whole point: a day that is over, without a recorder query."""
    sensor = UsedYesterdaySensor(yesterday(hass))

    assert sensor.native_value == 8040
    attributes = sensor.extra_state_attributes
    assert attributes["day"] == "2026-08-28"
    assert attributes["limit_s"] == 9000
    assert attributes["requests"]["denied"] == 1
    assert attributes["lock_count"] == 2
    assert attributes["per_app_names"]["com.netflix.ninja"] == "Netflix"


async def test_a_day_from_a_newer_schema_is_refused(hass: HomeAssistant) -> None:
    """The same rule as the state payload: guessing what fields mean is worse."""
    payload = json.dumps({"schema": 99, "day": "2026-08-28", "used_s": 1})
    client = yesterday(hass, payload)

    assert client.day is None


async def test_a_day_about_nothing_is_refused(hass: HomeAssistant) -> None:
    """A summary with no day names no day, and would overwrite one that did."""
    client = yesterday(hass, json.dumps({"schema": 1, "used_s": 60}))

    assert client.day is None


async def test_rubbish_leaves_the_last_good_day_alone(hass: HomeAssistant) -> None:
    """Blanking it would read as a day with no television in it."""
    client = yesterday(hass)

    client._handle_day(SimpleNamespace(topic=f"{PREFIX}/day", payload="not json"))

    assert client.day is not None
    assert client.day.used_seconds == 8040


async def test_before_the_first_rollover_there_is_no_yesterday(
    hass: HomeAssistant,
) -> None:
    """A television installed this afternoon has not closed a day yet."""
    sensor = UsedYesterdaySensor(make_client(hass))

    assert sensor.native_value is None
    assert sensor.extra_state_attributes is None


ALERT = json.dumps(
    {
        "schema": 1,
        "id": "a1b2c3d4",
        "kind": "pin_lockout",
        "ts": 1787490000000,
        "detail": {"failures": 5, "seconds": 300},
    }
)


async def test_a_keypad_that_shut_reaches_home_assistant(hass: HomeAssistant) -> None:
    """#41 and #77. Working through PINs was invisible until one of them worked."""
    client = make_client(hass)
    seen: list[object] = []
    client.async_add_alert_listener(seen.append)

    client._handle_alert(SimpleNamespace(topic=f"{PREFIX}/alert", payload=ALERT))

    assert len(seen) == 1
    assert client.last_alert.kind == "pin_lockout"
    assert client.last_alert.detail["failures"] == 5


async def test_an_alarm_that_cannot_be_read_is_not_an_alarm(
    hass: HomeAssistant,
) -> None:
    """An exception inside an MQTT callback takes the subscription down with it."""
    client = make_client(hass)
    seen: list[object] = []
    client.async_add_alert_listener(seen.append)

    client._handle_alert(SimpleNamespace(topic=f"{PREFIX}/alert", payload="not json"))
    payload = json.dumps({"schema": 1, "id": "", "kind": "pin_lockout"})
    client._handle_alert(SimpleNamespace(topic=f"{PREFIX}/alert", payload=payload))

    assert seen == []
    assert client.last_alert is None


async def test_silence_is_noticed_without_blanking_anything(
    hass: HomeAssistant,
) -> None:
    """#83. A quiet television still has a last known state worth reading."""
    client = make_client(hass)

    stale = dt_util.utcnow() + timedelta(seconds=QUIET_AFTER_SECONDS + 60)
    with patch(
        "custom_components.tvsitter.coordinator.dt_util.utcnow", return_value=stale
    ):
        client._check_for_silence(stale)

    assert client.reporting_stopped is True
    assert UsedTodaySensor(client).available is True, "the evidence stays visible"
    assert UsedTodaySensor(client).native_value == 4800


async def test_a_television_reporting_normally_is_not_a_problem(
    hass: HomeAssistant,
) -> None:
    """The heartbeat is 60 s, so four of them is the bar rather than one missed tick."""
    client = make_client(hass)

    fresh = dt_util.utc_from_timestamp(1787490000 + 90)
    with patch(
        "custom_components.tvsitter.coordinator.dt_util.utcnow", return_value=fresh
    ):
        client._check_for_silence(fresh)

    assert client.reporting_stopped is False


def test_every_entity_has_an_icon() -> None:
    """A row with no icon reads as an entity somebody forgot, and often it is one.

    Against `strings.json` rather than a hand-written list, so an entity added without
    an icon fails here instead of showing up as the default dot in the entity list.
    """
    package = Path("custom_components/tvsitter")
    document = json.loads((package / "strings.json").read_text())
    icons = json.loads((package / "icons.json").read_text())

    for platform, entities in document["entity"].items():
        drawn = set(icons["entity"].get(platform, {}))
        assert set(entities) <= drawn, (
            f"{platform} is missing {sorted(set(entities) - drawn)}"
        )

    assert set(document["services"]) <= set(icons["services"])
