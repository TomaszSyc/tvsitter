"""The daily limit, as something a parent can set.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TvSitterConfigEntry
from .const import (
    RULE_APP_LIMITS,
    RULE_DAILY_LIMIT,
    RULE_DAYS,
    RULE_WARN_BEFORE,
    WIRE_DAYS,
)
from .coordinator import TvSitterClient
from .entity import TvSitterEntity

LOGGER = logging.getLogger(__name__)

SECONDS_PER_MINUTE = 60

# Twelve hours. Not a technical ceiling: a limit longer than a waking day is not a
# limit, and a control that goes to twenty-four is harder to set precisely for no gain.
MAX_MINUTES = 720
STEP_MINUTES = 5

# An hour. A warning further out than that is not a warning, it is a weather forecast.
MAX_WARNING_MINUTES = 60

# The television's own default, in minutes, used when nobody has ever set one.
DEFAULT_WARNING_MINUTES = 5

# Four hours. Past that it is not "finish this and go to bed", it is tomorrow's problem,
# and the daily limit is the control for that.
MAX_SLEEP_MINUTES = 240

# The same ceiling as the per-app sensors, for the same reason: a television with a
# shopful of apps must not fill the interface with rows nobody set.
MAX_APP_LIMITS = 12


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TvSitterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the daily limit for one TV."""
    client = entry.runtime_data
    async_add_entities(
        [DailyLimitNumber(client), WarnBeforeNumber(client), SleepTimerNumber(client)]
        + [DayLimitNumber(client, day) for day in WIRE_DAYS]
    )

    known: set[str] = set()

    @callback
    def add_limits_for_apps_that_appeared() -> None:
        """Give every app the television has seen a limit somebody can move.

        The same machinery as the per-app sensors, and for the same reason: the list is
        whatever the child opens, so it cannot be declared in advance.
        Without this the only
        way to give Netflix half an hour was a hand-written payload (#114).
        """
        snapshot = client.snapshot
        if snapshot is None:
            return
        fresh = [package for package in snapshot.per_app if package not in known]
        if not fresh:
            return
        room = MAX_APP_LIMITS - len(known)
        taking, dropped = fresh[:room], fresh[room:]
        if taking:
            known.update(taking)
            async_add_entities([AppLimitNumber(client, package) for package in taking])
        if dropped:
            LOGGER.warning(
                "%s: not adding limits for %s, already at %s apps",
                client.name,
                ", ".join(dropped),
                MAX_APP_LIMITS,
            )

    add_limits_for_apps_that_appeared()
    entry.async_on_unload(client.async_add_listener(add_limits_for_apps_that_appeared))


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


class WarnBeforeNumber(TvSitterEntity, NumberEntity):
    """How long before the end the TV says so, and zero for not saying it at all.

    Absent and zero mean opposite things here, the reverse of the daily limit and worth
    stating: somebody who has never touched this should still get a warning, so
    an absent
    rule is the default rather than silence. Zero reads naturally as "no time before the
    end", which is when no warning appears.

    The engine takes a list — a quarter of an hour and then five minutes is a
    thing people
    want — and this control writes one. Setting it therefore collapses a ladder
    to a single
    warning, which is why the whole list is in the attributes: a parent who set
    two from an
    automation can see that this box shows only the nearest.
    """

    _attr_native_min_value = 0
    _attr_native_max_value = MAX_WARNING_MINUTES
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, client: TvSitterClient) -> None:
        """Create the warning control."""
        super().__init__(client, "warn_before")

    @property
    def native_value(self) -> float | None:
        """Return the nearest warning, in minutes."""
        thresholds = self._thresholds()
        if thresholds is None:
            return None
        return min(thresholds) / SECONDS_PER_MINUTE if thresholds else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Show the whole ladder when there is more than one rung."""
        thresholds = self._thresholds()
        if not thresholds or len(thresholds) < 2:
            return None
        return {"all_warnings_s": sorted(thresholds, reverse=True)}

    def _thresholds(self) -> list[int] | None:
        """Read the thresholds in force, or None while the TV has not said."""
        rules = self._client.rules
        if rules is None:
            return None
        if RULE_WARN_BEFORE not in rules:
            return [DEFAULT_WARNING_MINUTES * SECONDS_PER_MINUTE]
        raw = rules[RULE_WARN_BEFORE]
        if isinstance(raw, int):
            return [raw]
        if not isinstance(raw, list):
            return None
        return [item for item in raw if isinstance(item, int)]

    async def async_set_native_value(self, value: float) -> None:
        """Set one warning, or none at all."""
        if not self._client.available:
            raise ServiceValidationError(
                f"{self._client.name} is not listening; the change would go nowhere"
            )
        seconds = int(value * SECONDS_PER_MINUTE)
        await self._client.async_set_rules(
            {RULE_WARN_BEFORE: [] if seconds <= 0 else [seconds]}
        )


class SleepTimerNumber(TvSitterEntity, NumberEntity):
    """Minutes until the television locks itself tonight, and zero for not tonight.

    One evening's decision rather than a rule, so it is not stored with them and
    does not
    survive the night. It is a command, and the television keeps the deadline in
    the same
    device-encrypted corner as a granted-time stand-down — a deadline a child would most
    like to lose is one they could otherwise lose by pulling the plug.

    Write-only, like the parent PIN. The state payload does not carry the
    deadline, and a
    box that read back the minutes remaining would need the television to be
    publishing a
    countdown it has no other use for. What it does carry is `until_s`, which
    says the same
    thing when the timer is the rule that binds.
    """

    _attr_native_min_value = 0
    _attr_native_max_value = MAX_SLEEP_MINUTES
    _attr_native_step = 5
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_mode = NumberMode.BOX

    def __init__(self, client: TvSitterClient) -> None:
        """Create the sleep timer."""
        super().__init__(client, "sleep_timer")

    @property
    def native_value(self) -> float | None:
        """Return nothing: this is a control, not a reading."""
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Arm the timer, or cancel one already set."""
        if not self._client.available:
            raise ServiceValidationError(
                f"{self._client.name} is not listening; nothing would be armed"
            )
        await self._client.async_send({"op": "lock", "in_minutes": int(value)})


