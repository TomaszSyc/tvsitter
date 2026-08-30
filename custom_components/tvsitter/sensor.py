"""Sensors for TV Sitter.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.schedule.const import DOMAIN as SCHEDULE_DOMAIN
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import TvSitterConfigEntry
from .const import (
    ATTR_DAY,
    ATTR_EXEMPT_APPS,
    ATTR_FOLLOWING_SCHEDULE,
    ATTR_MINUTES,
    ATTR_PACKAGE,
    ATTR_PACKAGES,
    ATTR_PENDING_RULES,
    ATTR_SCHEDULE,
    ATTR_WINDOWS,
    RULE_APP_LIMITS,
    RULE_APPS_ALLOWED,
    RULE_DAYS,
    RULE_WINDOWS,
    SERVICE_FORGET_PENDING_RULES,
    SERVICE_FORGET_SCHEDULE,
    SERVICE_SET_ALLOWED_APPS,
    SERVICE_SET_APP_LIMIT,
    SERVICE_SET_SCHEDULE,
    SERVICE_SET_WINDOWS,
    SERVICE_USE_SCHEDULE,
    WIRE_DAYS,
)
from .coordinator import TvSitterClient
from .entity import TvSitterEntity

_LOGGER = logging.getLogger(__name__)

# Twelve. Enough for what a child actually opens, few enough that a television with a
# shopful of apps installed does not fill the recorder with rows nobody reads.
MAX_APP_SENSORS = 12

SECONDS_PER_MINUTE = 60

# Twelve hours, the same ceiling as the daily limit itself: a day's allowance longer
# than a waking day is not an allowance.
MAX_DAY_MINUTES = 720

# What a window has to say to be one. `id` is a name a parent gives it, and it is what
# `active_window` reports when the lock goes up, so it is worth insisting on.
WINDOW_SCHEMA = vol.Schema(
    {
        vol.Required("id"): cv.string,
        vol.Required("from"): cv.string,
        vol.Required("to"): cv.string,
        vol.Optional("days"): vol.All(cv.ensure_list, [vol.In(WIRE_DAYS)]),
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TvSitterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors for one TV."""
    client = entry.runtime_data
    known_apps: set[str] = set()

    @callback
    def add_apps_that_appeared() -> None:
        """Give a sensor to each package the TV has charged time to.

        Created as they turn up rather than declared in advance, because the list is
        whatever the child opens. The retained state payload arrives before
        this runs on a
        restart, so it is called once immediately as well as on every update
        — waiting for
        a change would leave a television that has been quiet all evening with no app
        sensors at all.
        """
        snapshot = client.snapshot
        if snapshot is None:
            return
        fresh = [package for package in snapshot.per_app if package not in known_apps]
        if not fresh:
            return

        room = MAX_APP_SENSORS - len(known_apps)
        taking, dropped = fresh[:room], fresh[room:]
        if taking:
            known_apps.update(taking)
            async_add_entities([AppUsageSensor(client, package) for package in taking])
        if dropped:
            # Said out loud rather than dropped quietly: a television with fifty apps
            # must
            # not put fifty rows in the recorder, and somebody looking for a missing app
            # should find the reason here instead of assuming it is not being counted.
            _LOGGER.warning(
                "%s: not adding sensors for %s, already at %s apps",
                client.name,
                ", ".join(dropped),
                MAX_APP_SENSORS,
            )

    async_add_entities(
        [
            ActiveAppSensor(client),
            UsedTodaySensor(client),
            RemainingTodaySensor(client),
            RulesSensor(client),
            BonusTodaySensor(client),
            LimitTodaySensor(client),
            LastReportedSensor(client),
            UsedYesterdaySensor(client),
        ]
    )

    add_apps_that_appeared()
    entry.async_on_unload(client.async_add_listener(add_apps_that_appeared))

    # Aimed at the rules sensor, which is the thing that shows what they write. Neither
    # of these is one number, so neither has an entity a parent could simply move.
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_SCHEDULE,
        {
            vol.Required(ATTR_DAY): vol.In(WIRE_DAYS),
            # Absent removes the override and hands the day back to the plain daily
            # limit, which is the documented meaning of a null there. Zero is a real
            # setting — no viewing that day — so it must stay tellable from absent.
            vol.Optional(ATTR_MINUTES): vol.Any(
                None, vol.All(vol.Coerce(float), vol.Range(min=0, max=MAX_DAY_MINUTES))
            ),
        },
        "async_set_schedule",
    )
    platform.async_register_entity_service(
        SERVICE_SET_WINDOWS,
        {vol.Required(ATTR_WINDOWS): vol.All(cv.ensure_list, [WINDOW_SCHEMA])},
        "async_set_windows",
    )
    # The everyday way to give an app a budget is the number beside its sensor. This
    # is for the two things a number cannot say: a budget for an app the television
    # has never opened, and taking a budget away — zero is a block, not an absence.
    platform.async_register_entity_service(
        SERVICE_SET_APP_LIMIT,
        {
            vol.Required(ATTR_PACKAGE): cv.string,
            vol.Optional(ATTR_MINUTES): vol.Any(
                None, vol.All(vol.Coerce(float), vol.Range(min=0, max=MAX_DAY_MINUTES))
            ),
        },
        "async_set_app_limit",
    )
    # Which apps exist for this child at all — a different question from how long each
    # run. An empty list is no restriction rather than a locked television — what
    # every list-shaped rule here means (D27), and the reading that fails recoverably.
    platform.async_register_entity_service(
        SERVICE_SET_ALLOWED_APPS,
        {vol.Required(ATTR_PACKAGES): vol.All(cv.ensure_list, [cv.string])},
        "async_set_allowed_apps",
    )
    # The weekly grid a schedule helper already draws, rather than a second editor here.
    # Home Assistant has the better one and it is built in (#119).
    platform.async_register_entity_service(
        SERVICE_USE_SCHEDULE,
        {vol.Required(ATTR_SCHEDULE): cv.entity_domain(SCHEDULE_DOMAIN)},
        "async_use_schedule",
    )
    # The way back out of the one above. No fields: which helper is being followed is
    # something the entry already knows, and asking for it again would let somebody
    # name the wrong one and be told nothing happened.
    platform.async_register_entity_service(
        SERVICE_FORGET_SCHEDULE,
        None,
        "async_forget_schedule",
    )
    # For a change that is never going to land: a television sold, a prefix retyped.
    # No fields, like the one above and for the same reason — what is waiting is
    # something the entry already knows, and naming it again would only let somebody
    # name the wrong thing and be told nothing happened.
    platform.async_register_entity_service(
        SERVICE_FORGET_PENDING_RULES,
        None,
        "async_forget_pending_rules",
    )


