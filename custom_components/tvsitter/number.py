"""The daily limit, as something a parent can set.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TvSitterConfigEntry
from .const import RULE_DAILY_LIMIT
from .coordinator import TvSitterClient
from .entity import TvSitterEntity

SECONDS_PER_MINUTE = 60

# Twelve hours. Not a technical ceiling: a limit longer than a waking day is not a
# limit, and a control that goes to twenty-four is harder to set precisely for no gain.
MAX_MINUTES = 720
STEP_MINUTES = 5


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TvSitterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the daily limit for one TV."""
    async_add_entities([DailyLimitNumber(entry.runtime_data)])


class DailyLimitNumber(TvSitterEntity, NumberEntity):
    """How much screen time the budget day allows.

    Reads the limit the TV says it is enforcing, not the last value sent from here. The
    TV keeps the rules and enforces them offline (D3), so it is the only thing that
    knows what is actually in force. Showing what we last sent would let this disagree
    with the television and look right while doing it.
    """

    _attr_device_class = NumberDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = 0
    _attr_native_max_value = MAX_MINUTES
    _attr_native_step = STEP_MINUTES
    _attr_mode = NumberMode.BOX

    def __init__(self, client: TvSitterClient) -> None:
        """Create the daily limit."""
        super().__init__(client, "daily_limit")

    @property
    def native_value(self) -> float | None:
        """Return the limit in minutes, or None when the TV is enforcing none.

        None rather than zero, for the reason it is None everywhere else here: zero
        minutes is a real setting a parent may mean, and no limit is not it.
        """
        snapshot = self._client.snapshot
        if snapshot is None or snapshot.limit_seconds is None:
            return None
        return snapshot.limit_seconds / SECONDS_PER_MINUTE

    async def async_set_native_value(self, value: float) -> None:
        """Send a new limit to the TV.

        The revision comes back in the next state payload, so the two sides can be seen
        to agree rather than assumed to.

        Refused outright while the TV is not listening. This entity stays readable then,
        because the limit in force is still the limit in force (#90) — but commands are
        never retained, so a limit set now would go nowhere and the box would show a
        number nobody is enforcing. Saying so beats accepting it.
        """
        if not self._client.available:
            raise ServiceValidationError(
                f"{self._client.name} is not listening; the limit would go nowhere"
            )
        await self._client.async_set_rules(
            {RULE_DAILY_LIMIT: int(value * SECONDS_PER_MINUTE)}
        )
