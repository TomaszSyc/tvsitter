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
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "custom_components"))

MODULES = [
    "tvsitter",
    "tvsitter.binary_sensor",
    "tvsitter.config_flow",
    "tvsitter.const",
    "tvsitter.coordinator",
    "tvsitter.entity",
    "tvsitter.models",
    "tvsitter.sensor",
]


@pytest.mark.parametrize("module", MODULES)
def test_module_imports(module: str) -> None:
    """Import the module and let any failure surface as a test failure."""
    assert importlib.import_module(module) is not None


def test_every_python_module_is_covered() -> None:
    """A new module must not slip past this check by simply not being listed."""
    package = Path(__file__).resolve().parent.parent / "custom_components" / "tvsitter"
    on_disk = {
        f"tvsitter.{path.stem}" if path.stem != "__init__" else "tvsitter"
        for path in package.glob("*.py")
    }

    assert on_disk == set(MODULES), f"update MODULES: {on_disk ^ set(MODULES)}"
