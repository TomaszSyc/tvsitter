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
from homeassistant.const import UnitOfTime
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
        ]
    )


class ActiveAppSensor(TvSitterEntity, SensorEntity):
    """Which app is in the foreground."""

    def __init__(self, client: TvSitterClient) -> None:
        """Create the active app sensor."""
        super().__init__(client, "active_app")

    @property
    def native_value(self) -> str | None:
        """Return the app's display name."""
        snapshot = self._client.snapshot
        return None if snapshot is None else snapshot.app_name

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the package id, which is what rules are written against."""
        snapshot = self._client.snapshot
        if snapshot is None:
            return None
        return {"app_id": snapshot.app_id, "active_window": snapshot.active_window}


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
