"""Client for a TV's one-shot pairing endpoint.

The server on the other side is the hand-rolled one in `PairingServer.kt`: a single
POST to `/pair`, sequential, and gone as soon as it accepts. Kept in its own module so
the config flow deals with forms and this deals with the wire.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .broker import BrokerSettings
from .const import PAIRING_PATH, PAIRING_TIMEOUT_S

_LOGGER = logging.getLogger(__name__)

# Mirrors PairResponse.Companion on the TV side. These strings are also translation
# keys, so the form can say what actually went wrong rather than "invalid input".
ERROR_WRONG_PIN = "wrong_pin"
ERROR_EXPIRED = "expired"
ERROR_NO_ATTEMPTS = "no_attempts_left"
ERROR_ALREADY_USED = "already_used"
ERROR_NOT_PAIRING = "pairing_not_active"
ERROR_BAD_REQUEST = "bad_request"

# Ours rather than the TV's: it never answered.
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_UNEXPECTED_RESPONSE = "unexpected_response"


@dataclass(frozen=True, slots=True)
class PairResult:
    """What came back from `/pair`."""

    ok: bool
    error: str | None = None
    attempts_remaining: int | None = None
    device_id: str | None = None
    name: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> PairResult:
        """Read a PairResponse."""
        return cls(
            ok=bool(payload.get("ok")),
            error=payload.get("error"),
            attempts_remaining=payload.get("attempts_remaining"),
            device_id=payload.get("device_id"),
            name=payload.get("name"),
        )


async def async_pair(
    hass: HomeAssistant,
    *,
    host: str,
    port: int,
    pin: str,
    topic_prefix: str,
    broker: BrokerSettings,
) -> PairResult:
    """Send the PIN and the broker settings to a TV, and report what it said."""
    payload = {
        "pin": pin,
        "host": broker.host,
        "port": broker.port,
        "username": broker.username,
        "password": broker.password,
        "topic_prefix": topic_prefix,
        "use_tls": broker.use_tls,
    }
    url = f"http://{host}:{port}{PAIRING_PATH}"
    session = async_get_clientsession(hass)

    try:
        async with asyncio.timeout(PAIRING_TIMEOUT_S):
            # Connection: close because the server accepts one connection at a time and
            # stops listening the moment it accepts a correct PIN. Nothing good comes of
            # holding a keep-alive socket open to a server that is about to disappear.
            response = await session.post(
                url, json=payload, headers={"Connection": "close"}
            )
            async with response:
                body = await response.json(content_type=None)
    except (TimeoutError, aiohttp.ClientError, ValueError) as err:
        # ValueError covers a body that is not JSON, which for this server would mean
        # something other than TV Sitter is answering on that port.
        _LOGGER.debug("Pairing request to %s failed: %s", url, err)
        return PairResult(ok=False, error=ERROR_CANNOT_CONNECT)

    if not isinstance(body, dict):
        _LOGGER.debug("Pairing request to %s returned %r", url, body)
        return PairResult(ok=False, error=ERROR_UNEXPECTED_RESPONSE)

    return PairResult.from_payload(body)
