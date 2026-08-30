"""MQTT plumbing: one subscription set per configured TV.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import json
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.schedule.const import (
    DOMAIN as SCHEDULE_DOMAIN,
)
from homeassistant.components.schedule.const import (
    SERVICE_GET as SERVICE_GET_SCHEDULE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_SCHEDULE,
    OP_SET_RULES,
    PAYLOAD_ONLINE,
    QUIET_AFTER_SECONDS,
    RULE_WINDOWS,
    SCHEMA_VERSION,
    SILENCE_CHECK_SECONDS,
    TOPIC_ALERT,
    TOPIC_AVAILABILITY,
    TOPIC_COMMAND,
    TOPIC_DAY,
    TOPIC_REQUEST,
    TOPIC_RULES,
    TOPIC_STATE,
)
from .models import (
    Alert,
    DaySummary,
    StateSnapshot,
    TimeRequest,
    UnsupportedSchemaError,
)
from .schedules import windows_from

_LOGGER = logging.getLogger(__name__)


class TvSitterClient:
    """Holds the last known state of one TV and tells entities when it changes.

    Deliberately not a DataUpdateCoordinator: there is nothing to poll. The TV pushes,
    and the retained `state` topic means the first payload arrives on subscribe rather
    than after a first refresh.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        topic_prefix: str,
        entry: ConfigEntry | None = None,
    ) -> None:
        """Prepare a client for the given topic prefix.

        The entry is optional only so the tests can build a client without one; nothing
        that needs it — remembering which schedule helper to follow — runs without it.
        """
        self._hass = hass
        self.entry = entry
        self._prefix = topic_prefix
        self.name = name
        self.snapshot: StateSnapshot | None = None
        self.rules: dict[str, Any] | None = None
        self.day: DaySummary | None = None
        self.last_alert: Alert | None = None
        self.reporting_stopped = False
        self._schedule_watch: Callable[[], None] | None = None
        self._alert_listeners: list[Callable[[Alert], None]] = []
        self._quiet_timer: Callable[[], None] | None = None
        self._sent_rev = 0
        self.available = False
        # The last request the TV made, so an answer can be addressed without the caller
        # having to carry the id around. A blueprint answering a notification does carry
        # it; a person pressing a button in the interface does not.
        self.last_request: TimeRequest | None = None

        self._listeners: list[Callable[[], None]] = []
        self._request_listeners: list[Callable[[TimeRequest], None]] = []
        self._unsubscribers: list[Callable[[], None]] = []
        self._warned_about_schema = False

    @property
    def device_id(self) -> str:
        """Stable identifier, derived from the topic prefix.

        The prefix is what a TV is addressed by, so two entries cannot share one without
        also sharing their commands — which makes it a sound identity.
        """
        return self._prefix

    async def async_start(self) -> None:
        """Subscribe to the TV's topics."""
        self._unsubscribers.append(
            await mqtt.async_subscribe(
                self._hass, f"{self._prefix}/{TOPIC_STATE}", self._handle_state, qos=0
            )
        )
        self._unsubscribers.append(
            await mqtt.async_subscribe(
                self._hass,
                f"{self._prefix}/{TOPIC_AVAILABILITY}",
                self._handle_availability,
                qos=1,
            )
        )
        # QoS 1, to match the TV: a request that goes missing is a child staring at a
        # screen that says nothing happened.
        self._unsubscribers.append(
            await mqtt.async_subscribe(
                self._hass,
                f"{self._prefix}/{TOPIC_REQUEST}",
                self._handle_request,
                qos=1,
            )
        )
        self._unsubscribers.append(
            await mqtt.async_subscribe(
                self._hass,
                f"{self._prefix}/{TOPIC_ALERT}",
                self._handle_alert,
                qos=1,
            )
        )
        self._unsubscribers.append(
            await mqtt.async_subscribe(
                self._hass,
                f"{self._prefix}/{TOPIC_DAY}",
                self._handle_day,
                qos=1,
            )
        )
        self._unsubscribers.append(
            await mqtt.async_subscribe(
                self._hass,
                f"{self._prefix}/{TOPIC_RULES}",
                self._handle_rules,
                qos=1,
            )
        )
        # Nothing else watches the clock. Availability is the Last Will, and D24
        # measured what
        # that means: a set going to standby holds the network for a minute or two
        # before it
        # flips, so "the app was killed" and "the television is asleep" look identical
        # from
        # there. This is the other half of telling them apart.
        self._quiet_timer = async_track_time_interval(
            self._hass,
            self._check_for_silence,
            timedelta(seconds=SILENCE_CHECK_SECONDS),
        )
        _LOGGER.debug("Subscribed to %s/#", self._prefix)

    async def async_send(self, command: dict[str, Any]) -> None:
        """Send one command to the TV.

        Never retained. That is a rule in docs/mqtt-contract.md rather than a detail: a
        retained `lock` would be replayed to the TV after every broker restart and lock
        it with nobody having asked. QoS 1, because a command that goes missing is worse
        than one that arrives twice.
        """
        await mqtt.async_publish(
            self._hass,
            f"{self._prefix}/{TOPIC_COMMAND}",
            json.dumps(command),
            qos=1,
            retain=False,
        )

    async def async_set_rules(self, rules: dict[str, Any]) -> None:
        """Change some rules, leaving the ones nobody named alone.

        The one way rules are written, because the revision has to come from one place.
        The TV ignores a `set_rules` whose revision is not higher than the one
        it already
        has — that is what stops a redelivered message rolling the rules back — and the
        revision used to be derived from the last state payload at each call site. Two
        changes made before the TV had republished its state therefore computed the same
        number, and the second was dropped on arrival with nothing said anywhere (#72).

        So the highest revision sent from here is remembered, and a burst keeps climbing
        without waiting for a round trip. The TV's own number still wins when
        it is ahead,
        which is what happens after a restart of Home Assistant, or when something else
        has been writing rules.
        """
        await self.async_send(
            {"op": OP_SET_RULES, "rev": self._next_revision(), "rules": rules}
        )

    @property
    def followed_schedule(self) -> str | None:
        """Which schedule helper the hours are being taken from, if any.

        Asked of the config entry every time rather than kept beside it: a second copy
        is one more thing to keep in step, and this one would go stale exactly when it
        mattered — after a restart, with a helper still being followed.
        """
        if self.entry is None:
            return None
        return self.entry.options.get(CONF_SCHEDULE)

    async def async_follow_schedule(self, entity_id: str) -> None:
        """Take the hours from a schedule helper now, and whenever it is edited.

        The entity is remembered on the config entry rather than in memory, so an edit
        made next week still reaches the television. A schedule imported once and left
        to drift would be worse than none at all — the dashboard would show hours the
        set is not enforcing, the failure this project keeps designing against.
        """
        if self.entry is not None:
            self._hass.config_entries.async_update_entry(
                self.entry, options={**self.entry.options, CONF_SCHEDULE: entity_id}
            )
        await self.async_import_schedule(entity_id)
        self.watch_schedule(entity_id)

    @callback
    def watch_schedule(self, entity_id: str | None) -> None:
        """Follow one schedule helper, replacing whatever was being followed before."""
        if self._schedule_watch is not None:
            self._schedule_watch()
            self._schedule_watch = None
        if entity_id is None:
            return
        self._schedule_watch = async_track_state_change_event(
            self._hass, [entity_id], self._schedule_changed
        )

    @callback
    def _schedule_changed(self, event: Any) -> None:
        """Re-read the grid when the helper changes in any way."""
        entity_id = event.data.get("entity_id")
        if entity_id:
            self._hass.async_create_task(self.async_import_schedule(entity_id))

    async def async_import_schedule(self, entity_id: str) -> None:
        """Read the helper's weekly blocks and send them, if they say anything new.

        Nothing is sent when the television already holds these hours. The helper's
        entity changes state at every block boundary — that is what it is for — and a
        write on each would spend a revision to say nothing, several times a day.
        """
        answer = await self._hass.services.async_call(
            SCHEDULE_DOMAIN,
            SERVICE_GET_SCHEDULE,
            {"entity_id": entity_id},
            blocking=True,
            return_response=True,
        )
        grid = (answer or {}).get(entity_id)
        if not isinstance(grid, dict):
            _LOGGER.warning("%s: %s had nothing to read", self.name, entity_id)
            return

        windows = windows_from(grid)
        if self.rules is not None and self.rules.get(RULE_WINDOWS) == windows:
            return
        if not self.available:
            _LOGGER.debug(
                "%s: not listening, leaving %s for later", self.name, entity_id
            )
            return
        _LOGGER.info(
            "%s: taking %s windows from %s", self.name, len(windows), entity_id
        )
        await self.async_set_rules({RULE_WINDOWS: windows})

    def _next_revision(self) -> int:
        """Work out the next revision, from the TV's number and our own."""
        seen = self.snapshot.rules_rev if self.snapshot else 0
        self._sent_rev = max(seen, self._sent_rev) + 1
        return self._sent_rev

    @callback
    def async_stop(self) -> None:
        """Drop every subscription."""
        while self._unsubscribers:
            self._unsubscribers.pop()()

    @callback
    def async_add_request_listener(
        self, handle: Callable[[TimeRequest], None]
    ) -> Callable[[], None]:
        """Register for requests from the TV and hand back the removal callback.

        Separate from the state listeners because a request is a moment rather than a
        value: two identical requests are two events, where two identical state payloads
        are one state.
        """
        self._request_listeners.append(handle)

        @callback
        def remove() -> None:
            self._request_listeners.remove(handle)

        return remove

    @callback
    def async_add_listener(self, update: Callable[[], None]) -> Callable[[], None]:
        """Register an entity for updates and hand back its removal callback."""
        self._listeners.append(update)

        @callback
        def remove() -> None:
            self._listeners.remove(update)

        return remove

    @callback
    def _handle_state(self, message: mqtt.ReceiveMessage) -> None:
        try:
            self.snapshot = StateSnapshot.from_payload(message.payload)
        except UnsupportedSchemaError as err:
            # Warn once. A newer TV against an older integration would otherwise
            # fill the log at the heartbeat rate, hiding whatever else went wrong.
            if not self._warned_about_schema:
                self._warned_about_schema = True
                _LOGGER.warning(
                    "%s speaks payload schema %s; this integration understands %s. "
                    "Update TV Sitter in Home Assistant",
                    self.name,
                    err.found,
                    SCHEMA_VERSION,
                )
            return
        except ValueError, TypeError:
            _LOGGER.warning("Undecodable state payload on %s", message.topic)
            return

        self._notify()

    @callback
    def _handle_request(self, message: mqtt.ReceiveMessage) -> None:
        try:
            request = TimeRequest.from_payload(message.payload)
        except UnsupportedSchemaError as err:
            _LOGGER.warning(
                "%s asked for time with payload schema %s; this build understands %s. "
                "Update TV Sitter in Home Assistant",
                self.name,
                err.found,
                SCHEMA_VERSION,
            )
            return
        except ValueError, TypeError:
            # Not warned once and then swallowed, unlike the state topic: a request is
            # a child waiting for an answer, and every one of them is worth a line.
            _LOGGER.warning("Undecodable request payload on %s", message.topic)
            return

        self.last_request = request
        for handle in list(self._request_listeners):
            handle(request)

    @callback
    def _handle_alert(self, message: mqtt.ReceiveMessage) -> None:
        """Take an alarm and pass it on once."""
        try:
            alert = Alert.from_payload(message.payload)
        except UnsupportedSchemaError as newer:
            _LOGGER.warning("%s raised an alarm from schema %s", self.name, newer.found)
            return
        except ValueError, TypeError:
            _LOGGER.warning("%s raised an alarm that cannot be read", self.name)
            return

        _LOGGER.info("%s raised %s", self.name, alert.kind)
        self.last_alert = alert
        for handle in list(self._alert_listeners):
            handle(alert)

    @callback
    def async_add_alert_listener(
        self, handle: Callable[[Alert], None]
    ) -> Callable[[], None]:
        """Listen for alarms.

        A moment, like a request, rather than a value an entity re-reads.
        """
        self._alert_listeners.append(handle)

        @callback
        def remove() -> None:
            self._alert_listeners.remove(handle)

        return remove

    @callback
    def _check_for_silence(self, _now: datetime) -> None:
        """Notice that the television has stopped saying anything.

        Deliberately does not touch availability: a quiet set still has a
        last known state
        worth showing, and blanking every entity would hide the very
        evidence somebody is
        looking at.
        """
        snapshot = self.snapshot
        quiet = False
        if snapshot is not None and snapshot.ts:
            age = dt_util.utcnow().timestamp() - snapshot.ts / 1000
            quiet = age > QUIET_AFTER_SECONDS
        if quiet == self.reporting_stopped:
            return
        self.reporting_stopped = quiet
        _LOGGER.log(
            logging.WARNING if quiet else logging.INFO,
            "%s has %s",
            self.name,
            "stopped reporting" if quiet else "started reporting again",
        )
        self._notify()

    @callback
    def _handle_day(self, message: mqtt.ReceiveMessage) -> None:
        """Take the last closed budget day.

        Notified like state rather than like a request, because it is
        retained: it arrives
        again on every reconnect and an entity holds it, where a request is
        a moment that
        happens once.
        """
        try:
            self.day = DaySummary.from_payload(message.payload)
        except UnsupportedSchemaError as newer:
            _LOGGER.warning(
                "%s sent a day summary from schema %s", self.name, newer.found
            )
            return
        except ValueError, TypeError:
            _LOGGER.warning("%s sent a day summary that cannot be read", self.name)
            return
        self._notify()

    @callback
    def _handle_rules(self, message: mqtt.ReceiveMessage) -> None:
        """Take the rules the TV says it is enforcing.

        Kept as they arrive rather than parsed into fields. The engine owns their shape
        and the contract keeps them opaque on purpose, so a rule this build has never
        heard of is still visible to whoever is looking at the dashboard.
        """
        try:
            rules = json.loads(message.payload)
        except ValueError, TypeError:
            _LOGGER.warning("%s sent rules that are not JSON", self.name)
            return
        if not isinstance(rules, dict):
            _LOGGER.warning("%s sent rules that are not an object", self.name)
            return
        self.rules = rules
        self._notify()

    @callback
    def _handle_availability(self, message: mqtt.ReceiveMessage) -> None:
        was = self.available
        self.available = message.payload.strip() == PAYLOAD_ONLINE
        _LOGGER.debug("%s is %s", self.name, "online" if self.available else "offline")
        # A grid edited while the set was asleep is sent now. Without this the schedule
        # and the television drift apart in silence, which is the failure the whole
        # follow-the-helper arrangement exists to avoid.
        followed = self.followed_schedule
        if self.available and not was and followed:
            self._hass.async_create_task(self.async_import_schedule(followed))
        self._notify()

    @callback
    def _notify(self) -> None:
        for update in list(self._listeners):
            update()
