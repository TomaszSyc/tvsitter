"""Binary sensors for TV Sitter.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
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
    """Set up the binary sensors for one TV."""
    client = entry.runtime_data
    async_add_entities(
        [
            ScreenOnSensor(client),
            ParentPinSetSensor(client),
            ReportingSensor(client),
            ReportingStoppedSensor(client),
        ]
    )


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
        """Return True while the screen is on.

        A television we cannot reach is not showing anything. On this hardware the set
        drops off the network *because* it went to standby, so reading the last value
        would leave "on" beside a television that is off, all night.

        Wrong in one case: the network dropping while somebody is watching. That case is
        worth catching for its own sake rather than by leaving this ambiguous — the
        connectivity entity says the reporting stopped, and #83 is the alarm for it.
        """
        snapshot = self._client.snapshot
        if snapshot is None:
            return None
        return snapshot.screen_on and self._client.available


class ParentPinSetSensor(TvSitterEntity, BinarySensorEntity):
    """Whether the TV has a parent PIN, and when it last changed.

    Worth surfacing because the answer matters most on the evening Home Assistant
    cannot be reached: the PIN is the only thing that lifts a lock at the set itself,
    and "there isn't one" is a bad thing to discover at that point rather than before.

    The attributes are the other half. A PIN changed on the television reaches here as
    soon as the broker is back, because the state payload is retained and republished
    on every connect — so a change made while Home Assistant was down is not lost, it
    is merely late. If it says the PIN changed on the TV and nobody in the house
    changed it, that is the only warning there will be.

    What is deliberately not here is the hash. Publishing it would put something worth
    attacking offline onto the broker and into the recorder, and nothing in Home
    Assistant has any use for it.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client: TvSitterClient) -> None:
        """Create the PIN sensor."""
        super().__init__(client, "pin_set")

    @property
    def is_on(self) -> bool | None:
        """Return True while a parent PIN is set on the TV."""
        snapshot = self._client.snapshot
        return None if snapshot is None else snapshot.pin_set

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return when the PIN last changed, and where."""
        snapshot = self._client.snapshot
        if snapshot is None:
            return None
        changed_at = snapshot.pin_changed_at
        return {
            "changed_at": (
                dt_util.utc_from_timestamp(changed_at / 1000).isoformat()
                if changed_at
                else None
            ),
            "changed_by": snapshot.pin_changed_by,
        }


class ReportingSensor(TvSitterEntity, BinarySensorEntity):
    """Whether the TV is reporting in at all.

    What the availability topic used to say by taking every entity away. It is a real
    question — is the app running, is the set reachable — and it deserves an entity that
    answers it rather than an absence that could mean anything.

    Always available, because "no" is the answer it exists to give.
    """

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client: TvSitterClient) -> None:
        """Create the reporting sensor."""
        super().__init__(client, "reporting")

    @property
    def available(self) -> bool:
        """Always, unlike the rest."""
        return True

    @property
    def is_on(self) -> bool:
        """Return True while the TV is online."""
        return self._client.available


class ReportingStoppedSensor(TvSitterEntity, BinarySensorEntity):
    """On when nothing has arrived from the television for four heartbeats.

    The alarm this milestone is named for, and the half that can be built here.
    Availability
    cannot raise it: it is the Last Will, and D24 measured what that means — a
    set going to
    standby holds the network for a minute or two before it flips, so "the app
    was killed"
    and "the television is asleep" look identical from there.

    This says only that the reporting stopped. Whether the set is powered is a
    question for
    the household's own witness — philips_js, or whatever media_player is in
    that house — and
    the comparison belongs in a blueprint rather than in here, because the
    integration has no
    business guessing which entity that is.

    Always available, and deliberately does not blank its neighbours: a quiet
    television still
    has a last known state worth reading, and hiding it would hide the evidence.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client: TvSitterClient) -> None:
        """Create the silence sensor."""
        super().__init__(client, "reporting_stopped")

    @property
    def available(self) -> bool:
        """Always, like the reporting sensor: silence is the answer it gives."""
        return True

    @property
    def is_on(self) -> bool:
        """Return True while the television has gone quiet."""
        return self._client.reporting_stopped
