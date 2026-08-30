"""What the panel shows, and what it changes, apart from how either is served.

The shape built here is the whole contract the page is written against, so the page can
be replaced without touching Home Assistant and this can be tested without one. Every
duration is minutes and everything unset is null rather than zero: zero is a real
setting in every rule this project has — no viewing today, a blocked app — so a panel
that cannot tell an unset limit from a blocked one tells two lies with one number.

`apply` is the only place that knows which service a control on the page turns into. It
raises `ValueError` for anything the page asked for that is not there, because that is a
sentence to put on the page rather than a fault to log.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from typing import Any

from .home_assistant import DOMAIN, WEEK, HomeAssistant, Television

# The rules the television echoes back, under the names it sends them by. Only the two
# list-shaped ones are read here; the rest have entities of their own that say the same
# thing, and reading a number twice is how the two come to disagree.
RULE_WINDOWS = "windows"
RULE_APPS_ALLOWED = "apps_allowed"


def snapshot(televisions: list[Television]) -> dict[str, Any]:
    """Build everything the page draws, out of what was read from Home Assistant.

    Pure, so what a parent would see can be checked against a handful of made-up states
    rather than against a house.
    """
    return {"televisions": [described(one) for one in televisions], "error": None}


def described(television: Television) -> dict[str, Any]:
    """Say everything about one television, in the words the contract uses."""
    allowed = strings(television.rules.get(RULE_APPS_ALLOWED))
    return {
        "id": television.device_id,
        "name": television.name,
        "reporting": flag(television, "reporting"),
        "screen": flag(television, "screen"),
        "locked": flag(television, "lock"),
        "playing": television.state("active_app"),
        "pin_set": flag(television, "pin_set"),
        "used_today": television.number("used_today"),
        "limit_today": television.number("limit_today"),
        "remaining_today": television.number("remaining_today"),
        "bonus_today": television.number("bonus_today"),
        "used_yesterday": television.number("used_yesterday"),
        "last_reported": television.state("last_reported"),
        "rules_revision": revision(television),
        "daily_limit": television.number("daily_limit"),
        "sleep_timer": television.number("sleep_timer"),
        "warn_before": television.number("warn_before"),
        "block_settings": flag(television, "block_settings"),
        "week": {day: television.number(f"limit_{day}") for day in WEEK},
        "apps": apps(television, allowed),
        "allowed_apps": allowed,
        "windows": windows(television.rules.get(RULE_WINDOWS)),
        "trouble": trouble(television),
    }


def apps(television: Television, allowed: list[str]) -> list[dict[str, Any]]:
    """List what the child has watched today, the longest first.

    An empty allow-list allows everything rather than nothing — the reading every
    list-shaped rule here has (D27), and the one that fails towards a television
    somebody can still use.
    """
    listed = [
        {
            "package": package,
            "name": television.app_name(package),
            "minutes": television.app_minutes(package),
            "limit": television.app_limit(package),
            "allowed": not allowed or package in allowed,
        }
        for package in television.apps
    ]
    # Name as the tie-break: the registry hands these over in whatever order it holds
    # them, and two apps on nought minutes would otherwise swap places on a refresh.
    return sorted(listed, key=lambda app: (-app["minutes"], app["name"]))


def windows(said: Any) -> list[dict[str, Any]]:
    """List the hours viewing is allowed, with every key present.

    `days` is optional on the wire and means every day when it is missing. It is filled
    in here so the page has one shape to draw rather than two.
    """
    if not isinstance(said, list):
        return []
    return [
        {
            "id": window.get("id"),
            "from": window.get("from"),
            "to": window.get("to"),
            "days": strings(window.get("days")),
        }
        for window in said
        if isinstance(window, dict)
    ]


def trouble(television: Television) -> list[str]:
    """List what is wrong with one television, in sentences rather than in states.

    Empty when there is nothing to say, which is the only thing the page needs to
    know to stay quiet.
    """
    said: list[str] = []
    if not flag(television, "reporting"):
        said.append("Not reporting to Home Assistant.")
    elif flag(television, "reporting_stopped"):
        # Only while it still claims to be reporting. A set that has dropped off raises
        # both, and two sentences about one silence is one sentence too many.
        said.append("Nothing has arrived from this television for a while.")
    if not flag(television, "pin_set"):
        said.append("No parent PIN, so a lock cannot be lifted at the set.")
    return said


def flag(television: Television, key: str) -> bool:
    """Say whether one thing is so, treating nothing said as no.

    Unlike the numbers, which keep their difference between unset and zero: there is no
    third state a switch can be in that a parent would act on differently.
    """
    return television.state(key) == "on"


def revision(television: Television) -> int | None:
    """Say which revision of the rules the television is enforcing."""
    said = television.number("rules")
    return None if said is None else int(said)


def strings(said: Any) -> list[str]:
    """Take a list of package ids or day names off an attribute, or nothing at all."""
    if not isinstance(said, list):
        return []
    return [str(item) for item in said]


async def apply(
    home: HomeAssistant,
    televisions: list[Television],
    request: dict[str, Any],
) -> None:
    """Do the one thing the page asked for.

    Everything goes out as a service call, so the integration stays the only writer and
    the revision guard on `set_rules` keeps the single writer it was built for (D34).
    """
    television = found(televisions, request.get("id"))
    action = request.get("action")
    if not isinstance(action, str):
        raise ValueError("This needs an action.")

    match action:
        case "lock":
            await switched(home, entity(television, "lock"), request)
        case "block_settings":
            await switched(home, entity(television, "block_settings"), request)
        case "clear_limit":
            await home.call(
                "button", "press", {"entity_id": entity(television, "clear_limit")}
            )
        case "number":
            key = text(request, "key")
            await home.call(
                "number",
                "set_value",
                {
                    "entity_id": entity(television, key),
                    "value": needed(request, "value"),
                },
            )
        case "app_limit":
            await rule(
                home,
                television,
                "set_app_limit",
                {"package": text(request, "package")},
                request,
            )
        case "allowed_apps":
            await home.call(
                DOMAIN,
                "set_allowed_apps",
                {
                    "entity_id": entity(television, "rules"),
                    "packages": strings(request.get("packages")),
                },
            )
        case "schedule":
            await rule(
                home,
                television,
                "set_schedule",
                {"day": text(request, "day")},
                request,
            )
        case _:
            raise ValueError(f"There is nothing called {action!r} to do.")


async def switched(
    home: HomeAssistant, entity_id: str, request: dict[str, Any]
) -> None:
    """Turn one switch on or off, whichever the page asked for."""
    service = "turn_on" if request.get("on") else "turn_off"
    await home.call("switch", service, {"entity_id": entity_id})


async def rule(
    home: HomeAssistant,
    television: Television,
    service: str,
    data: dict[str, Any],
    request: dict[str, Any],
) -> None:
    """Write one rule that takes an optional number of minutes.

    The minutes are left out rather than sent as null when there are none: that is
    what both services read as "take the override away", and zero already means
    something else entirely.
    """
    minutes = request.get("minutes")
    if minutes is not None:
        data["minutes"] = number(minutes, "minutes")
    data["entity_id"] = entity(television, "rules")
    await home.call(DOMAIN, service, data)


def found(televisions: list[Television], device_id: Any) -> Television:
    """Find the television the page named, or say it is not there any more."""
    for television in televisions:
        if television.device_id == device_id:
            return television
    raise ValueError("That television is not here any more.")


def entity(television: Television, key: str) -> str:
    """Find one of a television's entities, or say which one it has not got.

    A television that was set up by an older version of the integration, or one whose
    entity a parent has deleted, is missing exactly one control rather than broken.
    """
    entity_id = television.entities.get(key)
    if entity_id is None:
        raise ValueError(f"{television.name} has no {key} to change.")
    return entity_id


def needed(request: dict[str, Any], name: str) -> float:
    """Read a number the request cannot be carried out without."""
    if request.get(name) is None:
        raise ValueError(f"This needs a {name}.")
    return number(request[name], name)


def number(said: Any, name: str) -> float:
    """Read one number, or say which field was not one."""
    try:
        return float(said)
    except (TypeError, ValueError):
        raise ValueError(f"{name} is not a number.") from None


def text(request: dict[str, Any], name: str) -> str:
    """Read one word the request cannot be carried out without."""
    said = request.get(name)
    if not isinstance(said, str) or not said:
        raise ValueError(f"This needs a {name}.")
    return said
