"""MQTT plumbing: one subscription set per configured TV.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from collections.abc import Callable
import logging

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback

from .const import (
    PAYLOAD_ONLINE,
    SCHEMA_VERSION,
    TOPIC_AVAILABILITY,
    TOPIC_STATE,
)
from .models import StateSnapshot, UnsupportedSchemaError

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
        self.available = False

        self._listeners: list[Callable[[], None]] = []
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
        _LOGGER.debug("Subscribed to %s/#", self._prefix)

    @callback
    def async_stop(self) -> None:
        """Drop every subscription."""
        while self._unsubscribers:
            self._unsubscribers.pop()()

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
        except (ValueError, TypeError):
            _LOGGER.warning("Undecodable state payload on %s", message.topic)
            return

        self._notify()

    @callback
    def _handle_availability(self, message: mqtt.ReceiveMessage) -> None:
        self.available = message.payload.strip() == PAYLOAD_ONLINE
        _LOGGER.debug("%s is %s", self.name, "online" if self.available else "offline")
        self._notify()

    @callback
    def _notify(self) -> None:
        for update in list(self._listeners):
            update()
