"""The week behind the panel, which only Home Assistant's recorder remembers.

A television keeps a budget day and yesterday's closed one, and nothing further back:
the history is Home Assistant's job, not the set's (#103). It lives in the long-term
statistics, which have no REST route at all — so this opens a WebSocket of its own,
asks one question and closes it, the way the registry is read.

Nothing here is worth a blank panel. Every way this can fail ends as no figures, and no
figures is also what a fresh install honestly looks like: the recorder needs a day
before it has anything to say.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
from typing import Any

import aiohttp
from aiohttp import ClientError

from .home_assistant import CORE_WEBSOCKET, HomeAssistant, Television

_LOGGER = logging.getLogger("panel")

COMMAND = "recorder/statistics_during_period"

DAYS = 7

# Day by day rather than one seven-day period: the recorder's `week` is a calendar week
# from Monday, which would answer for this week so far rather than for the last seven
# days. Seven daily figures added up are the week a parent means.
PERIOD = "day"

# `change`, which is the only one of the seven that answers "how many minutes did this
# app get". The per-app sensors are `total_increasing` and drop to nought at 04:00 when
# the budget day rolls over, so: `state` is the counter itself, which on any given day
# is only its reading at the end of that period; `sum` is the running total since the
# sensor was created and climbs for ever; and `mean`, `min` and `max` are not recorded
# at all for a counter — the recorder keeps sums for those, not averages. `change` is
# the difference between the sum at the two ends of the period, and the sum is built to
# carry on across a reset rather than to fall with it, so a day that started at nought
# still reports what it gained.
TYPES = ["change"]

# Minutes, asked for rather than assumed. The figures are handed over in whatever unit
# the sensor displays in, and a parent who has set one of these to hours would
# otherwise be shown hours labelled as minutes — sixty times the week they had.
UNITS = {"duration": "min"}

# What a socket to Home Assistant can do instead of answering. Every one of them means
# the same thing here — no figures this time — but they are named rather than caught
# wholesale, so a mistake in this module still surfaces as a mistake.
UNANSWERED = (
    ClientError,
    OSError,
    TimeoutError,
    RuntimeError,
    PermissionError,
    ValueError,
    TypeError,
)


async def by_television(
    home: HomeAssistant, televisions: list[Television]
) -> dict[str, list[dict[str, Any]]]:
    """Say what each television's apps were watched for over the last seven days.

    Keyed by device, because that is what the page names a television by. One question
    covers every set on the page: the statistics are asked for by id, and a house with
    three televisions is no reason for three sockets.
    """
    wanted = sorted(
        {entity_id for television in televisions for entity_id in sensors(television)}
    )
    if not wanted:
        return {}

    try:
        # The session and the token belong to the client because nothing else here
        # speaks to Home Assistant. This does, for want of a REST route — and it
        # borrows rather than opening a second session, which would be a second
        # connection pool and a second thing to close.
        figures = await read(home._session, home._token, wanted)
    except UNANSWERED as failure:
        _LOGGER.warning("no figures for the week: %s", failure)
        return {}

    minutes = totals(figures)
    return {
        television.device_id: listed(television, minutes) for television in televisions
    }


async def read(
    session: aiohttp.ClientSession, token: str, statistic_ids: list[str]
) -> Any:
    """Ask the recorder for seven days of figures, over a socket of this call's own.

    Opened and closed around the one question, like the registry read beside it: a week
    changes once a day, which is not often enough to hold a connection for.
    """
    # A limit on waiting as well as on closing, unlike the registry read: that one is
    # the page, and this one is a figure on it. A Home Assistant that takes the
    # question and never answers must cost the week rather than the whole refresh.
    async with session.ws_connect(
        CORE_WEBSOCKET, timeout=aiohttp.ClientWSTimeout(ws_receive=15, ws_close=15)
    ) as socket:
        await socket.receive_json()  # auth_required
        await socket.send_json({"type": "auth", "access_token": token})
        greeting = await socket.receive_json()
        if greeting.get("type") != "auth_ok":
            raise PermissionError("Home Assistant refused the Supervisor token")

        await socket.send_json(
            {
                "id": 1,
                "type": COMMAND,
                "statistic_ids": statistic_ids,
                "start_time": since().isoformat(),
                "period": PERIOD,
                "types": TYPES,
                "units": UNITS,
            }
        )
        return await answered(socket, 1)


async def answered(socket: aiohttp.ClientWebSocketResponse, message_id: int) -> Any:
    """Wait for the answer carrying one id, whatever else arrives first.

    Matched on the id rather than taken as the next message, for the reason the
    registry read gives: the socket also carries events, and the first thing along is
    not necessarily the answer to the question just asked.
    """
    while True:
        said = await socket.receive_json()
        if said.get("id") != message_id or said.get("type") != "result":
            continue
        if not said.get("success", False):
            # A recorder that is switched off answers this way rather than by failing
            # to connect, and so does a Home Assistant too old to know the command.
            raise RuntimeError(f"{COMMAND} was refused: {said.get('error')}")
        return said.get("result")


def since(now: datetime | None = None) -> datetime:
    """Say when the seven days start.

    A rolling week rather than seven whole days. The first day is a part day, and it is
    counted from this hour a week ago: `change` measures from the start time asked for,
    not from the midnight before it.
    """
    return (now or datetime.now(UTC)) - timedelta(days=DAYS)


def totals(said: Any) -> dict[str, float]:
    """Add up what each statistic gained across the days it was asked about.

    Pure, so the arithmetic can be checked against an answer written out by hand rather
    than against a house with a recorder in it.

    A statistic the recorder said nothing about is absent rather than nought. The two
    are different answers — "there is no history for this app" against "this app was
    not watched" — and the first is what every install looks like on its first day.
    """
    if not isinstance(said, dict):
        return {}

    gathered: dict[str, float] = {}
    for statistic_id, rows in said.items():
        if not isinstance(rows, list):
            continue
        minutes = [change_in(row) for row in rows]
        counted = [one for one in minutes if one is not None]
        if counted:
            # Rounded because seven added floats land on 312.50000000000006, and a
            # number the page has to format is not the place to carry that.
            gathered[str(statistic_id)] = round(sum(counted), 1)
    return gathered


def change_in(row: Any) -> float | None:
    """Read one period's minutes, or nothing where the recorder had none.

    A row whose sum is missing carries a null change — a gap in the history rather than
    a day with no viewing — and a gap adds nothing to the week.
    """
    if not isinstance(row, dict):
        return None
    change = row.get("change")
    # Booleans are integers in Python and nothing here should ever be one, but a
    # `True` counted as a minute is the kind of figure nobody questions afterwards.
    if isinstance(change, bool) or not isinstance(change, int | float):
        return None
    return float(change)


def listed(television: Television, minutes: dict[str, float]) -> list[dict[str, Any]]:
    """Say what one television's apps were watched for, longest first.

    Named the way the daily list names them, off the sensor's own friendly name, so one
    app reads the same in both places rather than as a package id in one of them.

    An app with no figures is left out, and so is one whose seven days come to nothing:
    a week is a list of what was watched, and a row of noughts is a page a parent has
    to read past. What they have decided about is on the daily list, which keeps them.
    """
    found = [
        {
            "package": package,
            "name": television.app_name(package),
            "minutes": minutes[entity_id],
        }
        for entity_id, package in sensors(television).items()
        if minutes.get(entity_id)
    ]
    # Name as the tie-break, as on the daily list: two apps on the same figure would
    # otherwise swap places between one refresh and the next.
    return sorted(found, key=lambda app: (-app["minutes"], app["name"]))


def sensors(television: Television) -> dict[str, str]:
    """Name the statistic behind each of one television's apps, keyed by statistic.

    A sensor's statistic is named by the entity itself, so the per-app sensors are the
    ids to ask for — and the answer comes back under the same names.
    """
    return {
        found["sensor"]: package
        for package, found in television.apps.items()
        if found.get("sensor")
    }
