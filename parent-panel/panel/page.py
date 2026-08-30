"""The one page this skeleton serves, and the words on it.

Its own module because the markup is the part that will grow and the server is the
part that should not. Written by hand rather than through a template engine: one page
does not earn a dependency, and every value on it goes through `escape`.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from html import escape

from .home_assistant import Television

# The same colours as the television's own screens, so the two halves of the product
# look like one thing. They live twice because two languages read them; the app's copy
# in TvStyle.kt is the original.
STYLE = """
:root { color-scheme: dark; }
body {
  margin: 0; padding: 2rem;
  background: #0B1017; color: #F2F6F9;
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
h1 { font-size: 1.5rem; margin: 0 0 0.25rem; }
p.lead { color: #8FA3B3; margin: 0 0 2rem; }
ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 1rem; }
li { background: #141F2B; border-radius: 16px; padding: 1.25rem 1.5rem; }
h2 { font-size: 1.125rem; margin: 0 0 0.75rem; }
dl { display: grid; grid-template-columns: auto 1fr; gap: 0.25rem 1.5rem; margin: 0; }
dt { color: #8FA3B3; }
dd { margin: 0; }
.accent { color: #5BE1BE; }
.warn { color: #FFC46B; }
"""


def render(televisions: list[Television], trouble: str | None = None) -> str:
    """Build the page, whatever there is to say.

    Three states, and each is a different sentence rather than an empty list: nobody has
    let the panel ask, nothing answered, or here is what there is.
    """
    if trouble is not None:
        body = f'<p class="warn">{escape(trouble)}</p>'
    elif not televisions:
        body = (
            '<p class="warn">No televisions yet. The panel reads them from the TV '
            "Sitter integration, so add that first — this page is a second way to see "
            "what it already knows, not a way round it.</p>"
        )
    else:
        body = "<ul>" + "".join(card(one) for one in televisions) + "</ul>"

    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>TV Sitter</title><style>{STYLE}</style></head><body>"
        "<h1>TV Sitter</h1>"
        '<p class="lead">What the panel can see. Everything here comes from Home '
        "Assistant, which is the only thing that talks to the televisions.</p>"
        f"{body}</body></html>"
    )


def card(television: Television) -> str:
    """One television, and the four things worth knowing before anything else."""
    rows = [
        ("Reporting", said(television, "reporting")),
        ("Screen", said(television, "screen")),
        ("Playing", said(television, "active_app")),
        ("Watched today", said(television, "used_today", unit=" min")),
    ]
    written = "".join(
        f"<dt>{escape(label)}</dt><dd>{escape(value)}</dd>" for label, value in rows
    )
    return (
        f"<li><h2>{escape(television.name)}</h2>"
        f"<dl>{written}</dl>"
        f'<p class="accent">{escape(str(len(television.entities)))} entities</p></li>'
    )


def said(television: Television, key: str, unit: str = "") -> str:
    """Say what one entity holds, in words rather than in Home Assistant's vocabulary.

    `unknown` and `unavailable` are states a parent should never have to learn. They
    become a dash, which reads as "nothing to say" and is what they mean.
    """
    state = television.state_of(key)
    if state in (None, "unknown", "unavailable"):
        return "—"
    if state == "on":
        return "yes"
    if state == "off":
        return "no"
    return f"{state}{unit}"
