"""TV Sitter integration for Home Assistant.

The Home Assistant side is deliberately thin: the app on the TV counts screen time and
enforces the lock on its own, and this integration turns what arrives over MQTT into
entities and actions. A Home Assistant outage therefore cannot unlock the TV.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SCHEDULE, CONF_TOPIC_PREFIX, DEFAULT_NAME, PLATFORMS
from .coordinator import TvSitterClient

_LOGGER = logging.getLogger(__name__)

type TvSitterConfigEntry = ConfigEntry[TvSitterClient]


async def async_setup_entry(hass: HomeAssistant, entry: TvSitterConfigEntry) -> bool:
    """Set up one TV."""
    # Waiting rather than assuming: the manifest depends on mqtt, but the broker
    # itself can be down while Home Assistant starts, and retrying beats failing.
    if not await mqtt.async_wait_for_mqtt_client(hass):
        raise ConfigEntryNotReady("MQTT is not available")

    client = TvSitterClient(
        hass,
        name=entry.data.get(CONF_NAME, DEFAULT_NAME),
        topic_prefix=entry.data[CONF_TOPIC_PREFIX],
        entry=entry,
    )
    await client.async_start()
    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Picked up again after a restart, so a grid edited next week still reaches the TV.
    # After the platforms, because importing writes rules and the entities showing
    # them should exist by the time it does.
    client.watch_schedule(entry.options.get(CONF_SCHEDULE))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TvSitterConfigEntry) -> bool:
    """Tear down one TV."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data.watch_schedule(None)
        entry.runtime_data.async_stop()
    return unloaded
