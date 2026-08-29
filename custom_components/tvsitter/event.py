"""A child asking for more time, as something an automation can answer.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import logging
from typing import ClassVar

import voluptuous as vol

from homeassistant.components.event import EventEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TvSitterConfigEntry
from .const import (
    ALERT_KINDS,
    ALERT_UNKNOWN,
    ATTR_MINUTES,
    ATTR_REQUEST_ID,
    KIND_MORE_TIME,
    SERVICE_DENY_TIME,
    SERVICE_GRANT_TIME,
)
from .coordinator import TvSitterClient
from .entity import TvSitterEntity
from .models import Alert, TimeRequest

_LOGGER = logging.getLogger(__name__)

# Four hours. Not a technical ceiling: past this it is not "a bit more time", it is a
# different evening, and the daily limit is the control for that.
MAX_MINUTES = 240


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TvSitterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the request event for one TV, and the actions that answer it."""
    async_add_entities(
        [TimeRequestEvent(entry.runtime_data), TamperEvent(entry.runtime_data)]
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_GRANT_TIME,
        {
            vol.Required(ATTR_MINUTES): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=MAX_MINUTES)
            ),
            vol.Optional(ATTR_REQUEST_ID): cv.string,
        },
        "async_grant_time",
    )
    platform.async_register_entity_service(
        SERVICE_DENY_TIME,
        {vol.Optional(ATTR_REQUEST_ID): cv.string},
        "async_deny_time",
    )


class TimeRequestEvent(TvSitterEntity, EventEntity):
    """Fires when the child presses "ask a parent for more time" on the TV.

    An event entity rather than a sensor holding the last request, because a request is
    a moment: two identical requests half an hour apart are two questions, where two
    identical state payloads are one state. It also means an automation triggers on the
    asking rather than on a value changing to something it might already have been.
    """

    _attr_event_types: ClassVar[list[str]] = [KIND_MORE_TIME]

    def __init__(self, client: TvSitterClient) -> None:
        """Create the request event."""
        super().__init__(client, "time_request")

    async def async_added_to_hass(self) -> None:
        """Listen for requests as well as for state."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._client.async_add_request_listener(self._handle_request)
        )

    @callback
    def _handle_request(self, request: TimeRequest) -> None:
        """Turn one request into an event."""
        if request.kind not in self.event_types:
            # A newer TV asking for something this build has no name for. Ignored with a
            # line in the log rather than raised: the alternative is an exception inside
            # an MQTT callback, which takes the subscription down with it.
            _LOGGER.warning(
                "%s asked for %s, which this build does not understand",
                self._client.name,
                request.kind,
            )
            return

        self._trigger_event(request.kind, self._details(request))
        self.async_write_ha_state()

    def _details(self, request: TimeRequest) -> dict[str, object]:
        """Describe the request, naming the app when we can be sure which it is."""
        snapshot = self._client.snapshot
        # What the request says, first: the TV resolved that name itself, at the
        # moment of asking. The state payload is only a fallback for a TV that sends
        # no name, and then only when the two agree about which app it was — pairing
        # them up when they disagree names the wrong programme.
        app_name = request.app_name or (
            snapshot.app_name
            if snapshot is not None and snapshot.app_id == request.app_id
            else None
        )
        return {
            "id": request.id,
            "app_id": request.app_id,
            "app_name": app_name,
            "asked_minutes": request.asked_minutes,
        }

    async def async_grant_time(self, minutes: int, req_id: str | None = None) -> None:
        """Give the child the time they asked for, or some of it."""
        await self._client.async_send(
            {"op": "grant", "req_id": self._answering(req_id), "minutes": minutes}
        )

    async def async_deny_time(self, req_id: str | None = None) -> None:
        """Refuse, which the TV shows rather than leaving the child waiting."""
        await self._client.async_send({"op": "deny", "req_id": self._answering(req_id)})

    def _answering(self, req_id: str | None) -> str:
        """Work out which request is being answered.

        A blueprint answering a notification carries the id, because the notification
        was tagged with it. A person pressing a button in the interface does not, and
        the only request they could mean is the last one.
        """
        if req_id:
            return req_id
        last = self._client.last_request
        if last is None:
            raise ServiceValidationError(
                f"{self._client.name} has not asked for more time"
            )
        return last.id


class TamperEvent(TvSitterEntity, EventEntity):
    """Fires when the television reports that somebody has been at it.

    Every tamper signal is one kind on one entity rather than an entity each:
    they are rare,
    they are all the same shape, and a parent wants one automation that says "something
    happened" rather than six that each watch for one thing.

    A kind this build has never heard of still fires. A newer television must be able to
    raise an alarm an older integration can pass on — refusing it would drop exactly the
    message somebody needs.
    """

    _attr_event_types: ClassVar[list[str]] = list(ALERT_KINDS)
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client: TvSitterClient) -> None:
        """Create the tamper event."""
        super().__init__(client, "tamper")

    async def async_added_to_hass(self) -> None:
        """Listen for alarms as well as for state."""
        await super().async_added_to_hass()
        self.async_on_remove(self._client.async_add_alert_listener(self._handle_alert))

    @callback
    def _handle_alert(self, alert: Alert) -> None:
        """Turn one alarm into an event."""
        kind = alert.kind
        if kind not in self.event_types:
            # Shown rather than refused, but under a name this build does understand,
            # because
            # an event entity can only fire a type it declared.
            _LOGGER.warning(
                "%s raised %s, which this build does not know", self._client.name, kind
            )
            kind = ALERT_UNKNOWN
        self._trigger_event(kind, {"id": alert.id, "kind": alert.kind, **alert.detail})
        self.async_write_ha_state()
