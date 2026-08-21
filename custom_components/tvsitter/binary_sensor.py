"""Binary sensors for TV Sitter.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    """Set up the binary sensors for one TV."""
    client = entry.runtime_data
    async_add_entities([ScreenOnSensor(client), LockedSensor(client)])


class ScreenOnSensor(TvSitterEntity, BinarySensorEntity):
    """Whether the panel is showing anything.

    Not the same question as whether the app is running: a Google TV in standby keeps
    the system alive, so this reads false while the integration stays available. The
    pair of signals is what separates "TV off" from "app crashed".
    """

    def __init__(self, client: TvSitterClient) -> None:
        """Create the screen sensor."""
        super().__init__(client, "screen")

    @property
    def is_on(self) -> bool | None:
        """Return True while the screen is on."""
        snapshot = self._client.snapshot
        return None if snapshot is None else snapshot.screen_on


class LockedSensor(TvSitterEntity, BinarySensorEntity):
    """Whether the lock screen is currently up."""

    def __init__(self, client: TvSitterClient) -> None:
        """Create the lock sensor."""
        super().__init__(client, "locked")

    @property
    def is_on(self) -> bool | None:
        """Return True while the TV is locked."""
        snapshot = self._client.snapshot
        return None if snapshot is None else snapshot.locked
