"""Config flow for TV Sitter.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME

from .const import CONF_TOPIC_PREFIX, DEFAULT_NAME, DEFAULT_TOPIC_PREFIX, DOMAIN

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_TOPIC_PREFIX, default=DEFAULT_TOPIC_PREFIX): str,
    }
)

# MQTT wildcards in the prefix would mean subscribing to other people's topics and
# publishing commands into unknown places.
FORBIDDEN_IN_PREFIX = ("+", "#")


class TvSitterConfigFlow(ConfigFlow, domain=DOMAIN):
    """One config entry per TV."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the TV name and the MQTT topic prefix."""
        errors: dict[str, str] = {}

        if user_input is not None:
            prefix = user_input[CONF_TOPIC_PREFIX].strip().strip("/")
            if not prefix or any(char in prefix for char in FORBIDDEN_IN_PREFIX):
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
