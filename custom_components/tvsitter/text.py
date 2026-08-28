"""Setting the parent PIN, without keeping it.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TvSitterConfigEntry
from .coordinator import TvSitterClient
from .entity import TvSitterEntity
from .parent_pin import LENGTH, hash_pin, is_plausible


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TvSitterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the parent PIN for one TV."""
    async_add_entities([ParentPinText(entry.runtime_data)])


class ParentPinText(TvSitterEntity, TextEntity):
    """The PIN a parent types on the TV to lift a lock by hand.

    Write-only, deliberately. The state stays unknown however many times a PIN is set,
    because returning the PIN would put it in the state machine and from there into the
    recorder database, in clear text, for as long as the history is kept. What is stored
    on the TV is a hash of it, and what is stored here is nothing at all.

    Which means this entity cannot show whether a PIN exists. The `pin_set` binary
    sensor answers that, from what the TV reports.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = TextMode.PASSWORD
    _attr_native_min = LENGTH
    _attr_native_max = LENGTH
    # Anchored at the end as well: Home Assistant matches this with `re.match`, which on
    # its own would accept anything merely starting with digits.
    _attr_pattern = rf"[0-9]{{{LENGTH}}}$"

    def __init__(self, client: TvSitterClient) -> None:
        """Create the parent PIN."""
        super().__init__(client, "parent_pin")

    @property
    def native_value(self) -> str | None:
        """Return nothing, always.

        None keeps the state at unknown. Anything else here would be a PIN in the state
        machine, and the point of hashing it before it leaves is that it is not.
        """
        return None

    async def async_set_value(self, value: str) -> None:
        """Hash the PIN and send the result to the TV.

        The PIN does not reach MQTT: what goes out is the digest and the parameters used
        to derive it. A null hash removes the PIN, which is what the clear-PIN button
        sends — this one only ever sets.
        """
        if not is_plausible(value):
            # Reached only by a caller bypassing the pattern, but the alternative is
            # storing a hash of something nobody can type on a television.
            raise ServiceValidationError(f"a PIN is {LENGTH} digits")
        if not self._client.available:
            # Worse than most: a parent who believes the television has a new PIN, and
            # finds out in front of the lock screen that it never arrived.
            raise ServiceValidationError(
                f"{self._client.name} is not listening; the PIN would not arrive"
            )
        await self._client.async_send({"op": "set_pin", "hash": hash_pin(value)})
