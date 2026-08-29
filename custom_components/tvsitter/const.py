"""Constants for the TV Sitter integration.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "tvsitter"

PLATFORMS: Final[list[Platform]] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
]

CONF_TOPIC_PREFIX: Final = "topic_prefix"
CONF_DEVICE_ID: Final = "device_id"
CONF_USE_TLS: Final = "use_tls"
CONF_PIN: Final = "pin"
CONF_BROKER: Final = "broker"

DEFAULT_NAME: Final = "TV Sitter"
DEFAULT_TOPIC_PREFIX: Final = "tvsitter/livingroom"

# Pairing, as described in D14 and implemented by PairingProtocol on the TV side.
ZEROCONF_TYPE: Final = "_tvsitter._tcp.local."
PAIRING_PATH: Final = "/pair"
PAIRING_TIMEOUT_S: Final = 10

TXT_DEVICE_ID: Final = "id"
TXT_NAME: Final = "name"
TXT_VERSION: Final = "version"
TXT_PAIRED: Final = "paired"
# Advertised only by a TV that is already using one, so its absence means "never paired"
# rather than "no opinion". Kept in step with PairingProtocol on the Kotlin side.
TXT_PREFIX: Final = "prefix"

# Payload schema this build understands. A payload declaring a higher one is refused
# rather than guessed at: past that point the meaning of existing fields cannot be
# assumed. Kept in step with Contract.SCHEMA_VERSION on the Kotlin side.
SCHEMA_VERSION: Final = 1

# Topic suffixes. The contract is docs/mqtt-contract.md; both halves of the project
# have to agree on it, which is why they live in one repository.
TOPIC_AVAILABILITY: Final = "availability"
TOPIC_STATE: Final = "state"
TOPIC_REQUEST: Final = "request"
TOPIC_RULES: Final = "rules"
TOPIC_COMMAND: Final = "cmd"

PAYLOAD_ONLINE: Final = "online"
PAYLOAD_OFFLINE: Final = "offline"

# The only kind of request there is so far. Named rather than assumed, because the field
# exists precisely so that a second kind can be added without a schema bump.
# Commands. Named here rather than spelled out at each call site: every one of them is a
# word in docs/mqtt-contract.md, and a typo in one would be a command the TV silently
# ignores.
OP_SET_RULES: Final = "set_rules"

# Rule keys, same reason. `rules` is deliberately opaque in the contract, so these are
# the
# only record on this side of what the engine understands.
RULE_DAILY_LIMIT: Final = "daily_limit_s"

KIND_MORE_TIME: Final = "more_time"

SERVICE_GRANT_TIME: Final = "grant_time"
SERVICE_DENY_TIME: Final = "deny_time"
ATTR_MINUTES: Final = "minutes"
ATTR_REQUEST_ID: Final = "req_id"
