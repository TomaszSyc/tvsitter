"""Shared entity behaviour for TV Sitter.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .coordinator import TvSitterClient


class TvSitterEntity(Entity):
    """Base for every entity fed by one TV's MQTT topics."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, client: TvSitterClient, key: str) -> None:
        """Attach to a client and take an identity from its device id."""
        self._client = client
        self._attr_translation_key = key
        self._attr_unique_id = f"{client.device_id}_{key}"
        snapshot = client.snapshot
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, client.device_id)},
            name=client.name,
            manufacturer="TV Sitter",
            model="Android TV parental control",
            # Parsed since M1 and dropped ever since. On the device rather than in an
            # entity: it answers "which build is on that television", which is what the
            # device page is for, and it is the first thing worth knowing when a report
            # says something behaves differently than it does here.
            sw_version=snapshot.firmware if snapshot else None,
        )

    @property
    def available(self) -> bool:
        """Have something to show, rather than have a television awake to show it.

        Most of what is published stays true while the set sleeps — time used today, the
        limit in force, whether a parent PIN exists. A television that is not running
        cannot change any of them, and they are what a parent looks at in the evening,
        after it has been switched off. Following the availability topic took the whole
        device out at exactly that moment (#90).

        The two readings that are only true while it runs — the screen and the app in
        front — answer for themselves instead. What the availability topic says has not
        been thrown away: it is its own entity now, which is the honest place for "is
        this thing actually running", and what #83 will alarm on.
        """
        return self._client.snapshot is not None

    async def async_added_to_hass(self) -> None:
        """Start listening for pushes from the client."""
        self.async_on_remove(self._client.async_add_listener(self.async_write_ha_state))