class ActiveAppSensor(TvSitterEntity, SensorEntity):
    """Which app is in the foreground."""

    def __init__(self, client: TvSitterClient) -> None:
        """Create the active app sensor."""
        super().__init__(client, "active_app")

    @property
    def native_value(self) -> str | None:
        """Return the app's display name, including the last one before it went quiet.

        Not a claim that it is playing. "Screen: off" and "Reporting: no" sit beside
        this one, so what it reads as is what was last on — a thing worth knowing, and
        one that unknown threw away (#91). Whether the television is running is a
        question those two answer; answering it here as well only loses the name.
        """
        snapshot = self._client.snapshot
        return None if snapshot is None else snapshot.app_name

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the package id, which is what rules are written against."""
        snapshot = self._client.snapshot
        if snapshot is None:
            return None
        return {
            "app_id": snapshot.app_id,
            "active_window": snapshot.active_window,
            "lock_reason": snapshot.lock_reason,
            "until_s": snapshot.until_seconds,
        }


class UsedTodaySensor(TvSitterEntity, SensorEntity):
    """Screen time used in the current budget day."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_suggested_unit_of_measurement = UnitOfTime.MINUTES
    # The counter resets to zero when the budget day rolls over at 04:00, which is
    # exactly what total_increasing is built for — it reads a drop as a new cycle
    # rather than as negative consumption.
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, client: TvSitterClient) -> None:
        """Create the used-today sensor."""
        super().__init__(client, "used_today")

    @property
    def native_value(self) -> int | None:
        """Return seconds used today."""
        snapshot = self._client.snapshot
        return None if snapshot is None else snapshot.used_seconds

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the per-app breakdown behind the total."""
        snapshot = self._client.snapshot
        if snapshot is None:
            return None
        return {"per_app": snapshot.per_app, "bonus_seconds": snapshot.bonus_seconds}


class RemainingTodaySensor(TvSitterEntity, SensorEntity):
    """Screen time left in the current budget day.

    Unknown rather than zero when no limit applies. Reporting zero would read as
    "time is up" to every automation and dashboard card looking at it.
    """

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_suggested_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, client: TvSitterClient) -> None:
        """Create the remaining-today sensor."""
        super().__init__(client, "remaining_today")

    @property
    def native_value(self) -> int | None:
        """Return seconds remaining, or None when unlimited."""
        snapshot = self._client.snapshot
        return None if snapshot is None else snapshot.remaining_seconds

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Say plainly whether a limit is in force at all."""
        snapshot = self._client.snapshot
        if snapshot is None:
            return None
        return {"limit_active": snapshot.remaining_seconds is not None}


