"""Every module has to import against the pinned Home Assistant release.

This is the cheapest guard against the failure mode where an API symbol quietly
disappears and nothing notices until somebody's instance refuses to load the
integration. Pinned in requirements-dev.txt, so a Home Assistant bump arrives as a pull
request that answers "does this still import?".

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import importlib
from importlib.metadata import requires, version
from pathlib import Path

import pytest

PACKAGE = "custom_components.tvsitter"

MODULES = [
    PACKAGE,
    f"{PACKAGE}.binary_sensor",
    f"{PACKAGE}.broker",
    f"{PACKAGE}.config_flow",
    f"{PACKAGE}.const",
    f"{PACKAGE}.coordinator",
    f"{PACKAGE}.entity",
    f"{PACKAGE}.models",
    f"{PACKAGE}.pairing",
    f"{PACKAGE}.sensor",
]


@pytest.mark.parametrize("module", MODULES)
def test_module_imports(module: str) -> None:
    """Import the module and let any failure surface as a test failure."""
    assert importlib.import_module(module) is not None


def test_every_python_module_is_covered() -> None:
    """A new module must not slip past this check by simply not being listed."""
    package = Path(__file__).resolve().parent.parent / "custom_components" / "tvsitter"
    on_disk = {
        f"{PACKAGE}.{path.stem}" if path.stem != "__init__" else PACKAGE
        for path in package.glob("*.py")
    }

    assert on_disk == set(MODULES), f"update MODULES: {on_disk ^ set(MODULES)}"


def test_the_test_harness_and_home_assistant_agree() -> None:
    """Dependabot bumps these two separately, and a mismatched pair is silent.

    pytest-homeassistant-custom-component pins exactly one Home Assistant release. If it
    ends up pinning a different one from requirements-dev.txt, pip installs whichever it
    resolves last, and the flow tests quietly run against a core the integration was
    never checked against.
    """
    pinned = [
        requirement.split("==", 1)[1].split(";")[0].strip()
        for requirement in requires("pytest-homeassistant-custom-component") or []
        if requirement.lower().startswith("homeassistant==")
    ]

    installed = version("homeassistant")

    assert pinned, "the harness no longer pins homeassistant; check what changed"
    assert pinned[0] == installed, f"harness wants {pinned[0]}, got {installed}"
