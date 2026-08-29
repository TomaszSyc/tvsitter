"""The lock, as something a parent can actually press.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from . import TvSitterConfigEntry
from .const import RULE_BLOCK_SETTINGS
from .coordinator import TvSitterClient
from .entity import TvSitterEntity

_LOGGER = logging.getLogger(__name__)

OP_LOCK = {"op": "lock"}
OP_UNLOCK = {"op": "unlock"}

ATTR_PENDING = "pending"
ATTR_PENDING_UNTIL = "pending_until"

# How long a remembered unlock is worth acting on.
#
# Long enough for "I am about to switch it on", short enough that one forgotten last
# night
# cannot hand over this evening. A remembered lock has no deadline and needs none: a
# lock
# that arrives late can be lifted, and an unlock that arrives late has already given
# away
# the thing it was guarding.
PENDING_UNLOCK_TTL = timedelta(minutes=15)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TvSitterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the lock switch for one TV."""
    client = entry.runtime_data
    async_add_entities([LockSwitch(client), BlockSettingsSwitch(client)])


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
        self._pending_until: datetime | None = None

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
        pending = self._live_pending()
        if pending is not None:
            return pending
        snapshot = self._client.snapshot
        return None if snapshot is None else snapshot.locked

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Say when the switch is showing an intention rather than a fact."""
        pending = self._live_pending()
        if pending is None:
            return None
        attributes: dict[str, Any] = {ATTR_PENDING: STATE_ON if pending else STATE_OFF}
        if self._pending_until is not None:
            attributes[ATTR_PENDING_UNTIL] = self._pending_until.isoformat()
        return attributes

    def _live_pending(self) -> bool | None:
        """Return the remembered intention, unless it has run out of time.

        Checked when read rather than on a timer. A lapsed intention nobody looks at
        changes nothing, and a timer firing in an empty house wakes the box for nothing.
        """
        if self._pending is None:
            return None
        if self._pending_until is not None and dt_util.utcnow() >= self._pending_until:
            _LOGGER.debug(
                "%s: the unlock that was waiting has lapsed", self._client.name
            )
            self._pending = None
            self._pending_until = None
            return None
        return self._pending

    async def async_added_to_hass(self) -> None:
        """Listen for the TV, and pick up an intention left over from a restart."""
        await super().async_added_to_hass()
        self.async_on_remove(self._client.async_add_listener(self._deliver_pending))

        last = await self.async_get_last_state()
        if last is None:
            return
        pending = last.attributes.get(ATTR_PENDING)
        if pending not in (STATE_ON, STATE_OFF):
            return

        # Restarting Home Assistant while the TV is off must not quietly drop a decision
        # somebody made about tonight.
        if pending == STATE_ON:
            self._pending = True
            _LOGGER.debug("%s: restored a pending lock", self._client.name)
            return

        deadline = dt_util.parse_datetime(
            str(last.attributes.get(ATTR_PENDING_UNTIL) or "")
        )
        if deadline is None:
            # An unlock with no deadline is one from a build that had none, or a state
            # written without it. Dropped rather than honoured for ever: that is exactly
            # the stale unlock the deadline exists to prevent.
            _LOGGER.debug(
                "%s: dropped a restored unlock with no deadline", self._client.name
            )
            return
        self._pending = False
        self._pending_until = deadline
        _LOGGER.debug(
            "%s: restored a pending unlock until %s", self._client.name, deadline
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Put the lock screen up, now or as soon as the TV is listening."""
        await self._ask_for(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Take the lock screen down, now or as soon as the TV is listening."""
        await self._ask_for(False)

    async def _ask_for(self, locked: bool) -> None:
        if self._client.available and self._client.snapshot is not None:
            self._pending = None
            self._pending_until = None
            await self._client.async_send(OP_LOCK if locked else OP_UNLOCK)
            return

        snapshot = self._client.snapshot
        if locked and snapshot is not None and snapshot.locked:
            # Nothing to ask for: it is already up, and it cannot go further up.
            self._pending = None
            self._pending_until = None
            self.async_write_ha_state()
            return

        # An unlock is queued even when the last state agrees with it, which is the
        # whole
        # of #89. A television asleep and unlocked will very often wake up locked — by
        # its
        # own budget, or by a lock restored from before the reboot — and a parent
        # pressing
        # unlock a minute before switching it on is asking about that lock, not about
        # the
        # state it went to sleep in. The deadline is what keeps that different from an
        # unlock forgotten overnight.
        self._pending = locked
        self._pending_until = None if locked else dt_util.utcnow() + PENDING_UNLOCK_TTL
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
        locked = self._live_pending()
        if locked is None:
            return
        snapshot = self._client.snapshot
        if not self._client.available or snapshot is None:
            return

        if not locked and not snapshot.locked:
            # It came back with nothing to lift. Sending the unlock anyway would set the
            # daily limit aside for the rest of the day, which is not what the parent
            # was
            # asking for — they were asking about a lock that never appeared.
            _LOGGER.debug(
                "%s came back unlocked; the waiting unlock is not needed",
                self._client.name,
            )
            self._pending = None
            self._pending_until = None
            self.async_write_ha_state()
            return

        self._pending = None
        self._pending_until = None
        _LOGGER.info(
            "%s is back; sending the %s that was waiting",
            self._client.name,
            "lock" if locked else "unlock",
        )
        self.hass.async_create_task(
            self._client.async_send(OP_LOCK if locked else OP_UNLOCK)
        )


class BlockSettingsSwitch(TvSitterEntity, SwitchEntity):
    """Keeps the Settings app out of reach, lock or no lock.

    The one app whose reach decides whether any of the others can be enforced:
    force stop,
    "draw on top" and the date all live behind it. Behind a lock it already
    lasts under a
    second before the television is sent home; with no lock up it lasts all day,
    and that is
    when a child would go looking (D30).

    A switch rather than a budget, because "twenty minutes of Settings a day" is
    not a thing
    anybody means.

    The parent is shut out too while it is on. That is the honest cost, and it
    is one toggle
    away from being off — unlike suspending the package, which needs ADB in both
    directions.
    """

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, client: TvSitterClient) -> None:
        """Create the settings switch."""
        super().__init__(client, "block_settings")

    @property
    def is_on(self) -> bool | None:
        """Return what the TV says it is enforcing, not what was last sent from here."""
        rules = self._client.rules
        return None if rules is None else bool(rules.get(RULE_BLOCK_SETTINGS, False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Put Settings out of reach."""
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Hand Settings back."""
        await self._set(False)

    async def _set(self, blocked: bool) -> None:
        if not self._client.available:
            raise ServiceValidationError(
                f"{self._client.name} is not listening; the change would go nowhere"
            )
        await self._client.async_set_rules({RULE_BLOCK_SETTINGS: blocked})
