"""Constants for the TV Sitter integration.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "tvsitter"

PLATFORMS: Final[list[Platform]] = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONF_TOPIC_PREFIX: Final = "topic_prefix"

DEFAULT_NAME: Final = "TV Sitter"
DEFAULT_TOPIC_PREFIX: Final = "tvsitter/livingroom"

# Payload schema this build understands. A payload declaring a higher one is refused
# rather than guessed at: past that point the meaning of existing fields cannot be
# assumed. Kept in step with Contract.SCHEMA_VERSION on the Kotlin side.
SCHEMA_VERSION: Final = 1

# Topic suffixes. The contract is docs/mqtt-contract.md; both halves of the project
# have to agree on it, which is why they live in one repository.
TOPIC_AVAILABILITY: Final = "availability"
TOPIC_STATE: Final = "state"
TOPIC_REQUEST: Final = "request"
TOPIC_COMMAND: Final = "cmd"

PAYLOAD_ONLINE: Final = "online"
PAYLOAD_OFFLINE: Final = "offline"