class AppLimitNumber(TvSitterEntity, NumberEntity):
    """How long one app may be watched in a day, and zero to block it outright.

    A control rather than a payload. The engine has understood per-app budgets since
    M4, and the only way to set one was a hand-written `set_rules` — not a thing
    anybody does from a sofa (#114).

    Zero is the block, exactly as it is everywhere else here: one mechanism rather than
    two, and it keeps the convention that zero is a real setting, not a missing one.

    Unset means the app has no budget of its own and runs on the day's. That is not the
    same as zero, so an unset limit reads as nothing rather than as a number.
    """

    _attr_native_min_value = 0
    _attr_native_max_value = MAX_MINUTES
    _attr_native_step = STEP_MINUTES
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, client: TvSitterClient, package: str) -> None:
        """Create the limit for one package."""
        super().__init__(client, f"app_limit_{package}")
        self._package = package
        self._attr_translation_key = None

    @property
    def name(self) -> str:
        """Return the app's label with what this is: the bare name is the sensor."""
        snapshot = self._client.snapshot
        label = (
            snapshot.per_app_names.get(self._package, self._package)
            if snapshot
            else self._package
        )
        return f"{label} limit"

    @property
    def native_value(self) -> float | None:
        """Return this app's own budget, or nothing when it has none."""
        rules = self._client.rules
        if rules is None:
            return None
        limits = rules.get(RULE_APP_LIMITS)
        if not isinstance(limits, dict):
            return None
        seconds = limits.get(self._package)
        return None if not isinstance(seconds, int) else seconds / SECONDS_PER_MINUTE

    async def async_set_native_value(self, value: float) -> None:
        """Give this app its own budget, or take it away."""
        if not self._client.available:
            raise ServiceValidationError(
                f"{self._client.name} is not listening; the change would go nowhere"
            )
        await self._client.async_set_rules(
            {RULE_APP_LIMITS: {self._package: int(value * SECONDS_PER_MINUTE)}}
        )


class DayLimitNumber(TvSitterEntity, NumberEntity):
    """One day of the week's own allowance, instead of the plain daily limit.

    Seven of them, declared rather than discovered: the week is the same seven days on
    every television, so unlike the per-app limits there is nothing to wait and see.

    A week is not one number, but a day is — the argument that gave every app a
    control of its own, unchanged. The dashboard used to send a parent to an action
    to give Saturday two hours, which is not what anybody opens a dashboard for (#119).

    Nothing set means this day takes the plain daily limit, which is not the same as
    zero — zero is a real setting and means no viewing that day. A number cannot say
    "nothing", so removing an override stays with `tvsitter.set_schedule`.
    """

    _attr_native_min_value = 0
    _attr_native_max_value = MAX_MINUTES
    _attr_native_step = STEP_MINUTES
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, client: TvSitterClient, day: str) -> None:
        """Create the allowance for one day of the week."""
        super().__init__(client, f"limit_{day}")
        self._day = day

    @property
    def native_value(self) -> float | None:
        """Return this day's own allowance, or nothing when it has none."""
        rules = self._client.rules
        if rules is None:
            return None
        days = rules.get(RULE_DAYS)
        if not isinstance(days, dict):
            return None
        seconds = days.get(self._day)
        return None if not isinstance(seconds, int) else seconds / SECONDS_PER_MINUTE

    async def async_set_native_value(self, value: float) -> None:
        """Give this day its own allowance."""
        if not self._client.available:
            raise ServiceValidationError(
                f"{self._client.name} is not listening; the change would go nowhere"
            )
        await self._client.async_set_rules(
            {RULE_DAYS: {self._day: int(value * SECONDS_PER_MINUTE)}}
        )
