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
# This app's own package. Written here rather than discovered: it is a constant of the
# product — the panel, the integration and the television are one thing with one name.
OURS = "app.tvsitter.tv"

RULE_WINDOWS = "windows"
RULE_APPS_ALLOWED = "apps_allowed"

# Not a rule the television enforces but something the integration says about itself,
# published beside the rules because the hours are what it affects.
RULE_FOLLOWING = "following_schedule"

# The grid is half-hourly. Finer would be a row of ninety-six boxes to tap on a phone;
# coarser would not express the half past four a school day actually starts at.
SLOT_MINUTES = 30
SLOTS_PER_DAY = 24 * 60 // SLOT_MINUTES


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
        "following_schedule": following(television),
        "hours": hours(television.rules.get(RULE_WINDOWS)),
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
        if worth_showing(package, television, allowed)
    ]
    # Name as the tie-break: the registry hands these over in whatever order it holds
    # them, and two apps on nought minutes would otherwise swap places on a refresh.
    return sorted(listed, key=lambda app: (-app["minutes"], app["name"]))


def worth_showing(package: str, television: Television, allowed: list[str]) -> bool:
    """Say whether an app belongs on a page a parent is deciding things on.

    Two kinds are dropped, and both would otherwise be controls that lie.

    This app is never listed. The engine exempts it and the launcher from an allow-list
    on purpose (D35): a parent who ticked four apps would leave the launcher off it, and
    the answer to "the launcher is not allowed" would be to send the television to the
    launcher, forever. A tick beside TV Sitter would do nothing, and a control that does
    nothing is worse than none. The launcher is not known here — its own issue.

    And a package with no time, no budget and no place on the allow-list is not
    something anybody watched: `android` and `com.android.systemui` arrive because the
    set charges them the odd second between apps. Anything a parent has decided about
    stays, however little it has run.
    """
    if package == OURS:
        return False
    return bool(
        television.app_minutes(package)
        or television.app_limit(package) is not None
        or package in allowed
    )


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


def following(television: Television) -> str | None:
    """Name the schedule helper the hours are being taken from, or nothing.

    While one is followed the grid is read-only: the integration re-imports the helper
    whenever it is edited, so hours written here would hold until somebody touched the
    helper and then vanish without a word. An integration too old to say anything about
    it is not following one.
    """
    said = television.rules.get(RULE_FOLLOWING)
    return said if isinstance(said, str) and said else None


def hours(said: Any) -> dict[str, list[str]]:
    """Lay the windows out as the half hours of each day they allow viewing in.

    The same weekly grid the windows already are, written the way a grid is drawn: one
    row per day, one box per half hour, named by the time the box starts. Derived from
    the windows on every read rather than kept beside them, because two copies of one
    rule is how a panel comes to show hours the television is not enforcing.

    Every day is present, and a day with nothing in it is a day with no window. Seven
    empty days is no restriction rather than a closed week (D27), which the page has to
    say in words — an empty grid on its own reads as the opposite.
    """
    ticked: dict[str, set[int]] = {day: set() for day in WEEK}
    for window in windows(said):
        slots = covered(window["from"], window["to"])
        for day in window["days"] or WEEK:
            # The engine takes `monday` beside `mon`, so a rule somebody wrote by hand
            # can carry either and both belong on the same row.
            named = day[:3].lower()
            if named in ticked:
                ticked[named] |= slots
    return {day: [time_of(slot) for slot in sorted(ticked[day])] for day in WEEK}


def covered(opens: Any, closes: Any) -> set[int]:
    """Say which half hours one window touches, as places in the day.

    A window that does not sit on the grid takes every half hour it reaches into,
    rather than only the whole ones. Rounding the other way would draw an empty day for
    a window of twenty minutes, and a grid saying nothing is allowed on a day the
    television allows viewing on is the worst of the readings available here.

    A window that starts when it ends is refused by the television and by the contract,
    so it is drawn as nothing rather than as the whole day it does not grant.
    """
    start, end = minute_of(opens), minute_of(closes)
    if start is None or end is None or start == end:
        return set()
    first = start // SLOT_MINUTES
    last = (end + SLOT_MINUTES - 1) // SLOT_MINUTES
    if start < end:
        return set(range(first, last))
    # Past midnight, and on the same row: the day a window names is the budget day, so
    # the small hours at the end of Monday evening are Monday's (D27).
    return set(range(first, SLOTS_PER_DAY)) | set(range(last))


