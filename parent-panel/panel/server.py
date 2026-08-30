"""The web server, which does as little as a web server can.

Bound to every interface because the Supervisor's Ingress reaches it from another
container, and refusing everybody else because that is the whole of an Ingress app's
network security: the Supervisor is the only thing that should ever connect, and it
always connects from one address.

Four routes and no rendering. The page arrives once and asks for its own values
afterwards, so nothing here builds markup out of a state — which is why neither of the
two API routes ever answers with an error status. A 500 is a blank panel with nothing on
it saying why; the sentence travels in the body instead, and the page shows it.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError, ClientSession, web

from .api import apply, snapshot
from .home_assistant import HomeAssistant
from .page import render_shell

_LOGGER = logging.getLogger("panel")

PORT = 8099

# The Supervisor's own address on the internal network. Documented as the only source an
# Ingress app must accept, and checked here rather than assumed: this container has no
# other authentication, so the address is the door.
INGRESS = "172.30.32.2"

# What can go wrong between here and Home Assistant, said the way a parent reading the
# panel would say it. The reason goes to the log, where whoever is fixing it will look.
NO_TOKEN = (
    "No Supervisor token. This runs as a Home Assistant App, and started outside "
    "one it has nobody to ask."
)
REFUSED = "Home Assistant refused the token this App was given."
SILENT = "Home Assistant did not answer. It may still be starting."


async def index(request: web.Request) -> web.Response:
    """Answer with the page, which fetches everything on it for itself."""
    return no_store(web.Response(text=render_shell(), content_type="text/html"))


async def state(request: web.Request) -> web.Response:
    """Answer with everything the page draws, or with why there is nothing to draw."""
    home: HomeAssistant = request.app["home"]
    if not home.authorised:
        return nothing(NO_TOKEN)
    try:
        found = await home.televisions()
    except PermissionError as refused:
        _LOGGER.error("%s", refused)
        return nothing(REFUSED)
    except (ClientError, TimeoutError) as failure:
        _LOGGER.warning("could not read Home Assistant: %s", failure)
        return nothing(SILENT)
    return answer(snapshot(found))


async def do(request: web.Request) -> web.Response:
    """Make one change, and say plainly when it could not be made."""
    home: HomeAssistant = request.app["home"]
    if not home.authorised:
        return answer({"ok": False, "error": NO_TOKEN})

    try:
        asked = await request.json()
    except ValueError:
        return answer({"ok": False, "error": "That was not a request."})
    if not isinstance(asked, dict):
        return answer({"ok": False, "error": "That was not a request."})

    try:
        # Read afresh rather than from anything held: the page names a television by its
        # device, and which entity carries which control is a registry answer that
        # changes when somebody renames a set or the integration gains a control.
        await apply(home, await home.televisions(), asked)
    except ValueError as wrong:
        return answer({"ok": False, "error": str(wrong)})
    except PermissionError as refused:
        _LOGGER.error("%s", refused)
        return answer({"ok": False, "error": REFUSED})
    except RuntimeError as failure:
        _LOGGER.warning("the change was refused: %s", failure)
        return answer(
            {"ok": False, "error": "Home Assistant would not make that change."}
        )
    except (ClientError, TimeoutError) as failure:
        _LOGGER.warning("could not reach Home Assistant: %s", failure)
        return answer({"ok": False, "error": SILENT})
    return answer({"ok": True})


async def health(request: web.Request) -> web.Response:
    """Say the panel is up, for anything that wants to know without loading a page."""
    return web.json_response({"ok": True})


def nothing(said: str) -> web.Response:
    """Answer the page with no televisions and the reason there are none."""
    return answer({"televisions": [], "error": said})


def answer(body: dict[str, Any]) -> web.Response:
    """Send one JSON answer, which nobody may keep a copy of."""
    return no_store(web.json_response(body))


def no_store(response: web.Response) -> web.Response:
    """Forbid caching.

    Nothing here is worth a stale copy of: every value the panel serves is a state that
    can change while the page is open.
    """
    response.headers["Cache-Control"] = "no-store"
    return response


@web.middleware
async def only_ingress(request: web.Request, handler) -> web.StreamResponse:
    """Refuse anything that did not come through the Supervisor."""
    if request.remote != INGRESS:
        _LOGGER.warning("refused a request from %s", request.remote)
        raise web.HTTPForbidden(text="This panel is reachable through Home Assistant.")
    return await handler(request)


def build() -> web.Application:
    """Assemble the application, with its session owned by the app's own lifetime."""
    app = web.Application(middlewares=[only_ingress])
    app.router.add_get("/", index)
    app.router.add_get("/api/state", state)
    app.router.add_post("/api/do", do)
    app.router.add_get("/health", health)

    async def open_session(app: web.Application) -> None:
        app["session"] = session = ClientSession()
        app["home"] = HomeAssistant(session)

    async def close_session(app: web.Application) -> None:
        await app["session"].close()

    app.on_startup.append(open_session)
    app.on_cleanup.append(close_session)
    return app


def main() -> None:
    """Run until the Supervisor stops the container."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    _LOGGER.info("listening on %s", PORT)
    web.run_app(build(), host="0.0.0.0", port=PORT, print=None)
