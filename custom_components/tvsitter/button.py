"""Lifting the daily limit, which a number cannot express.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    """Set up the buttons for one TV."""
    async_add_entities([ClearLimitButton(entry.runtime_data)])


class ClearLimitButton(TvSitterEntity, ButtonEntity):
    """Lifts the daily limit entirely.

    A `number` can hold a limit and change it, and has no way to say "none". Zero cannot
    stand in: zero minutes means no viewing today, which is a real thing a parent may
    mean, so it must not double as lifting the limit. A button is the honest shape — one
    thing that happens when pressed, with no state of its own to disagree with the TV
    about.
    """

    def __init__(self, client: TvSitterClient) -> None:
        """Create the clear-limit button."""
        super().__init__(client, "clear_limit")

    async def async_press(self) -> None:
        """Remove the daily limit, leaving every other rule alone.

        `set_rules` merges, so naming one key with null removes exactly that rule.
        Sending an empty object would change nothing, and sending a whole rules object
        would mean knowing every rule in force — which this cannot and should not.
        """
        snapshot = self._client.snapshot
        revision = (snapshot.rules_rev if snapshot else 0) + 1
        await self._client.async_send(
            {"op": "set_rules", "rev": revision, "rules": {"daily_limit_s": None}}
        )
