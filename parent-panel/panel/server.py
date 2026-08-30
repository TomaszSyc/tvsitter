"""The web server, which does as little as a web server can.

Bound to every interface because the Supervisor's Ingress reaches it from another
container, and refusing everybody else because that is the whole of an Ingress app's
network security: the Supervisor is the only thing that should ever connect, and it
always connects from one address.

Six routes and no rendering. The page arrives once and asks for its own values
afterwards, so nothing here builds markup out of a state — which is why none of the API
routes ever answers with an error status. A 500 is a blank panel with nothing on it
saying why; the sentence travels in the body instead, and the page shows it.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError, ClientSession, web

from .api import apply, gathered
from .automations import Automations, configure, offer
from .blueprints import install
from .home_assistant import HomeAssistant, Refused
from .page import render_shell
from .words import phrase, words

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

# Said separately from the refusal above because it is a different thing to do next: a
# change to a television is worth trying again, an automation Home Assistant will not
# validate needs somebody to look at the log the reason went to.
NOT_A_REQUEST = "That was not a request."
UNKEPT = "Home Assistant would not keep that automation."
UNMADE = "Home Assistant would not make that change."


async def index(request: web.Request) -> web.Response:
    """Answer with the page, which fetches everything on it for itself.

    The words come with it rather than after it, because the page says things before it
    has asked Home Assistant anything — the destinations in the rail and the sentence
    under the title are on the screen while the first request is still in flight, and a
    rail that is briefly English is a rail that flickers. Asking which language costs
    one small request per page load, and a page load is not a thing that happens often.
    """
    home: HomeAssistant = request.app["home"]
    tongue = await home.language() if home.authorised else "en"
    # Kept for the actions that follow this page, which are answered in the same
    # language it was read in and have no page load of their own to ask on.
    request.app["tongue"] = tongue
    return no_store(
        web.Response(text=render_shell(words(tongue), tongue), content_type="text/html")
    )


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
    # `gathered` rather than `snapshot`: the week per app needs a second round trip for
    # the recorder's statistics, and it fails on its own rather than costing the page.
    return answer(await gathered(home, found))


async def do(request: web.Request) -> web.Response:
    """Make one change, and say why it could not, in the language it was asked in."""
    home: HomeAssistant = request.app["home"]
    tongue = request.app.get("tongue", "en")
    if not home.authorised:
        return answer({"ok": False, "error": phrase(NO_TOKEN, tongue)})

    try:
        asked = await request.json()
    except ValueError:
        return answer({"ok": False, "error": phrase(NOT_A_REQUEST, tongue)})
    if not isinstance(asked, dict):
        return answer({"ok": False, "error": phrase(NOT_A_REQUEST, tongue)})

    try:
        # Read afresh rather than from anything held: the page names a television by its
        # device, and which entity carries which control is a registry answer that
        # changes when somebody renames a set or the integration gains a control.
        await apply(home, await home.televisions(), asked)
    except ValueError as wrong:
        # Translated where there are words for it. Most of these name a television or a
        # field, so they are built where that is known and stay in English — which is
        # what this leaves behind rather than what it fixes.
        return answer({"ok": False, "error": phrase(str(wrong), tongue)})
    except PermissionError as refused:
        _LOGGER.error("%s", refused)
        return answer({"ok": False, "error": phrase(REFUSED, tongue)})
    except Refused as failure:
        # Home Assistant's own sentence when it wrote one: it says which television is
        # not listening, or which value it would not take, and the generic line said
        # neither. A parent painting a week while the set is asleep got "Home Assistant
        # would not make that change" and no idea what to do about it.
        _LOGGER.warning("the change was refused: %s", failure)
        return answer({"ok": False, "error": failure.why or phrase(UNMADE, tongue)})
    except RuntimeError as failure:
        _LOGGER.warning("the change was refused: %s", failure)
        return answer({"ok": False, "error": phrase(UNMADE, tongue)})
    except (ClientError, TimeoutError) as failure:
        _LOGGER.warning("could not reach Home Assistant: %s", failure)
        return answer({"ok": False, "error": phrase(SILENT, tongue)})
    return answer({"ok": True})


async def setup(request: web.Request) -> web.Response:
    """Answer with the choice a parent has to make, and what is already chosen."""
    home: HomeAssistant = request.app["home"]
    if not home.authorised:
        return unmade(NO_TOKEN)
    try:
        found = await home.televisions()
        return answer(await offer(request.app["automations"], found))
    except PermissionError as refused:
        _LOGGER.error("%s", refused)
        return unmade(REFUSED)
    except RuntimeError as failure:
        _LOGGER.warning("could not read the automations: %s", failure)
        return unmade(UNKEPT)
    except (ClientError, TimeoutError) as failure:
        _LOGGER.warning("could not read Home Assistant: %s", failure)
        return unmade(SILENT)


async def make(request: web.Request) -> web.Response:
    """Make one television's automation, and say plainly when it could not be made."""
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
        # Read afresh, as `/api/do` does: which event entity belongs to which television
        # is a registry answer, and the automation is written against that entity.
        await configure(request.app["automations"], await home.televisions(), asked)
    except ValueError as wrong:
        return answer({"ok": False, "error": str(wrong)})
    except PermissionError as refused:
        _LOGGER.error("%s", refused)
        return answer({"ok": False, "error": REFUSED})
    except RuntimeError as failure:
        _LOGGER.warning("the automation was refused: %s", failure)
        return answer({"ok": False, "error": UNKEPT})
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


def unmade(said: str) -> web.Response:
    """Answer the setup page with nothing to choose and the reason there is nothing."""
    return answer({"notify": [], "televisions": [], "error": said})


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
    app.router.add_get("/api/setup", setup)
    app.router.add_post("/api/setup", make)
    app.router.add_get("/health", health)

    async def open_session(app: web.Application) -> None:
        app["session"] = session = ClientSession()
        app["home"] = HomeAssistant(session)
        app["automations"] = Automations(session)

    async def close_session(app: web.Application) -> None:
        await app["session"].close()

    async def write_blueprints(app: web.Application) -> None:
        # On every start, not only the first: an update carries a new blueprint and the
        # copy in the configuration directory is the one Home Assistant actually reads.
        install()

    app.on_startup.append(write_blueprints)
    app.on_startup.append(open_session)
    app.on_cleanup.append(close_session)
    return app


def main() -> None:
    """Run until the Supervisor stops the container."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    _LOGGER.info("listening on %s", PORT)
    web.run_app(build(), host="0.0.0.0", port=PORT, print=None)