def time_of(slot: int) -> str:
    """Name a half hour by the time it starts, and the one past the day by midnight."""
    minutes = (slot % SLOTS_PER_DAY) * SLOT_MINUTES
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def minute_of(said: Any) -> int | None:
    """Read `HH:MM` as minutes past midnight, or nothing when it is not a time.

    `HH:MM` and nothing else, the same strictness the engine reads windows with: a rule
    carrying `16:00:30` is refused there rather than rounded, and a panel that quietly
    accepted it would draw hours no television has.
    """
    if not isinstance(said, str):
        return None
    hour, _, minute = said.partition(":")
    if not (len(hour) == 2 and len(minute) == 2):
        return None
    # Plain digits, not merely digit-like: a superscript two passes `isdigit` and then
    # `int` refuses it, which would be a stack trace out of a rule somebody typed.
    if not all(part.isascii() and part.isdigit() for part in (hour, minute)):
        return None
    return None if int(hour) > 23 or int(minute) > 59 else int(hour) * 60 + int(minute)


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
        case "hours":
            refuse_while_following(television)
            await home.call(
                DOMAIN,
                "set_windows",
                {
                    "entity_id": entity(television, "rules"),
                    "windows": windows_for(request.get("days")),
                },
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


def refuse_while_following(television: Television) -> None:
    """Refuse to write hours a schedule helper is going to overwrite.

    The integration re-imports the helper whenever it changes, so a grid saved here
    would stand until somebody edited the helper and then be undone silently. Said
    rather than done: a control that writes something which disappears later is worse
    than one that explains why it will not.
    """
    followed = following(television)
    if followed is not None:
        raise ValueError(
            f"{television.name} takes its hours from {followed}, so they have to be "
            "changed there — anything set here would be undone by its next edit."
        )


def windows_for(said: Any) -> list[dict[str, Any]]:
    """Turn a week of ticked half hours back into the windows the rules carry.

    The same shape the schedule import writes, because it is the same weekly grid
    arriving by another door: contiguous half hours become one window, days that end
    up with identical hours share a window with a `days` list, and a window on the
    whole week drops `days` because that is what the rules mean by every day.

    A full week of ticked boxes is no restriction rather than seven windows: it is the
    same permission, said in the way the rules already have a word for (D27).
    """
    ticked = grid(said)
    if all(len(ticked[day]) == SLOTS_PER_DAY for day in WEEK):
        return []

    days_by_hours: dict[tuple[str, str], list[str]] = {}
    for day in WEEK:
        for span in spans(ticked[day]):
            days_by_hours.setdefault(span, []).append(day)

    written: list[dict[str, Any]] = []
    for (opens, closes), days in days_by_hours.items():
        window: dict[str, Any] = {
            "id": f"{opens}-{closes}".replace(":", ""),
            "from": opens,
            "to": closes,
        }
        # The days are collected in week order above, so they need no sorting here.
        if len(days) < len(WEEK):
            window["days"] = days
        written.append(window)
    return sorted(written, key=lambda window: (window["from"], window["to"]))


def spans(ticked: set[int]) -> list[tuple[str, str]]:
    """Gather one day's half hours into the fewest windows that say the same thing.

    A whole day cannot be one window: `from` equal to `to` is refused by the contract
    and dropped by the television, which would lock the day a parent had just opened
    entirely. Two halves say it instead, and read as it too.
    """
    if not ticked:
        return []
    if len(ticked) == SLOTS_PER_DAY:
        midday = SLOTS_PER_DAY // 2
        return [
            (time_of(0), time_of(midday)),
            (time_of(midday), time_of(SLOTS_PER_DAY)),
        ]

    runs: list[list[int]] = []
    for slot in sorted(ticked):
        if runs and slot == runs[-1][-1] + 1:
            runs[-1].append(slot)
        else:
            runs.append([slot])
    # Midnight is not a boundary in a day's own row — the window a parent drew from ten
    # at night to one in the morning arrives here as both ends of Monday, and two
    # windows meeting at midnight would warn the child that time was up as it passed.
    if len(runs) > 1 and runs[0][0] == 0 and runs[-1][-1] == SLOTS_PER_DAY - 1:
        evening = runs.pop()
        runs[0] = evening + runs[0]
    return [(time_of(run[0]), time_of(run[-1] + 1)) for run in runs]


def grid(said: Any) -> dict[str, set[int]]:
    """Read the week of ticked half hours the page sent, or say what is wrong with it.

    The whole grid every time, like the windows it becomes: an unticked half hour has
    no other way of being said, so a day the page leaves out is a day with no window.
    Anything else is refused rather than guessed at — this writes a rule that locks a
    television, and a misread key would take an evening away silently.
    """
    if not isinstance(said, dict):
        raise ValueError("This needs the days of the week and their half hours.")
    ticked: dict[str, set[int]] = {day: set() for day in WEEK}
    for day, slots in said.items():
        if day not in ticked:
            raise ValueError(f"There is no day called {day!r}.")
        if not isinstance(slots, list):
            raise ValueError(f"The half hours for {day} are not a list.")
        ticked[day] = {slot_of(slot) for slot in slots}
    return ticked


def slot_of(said: Any) -> int:
    """Read one `HH:MM` half hour as its place in the day, or say it is not one."""
    minutes = minute_of(said)
    if minutes is None or minutes % SLOT_MINUTES:
        raise ValueError(f"{said!r} is not a half hour this grid has.")
    return minutes // SLOT_MINUTES


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
