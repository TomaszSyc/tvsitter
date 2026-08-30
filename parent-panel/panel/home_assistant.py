"""Everything the panel knows, and every change it makes, through Home Assistant.

The panel never speaks the MQTT contract (D34). It reads Home Assistant's registries and
states, and changes things by calling services — so the integration stays the only thing
publishing to a television, and the revision guard on `set_rules` keeps the single
writer it was built for.

Which entity is which comes from the registry, never from an entity id. Entity ids are
built from translated names — on a Polish Home Assistant the rules sensor is
`sensor.tv_salon_reguly` — so matching on a suffix works in English and silently finds
nothing anywhere else. `platform`, `device_id`, `unique_id` and `translation_key` are
not translated.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from typing import Any

import aiohttp

DOMAIN = "tvsitter"

CORE_API = "http://supervisor/core/api"
CORE_WEBSOCKET = "ws://supervisor/core/websocket"

# The per-app entities carry no translation key: they are named after apps a television
# reported, which no language file knows in advance. They are found by the shape of the
# unique id the integration builds — `<device>_app_<package>` for the sensor, and
# `<device>_app_limit_<package>` for the number beside it.
APP_SENSOR = "_app_"
APP_LIMIT = "_app_limit_"

WEEK = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass(slots=True)
class Television:
    """One television, keyed by its device rather than by its name.

    Two sets called the same thing are still two televisions, and a set that is
    renamed is still the same one.
    """

    device_id: str
    name: str

    # translation key -> entity id, for everything the integration declares.
    entities: dict[str, str] = field(default_factory=dict)

    # package -> {"sensor": entity_id, "limit": entity_id}, for what the set has opened.
    apps: dict[str, dict[str, str]] = field(default_factory=dict)

    states: dict[str, dict[str, Any]] = field(default_factory=dict)

    def entity(self, key: str) -> dict[str, Any] | None:
        """Read one entity whole, or nothing when this set has no such entity."""
        entity_id = self.entities.get(key)
        return None if entity_id is None else self.states.get(entity_id)

    def state(self, key: str) -> str | None:
        """Read what one entity says, or nothing when it has nothing to say."""
        found = self.entity(key)
        if found is None:
            return None
        value = found.get("state")
        return None if value in ("unknown", "unavailable", "") else value

    def number(self, key: str) -> float | None:
        """Read a numeric state. Unset and zero are different things here."""
        value = self.state(key)
        try:
            return None if value is None else float(value)
        except ValueError:
            return None

    def attribute(self, key: str, name: str) -> Any:
        """One attribute of one entity, which is where the rules themselves live."""
        found = self.entity(key)
        return None if found is None else found.get("attributes", {}).get(name)

    def app_name(self, package: str) -> str:
        """Name an app the way the television does, falling back to its package id.

        The label comes from the set and lands in the sensor's friendly name, with the
        device name in front of it because the entity has one. The prefix comes off
        here rather than being asked for separately.
        """
        entity_id = self.apps.get(package, {}).get("sensor")
        if entity_id is None:
            return package
        written = (
            self.states.get(entity_id, {}).get("attributes", {}).get("friendly_name")
        )
        if not written:
            return package
        return (
            written[len(self.name) :].strip()
            if written.startswith(self.name)
            else written
        )

    def app_minutes(self, package: str) -> float:
        """How long an app has been watched today, in minutes."""
        entity_id = self.apps.get(package, {}).get("sensor")
        try:
            return float(self.states.get(entity_id, {}).get("state", 0))
        except (ValueError, TypeError):
            return 0.0

    def app_limit(self, package: str) -> float | None:
        """Read that app's own budget in minutes, or nothing when it has none."""
        entity_id = self.apps.get(package, {}).get("limit")
        try:
            return float(self.states.get(entity_id, {}).get("state"))
        except (ValueError, TypeError):
            return None

    @property
    def rules(self) -> dict[str, Any]:
        """Read the rules the set says it enforces, straight from its own sensor."""
        found = self.entity("rules")
        if found is None:
            return {}
        return {
            key: value
            for key, value in found.get("attributes", {}).items()
            if key != "friendly_name"
        }


class Refused(RuntimeError):
    """A service Home Assistant would not run, and what it said about it."""

    def __init__(self, what: str, why: str | None) -> None:
        """Keep the reason apart from the call, so only the reason is shown."""
        super().__init__(f"{what}: {why}" if why else what)
        self.why = why


def said(body: str) -> str | None:
    """Pull Home Assistant's own sentence out of a refusal.

    It answers with JSON carrying a `message`, and nothing else in it is worth reading.
    A body that is not JSON, or carries no message, gives nothing rather than a page
    full of somebody else's stack trace.
    """
    try:
        message = json.loads(body).get("message")
    except (ValueError, AttributeError):
        return None
    return message.strip() if isinstance(message, str) and message.strip() else None


