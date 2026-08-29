"""Sensors for TV Sitter.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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
