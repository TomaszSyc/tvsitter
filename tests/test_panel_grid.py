"""The weekly grid, driven the way a parent drives it.

Everything else about the panel is tested on the Python side, which is every part of it
except the part a parent actually touches. The page is a script in a string: it is
imported, served and shipped without one line of it ever running, and the three rounds
of complaints it took to make the grid usable were all about behaviour no test here
could see.

So it runs, on a DOM small enough to read (`tests/page/dom.js`) rather than in a
browser. Not a rendering test — nothing here knows what anything looks like. It draws
on the grid, answers the writes, lands the polls, and asks what is left on the boxes.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from panel.page import _SCRIPT
import pytest

DRIVERS = Path(__file__).resolve().parent / "page"


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
    served.write_text(_SCRIPT, encoding="utf-8")

    done = subprocess.run(
        [node, str(driver), str(served)],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )

    # The driver names every check it made, so its own output is the failure report.
    assert done.returncode == 0, done.stdout + done.stderr
