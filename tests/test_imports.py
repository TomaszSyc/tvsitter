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
import re

import pytest

PACKAGE = "custom_components.tvsitter"

MODULES = [
    PACKAGE,
    f"{PACKAGE}.binary_sensor",
    f"{PACKAGE}.broker",
    f"{PACKAGE}.button",
    f"{PACKAGE}.config_flow",
    f"{PACKAGE}.const",
    f"{PACKAGE}.coordinator",
    f"{PACKAGE}.entity",
    f"{PACKAGE}.event",
    f"{PACKAGE}.models",
    f"{PACKAGE}.number",
    f"{PACKAGE}.pairing",
    f"{PACKAGE}.parent_pin",
    f"{PACKAGE}.schedules",
    f"{PACKAGE}.sensor",
    f"{PACKAGE}.switch",
    f"{PACKAGE}.text",
]


# The panel's modules, imported for the same reason as the integration's — and after the
# reason arrived. `server.py` imported a name that had become a method two commits
# earlier, and nothing noticed until the container refused to start: every panel test
# imported the two modules it exercised and never the one that wires them together.
PANEL_MODULES = [
    "panel",
    "panel.api",
    "panel.automations",
    "panel.blueprints",
    "panel.home_assistant",
    "panel.page",
    "panel.server",
    "panel.statistics",
]


@pytest.mark.parametrize("module", PANEL_MODULES)
def test_panel_module_imports(module: str) -> None:
    """Import the module and let any failure surface as a test failure."""
    assert importlib.import_module(module) is not None


def test_every_panel_module_is_covered() -> None:
    """A new module must not slip past this check by simply not being listed."""
    package = Path(__file__).resolve().parent.parent / "parent-panel" / "panel"
    on_disk = {
        f"panel.{path.stem}" if path.stem != "__init__" else "panel"
        for path in package.glob("*.py")
        if path.stem != "__main__"
    }

    assert on_disk == set(PANEL_MODULES), (
        f"not listed: {sorted(on_disk - set(PANEL_MODULES))}"
    )


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


def test_every_action_in_services_yaml_is_registered_exactly_once() -> None:
    """The names in `services.yaml` and the names registered have to be the same set.

    They were not. `SERVICE_SET_ALLOWED_APPS` was inserted above `SERVICE_SET_APP_LIMIT`
    by a replace that matched twice: once in the import list, where it belonged, and
    once in the call registering the app-limit action, where it took the name's place.
    Home Assistant was then offered `set_allowed_apps` twice and `set_app_limit` never,
    and every test still passed: they all call the entity's method directly, and none
    ever asked what the platform had been told.
    """
    package = Path(__file__).resolve().parent.parent / "custom_components" / "tvsitter"
    const = (package / "const.py").read_text(encoding="utf-8")

    names = dict(re.findall(r'^(SERVICE_\w+):\s*Final\s*=\s*"([^"]+)"', const, re.M))
    declared = set(
        re.findall(r"^(\w+):$", (package / "services.yaml").read_text(), re.M)
    )

    registered: list[str] = []
    for source in package.glob("*.py"):
        for constant in re.findall(
            r"async_register_entity_service\(\s*(SERVICE_\w+)", source.read_text()
        ):
            registered.append(names[constant])

    assert sorted(registered) == sorted(set(registered)), (
        f"registered more than once: {sorted(registered)}"
    )
    assert set(registered) == declared, (
        f"only in code: {sorted(set(registered) - declared)}; "
        f"only in services.yaml: {sorted(declared - set(registered))}"
    )
