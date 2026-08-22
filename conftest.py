"""Test configuration.

At the repository root rather than under `tests/`, because that is what puts the root
on `sys.path` and lets the integration be imported as `custom_components.tvsitter` —
the name Home Assistant's own loader uses. Importing it under any other name would give
the tests a second copy of every module, and patching one would not affect the other.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

import custom_components

# pytest-homeassistant-custom-component ships its own `custom_components` package, with
# an `__init__.py`. A regular package beats a namespace directory whatever the sys.path
# order, so `import custom_components` finds the plugin's and never ours, and Home
# Assistant then reports "Integration 'tvsitter' not found". Adding our directory to the
# package it did find is additive: the plugin's own test components stay visible too.
_OURS = str(Path(__file__).parent / "custom_components")
if _OURS not in custom_components.__path__:
    custom_components.__path__.append(_OURS)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Let Home Assistant load `custom_components/tvsitter` in every test.

    Home Assistant refuses to load custom integrations under test unless asked, and the
    ask has to happen before `hass` is built, which is what makes this autouse.
    """
    yield
