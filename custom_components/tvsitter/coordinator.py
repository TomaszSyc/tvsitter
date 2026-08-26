"""MQTT plumbing: one subscription set per configured TV.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from collections.abc import Callable
import json
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback

from .const import (
    OP_SET_RULES,
    PAYLOAD_ONLINE,
    SCHEMA_VERSION,
    TOPIC_AVAILABILITY,
    TOPIC_COMMAND,
    TOPIC_REQUEST,
    TOPIC_STATE,
)
from .models import StateSnapshot, TimeRequest, UnsupportedSchemaError

_LOGGER = logging.getLogger(__name__)


class TvSitterClient:
    """Holds the last known state of one TV and tells entities when it changes.

    Deliberately not a DataUpdateCoordinator: there is nothing to poll. The TV pushes,
    and the retained `state` topic means the first payload arrives on subscribe rather
    than after a first refresh.
    """

    def __init__(self, hass: HomeAssistant, name: str, topic_prefix: str) -> None:
        """Prepare a client for the given topic prefix."""
        self._hass = hass
        self._prefix = topic_prefix
        self.name = name
        self.snapshot: StateSnapshot | None = None
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
    def _handle_availability(self, message: mqtt.ReceiveMessage) -> None:
        self.available = message.payload.strip() == PAYLOAD_ONLINE
        _LOGGER.debug("%s is %s", self.name, "online" if self.available else "offline")
        self._notify()

    @callback
    def _notify(self) -> None:
        for update in list(self._listeners):
            update()