class HomeAssistant:
    """A client for the Core API, holding one session for the panel's lifetime."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Take a session rather than making one, so shutdown has a single owner."""
        self._session = session
        self._token = os.environ.get("SUPERVISOR_TOKEN", "")

    @property
    def authorised(self) -> bool:
        """Say whether there is a token at all.

        A panel started outside the Supervisor has none, and "no televisions" and
        "nobody let me ask" are different things to put on a page.
        """
        return bool(self._token)

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def televisions(self) -> list[Television]:
        """Find the televisions, and everything each of them is currently saying."""
        registry = await self._registry()
        found = collect(registry["devices"], registry["entities"])
        states = {state["entity_id"]: state for state in await self.states()}
        for television in found:
            television.states = states
        return found

    async def states(self) -> list[dict[str, Any]]:
        """Fetch every entity state Home Assistant currently holds."""
        async with self._session.get(
            f"{CORE_API}/states",
            headers=self._headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as answer:
            answer.raise_for_status()
            return await answer.json()

    async def call(self, domain: str, service: str, data: dict[str, Any]) -> None:
        """Ask Home Assistant to do something.

        Every change the panel makes goes through here. Nothing is evaluated in this
        process and nothing is published to a broker from it — the panel asks, the
        integration writes, the television decides (D25, D34).
        """
        async with self._session.post(
            f"{CORE_API}/services/{domain}/{service}",
            headers=self._headers,
            json=data,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as answer:
            if answer.status >= 400:
                # The sentence Home Assistant wrote, kept apart from the rest. It is the
                # only part worth putting in front of a parent — "TV Salon is not
                # listening" answers the question, and `tvsitter.set_windows was refused
                # by 500` does not. Never a PIN: `set_pin` refuses before it reaches
                # here, precisely because the sentence would carry the value.
                raise Refused(
                    f"{domain}.{service} was refused", said(await answer.text())
                )

    async def _registry(self) -> dict[str, list[dict[str, Any]]]:
        """Read the device and entity registries, which are WebSocket-only.

        One connection for both lists and then closed. Asked on each refresh rather than
        held open: a registry changes when somebody adds a television, which is not
        often enough to keep a socket for.
        """
        async with self._session.ws_connect(
            CORE_WEBSOCKET, timeout=aiohttp.ClientWSTimeout(ws_close=15)
        ) as socket:
            await socket.receive_json()  # auth_required
            await socket.send_json({"type": "auth", "access_token": self._token})
            greeting = await socket.receive_json()
            if greeting.get("type") != "auth_ok":
                raise PermissionError("Home Assistant refused the Supervisor token")

            return {
                "devices": await ask(socket, 1, "config/device_registry/list"),
                "entities": await ask(socket, 2, "config/entity_registry/list"),
            }


async def ask(
    socket: aiohttp.ClientWebSocketResponse, message_id: int, command: str
) -> list[dict[str, Any]]:
    """Send one command and wait for the answer carrying its id.

    Matched on the id rather than taking the next message: the socket also carries
    events, and reading whichever arrives first is how a client comes to believe a
    device list is a state change.
    """
    await socket.send_json({"id": message_id, "type": command})
    while True:
        answer = await socket.receive_json()
        if answer.get("id") != message_id or answer.get("type") != "result":
            continue
        if not answer.get("success", False):
            raise RuntimeError(f"{command} failed: {answer.get('error')}")
        return answer.get("result", [])


def collect(
    devices: list[dict[str, Any]], entities: list[dict[str, Any]]
) -> list[Television]:
    """Group the registry into televisions.

    A pure function, so what the panel finds can be tested without a Home Assistant.
    """
    named = {
        device["id"]: device.get("name_by_user") or device.get("name") or device["id"]
        for device in devices
    }
    found: dict[str, Television] = {}

    for entity in entities:
        if entity.get("platform") != DOMAIN:
            continue
        device_id = entity.get("device_id")
        if device_id is None:
            continue
        television = found.setdefault(
            device_id,
            Television(device_id=device_id, name=named.get(device_id, device_id)),
        )
        key = entity.get("translation_key")
        if key:
            television.entities[key] = entity["entity_id"]
            continue
        remember_app(television, entity)

    return sorted(found.values(), key=lambda television: television.name)


def remember_app(television: Television, entity: dict[str, Any]) -> None:
    """File a per-app entity under the package it belongs to.

    These have no translation key, being named after apps a television reported, so the
    package comes out of the unique id the integration built — the one identifier in the
    whole chain that nothing translates.
    """
    unique = entity.get("unique_id") or ""
    entity_id = entity["entity_id"]
    if APP_LIMIT in unique:
        package = unique.split(APP_LIMIT, 1)[1]
        television.apps.setdefault(package, {})["limit"] = entity_id
    elif APP_SENSOR in unique:
        package = unique.split(APP_SENSOR, 1)[1]
        television.apps.setdefault(package, {})["sensor"] = entity_id
