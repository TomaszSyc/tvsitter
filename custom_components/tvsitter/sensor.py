"""Sensors for TV Sitter.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import TvSitterConfigEntry
from .coordinator import TvSitterClient
from .entity import TvSitterEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TvSitterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors for one TV."""
    client = entry.runtime_data
    async_add_entities(
        [
            ActiveAppSensor(client),
            UsedTodaySensor(client),
            RemainingTodaySensor(client),
            RulesSensor(client),
            BonusTodaySensor(client),
            LimitTodaySensor(client),
            LastReportedSensor(client),
        ]
    )


class ActiveAppSensor(TvSitterEntity, SensorEntity):
    """Which app is in the foreground."""

    def __init__(self, client: TvSitterClient) -> None:
        """Create the active app sensor."""
        super().__init__(client, "active_app")

    @property
    def native_value(self) -> str | None:
        """Return the app's display name, including the last one before it went quiet.

        Not a claim that it is playing. "Screen: off" and "Reporting: no" sit beside
        this one, so what it reads as is what was last on — a thing worth knowing, and
        one that unknown threw away (#91). Whether the television is running is a
        question those two answer; answering it here as well only loses the name.
        """
        snapshot = self._client.snapshot
        return None if snapshot is None else snapshot.app_name

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the package id, which is what rules are written against."""
        snapshot = self._client.snapshot
        if snapshot is None:
            return None
        return {
            "app_id": snapshot.app_id,
            "active_window": snapshot.active_window,
            "lock_reason": snapshot.lock_reason,
            "until_s": snapshot.until_seconds,
        }


class UsedTodaySensor(TvSitterEntity, SensorEntity):
    """Screen time used in the current budget day."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_suggested_unit_of_measurement = UnitOfTime.MINUTES
    # The counter resets to zero when the budget day rolls over at 04:00, which is
    # exactly what total_increasing is built for — it reads a drop as a new cycle
    # rather than as negative consumption.
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, client: TvSitterClient) -> None:
        """Create the used-today sensor."""
        super().__init__(client, "used_today")

    @property
    def native_value(self) -> int | None:
        """Return seconds used today."""
        snapshot = self._client.snapshot
        return None if snapshot is None else snapshot.used_seconds

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the per-app breakdown behind the total."""
        snapshot = self._client.snapshot
        if snapshot is None:
            return None
        return {"per_app": snapshot.per_app, "bonus_seconds": snapshot.bonus_seconds}


class RemainingTodaySensor(TvSitterEntity, SensorEntity):
    """Screen time left in the current budget day.

    Unknown rather than zero when no limit applies. Reporting zero would read as
    "time is up" to every automation and dashboard card looking at it.
    """

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_suggested_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, client: TvSitterClient) -> None:
        """Create the remaining-today sensor."""
        super().__init__(client, "remaining_today")

    @property
    def native_value(self) -> int | None:
        """Return seconds remaining, or None when unlimited."""
        snapshot = self._client.snapshot
        return None if snapshot is None else snapshot.remaining_seconds

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Say plainly whether a limit is in force at all."""
        snapshot = self._client.snapshot
        if snapshot is None:
            return None
        return {"limit_active": snapshot.remaining_seconds is not None}


class RulesSensor(TvSitterEntity, SensorEntity):
    """The rules the TV says it is enforcing, and which revision they are.

    The television keeps the rules and enforces them offline (D3), so it is the only
    thing that knows what is in force. Without this, Home Assistant can show the daily
    limit — the state payload carries that one — and nothing else: not the week, not
    the hours, not one app's budget. "Why did it lock at half past seven" is a question
    a schedule invites and a dashboard could not answer.

    Read-only, deliberately. Editing a week's schedule through entities is not the plan
    (#60); seeing it is a different job and a much smaller one.

    The revision is the state, because that is the part that changes meaningfully and
    can be compared with the one the TV echoes in its state payload — the two agreeing
    is the whole point of having a revision at all.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = None

    def __init__(self, client: TvSitterClient) -> None:
        """Create the rules sensor."""
        super().__init__(client, "rules")

    @property
    def native_value(self) -> int | None:
        """Return the revision of the rules in force."""
        snapshot = self._client.snapshot
        return None if snapshot is None else snapshot.rules_rev

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the rules themselves, exactly as the TV sent them."""
        if self._client.rules is None:
            return None
        return dict(self._client.rules)


class BonusTodaySensor(TvSitterEntity, SensorEntity):
    """Time granted on top of the day's allowance, in the budget day.

    On the wire since M2 and visible only as an attribute until now, which meant
    "how much
    extra did this month cost" could not be answered at all: attributes are not
    recorded as
    statistics. A bonus rather than a reduction of what was used, so the two
    numbers answer
    different questions — this one is what was given, `used_today` is what was watched.
    """

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_suggested_unit_of_measurement = UnitOfTime.MINUTES
    _attr_suggested_display_precision = 0
    # Resets to zero at 04:00 with the budget day, which is what this is for.
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, client: TvSitterClient) -> None:
        """Create the bonus sensor."""
        super().__init__(client, "bonus_today")

    @property
    def native_value(self) -> int | None:
        """Return the seconds granted today."""
        snapshot = self._client.snapshot
        return None if snapshot is None else snapshot.bonus_seconds


class LimitTodaySensor(TvSitterEntity, SensorEntity):
    """The allowance the television is actually enforcing today.

    Not `number.daily_limit`, which is the parent's intention. These differ
    whenever a day
    override is in force, and they differ again the moment a limit is set aside — the
    control still reads what was asked for, and this reads nothing, because nothing is
    being enforced.
    """

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_suggested_unit_of_measurement = UnitOfTime.MINUTES
    _attr_suggested_display_precision = 0
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, client: TvSitterClient) -> None:
        """Create the limit sensor."""
        super().__init__(client, "limit_today")

    @property
    def native_value(self) -> int | None:
        """Return today's limit, or nothing while none is being enforced."""
        snapshot = self._client.snapshot
        return None if snapshot is None else snapshot.limit_seconds


class LastReportedSensor(TvSitterEntity, SensorEntity):
    """When the television last said anything.

    The state payload is retained, so a dashboard shows numbers whether or not
    anything is
    still running. This is how old they are — the one question a retained topic cannot
    answer by itself, and the difference between "the child watched nothing
    today" and "the
    app died at breakfast".
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client: TvSitterClient) -> None:
        """Create the last-reported sensor."""
        super().__init__(client, "last_reported")

    @property
    def native_value(self) -> datetime | None:
        """Return the send time of the last state payload."""
        snapshot = self._client.snapshot
        if snapshot is None or not snapshot.ts:
            return None
        return dt_util.utc_from_timestamp(snapshot.ts / 1000)