class RulesSensor(TvSitterEntity, SensorEntity):
    """The rules the TV says it is enforcing, and which revision they are.

    The television keeps the rules and enforces them offline (D3), so it is the only
    thing that knows what is in force. Without this, Home Assistant can show the daily
    limit — the state payload carries that one — and nothing else: not the week, not
    the hours, not one app's budget. "Why did it lock at half past seven" is a question
    a schedule invites and a dashboard could not answer.

    Not read-only any more. A schedule and a set of viewing hours are not one number
    each, so they have no honest entity — but leaving them with no control at all meant
    the rules could be counted and never changed (#114). Two actions, aimed at this
    sensor because it is the thing that shows what they write. The one-number rules keep
    their own controls, where a parent can find them without writing an action call.

    The revision is the state, because that is the part that changes meaningfully and
    can be compared with the one the TV echoes in its state payload — the two agreeing
    is the whole point of having a revision at all. It is named for what it is: called
    "Rules", a state of 47 reads as forty-seven rules, which is nothing it has ever
    meant (#115).
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = None

    def __init__(self, client: TvSitterClient) -> None:
        """Create the rules sensor."""
        super().__init__(client, "rules")

    @property
    def native_value(self) -> int | None:
        """Return the revision of the rules in force."""
        snapshot = self._client.snapshot
        return None if snapshot is None else snapshot.rules_rev

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the rules themselves, and which schedule helper is writing the hours.

        The helper belongs here rather than on a sensor of its own because it is the
        reason some of these rules are what they are. A panel drawing its own weekly
        grid needs to know that the next import will overwrite whatever it writes, and
        nothing outside the integration could find that out (D33).

        Shown even before the rules arrive: a helper can be followed while the set is
        asleep, and that is precisely when a grid is most likely to be edited.

        The change still waiting for the television belongs here too. A rule changed
        while the set sleeps is now held rather than refused (#135), and a change
        accepted silently that has not happened yet would be worse than the refusal it
        replaced — so a panel has to be able to say what is waiting, and for which set.
        """
        rules = self._client.rules
        followed = self._client.followed_schedule
        pending = self._client.pending_rules
        snapshot = self._client.snapshot
        exempt = list(snapshot.exempt_apps) if snapshot else []
        if rules is None and followed is None and pending is None and not exempt:
            return None
        attributes = dict(rules or {})
        # This side owns the name outright, which is why the television's is dropped
        # first rather than merely overwritten. The rules are opaque and a set may send
        # a key of any spelling, but only Home Assistant knows what it is following, and
        # a set that could name a helper could make the panel lock a grid nothing is
        # importing. Absent rather than null when none is followed, so "not following"
        # reads as that instead of as a helper that has gone missing.
        attributes.pop(ATTR_FOLLOWING_SCHEDULE, None)
        if followed is not None:
            attributes[ATTR_FOLLOWING_SCHEDULE] = followed
        # The packages a rule cannot reach, from the set that resolved them. Beside the
        # rules because that is what they are about: an app on this list is one no rule
        # written here will ever apply to, so anything drawing a control for it is
        # drawing one that is ignored (D35, #130). The television owns this name — it is
        # the only thing that can answer it — so its value is kept rather than dropped.
        if exempt:
            attributes[ATTR_EXEMPT_APPS] = exempt
        # Dropped before it is set, exactly like the helper above and for the same
        # reason: only Home Assistant knows what it is holding, and a television
        # echoing this word could otherwise promise a panel a change nobody queued.
        # Absent rather than an empty object when nothing waits, so "nothing waiting"
        # cannot be read as a change with nothing in it.
        attributes.pop(ATTR_PENDING_RULES, None)
        if pending is not None:
            attributes[ATTR_PENDING_RULES] = pending
        return attributes

    async def async_set_schedule(self, day: str, minutes: float | None = None) -> None:
        """Give one day of the week its own allowance, or take the override away.

        One day at a time rather than the whole week in one call: a week is seven
        numbers, and an action that takes all seven means retyping the six that are not
        changing, which is how a Saturday quietly loses its limit.
        """
        seconds = None if minutes is None else int(minutes * SECONDS_PER_MINUTE)
        await self._client.async_set_rules({RULE_DAYS: {day: seconds}})

    async def async_set_windows(self, windows: list[dict[str, Any]]) -> None:
        """Say when viewing is allowed at all, or allow it at any hour.

        The whole list, unlike the schedule: windows have no key a parent names, so
        there is nothing to merge onto. An empty list is no restriction rather than a
        closed day — the same reading the engine has had since M4 (D27).
        """
        await self._client.async_set_rules({RULE_WINDOWS: list(windows)})

    async def async_use_schedule(self, schedule: str) -> None:
        """Take the hours from a schedule helper, and keep taking them.

        Home Assistant already has a weekly grid a parent can draw on, with a proper
        editor and no card to install; the rules already carry windows with the days
        they apply on. The two are the same picture, so this reads one and writes the
        other rather than inventing a second editor (#119).

        The helper is remembered, so a later edit to the grid reaches the television
        by itself. A schedule imported once and left to drift would be worse than no
        import at all: the dashboard would show hours the set is not enforcing.

        Unlike the other rule writes, this does not refuse while the set is asleep.
        What it sets up is the following, which is a real and lasting thing to have
        done, and the hours go out on the next reconnect rather than being lost.
        """
        await self._client.async_follow_schedule(schedule)

    async def async_forget_schedule(self) -> None:
        """Stop following the schedule helper, and keep the hours it wrote.

        The way back out of `use_schedule`, which had none. While a helper is followed
        the integration re-imports it whenever it changes, so the panel's own weekly
        grid is read-only then — which left a house that had ever run `use_schedule`
        unable to edit its hours anywhere ever again (D33, amended).

        The rules are not touched. Whatever the last import wrote is what the
        television goes on enforcing, and the only thing that stops is the following:
        clearing an evening's hours as a side effect of pressing "stop" would be the
        second-worst surprise this project can hand a parent.

        The helper is left alone too, so `use_schedule` can point at it again.
        """
        self._client.forget_schedule()

    async def async_set_app_limit(
        self, package: str, minutes: float | None = None
    ) -> None:
        """Give one app its own budget, or take the budget away.

        Leaving the minutes out removes it, which is the one thing the per-app number
        cannot express: zero there means blocked, and blocked is not the same as
        running on the day's allowance.
        """
        seconds = None if minutes is None else int(minutes * SECONDS_PER_MINUTE)
        await self._client.async_set_rules({RULE_APP_LIMITS: {package: seconds}})

    async def async_set_allowed_apps(self, packages: list[str]) -> None:
        """Say which apps this child may open at all, or lift the restriction.

        The whole list every time, like the windows: an allow-list has no key a parent
        names, so there is nothing to merge onto. An empty list allows everything, which
        is not the same as allowing nothing — a rule that fails towards nothing enforced
        is recoverable, and one that fails towards a television nobody can use is a
        parent locked out by a typo.

        Beside the per-app budgets rather than instead of them: a budget says how long,
        this says whether. An app has to pass both, and both are ways of saying no, so
        there is no case where the two disagree (#75).
        """
        await self._client.async_set_rules({RULE_APPS_ALLOWED: list(packages)})

    async def async_forget_pending_rules(self) -> None:
        """Throw away a rule change that is waiting for a television.

        The counterpart of holding one at all. A change held for a set that is never
        coming back — sold, replaced, or addressed by a prefix somebody has since
        retyped — would otherwise sit on the config entry for ever, with this sensor
        promising a panel something that will never happen.

        Nothing is written to the television and nothing already in force is touched:
        this throws away a change that never left, which is the opposite of undoing one
        that did.
        """
        self._client.forget_pending_rules()


