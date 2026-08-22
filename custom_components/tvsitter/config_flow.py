"""Config flow for TV Sitter.

Two ways in. A TV that is switched on advertises itself over mDNS and is paired by
typing the PIN it shows. A TV that is off, or on a network where mDNS does not travel,
can be added by hand from the topic prefix alone.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import section
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.util import slugify

from .broker import DEFAULT_PORT, BrokerSettings, async_broker_settings_for
from .const import (
    CONF_BROKER,
    CONF_DEVICE_ID,
    CONF_PIN,
    CONF_TOPIC_PREFIX,
    CONF_USE_TLS,
    DEFAULT_NAME,
    DEFAULT_TOPIC_PREFIX,
    DOMAIN,
    TXT_DEVICE_ID,
    TXT_NAME,
    TXT_PAIRED,
    TXT_PREFIX,
)
from .pairing import ERROR_WRONG_PIN, PairResult, async_pair

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_TOPIC_PREFIX, default=DEFAULT_TOPIC_PREFIX): str,
    }
)

# MQTT wildcards in the prefix would mean subscribing to other people's topics and
# publishing commands into unknown places.
FORBIDDEN_IN_PREFIX = ("+", "#")


def _clean_prefix(raw: str) -> str | None:
    """Normalise a topic prefix, or return None if it is not usable."""
    prefix = raw.strip().strip("/")
    if not prefix or any(char in prefix for char in FORBIDDEN_IN_PREFIX):
        return None
    return prefix


def _pair_schema(default_prefix: str, broker: BrokerSettings | None) -> vol.Schema:
    """Ask for the PIN, and let the broker details be overridden without insisting.

    The credential fields start empty, and empty means "reuse the account Home Assistant
    already talks to the broker with". Pre-filling a password into a form about to be
    rendered in a browser buys nothing: nobody needs to read it back, and the flow can
    read it itself.
    """
    return vol.Schema(
        {
            vol.Required(CONF_PIN): str,
            vol.Required(CONF_TOPIC_PREFIX, default=default_prefix): str,
            vol.Required(CONF_BROKER): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_HOST, default=broker.host if broker else ""
                        ): str,
                        vol.Optional(
                            CONF_PORT, default=broker.port if broker else DEFAULT_PORT
                        ): int,
                        vol.Optional(CONF_USERNAME, default=""): str,
                        vol.Optional(CONF_PASSWORD, default=""): str,
                        vol.Optional(CONF_USE_TLS, default=False): bool,
                    }
                ),
                {"collapsed": True},
            ),
        }
    )


def _resolve_broker(
    defaults: BrokerSettings | None, entered: dict[str, Any]
) -> BrokerSettings | None:
    """Combine what was typed with what Home Assistant already knows.

    A typed username is taken with the password typed beside it, even an empty one,
    because an anonymous broker is a real configuration. A blank username means the Home
    Assistant account, and then the password has to come from the same place: mixing a
    typed username with a stored password gives a TV that cannot authenticate.
    """
    host = str(entered.get(CONF_HOST) or "").strip()
    username = str(entered.get(CONF_USERNAME) or "").strip()
    password = str(entered.get(CONF_PASSWORD) or "")
    use_tls = bool(entered.get(CONF_USE_TLS))
    port = int(entered.get(CONF_PORT) or (defaults.port if defaults else DEFAULT_PORT))

    if not host:
        if defaults is None:
            return None
        host = defaults.host

    if username:
        return BrokerSettings(host, port, username, password, use_tls)

    if defaults is None:
        return None
    return BrokerSettings(host, port, defaults.username, defaults.password, use_tls)


class TvSitterConfigFlow(ConfigFlow, domain=DOMAIN):
    """One config entry per TV."""

    VERSION = 1

    def __init__(self) -> None:
        """Start with nothing discovered."""
        self._host: str | None = None
        self._port: int | None = None
        self._device_id: str | None = None
        self._tv_name: str = DEFAULT_NAME
        self._advertised_prefix: str | None = None
        self._attempts_left: str = ""

    async def _async_require_mqtt(self) -> ConfigFlowResult | None:
        """Refuse to go on without MQTT, saying so by name.

        Without this the entry fails later with a generic dependency error that names
        nothing the user can act on.
        """
        if not await mqtt.async_wait_for_mqtt_client(self.hass):
            return self.async_abort(reason="mqtt_unavailable")
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a TV by hand, from its topic prefix.

        Kept for a TV that is switched off, and for networks that do not carry mDNS.
        """
        if (abort := await self._async_require_mqtt()) is not None:
            return abort

        errors: dict[str, str] = {}

        if user_input is not None:
            prefix = _clean_prefix(user_input[CONF_TOPIC_PREFIX])
            if prefix is None:
                errors[CONF_TOPIC_PREFIX] = "invalid_topic_prefix"
            else:
                await self.async_set_unique_id(prefix)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={CONF_NAME: user_input[CONF_NAME], CONF_TOPIC_PREFIX: prefix},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Offer to pair with a TV that is advertising itself."""
        properties = discovery_info.properties
        device_id = str(properties.get(TXT_DEVICE_ID) or "").strip()
        if not device_id:
            # Something is answering on our service type without our TXT record.
            return self.async_abort(reason="not_tvsitter")

        # The TV stops advertising once it is paired, so this is belt and braces
        # against a cached mDNS record.
        if str(properties.get(TXT_PAIRED, "")).lower() == "true":
            return self.async_abort(reason="already_paired")

        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured()

        self._device_id = device_id
        self._host = discovery_info.host
        self._port = discovery_info.port
        self._tv_name = str(properties.get(TXT_NAME) or "").strip() or DEFAULT_NAME
        # Only a TV already using a prefix advertises one, so this is either the prefix
        # in force or nothing. Cleaned rather than trusted: it ends up in a topic.
        self._advertised_prefix = _clean_prefix(str(properties.get(TXT_PREFIX) or ""))

        self.context["title_placeholders"] = {"name": self._tv_name}
        return await self.async_step_pair()

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Take the PIN off the screen and hand the TV its broker settings."""
        if (abort := await self._async_require_mqtt()) is not None:
            return abort

        if self._host is None or self._port is None:
            return self.async_abort(reason="not_tvsitter")

        defaults = await async_broker_settings_for(self.hass, self._host)
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {"name": self._tv_name}

        if user_input is not None:
            result = await self._async_try_pair(user_input, defaults, errors)
            if result is not None:
                return result
            if errors.get(CONF_PIN) == "wrong_pin_attempts":
                placeholders["attempts"] = self._attempts_left

        return self.async_show_form(
            step_id="pair",
            data_schema=self.add_suggested_values_to_schema(
                _pair_schema(self._default_prefix(), defaults), user_input
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def _async_try_pair(
        self,
        user_input: dict[str, Any],
        defaults: BrokerSettings | None,
        errors: dict[str, str],
    ) -> ConfigFlowResult | None:
        """One pairing attempt. Returns a result to show, or None to redraw the form."""
        prefix = _clean_prefix(user_input[CONF_TOPIC_PREFIX])
        if prefix is None:
            errors[CONF_TOPIC_PREFIX] = "invalid_topic_prefix"
            return None

        broker = _resolve_broker(defaults, user_input.get(CONF_BROKER) or {})
        if broker is None or not broker.is_complete:
            return self.async_abort(reason="no_broker")

        if self._host is None or self._port is None:
            return self.async_abort(reason="not_tvsitter")

        outcome = await async_pair(
            self.hass,
            host=self._host,
            port=self._port,
            pin=str(user_input[CONF_PIN]).strip(),
            topic_prefix=prefix,
            broker=broker,
        )

        if outcome.ok:
            device_id = outcome.device_id or self._device_id
            name = outcome.name or self._tv_name

            # A TV added by hand keys its entry on the topic prefix; a paired one keys
            # on the device id, which mDNS cannot tell us beforehand. Adopting the entry
            # that already addresses this prefix is what stops one television becoming
            # two entries, with the first one's entities going quiet for good.
            adopted = self._existing_entry_for(prefix)
            if adopted is not None:
                # Only the identity is written. The title and the name stay as they
                # are: whoever added this TV by hand chose them, and pairing is no
                # reason to replace a chosen name with whatever the TV calls itself.
                return self.async_update_reload_and_abort(
                    adopted,
                    unique_id=device_id,
                    data_updates={CONF_DEVICE_ID: device_id},
                    reason="updated_existing",
                )

            return self.async_create_entry(
                title=name,
                data={
                    CONF_NAME: name,
                    CONF_TOPIC_PREFIX: prefix,
                    CONF_DEVICE_ID: device_id,
                },
            )

        errors[CONF_PIN] = self._error_key(outcome)
        return None

    def _existing_entry_for(self, prefix: str) -> ConfigEntry | None:
        """Find an entry already addressing this prefix, whatever its unique id."""
        return next(
            (
                entry
                for entry in self._async_current_entries()
                if entry.data.get(CONF_TOPIC_PREFIX) == prefix
            ),
            None,
        )

    def _error_key(self, outcome: PairResult) -> str:
        """Turn a refusal into a translation key, keeping any attempt count with it."""
        if outcome.error == ERROR_WRONG_PIN and outcome.attempts_remaining is not None:
            self._attempts_left = str(outcome.attempts_remaining)
            return "wrong_pin_attempts"
        return outcome.error or "unknown"

    def _default_prefix(self) -> str:
        """Suggest the prefix the TV is already using, or one derived from its name.

        Re-pairing a TV that is working used to suggest a prefix derived from its name,
        which is rarely the one in force — and accepting it silently moved the TV to a
        prefix Home Assistant had just invented, leaving the entities behind (#33).
        """
        if self._advertised_prefix:
            return self._advertised_prefix

        slug = slugify(self._tv_name)
        if not slug or slug == slugify(DEFAULT_NAME):
            slug = self._device_id or "tv"
        return f"tvsitter/{slug}"
