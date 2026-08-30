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
    CONF_PENDING_RULES,
    CONF_SCHEDULE,
    MAX_MERGE_DEPTH,
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


def merge_pending(
    earlier: dict[str, Any], later: dict[str, Any], depth: int = 1
) -> dict[str, Any]:
    """Fold two waiting `set_rules` deltas into one that means both, the later winning.

    Not the television's merge, and the difference is the whole reason this is written
    out rather than borrowed. `Rules.merge` folds a delta into the rules *in force*,
    where a `null` is an instruction to remove a key and so leaves nothing behind. Here
    both sides are deltas and neither has met the rules yet, so a `null` is a removal
    still on its way and is carried as a value. Folding it the television's way would
    turn "set the limit, then clear it" into an empty payload — and an empty payload
    changes nothing, so the limit would stand.

    Everything else matches D26, because what this builds is read by that merge: objects
    fold key by key, so two apps' budgets cannot displace each other; arrays and scalars
    replace whole, because a window in a list has no key to merge on; and it stops
    folding at the depth the set stops merging at.

    The one composition it cannot express is a `null` on a container followed by keys
    inside it — "clear every app budget, then give Netflix half an hour" needs two
    payloads, since a delta can either clear a container or reach into it. The later
    word wins there, which keeps the change somebody made last. Nothing here writes that
    shape: every rule key this integration sends has a fixed one, and the only nulls it
    sends sit on scalars or on keys inside a container.
    """
    folded = dict(earlier)
    for key, value in later.items():
        standing = folded.get(key)
        deep = isinstance(value, dict) and isinstance(standing, dict)
        folded[key] = (
            merge_pending(standing, value, depth + 1)
            if deep and depth < MAX_MERGE_DEPTH
            else value
        )
    return folded


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
        # A rule change made while the set was asleep, waiting for it to say hello.
        # Read back from the entry here rather than when the first change is made, so a
        # restart picks it up before anything can fold a second change onto nothing.
        self._pending_rules: dict[str, Any] | None = self._restore_pending()
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

        Held rather than refused while the set is not listening (#135). The refusal
        was right about the wire and wrong about the product: `<p>/cmd` is not retained,
        so a `set_rules` published now really would be lost — but the answer to that is
        to send it when the set comes back, not to tell a parent who has just drawn a
        week to come back later. A rule is a state somebody wants the television to be
        in, and it is still wanted an hour later.

        Only rules come this way. A command is a moment — a lock, an unlock, a grant, a
        sleep timer armed for tonight — and one replayed on Thursday is a television
        locking itself at breakfast for a reason nobody remembers. That is the line D30
        drew when it made the sleep timer a command rather than a rule.
        """
        if not self.available:
            self._hold(rules)
            return
        await self._publish_rules(rules)

    async def _publish_rules(self, rules: dict[str, Any]) -> None:
        """Put one rules delta on the wire, taking its revision as it goes.

        The one place a revision is spent, which is what keeps the guard working: a
        number reserved when a change was held could be overtaken while the set slept —
        by the television editing its own rules (D31), or by a second thing writing them
        — and would arrive too low to be accepted, with nothing said anywhere.
        """
        await self.async_send(
            {"op": OP_SET_RULES, "rev": self._next_revision(), "rules": rules}
        )

    @property
    def pending_rules(self) -> dict[str, Any] | None:
        """The change waiting for the television, or nothing when none is.

        Read by the rules sensor, so a panel can say what has been accepted and has not
        yet happened. Silently accepting a change that has not happened would be worse
        than the refusal this replaced.
        """
        return self._pending_rules

    @callback
    def _hold(self, rules: dict[str, Any]) -> None:
        """Keep a change until the set is listening, folding it into whatever waits.

        Folded rather than stacked. They are deltas of one object, so three edits become
        one payload and one revision — where a queue of them would spend a revision each
        to arrive in an order nothing guarantees. `merge_pending` says what the folding
        does, and where it differs from the television's own.
        """
        waiting = self._pending_rules
        self._pending_rules = (
            dict(rules) if waiting is None else merge_pending(waiting, rules)
        )
        self._remember_pending()
        _LOGGER.info(
            "%s is not listening; holding %s until it is",
            self.name,
            ", ".join(sorted(self._pending_rules)),
        )
        self._notify()

    async def async_send_pending_rules(self) -> None:
        """Send the change that was waiting for the television.

        Cleared as it goes rather than when the set confirms, which is the bargain
        the lock switch already struck: the holding exists to survive the wait, and
        after that the television's own reports are the truth again. It also means a
        change the set declines cannot become a payload resent for ever.

        Once it is on the wire, though, and not before. A broker refusing the publish is
        the one moment where "sent" and "asked for" come apart, and dropping a week
        somebody drew because the broker hiccuped would be this feature failing at the
        only job it has.
        """
        rules = self._pending_rules
        if rules is None:
            return
        _LOGGER.info(
            "%s is back; sending the %s that was waiting",
            self.name,
            ", ".join(sorted(rules)),
        )
        await self._publish_rules(rules)
        # Unless something was held again while that was in flight, which means the set
        # dropped off mid-publish. That change is somebody's and has not been sent.
        if self._pending_rules is rules:
            self._pending_rules = None
            self._remember_pending()
        self._notify()

    @callback
    def forget_pending_rules(self) -> None:
        """Throw away a change waiting for a television that is not coming back.

        A set sold or a prefix retyped leaves a change that can never land, and without
        this it sits on the entry for ever with the panel promising it.

        Doing nothing when nothing is waiting is the point rather than an oversight, for
        the reason `forget_schedule` gives: an action that can fail for having already
        happened is one nobody dares press. The entry is cleared whatever memory holds,
        so a stored change this build would not restore — one written against another
        payload schema — is got rid of by the same button.
        """
        self._pending_rules = None
        self._remember_pending()
        self._notify()

    @callback
    def _remember_pending(self) -> None:
        """Write what is waiting to the config entry, or take it off again.

        The entry rather than a restored entity state: a rules delta is not one value an
        entity could carry back, and a parent who drew a week must not lose it because
        Home Assistant updated overnight. The payload schema travels with it, because a
        delta only means anything against the contract it was written for.
        """
        if self.entry is None:
            return
        options = {
            key: value
            for key, value in self.entry.options.items()
            if key != CONF_PENDING_RULES
        }
        if self._pending_rules is not None:
            options[CONF_PENDING_RULES] = {
                "schema": SCHEMA_VERSION,
                "rules": self._pending_rules,
            }
        # Writing the same options back is not free — it wakes every listener on the
        # entry and rewrites the store — and forgetting a change that was never there is
        # the common case, since a panel offering the button cannot know what waits.
        if dict(self.entry.options) == options:
            return
        self._hass.config_entries.async_update_entry(self.entry, options=options)

    def _restore_pending(self) -> dict[str, Any] | None:
        """Pick up a change left waiting by a Home Assistant that has restarted.

        Refused rather than guessed at when it was stored against another payload
        schema, for the reason every payload reader here refuses one: past that point
        the meaning of the keys cannot be assumed, and a rules delta that means
        something else is a television enforcing something nobody asked for. Said out
        loud, because the cost of dropping it is a week somebody has to draw again — and
        left on the entry, so `forget_pending_rules` is what finally clears it.
        """
        stored = self.entry.options.get(CONF_PENDING_RULES) if self.entry else None
        if stored is None:
            return None
        schema = stored.get("schema") if isinstance(stored, dict) else None
        rules = stored.get("rules") if isinstance(stored, dict) else None
        if schema != SCHEMA_VERSION or not isinstance(rules, dict):
            _LOGGER.warning(
                "%s: a rule change was waiting, stored for payload schema %s where "
                "this build speaks %s. It has not been sent; make the change again",
                self.name,
                schema,
                SCHEMA_VERSION,
            )
            return None
        _LOGGER.debug("%s: picked up a rule change that was waiting", self.name)
        return dict(rules)

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
    def forget_schedule(self) -> None:
        """Stop taking the hours from a helper, and leave the hours themselves alone.

        The windows the helper last wrote stay in force. Undoing them would be a second
        decision nobody asked for, and the reason somebody stops the following is
        usually that they want to keep this evening's hours and edit them by hand — the
        panel's grid is read-only while a helper is followed, because the next import
        would silently paint over it (D33, amended).

        Doing nothing when nothing is followed is the point rather than an oversight: a
        button offered in a panel cannot know what the entry holds, and an action that
        can fail for having already happened is one nobody dares press.
        """
        # The watch first, then the entry. Both are callbacks with no await between
        # them, so no state change can slip in and re-import against a stale option.
        self.watch_schedule(None)
        if self.entry is None or CONF_SCHEDULE not in self.entry.options:
            return
        options = {
            key: value
            for key, value in self.entry.options.items()
            if key != CONF_SCHEDULE
        }
        self._hass.config_entries.async_update_entry(self.entry, options=options)
        # And say so. Everything else that changes what an entity shows arrives as a
        # payload and notifies on the way past; this one changes an option, and without
        # this the rules sensor keeps publishing the helper it is no longer following
        # until the next payload happens along. The panel reads that attribute to decide
        # whether its grid is editable, so the button reported success and the grid
        # stayed dead — which is exactly how it was found.
        self._notify()

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
            # Left for the reconnect rather than held like a rule change, and the
            # difference matters: this is a copy of a grid that may be drawn on again
            # before the set wakes. Re-reading the helper then gives the hours as they
            # are, where a held payload would give the hours as they were.
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
        # Everything that was waiting on the set goes now. Without this the rules and
        # the television drift apart in silence, which is the failure the whole
        # arrangement exists to avoid.
        followed = self.followed_schedule
        if self.available and not was:
            # The held change first, because it is what somebody actually asked for and
            # nothing else remembers it. The helper second, so a grid edited since has
            # the last word on the hours — which is what following one means.
            if self._pending_rules is not None:
                self._hass.async_create_task(self.async_send_pending_rules())
            if followed:
                self._hass.async_create_task(self.async_import_schedule(followed))
        self._notify()

    @callback
    def _notify(self) -> None:
        for update in list(self._listeners):
            update()
