"""One version for the whole product.

D6 accepted a cost to keep both halves in one repository, and a single SemVer version
for the product is the other side of that bargain. Nothing enforced it, and the two had
already drifted: the app said 0.1.0-m0 while the integration said 0.1.0.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "version.txt"
MANIFEST = ROOT / "custom_components" / "tvsitter" / "manifest.json"
APP_BUILD = ROOT / "app" / "build.gradle.kts"
ADDON_CONFIG = ROOT / "parent-panel" / "config.yaml"
ADDON_BUILD = ROOT / "parent-panel" / "build.yaml"

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def product_version() -> str:
    """Read the one place the version is written."""
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def test_the_version_is_plain_semver() -> None:
    """No milestone suffixes.

    `0.1.0-m0` outlived milestone zero by two milestones and still claimed to be it. A
    A version describing where the project was, rather than what the build is, says
    nothing useful, and HACS and Play both want ordinary SemVer anyway.
    """
    assert SEMVER.match(product_version()), product_version()


def test_the_integration_carries_the_product_version() -> None:
    """HACS reads this one, and it has to be the same number the app reports."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert manifest["version"] == product_version()


def test_the_app_reads_the_version_rather_than_repeating_it() -> None:
    """A literal here is how the drift happened the first time.

    The `fw` field in every state payload exists so that a misbehaving build can be
    identified from the payload alone, which a stale hard-coded string quietly prevents.
    """
    build = APP_BUILD.read_text(encoding="utf-8")

    assert "versionName = productVersion" in build
    literals = re.findall(r'versionName\s*=\s*"([^"]+)"', build)
    assert not literals, f"versionName is hard-coded: {literals}"


def test_the_panel_carries_the_product_version() -> None:
    """The Supervisor reads this one, and it is the third copy of the same number.

    Quoted in the YAML on purpose: `0.6.10` unquoted is a float that loses its last
    digit, and the Supervisor would then offer an update from 0.6.9 to 0.6.1.
    """
    written = ADDON_CONFIG.read_text(encoding="utf-8")
    quoted = re.search(r'^version:\s*"([^"]+)"\s*$', written, re.MULTILINE)

    assert quoted, "the add-on version must be quoted, or YAML reads it as a number"
    assert quoted.group(1) == product_version()


def test_the_panel_claims_only_what_is_built() -> None:
    """An app offered for an arch nobody built is an install that fails on a pull.

    The Supervisor hides an app whose `arch` does not match the machine, which is a
    much better failure than an image that is not there.
    """
    claimed = set(re.findall(r"^  - (\w+)$", ADDON_CONFIG.read_text(), re.MULTILINE))
    built = set(re.findall(r"^  (\w+):", ADDON_BUILD.read_text(), re.MULTILINE))

    assert claimed == built, f"config.yaml claims {claimed}, build.yaml has {built}"
