"""TV Sitter integration for Home Assistant.

The Home Assistant side is deliberately thin: the app on the TV counts screen time and
enforces the lock on its own, and this integration turns what arrives over MQTT into
entities and actions. That way a Home Assistant outage cannot unlock the TV.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# M1 adds Platform.BINARY_SENSOR and Platform.SENSOR (screen state, active app),
# M2 adds Platform.SWITCH and Platform.NUMBER, M3 adds Platform.EVENT.
PLATFORMS: list[Platform] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    _LOGGER.debug("Setting up TV Sitter for %s", entry.data)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Tear down a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
