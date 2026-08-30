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
TOPIC_DAY: Final = "day"
TOPIC_ALERT: Final = "alert"

# The tamper signals, as the television names them. Listed so the event entity can
# declare
# its types; one it has never heard of is still shown rather than refused, because a
# newer
# television must be able to raise an alarm an older integration can pass on.
ALERT_KINDS: Final = (
    "pin_lockout",
    "clock_changed",
    "overlay_lost",
    "usage_lost",
    "unclean_restart",
    "source_fight",
)

# What an alarm this build has never heard of is filed under. An event entity can only
# fire
# a type it declared, so a newer television's alarm is shown under a name rather than
# dropped — losing it would lose exactly the message somebody needs.
ALERT_UNKNOWN: Final = "unknown"

# Four heartbeats. The television publishes state every 60 s, so this is 240 s — long
# enough
# to ride out the reboot gap D22 measured at about a minute, short enough that an app
# killed
# at bedtime is noticed the same evening.
QUIET_AFTER_SECONDS: Final = 240

# How often that is checked. One heartbeat: checking faster cannot make the answer
# arrive
# sooner, and checking slower would add its own delay to a four-minute one.
SILENCE_CHECK_SECONDS: Final = 60
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
RULE_WARN_BEFORE: Final = "warn_before_s"
RULE_BLOCK_SETTINGS: Final = "block_settings"
RULE_APP_LIMITS: Final = "app_limits_s"
RULE_DAYS: Final = "days"
RULE_WINDOWS: Final = "windows"
RULE_APPS_ALLOWED: Final = "apps_allowed"

SERVICE_USE_SCHEDULE: Final = "use_schedule"
# The way back out. Without it a house that has ever followed a helper can never edit
# the hours anywhere else again: the panel's own grid is read-only while one is being
# followed, because the next import would undo whatever was painted (D33, amended).
SERVICE_FORGET_SCHEDULE: Final = "forget_schedule"
ATTR_SCHEDULE: Final = "schedule"

# Where the chosen schedule helper is remembered, so an edit to it still reaches the
# television after a restart.
CONF_SCHEDULE: Final = "schedule_entity"

# How the followed helper is published, on the rules sensor beside the rules themselves.
# It shares those attributes with whatever the television sends, and the rules are
# opaque by design — so this name is spoken for, and a rule key must never claim it.
ATTR_EXEMPT_APPS: Final = "exempt_apps"
ATTR_FOLLOWING_SCHEDULE: Final = "following_schedule"

KIND_MORE_TIME: Final = "more_time"

SERVICE_GRANT_TIME: Final = "grant_time"
SERVICE_DENY_TIME: Final = "deny_time"
SERVICE_SET_SCHEDULE: Final = "set_schedule"
SERVICE_SET_WINDOWS: Final = "set_windows"
SERVICE_SET_APP_LIMIT: Final = "set_app_limit"
SERVICE_SET_ALLOWED_APPS: Final = "set_allowed_apps"
ATTR_MINUTES: Final = "minutes"
ATTR_REQUEST_ID: Final = "req_id"
ATTR_DAY: Final = "day"
ATTR_WINDOWS: Final = "windows"
ATTR_PACKAGE: Final = "package"
ATTR_PACKAGES: Final = "packages"

# The wire spelling of the days, which is what the rules object uses. Short and lower
# case because that is what the engine parses; the interface translates them.
WIRE_DAYS: Final = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