class BonusTodaySensor(TvSitterEntity, SensorEntity):
    """Time granted on top of the day's allowance, in the budget day.

    On the wire since M2 and visible only as an attribute until now, which meant
    "how much
    extra did this month cost" could not be answered at all: attributes are not
    recorded as
    statistics. A bonus rather than a reduction of what was used, so the two
    numbers answer
    different questions — this one is what was given, `used_today` is what was watched.
    """

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_suggested_unit_of_measurement = UnitOfTime.MINUTES
    _attr_suggested_display_precision = 0
    # Resets to zero at 04:00 with the budget day, which is what this is for.
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, client: TvSitterClient) -> None:
        """Create the bonus sensor."""
        super().__init__(client, "bonus_today")

    @property
    def native_value(self) -> int | None:
        """Return the seconds granted today."""
        snapshot = self._client.snapshot
        return None if snapshot is None else snapshot.bonus_seconds


class LimitTodaySensor(TvSitterEntity, SensorEntity):
    """The allowance the television is actually enforcing today.

    Not `number.daily_limit`, which is the parent's intention. These differ
    whenever a day
    override is in force, and they differ again the moment a limit is set aside — the
    control still reads what was asked for, and this reads nothing, because nothing is
    being enforced.
    """

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_suggested_unit_of_measurement = UnitOfTime.MINUTES
    _attr_suggested_display_precision = 0
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, client: TvSitterClient) -> None:
        """Create the limit sensor."""
        super().__init__(client, "limit_today")

    @property
    def native_value(self) -> int | None:
        """Return today's limit, or nothing while none is being enforced."""
        snapshot = self._client.snapshot
        return None if snapshot is None else snapshot.limit_seconds


