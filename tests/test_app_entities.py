"""Which apps get a usage sensor and a limit, and which do not.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from custom_components.tvsitter import number, sensor
from custom_components.tvsitter.coordinator import TvSitterClient
from custom_components.tvsitter.models import StateSnapshot
from homeassistant.core import HomeAssistant

LAUNCHER = "com.google.android.apps.tv.launcherx"


def watched(hass: HomeAssistant) -> SimpleNamespace:
    """Build an entry for a set that charged time to an app and to the launcher."""
    client = TvSitterClient(hass, name="TV", topic_prefix="tvsitter/tv")
    client.snapshot = StateSnapshot.from_payload(
        json.dumps(
            {
                "schema": 1,
                "ts": 1,
                "screen_on": True,
                "per_app": {"tv.example.films": 600, LAUNCHER: 40, "android": 3},
                "exempt_apps": [LAUNCHER, "android"],
            }
        )
    )
    return SimpleNamespace(runtime_data=client, async_on_unload=lambda _undo: None)


async def packages_given(hass: HomeAssistant, platform: Any) -> set[str]:
    """Set the platform up and say which packages it made an entity for."""
    added: list[Any] = []
    # The sensors register entity actions on the platform; a direct call has none.
    with patch(
        "homeassistant.helpers.entity_platform.async_get_current_platform",
        MagicMock(),
    ):
        await platform.async_setup_entry(hass, watched(hass), added.extend)
    return {entity._package for entity in added if hasattr(entity, "_package")}


async def test_an_exempt_app_gets_no_usage_sensor(hass: HomeAssistant) -> None:
    """Nothing can be done about the launcher, so nothing should count it as an app.

    It also took one of the twelve places, and wrote statistics nobody looks at.
    """
    assert await packages_given(hass, sensor) == {"tv.example.films"}


async def test_an_exempt_app_gets_no_limit(hass: HomeAssistant) -> None:
    """The contract keeps the list so that nothing offers a control for them."""
    assert await packages_given(hass, number) == {"tv.example.films"}
