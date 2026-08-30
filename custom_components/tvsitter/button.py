"""Two things a parent does once: lifting the limit, and removing the PIN.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TvSitterConfigEntry
from .const import RULE_DAILY_LIMIT
from .coordinator import TvSitterClient
from .entity import TvSitterEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TvSitterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons for one TV."""
    client = entry.runtime_data
    async_add_entities([ClearLimitButton(client), ClearPinButton(client)])


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

        Lifting a limit is a rule, so pressing this on a sleeping television holds it
        until the set is listening rather than refusing it (#135). The null survives the
        wait as a value: a change waiting to remove a rule is not the same as no change
        waiting, and folding it the television's way would lose exactly that.
        """
        await self._client.async_set_rules({RULE_DAILY_LIMIT: None})


class ClearPinButton(TvSitterEntity, ButtonEntity):
    """Removes the parent PIN from the TV.

    The other half of a control that can only set. Without it a PIN could be changed but
    never taken off, and the only way back would be reinstalling the app on the TV.

    Pressing it on a television that has no PIN changes nothing, which is why it is not
    hidden when there is none: an automation that runs it should not start failing
    depending on the state of the thing it is trying to bring about.
    """

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, client: TvSitterClient) -> None:
        """Create the clear-PIN button."""
        super().__init__(client, "clear_pin")

    async def async_press(self) -> None:
        """Remove the PIN.

        A null hash, spelled out rather than left implicit: the TV refuses a `set_pin`
        with no `hash` key at all, so that a truncated command cannot quietly strip the
        PIN off a television.

        Still refused while the set is asleep, unlike the rule write on the button
        above. A PIN is a command: the parent who pressed this would believe the
        television has no PIN, and find out otherwise in front of the lock screen
        (#135).
        """
        if not self._client.available:
            raise ServiceValidationError(
                f"{self._client.name} is not listening; the PIN would stay as it is"
            )
        await self._client.async_send({"op": "set_pin", "hash": None})
