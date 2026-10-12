"""The panel's page, driven the way a parent drives it.

Everything else about the panel is tested on the Python side, which is every part of it
except the part a parent actually touches. The page is a handful of scripts that are
served and shipped without one line of them ever running, and the three rounds of
complaints it took to make the old weekly grid usable were all about behaviour no test
here could see.

So it runs, on a DOM small enough to read (`tests/page/dom.js`) rather than in a
browser. Not a rendering test — nothing here knows what anything looks like. It taps
the buttons, answers the writes, lands the polls, and asks what is left on the screen.

Two pages for now. The drivers written for the old one-file page keep running against
it until the screen that replaces what they test arrives with drivers of its own; every
other driver runs against the new scripts, joined in the order the shell loads them.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

from panel import page, shell
from panel.words import words
import pytest

DRIVERS = Path(__file__).resolve().parent / "page"

# Moved to the new page one at a time, by the task that rebuilds what each one drives.
LEGACY = {"asking.js", "language.js"}


def served_to(driver: Path) -> str:
    """Return the script a driver runs against: the old page or the new one."""
    return page._SCRIPT if driver.name in LEGACY else shell.script()


@pytest.mark.parametrize(
    "driver", sorted(DRIVERS.glob("*.js")), ids=lambda one: one.stem
)
def test_the_page_behaves(driver: Path, tmp_path: Path) -> None:
    """Run one driver against the page exactly as the browser is served it."""
    if driver.name == "dom.js":
        pytest.skip("the DOM the drivers run on, not a driver")
    node = shutil.which("node")
    if node is None:
        pytest.skip("no Node here to run the page in")

    served = tmp_path / "page.js"
    served.write_text(served_to(driver), encoding="utf-8")
    # The Polish words, in the shape the document carries them. Handed to every driver
    # and ignored by the ones that read the page in English.
    catalogue = tmp_path / "words.json"
    catalogue.write_text(json.dumps(words("pl")), encoding="utf-8")

    done = subprocess.run(
        [node, str(driver), str(served), str(catalogue)],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )

    # The driver names every check it made, so its own output is the failure report.
    assert done.returncode == 0, done.stdout + done.stderr


def test_some_driver_runs_against_the_new_page() -> None:
    """A rename that put every driver back in the old group would test nothing new."""
    drivers = {one.name for one in DRIVERS.glob("*.js")} - {"dom.js"}

    assert drivers - LEGACY
    assert drivers >= LEGACY
