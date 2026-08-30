"""Asking Home Assistant what it knows about the televisions.

The panel never speaks the MQTT contract (D34). Everything it shows or changes goes
through Home Assistant's own API, so the integration stays the only thing publishing to
the four topics — and the revision guard on `set_rules` keeps the single writer it was
built for.

Which entities belong to a television comes from the registry rather than from their
names. Entity ids are built from translated names — on this house's Home Assistant the
rules sensor is `sensor.tv_salon_reguly`, not `..._rules` — so anything matching on a
suffix works in English and silently finds nothing anywhere else. The registry carries
`platform`, `device_id` and `translation_key`, none of which are translated.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any

import aiohttp

DOMAIN = "tvsitter"

# The Supervisor's own proxy to Home Assistant. Reached by name rather than by address,
# and authorised by a token the Supervisor puts in the environment, so nothing here
# holds a credential of its own.
CORE_API = "http://supervisor/core/api"
CORE_WEBSOCKET = "ws://supervisor/core/websocket"


@dataclass(slots=True)
class Television:
    """One television, as the panel sees it through Home Assistant.

    Keyed by the device rather than by a name, so two sets called the same thing are
    still two televisions, and a set that is renamed is still the same one.
    """

    device_id: str
    name: str

    # By translation key, which is the integration's own word for what an entity is and
    # is the same in every language. Entities without one — the per-app limits, named
    # after apps the television reported — are not what this page asks for.
    entities: dict[str, str] = field(default_factory=dict)

    values: dict[str, str] = field(default_factory=dict)

    def state_of(self, key: str) -> str | None:
        """Read one of this television's entities, or nothing when it has none."""
        entity_id = self.entities.get(key)
        return None if entity_id is None else self.values.get(entity_id)


class HomeAssistant:
    """A client for the Core API, holding one session for the panel's lifetime."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Take a session rather than making one, so shutdown has a single owner."""
        self._session = session
        self._token = os.environ.get("SUPERVISOR_TOKEN", "")

    @property
    def authorised(self) -> bool:
        """Say whether there is a token at all.

        Worth answering separately: a panel started outside the Supervisor has no token,
        and "no televisions" and "nobody let me ask" are different things to put on a
        page.
        """
        return bool(self._token)

    async def televisions(self) -> list[Television]:
        """Find the televisions, and what each of them is currently saying."""
        registry = await self._registry()
        found = collect(registry["devices"], registry["entities"])
        values = {
            state["entity_id"]: state.get("state", "") for state in await self.states()
        }
        for television in found:
            television.values = values
        return found

    async def states(self) -> list[dict[str, Any]]:
        """Fetch every entity state Home Assistant currently holds."""
        async with self._session.get(
            f"{CORE_API}/states",
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as answer:
            answer.raise_for_status()
            return await answer.json()

    async def _registry(self) -> dict[str, list[dict[str, Any]]]:
        """Read the device and entity registries, which are WebSocket-only.

        One connection for both lists and then closed. The panel asks on each page
        rather than holding a subscription: a registry changes when somebody adds a
        television, which is not often enough to keep a socket open for.
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
    """Send one command and wait for the answer that carries its id.

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
    ours = [entity for entity in entities if entity.get("platform") == DOMAIN]
    names = {
        device["id"]: device.get("name_by_user") or device.get("name") or device["id"]
        for device in devices
    }

    found: dict[str, Television] = {}
    for entity in ours:
        device_id = entity.get("device_id")
        if device_id is None:
            continue
        television = found.setdefault(
            device_id,
            Television(device_id=device_id, name=names.get(device_id, device_id)),
        )
        key = entity.get("translation_key")
        if key:
            television.entities[key] = entity["entity_id"]
    return sorted(found.values(), key=lambda television: television.name)
