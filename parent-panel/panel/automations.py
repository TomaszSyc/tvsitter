"""Making the automation that answers a request, instead of describing how to.

`blueprints.py` puts the blueprint where Home Assistant reads it. A blueprint on its own
answers nobody: something has to say which television it watches and which phone it
rings, and `docs/setup.md` has been asking a person to say it in the automation editor
since M3 (#104).

Written through Home Assistant's own config API — the endpoints the automation editor
posts to — rather than into `automations.yaml` by hand. Generated YAML is a last resort
here, and it would be a bad one: the file is somebody's, it is loaded at startup and
rewritten by the editor, and two writers of one file is how a parent loses an automation
they wrote. The API takes JSON, validates the blueprint's inputs before keeping
anything, and reloads the automation itself.

Nothing of what the automation *does* is written here. That is the blueprint's, and a
second copy of it would be a second copy to keep in step.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
import logging
import os
from typing import Any
from urllib.parse import quote

import aiohttp

from .home_assistant import CORE_API, Television

_LOGGER = logging.getLogger("panel")

# The blueprint, named the way a `use_blueprint` config names one: the path under
# `blueprints/automation/`, which is what `blueprints.py` writes it to.
BLUEPRINT = "tvsitter/more_time_request.yaml"

# The entity the blueprint watches, by translation key rather than by entity id — a
# Polish Home Assistant calls it `event.tv_salon_prosba_o_czas`.
REQUEST_EVENT = "time_request"

NOTIFY = "notify"

# What the companion app registers a phone as. The blueprint needs one of these and not
# a notify entity: only the old-style service carries `actions`, and the buttons on the
# notification are the whole point of it.
MOBILE_APP = "mobile_app_"

CONFIG = f"{CORE_API}/config/automation/config"


@dataclass(slots=True)
class Answering:
    """The automation that already answers one television, as it is stored.

    The whole configuration is kept and not only what the page draws, because writing
    to it again means changing two inputs in something somebody else may have written.
    """

    config_id: str
    notify: str | None
    also_notify: str | None
    config: dict[str, Any]


class Automations:
    """The corner of the Core API that keeps automations.

    A client of its own rather than another method on `HomeAssistant`: that one reads
    states and registries and changes things by calling services, which is the whole of
    what the panel does to a television. This reads and writes Home Assistant's own
    stored configuration, which is a different thing to be allowed to do and worth
    keeping visibly separate.
    """

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Take the panel's one session, so shutdown still has a single owner."""
        self._session = session
        # The same App token the client uses, read from the environment the Supervisor
        # set it in rather than borrowed out of another object.
        self._token = os.environ.get("SUPERVISOR_TOKEN", "")

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def services(self) -> list[dict[str, Any]]:
        """Fetch everything this Home Assistant can be asked to do."""
        async with self._session.get(
            f"{CORE_API}/services",
            headers=self._headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as answer:
            await refused_or_broken(answer)
            return await answer.json()

    async def stored(self, config_id: str) -> dict[str, Any] | None:
        """Read one automation as Home Assistant has it written down.

        Nothing when there is no automation under that id, which is an answer rather
        than a fault: it is how "this television has none yet" is found out.
        """
        async with self._session.get(
            f"{CONFIG}/{quote(config_id, safe='')}",
            headers=self._headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as answer:
            if answer.status == HTTPStatus.NOT_FOUND:
                return None
            await refused_or_broken(answer)
            return await answer.json()

    async def store(self, config_id: str, config: dict[str, Any]) -> None:
        """Write one automation under an id chosen here.

        Home Assistant files automations by id and replaces the one it already has under
        that id, so the same id twice is one automation and not two. It validates the
        blueprint's inputs before keeping anything, and reloads the automation
        afterwards — so a parent who saves is answered by the next request.
        """
        async with self._session.post(
            f"{CONFIG}/{quote(config_id, safe='')}",
            headers=self._headers,
            json=config,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as answer:
            await refused_or_broken(answer)


async def refused_or_broken(answer: aiohttp.ClientResponse) -> None:
    """Turn a refusal into the two things the panel says differently.

    A token Home Assistant will not take is a sentence about this App; anything else is
    a sentence about the change not being made. The status alone cannot tell a page
    which, so it is sorted out here rather than at the route.
    """
    if answer.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
        raise PermissionError("Home Assistant refused the Supervisor token")
    if answer.status >= HTTPStatus.BAD_REQUEST:
        raise RuntimeError(
            f"{answer.url.path} answered {answer.status}: {await answer.text()}"
        )


def notify_services(services: list[dict[str, Any]]) -> list[str]:
    """List every notification this Home Assistant can be asked to send."""
    for domain in services:
        if domain.get("domain") == NOTIFY:
            return sorted(
                f"{NOTIFY}.{name}" for name in domain.get("services", {}) or {}
            )
    return []


def mobile_apps(services: list[dict[str, Any]]) -> list[str]:
    """Pick the phones out of them, which are the only ones worth offering.

    The blueprint says why in its own words: an action button only exists on the
    old-style `notify.mobile_app_…` service, and a notify entity would send the same
    sentence with nothing to tap on it.
    """
    return [
        service
        for service in notify_services(services)
        if service.startswith(f"{NOTIFY}.{MOBILE_APP}")
    ]


def automation_ids(states: dict[str, dict[str, Any]]) -> list[str]:
    """Name every automation in the house by the id its configuration is filed under.

    The id travels in the state, as a capability attribute — so the list costs nothing
    beyond the states the panel already fetched, and no second way of listing
    automations has to be invented.

    An automation written into `configuration.yaml` without an `id` is not here. Nothing
    can read or write one of those through the config API either, so a panel that listed
    it would only be offering to fail.
    """
    listed: list[str] = []
    for entity_id, state in states.items():
        if not entity_id.startswith("automation."):
            continue
        config_id = state.get("attributes", {}).get("id")
        if isinstance(config_id, str) and config_id:
            listed.append(config_id)
    return listed


def answers(config: dict[str, Any] | None, event_entity: str) -> bool:
    """Say whether one stored automation is this television's request being answered.

    Two things have to hold, and neither is the automation's name: it was made from this
    project's blueprint, and it was pointed at this television's event. The blueprint's
    path is how Home Assistant names a blueprint everywhere, and the input is the only
    thing in the whole configuration that names a television — everything else the
    automation does lives in the blueprint.
    """
    if not isinstance(config, dict):
        return False
    used = config.get("use_blueprint")
    if not isinstance(used, dict) or used.get("path") != BLUEPRINT:
        return False
    asked = used.get("input")
    if not isinstance(asked, dict):
        return False
    pointed = asked.get("request_event")
    # A single-entity selector hands back a string. The same input written by hand can
    # be a list, and one naming this television among others still answers it.
    if isinstance(pointed, list):
        return event_entity in pointed
    return pointed == event_entity


def chosen(config: dict[str, Any]) -> tuple[str | None, str | None]:
    """Read back which phones an automation notifies, so the page opens on them.

    The second one is nothing unless the switch beside it is on. The blueprint has a
    default for it — `notify.persistent_notification` — and showing a default that
    nothing is sent to would be a page inventing a setting.
    """
    asked = config.get("use_blueprint", {}).get("input", {})
    notify = asked.get("notify_action")
    second = asked.get("second_notify_action") if asked.get("also_notify") else None
    return (
        notify if isinstance(notify, str) else None,
        second if isinstance(second, str) else None,
    )


def ours(device_id: str) -> str:
    """Build the id this panel files a television's automation under.

    Derived from the device, where Home Assistant's own editor uses the clock. A clock
    gives a new id every time, and a new id is a new automation: two notifications for
    one request, both of which work, which is the failure #104 asks not to ship. The
    device id is the one name a television keeps through being renamed.
    """
    return f"tvsitter_more_time_{device_id}"


def body(
    name: str, event_entity: str, notify: str, also_notify: str | None
) -> dict[str, Any]:
    """Build the automation Home Assistant is asked to keep.

    The offers and the expiry are deliberately absent. The blueprint has defaults for
    them, and writing today's defaults in here would quietly stop them following the
    blueprint's — an automation pinned to fifteen minutes because a panel once wrote
    fifteen.
    """
    asked: dict[str, Any] = {
        "request_event": event_entity,
        "notify_action": notify,
    }
    if also_notify:
        asked["also_notify"] = True
        asked["second_notify_action"] = also_notify
    return {
        "alias": f"TV Sitter — more time on {name}",
        "description": (
            "Made by the TV Sitter parent panel, which changes the phones on it when "
            "they are chosen again. The wording is in the blueprint, not here."
        ),
        "use_blueprint": {"path": BLUEPRINT, "input": asked},
    }


def rewritten(
    config: dict[str, Any], notify: str, also_notify: str | None
) -> dict[str, Any]:
    """Change the phones in an automation that already exists, and nothing else.

    Everything else is left exactly as it was found — what a parent called it, what it
    is pointed at, whether they had disabled it. The panel was asked about a phone, and
    an automation somebody wrote by hand from this blueprint is theirs; rewriting it
    whole would quietly undo a second television they had added to it, or a name they
    chose. The one thing that has to go is the second device when it is switched off,
    which is why it is removed before it is written rather than left to be overwritten.
    """
    asked = dict(config.get("use_blueprint", {}).get("input", {}))
    asked["notify_action"] = notify
    asked.pop("also_notify", None)
    asked.pop("second_notify_action", None)
    if also_notify:
        asked["also_notify"] = True
        asked["second_notify_action"] = also_notify
    return {
        **config,
        "use_blueprint": {**config["use_blueprint"], "input": asked},
    }


def states_of(televisions: list[Television]) -> dict[str, dict[str, Any]]:
    """Take the states already fetched, which are every state there is.

    The client hands each television the whole map, so the house's automations are in
    there too and the search below costs no request of its own.
    """
    return televisions[0].states if televisions else {}


async def answering(
    client: Automations, televisions: list[Television]
) -> dict[str, Answering]:
    """Find, for each television, the automation that already answers its requests.

    Ours first, by the id it would have been filed under. After the first run that is
    the whole answer, at one request per television rather than one per automation in
    the house.

    Only a television with none of ours sends the panel through the rest of them. That
    is what finds an automation made by hand from this blueprint — which `docs/setup.md`
    asked for by hand for four milestones, so plenty exist. Finding it is the point:
    the panel then writes to that one instead of adding a second automation answering
    the same request.
    """
    wanted = {
        television.device_id: event
        for television in televisions
        if (event := television.entities.get(REQUEST_EVENT))
    }

    found: dict[str, Answering] = {}
    for device_id, event in wanted.items():
        config = await client.stored(ours(device_id))
        if config is not None and answers(config, event):
            found[device_id] = reading(ours(device_id), config)

    missing = {
        device_id: event
        for device_id, event in wanted.items()
        if device_id not in found
    }
    if not missing:
        return found

    read = {ours(device_id) for device_id in wanted}
    for config_id in automation_ids(states_of(televisions)):
        if config_id in read:
            continue
        read.add(config_id)
        config = await client.stored(config_id)
        for device_id, event in list(missing.items()):
            if answers(config, event):
                found[device_id] = reading(config_id, config)
                del missing[device_id]
        if not missing:
            break

    return found


def reading(config_id: str, config: dict[str, Any]) -> Answering:
    """Say what one stored automation amounts to, for a page to draw."""
    notify, second = chosen(config)
    return Answering(
        config_id=config_id, notify=notify, also_notify=second, config=config
    )


async def offer(client: Automations, televisions: list[Television]) -> dict[str, Any]:
    """Say what a parent can choose, and what has been chosen already.

    `ready` is a television with a request event to answer at all. One set up by an
    older integration has none, and a picker offering to notify a phone about nothing is
    a control that lies.
    """
    found = await answering(client, televisions)
    return {
        "notify": mobile_apps(await client.services()),
        "televisions": [told(television, found) for television in televisions],
        "error": None,
    }


def told(television: Television, found: dict[str, Answering]) -> dict[str, Any]:
    """Say what the page needs about one television, in the words the page uses."""
    said = found.get(television.device_id)
    return {
        "id": television.device_id,
        "name": television.name,
        "ready": REQUEST_EVENT in television.entities,
        "configured": said is not None,
        "notify": said.notify if said else None,
        "also_notify": said.also_notify if said else None,
    }


async def configure(
    client: Automations, televisions: list[Television], request: dict[str, Any]
) -> None:
    """Make one television's automation, or change the phones on the one it has.

    Idempotent from both ends. An automation the panel wrote is found by its own id;
    one made by hand is found by what it is pointed at, and either is written under the
    id it already had. However many times this is run, and whoever made the first one,
    a television ends up with exactly one automation answering its requests (#104).
    """
    television = named(televisions, request.get("id"))
    event = television.entities.get(REQUEST_EVENT)
    if event is None:
        raise ValueError(f"{television.name} has no time request to answer.")

    known = notify_services(await client.services())
    notify = picked(request.get("notify"), known)
    second = request.get("also_notify")
    also_notify = None if second in (None, "") else picked(second, known)
    if also_notify == notify:
        # Two notifications on one device, both of which work: whichever is answered
        # first settles the request and the other one is left on screen as a button
        # that now does nothing.
        raise ValueError("The second device has to be a different one.")

    said = (await answering(client, [television])).get(television.device_id)
    config_id = said.config_id if said else ours(television.device_id)
    config = (
        rewritten(said.config, notify, also_notify)
        if said
        else body(television.name, event, notify, also_notify)
    )

    await client.store(config_id, config)
    _LOGGER.info("automation %s answers %s on %s", config_id, event, television.name)


def named(televisions: list[Television], device_id: Any) -> Television:
    """Find the television the page named, or say it is not there any more."""
    for television in televisions:
        if television.device_id == device_id:
            return television
    raise ValueError("That television is not here any more.")


def picked(said: Any, known: list[str]) -> str:
    """Read one notification target, or say plainly what is wrong with it.

    Checked against what Home Assistant currently has rather than against its shape: a
    phone whose companion app was removed leaves an automation that fails silently every
    evening, and the panel is the last place that can say so out loud.
    """
    if not isinstance(said, str) or not said:
        raise ValueError("Choose a phone to notify.")
    if said not in known:
        raise ValueError(f"{said} is not a notification Home Assistant can send.")
    return said
