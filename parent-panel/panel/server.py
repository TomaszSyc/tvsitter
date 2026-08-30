"""The web server, which does as little as a web server can.

Bound to every interface because the Supervisor's Ingress reaches it from another
container, and refusing everybody else because that is the whole of an Ingress app's
network security: the Supervisor is the only thing that should ever connect, and it
always connects from one address.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import logging

from aiohttp import ClientError, ClientSession, web

from .home_assistant import HomeAssistant
from .page import render

_LOGGER = logging.getLogger("panel")

PORT = 8099

# The Supervisor's own address on the internal network. Documented as the only source an
# Ingress app must accept, and checked here rather than assumed: this container has no
# other authentication, so the address is the door.
INGRESS = "172.30.32.2"


async def index(request: web.Request) -> web.Response:
    """Answer with the page, or with what went wrong instead of a stack trace."""
    home: HomeAssistant = request.app["home"]
    if not home.authorised:
        return html(
            render(
                [],
                "No Supervisor token. This runs as a Home Assistant App, and "
                "started outside one it has nobody to ask.",
            )
        )
    try:
        found = await home.televisions()
    except PermissionError as refused:
        _LOGGER.error("%s", refused)
        return html(render([], "Home Assistant refused the token this App was given."))
    except (ClientError, TimeoutError) as failure:
        # Logged with the reason and shown without it: the page is read by a parent and
        # the log is read by whoever is fixing it.
        _LOGGER.warning("could not read Home Assistant: %s", failure)
        return html(
            render([], "Home Assistant did not answer. It may still be starting.")
        )
    return html(render(found))


async def health(request: web.Request) -> web.Response:
    """Say the panel is up, for anything that wants to know without rendering a page."""
    return web.json_response({"ok": True})


def html(body: str) -> web.Response:
    """Wrap markup as a response, with caching off.

    Nothing here is worth a stale copy of: every value on the page is a state that can
    change while the page is open.
    """
    return web.Response(
        text=body,
        content_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


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
