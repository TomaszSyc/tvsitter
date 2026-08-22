"""The lock, as something a parent can actually press.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import TvSitterConfigEntry
from .coordinator import TvSitterClient
from .entity import TvSitterEntity

_LOGGER = logging.getLogger(__name__)

OP_LOCK = {"op": "lock"}
OP_UNLOCK = {"op": "unlock"}

ATTR_PENDING = "pending"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TvSitterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the lock switch for one TV."""
    async_add_entities([LockSwitch(entry.runtime_data)])


class LockSwitch(TvSitterEntity, SwitchEntity, RestoreEntity):
    """Shows whether the lock screen is up, and puts it up or takes it down.

    A switch rather than a read-only sensor plus a pair of buttons, because that is what
    it is: one thing with two states that a parent changes. It also means the lock's
    history is recorded without a second entity mirroring it.

    Deliberately no optimistic state while the TV is listening. The TV publishes its own
    state within about half a second of acting. A switch that flipped before the TV had
    done anything would report a locked television that is not locked, which is the one
    lie this product cannot afford. If a command is lost the switch stays put, which is
    the truth.

    While the TV is *not* listening it works differently, and has to. A switched-off
    television drops off the network within about ninety seconds, the Last Will marks it
    offline, and commands are never retained — so a parent deciding at nine that the
    evening is over had nothing to press at all (#48). Availability is the right answer
    to "do I know whether it is locked" and the wrong answer to "may I ask for it to be
    locked", so this one entity stays operable and remembers the intention instead.
    """

    def __init__(self, client: TvSitterClient) -> None:
        """Create the lock switch."""
        super().__init__(client, "lock")
        self._pending: bool | None = None

    @property
    def available(self) -> bool:
        """Always available, unlike every other entity here.

        The rest follow the TV's own availability topic, because a value nobody can read
        is not a value. This one is a control as well as a reading, and the moment a
        parent most wants it is the moment the television is off.
        """
        return True

    @property
    def is_on(self) -> bool | None:
        """Return the intention if there is one, otherwise what the TV last reported.

        Reporting the last known state while the TV is offline is not optimism: a
        television that is not running cannot change whether it is locked, and "unknown"
        on a toggle is worse than a fact that is a few hours old.
        """
        if self._pending is not None:
            return self._pending
        snapshot = self._client.snapshot
        return None if snapshot is None else snapshot.locked

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Say when the switch is showing an intention rather than a fact."""
        if self._pending is None:
            return None
        return {ATTR_PENDING: STATE_ON if self._pending else STATE_OFF}

    async def async_added_to_hass(self) -> None:
        """Listen for the TV, and pick up an intention left over from a restart."""
        await super().async_added_to_hass()
        self.async_on_remove(self._client.async_add_listener(self._deliver_pending))

        last = await self.async_get_last_state()
        if last is None:
            return
        pending = last.attributes.get(ATTR_PENDING)
        if pending in (STATE_ON, STATE_OFF):
            # Restarting Home Assistant while the TV is off must not quietly drop a
            # decision somebody made about tonight.
            self._pending = pending == STATE_ON
            _LOGGER.debug("%s: restored a pending %s", self._client.name, pending)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Put the lock screen up, now or as soon as the TV is listening."""
        await self._ask_for(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Take the lock screen down, now or as soon as the TV is listening."""
        await self._ask_for(False)

    async def _ask_for(self, locked: bool) -> None:
        if self._client.available and self._client.snapshot is not None:
            self._pending = None
            await self._client.async_send(OP_LOCK if locked else OP_UNLOCK)
            return

        snapshot = self._client.snapshot
        if snapshot is not None and snapshot.locked == locked:
            # Nothing to ask for. Queuing it anyway would mean an `unlock` arriving on a
            # television that woke up locked by its own budget, which sets the daily
            # limit aside for the rest of the day — from a switch nobody moved.
            self._pending = None
            self.async_write_ha_state()
            return

        self._pending = locked
        self.async_write_ha_state()
        _LOGGER.debug(
            "%s is not listening; will %s as soon as it is",
            self._client.name,
            "lock" if locked else "unlock",
        )

    @callback
    def _deliver_pending(self) -> None:
        """Send a remembered intention the moment the TV reports in.

        Cleared as it is sent rather than when the TV confirms. The intention exists
        only to survive the wait, and after that the TV's own reports are the truth
        again — which also means an answer the TV declines, such as unlocking while the
        budget is spent, cannot turn into a command resent for ever.
        """
        if self._pending is None:
            return
        if not self._client.available or self._client.snapshot is None:
            return

        locked = self._pending
        self._pending = None
        _LOGGER.info(
            "%s is back; sending the %s that was waiting",
            self._client.name,
            "lock" if locked else "unlock",
        )
        self.hass.async_create_task(
            self._client.async_send(OP_LOCK if locked else OP_UNLOCK)
        )
