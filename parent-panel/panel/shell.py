"""The parent's page: a shell sent once, and static files that do the rest.

The shell is `static/index.html` with three things filled in per load: the language
tag, the words in that language, and one script element per file in `SCRIPTS`. Nothing
from Home Assistant is ever written into it — every value on the page arrives from
`GET /api/state` and every change leaves through `POST /api/do` — so there is nothing
here to escape but the catalogue, which is this project's own.

Classic scripts in a fixed order rather than modules or a bundle: no build step to
keep current, nothing to transpile for the companion app's web view, and each file can
be read on its own. Each one adds its part to `window.TS`, so the order is the
dependency graph.

Every address is relative, because an Ingress App is served under a path the Supervisor
invents per session and an absolute one would leave the App altogether.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import html
import json
from pathlib import Path
import re

STATIC = Path(__file__).resolve().parent / "static"

# The load order. The words first, because everything after them says something; the
# connection next; the bottom sheet before the screens that open it; the screens; and
# the shell that wires them together last, once every name it calls exists.
SCRIPTS: tuple[str, ...] = (
    "words.js",
    "api.js",
    "sheet.js",
    "now.js",
    "rules.js",
    "apps.js",
    "history.js",
    "settings.js",
    "main.js",
)

_SLOT = re.compile(r"\{\{(\w+)\}\}")


def render_shell(said: dict[str, str] | None = None, language: str = "en") -> str:
    """Return the whole document, which is the same every time in one language.

    The words go in ahead of the scripts rather than being fetched with the state,
    because the page says things before it has any state — the tabs and the gear are on
    the screen while Home Assistant is still being asked, and tabs that are briefly
    English are tabs that flicker.
    """
    # ASCII, so nothing in a translation can be a character this document has a meaning
    # for; and the one sequence that would still end the script early is escaped, which
    # in JSON is the same string written another way.
    catalogue = json.dumps(said or {}).replace("</", "<\\/")
    tongue = html.escape((language or "en").split("-")[0][:8], quote=True)
    scripts = "".join(f'<script src="static/js/{name}"></script>\n' for name in SCRIPTS)
    filled = {"lang": tongue, "said": catalogue, "scripts": scripts}
    # One pass, so a slot's name written inside a value is left as it is rather than
    # filled in turn.
    template = (STATIC / "index.html").read_text(encoding="utf-8")
    return _SLOT.sub(lambda slot: filled[slot[1]], template)


def script() -> str:
    """Every script, joined in the order the shell loads them, for the page drivers.

    The browser runs them as separate scripts sharing one global scope, and joined they
    run the same way: each file is a function that only reaches the others through
    `window.TS`.
    """
    return "\n".join(
        (STATIC / "js" / name).read_text(encoding="utf-8") for name in SCRIPTS
    )
