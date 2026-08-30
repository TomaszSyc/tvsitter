"""The panel's script, checked for the one thing Python cannot see in it.

`page.py` carries sixty kilobytes of JavaScript inside a string. Python imports it
happily whatever is written there, every panel test passes, the add-on builds, the
container starts, and the parent gets a blank page with a parse error in a console
nobody has open. A stray bracket in a card nothing else touches is a whole panel gone.

`node --check` is the cheapest answer: it parses and does not run. Skipped rather than
failed where there is no Node, because a machine without one is not a machine with a
broken script — but CI has one, so the guard is real where it counts.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from panel.page import _SCRIPT, render_shell
import pytest


def test_the_script_parses(tmp_path: Path) -> None:
    """Hand the script to Node exactly as the browser gets it."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("no Node here to parse it with")

    # The extension matters: `--check` reads a `.js` file as a script, which is what a
    # plain `<script>` element makes of it, and a `.mjs` as a module, which it is not.
    written = tmp_path / "page.js"
    written.write_text(_SCRIPT, encoding="utf-8")

    done = subprocess.run(
        [node, "--check", str(written)], capture_output=True, text=True, check=False
    )

    assert done.returncode == 0, done.stderr


def test_the_script_is_closed_inside_the_document() -> None:
    """An unescaped closing tag ends the script early wherever it appears.

    The browser looks for the characters and not for a string, so one written inside a
    quoted sentence would cut the page off mid-function — and it would still be a valid
    script as far as the test above is concerned.
    """
    assert "</script" not in _SCRIPT.lower()
    # Two blocks: the words the page says, then the page. Both have to be closed once
    # and no more, and a third would mean something has been cut in half.
    assert render_shell().lower().count("</script>") == 2
