"""The lock, as something a parent can actually press.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TvSitterConfigEntry
from .coordinator import TvSitterClient
from .entity import TvSitterEntity

OP_LOCK = {"op": "lock"}
OP_UNLOCK = {"op": "unlock"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TvSitterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the lock switch for one TV."""
    async_add_entities([LockSwitch(entry.runtime_data)])


class LockSwitch(TvSitterEntity, SwitchEntity):
    """Shows whether the lock screen is up, and puts it up or takes it down.

    A switch rather than a read-only sensor plus a pair of buttons, because that is what
    it is: one thing with two states that a parent changes. It also means the lock's
    history is recorded without a second entity mirroring it.
    """

    def __init__(self, client: TvSitterClient) -> None:
        """Create the lock switch."""
        super().__init__(client, "lock")

    @property
    def is_on(self) -> bool | None:
        """Return True while the lock screen is showing."""
        snapshot = self._client.snapshot
        return None if snapshot is None else snapshot.locked

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Put the lock screen up."""
        await self._client.async_send(OP_LOCK)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Take the lock screen down."""
        await self._client.async_send(OP_UNLOCK)

    # Deliberately no optimistic state. The TV publishes its own state within about half
    # a second of acting. A switch that flipped before the TV had done anything would
    # report a locked television that is not locked, which is the one lie this product
    # cannot afford. If a command is lost the switch stays put, which is the truth.
