"""What to tell a TV about the MQTT broker.

Home Assistant already knows where its broker is, so pairing should not ask anyone
to type it again. The catch is that what it knows is not always usable from a TV.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import socket

from homeassistant.const import CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# The key the MQTT integration stores its broker address under.
DATA_BROKER = "broker"

DEFAULT_PORT = 1883

# Addresses that work from inside Home Assistant and nowhere else. The Mosquitto add-on
# is reached as `core-mosquitto` over Supervisor's own container network, so that is
# what the MQTT config entry holds on a normal Home Assistant OS install. Handing it to
# a television produces one that can never connect, after a pairing that looked like it
# worked. Worth catching here rather than in somebody's bug report.
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})
SUPERVISOR_PREFIXES = ("core-", "core_", "addon-", "addon_", "hassio")


@dataclass(frozen=True, slots=True)
class BrokerSettings:
    """Broker details as a TV should be told them."""

    host: str
    port: int
    username: str
    password: str
    use_tls: bool = False

    @property
    def is_complete(self) -> bool:
        """Whether there is enough here to hand to a TV."""
        return bool(self.host)


def is_unreachable_from_elsewhere(host: str) -> bool:
    """Whether `host` only means anything inside Home Assistant's own network."""
    lowered = host.strip().lower()
    if not lowered:
        return True
    if lowered in LOOPBACK_HOSTS:
        return True
    return lowered.startswith(SUPERVISOR_PREFIXES)


def _local_address_towards(host: str, port: int) -> str | None:
    """Return the local address the routing table would use to reach `host`.

    A connected UDP socket sends nothing; it only asks the kernel which interface it
    would go out of. That answer is the address of this machine the TV can talk back to,
    which beats any configured URL as a default: it comes from the same network path the
    TV was just discovered over.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((host, port))
        return str(sock.getsockname()[0])
    except OSError as err:
        _LOGGER.debug("Could not work out the local address towards %s: %s", host, err)
        return None
    finally:
        sock.close()


async def async_broker_settings_for(
    hass: HomeAssistant, tv_host: str
) -> BrokerSettings | None:
    """Read Home Assistant's own MQTT config entry and adapt it for the TV at `tv_host`.

    Credentials and port are taken as they are. The address is replaced when it only
    resolves inside Home Assistant, and left alone when it is a real one somebody
    configured on purpose.
    """
    entries = hass.config_entries.async_entries("mqtt")
    if not entries:
        return None

    data = entries[0].data
    host = str(data.get(DATA_BROKER) or "")
    port = int(data.get(CONF_PORT) or DEFAULT_PORT)

    if is_unreachable_from_elsewhere(host):
        local = await hass.async_add_executor_job(_local_address_towards, tv_host, port)
        if local is None:
            return None
        _LOGGER.debug(
            "Broker address %s is local to Home Assistant; using %s", host, local
        )
        host = local

    return BrokerSettings(
        host=host,
        port=port,
        username=str(data.get(CONF_USERNAME) or ""),
        password=str(data.get(CONF_PASSWORD) or ""),
    )
