"""The panel's scripts, checked for the things Python cannot see in them.

The page is a handful of JavaScript files served as they are, with no build step to
complain. Python imports the panel happily whatever is written in them, every panel test
passes, the add-on builds, the container starts, and the parent gets a blank page with a
parse error in a console nobody has open. A stray bracket in a screen nothing else
touches is a whole panel gone.

`node --check` is the cheapest answer: it parses and does not run. Skipped rather than
failed where there is no Node, because a machine without one is not a machine with a
broken script — but CI has one, so the guard is real where it counts.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import shutil
import subprocess

from panel.shell import SCRIPTS, STATIC, render_shell
import pytest

SCRIPT_DIR = STATIC / "js"


@pytest.mark.parametrize("name", SCRIPTS)
def test_every_script_parses(name: str) -> None:
    """Hand each file to Node exactly as the browser gets it."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("no Node here to parse it with")

    # The extension matters: `--check` reads a `.js` file as a script, which is what a
    # plain `<script src>` makes of it, and a `.mjs` as a module, which it is not.
    done = subprocess.run(
        [node, "--check", str(SCRIPT_DIR / name)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == 0, done.stderr


def test_the_shell_names_every_script_once() -> None:
    """A file on disk the shell does not load is a screen that never appears.

    And one the shell loads that is not on disk is a 404 in the middle of the load
    order, which leaves every script after it without the names it expects.
    """
    page = render_shell()
    on_disk = sorted(path.name for path in SCRIPT_DIR.glob("*.js"))

    assert sorted(SCRIPTS) == on_disk
    assert len(set(SCRIPTS)) == len(SCRIPTS)
    for name in SCRIPTS:
        # Relative, because an Ingress App is served under a path the Supervisor
        # invents per session and an absolute address would leave the App altogether.
        assert page.count(f'<script src="static/js/{name}"></script>') == 1
    # In the order given: each file finds the names the ones before it left on `TS`.
    places = [page.index(f"static/js/{name}") for name in SCRIPTS]
    assert places == sorted(places)


def test_the_shell_carries_both_stylesheets_relative() -> None:
    """The tokens first, so the layout reads colours that are already defined."""
    page = render_shell()

    tokens = page.index('<link rel="stylesheet" href="static/tokens.css">')
    layout = page.index('<link rel="stylesheet" href="static/app.css">')
    assert tokens < layout


@pytest.mark.parametrize("name", SCRIPTS)
def test_no_script_closes_the_document(name: str) -> None:
    """Served from a file it cannot end a script element, but the drivers concatenate.

    And a file that once moved back inline would cut the page off mid-function while
    still being a valid script as far as the test above is concerned.
    """
    assert "</script" not in (SCRIPT_DIR / name).read_text(encoding="utf-8").lower()


def test_the_document_closes_each_script_once() -> None:
    """The words the page says, then one element per file, and nothing cut in half."""
    assert render_shell().lower().count("</script>") == 1 + len(SCRIPTS)