class LastReportedSensor(TvSitterEntity, SensorEntity):
    """When the television last said anything.

    The state payload is retained, so a dashboard shows numbers whether or not
    anything is
    still running. This is how old they are — the one question a retained topic cannot
    answer by itself, and the difference between "the child watched nothing
    today" and "the
    app died at breakfast".
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client: TvSitterClient) -> None:
        """Create the last-reported sensor."""
        super().__init__(client, "last_reported")

    @property
    def native_value(self) -> datetime | None:
        """Return the send time of the last state payload."""
        snapshot = self._client.snapshot
        if snapshot is None or not snapshot.ts:
            return None
        return dt_util.utc_from_timestamp(snapshot.ts / 1000)


class AppUsageSensor(TvSitterEntity, SensorEntity):
    """How long one app has been watched in this budget day.

    One per package rather than a dictionary on another sensor, because
    attributes are not
    recorded as statistics — and "what is he watching all week" is the question a parent
    actually asks, which a graph answers and a tooltip does not.

    The name comes from the television, which is the only thing that can turn a
    package id
    into "YouTube". Read on every update rather than fixed at creation, so a
    label arriving
    later corrects a sensor that was born with an id for a name.
    """

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_suggested_unit_of_measurement = UnitOfTime.MINUTES
    _attr_suggested_display_precision = 0
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, client: TvSitterClient, package: str) -> None:
        """Create a sensor for one package."""
        super().__init__(client, f"app_{package}")
        self._package = package
        # Named rather than translated: there is no translation for "Netflix", and the
        # television is the only side that knows what to call it.
        self._attr_translation_key = None

    @property
    def name(self) -> str:
        """Return the app's label, falling back to its package id."""
        snapshot = self._client.snapshot
        if snapshot is None:
            return self._package
        return snapshot.per_app_names.get(self._package, self._package)

    @property
    def native_value(self) -> int | None:
        """Return the seconds watched today, and zero once the day has rolled over."""
        snapshot = self._client.snapshot
        if snapshot is None:
            return None
        # Absent means the day rolled over and this app has not been opened since,
        # which is
        # zero rather than unknown — the sensor resets with the budget day like its
        # siblings.
        return snapshot.per_app.get(self._package, 0)


class UsedYesterdaySensor(TvSitterEntity, SensorEntity):
    """How long the last closed budget day came to, with the rest of it in attributes.

    So that "yesterday: 2 h 14 of 2 h 30, asked twice, locked once" can be said in one
    template rather than assembled from a recorder query. The graphs come off today's
    numbers; this is for telling somebody about a day that is over.

    A measurement rather than a total, because it is one finished number rather than a
    counter climbing towards a reset.
    """

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_suggested_unit_of_measurement = UnitOfTime.MINUTES
    _attr_suggested_display_precision = 0
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, client: TvSitterClient) -> None:
        """Create the yesterday sensor."""
        super().__init__(client, "used_yesterday")

    @property
    def native_value(self) -> int | None:
        """Return the seconds watched in the last closed day."""
        day = self._client.day
        return None if day is None else day.used_seconds

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Everything else about that day, so one template can say a sentence."""
        day = self._client.day
        if day is None:
            return None
        return {
            "day": day.day,
            "limit_s": day.limit_seconds,
            "bonus_s": day.bonus_seconds,
            "granted_s": day.granted_seconds,
            "lock_count": day.lock_count,
            "per_app": day.per_app,
            "per_app_names": day.per_app_names,
            "requests": day.requests,
        }
