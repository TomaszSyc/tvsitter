"""The week of viewing, checked without a recorder to remember one.

The arithmetic and the question are separated on purpose: what the panel asks Home
Assistant is written out here as a message, and what it makes of the answer is checked
against an answer written by hand. Neither needs a house with a database in it.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from aiohttp import ClientError
from panel.home_assistant import HomeAssistant, Television
from panel.statistics import DAYS, by_television, listed, since, totals
import pytest

DEVICE = "b0fc4e4987a5b78b71faf37e6a219e9b"

NETFLIX = "sensor.tv_salon_netflix"
YOUTUBE = "sensor.tv_salon_youtube"


def television() -> Television:
    """Build a television with two apps, each with a sensor a statistic is kept for."""
    one = Television(device_id=DEVICE, name="TV Salon")
    for package, entity_id, name in (
        ("com.netflix.ninja", NETFLIX, "Netflix"),
        ("com.google.android.youtube.tv", YOUTUBE, "YouTube"),
    ):
        one.apps[package] = {"sensor": entity_id, "limit": f"number.{name}"}
        one.states[entity_id] = {
            "state": "0",
            "attributes": {"friendly_name": f"TV Salon {name}"},
        }
    return one


def days(*changes: float | None) -> list[dict[str, Any]]:
    """Write out one statistic's days, the way the recorder hands them over."""
    return [
        {"start": index, "end": index + 1, "change": change}
        for index, change in enumerate(changes)
    ]


class Socket:
    """A WebSocket that answers what it was given and remembers what it was asked.

    An async context manager because that is how the real one is used, and the panel
    closing the socket after its one question is part of what is being checked.
    """

    def __init__(self, *answers: dict[str, Any]) -> None:
        """Queue the messages this socket will hand over, in order."""
        self.answers = list(answers)
        self.sent: list[dict[str, Any]] = []

    async def __aenter__(self) -> Socket:
        """Hand back the socket itself, as `ws_connect` does."""
        return self

    async def __aexit__(self, *failure: object) -> None:
        """Close, which for a written-down socket is nothing at all."""
        return None

    async def receive_json(self) -> dict[str, Any]:
        """Hand over the next message written down for this call."""
        return self.answers.pop(0)

    async def send_json(self, message: dict[str, Any]) -> None:
        """Remember one message instead of sending it."""
        self.sent.append(message)


class Session:
    """A client session whose socket, or whose failure, is written down in advance."""

    def __init__(self, socket: Socket | None = None, failure: Exception | None = None):
        """Take whichever of the two this test is about."""
        self.socket = socket
        self.failure = failure
        self.connected = 0

    def ws_connect(self, url: str, **named: Any) -> Socket:
        """Open the written-down socket, or fail the way a real one would."""
        self.connected += 1
        if self.failure is not None:
            raise self.failure
        assert self.socket is not None
        return self.socket


def answering(result: Any) -> Socket:
    """Build a socket that greets, authenticates, and answers the one question."""
    return Socket(
        {"type": "auth_required"},
        {"type": "auth_ok"},
        {"id": 1, "type": "result", "success": True, "result": result},
    )


def home(session: Session, monkeypatch: pytest.MonkeyPatch) -> HomeAssistant:
    """Build the client the panel uses, around a session that answers on paper."""
    monkeypatch.setenv("SUPERVISOR_TOKEN", "a-token")
    return HomeAssistant(session)


async def test_the_question_asks_the_recorder_for_the_change_over_seven_days(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`change` is the only statistic that answers what one day gave one app."""
    socket = answering({})
    await by_television(home(Session(socket), monkeypatch), [television()])

    asked = socket.sent[-1]
    assert asked["type"] == "recorder/statistics_during_period"
    assert asked["period"] == "day"
    assert asked["types"] == ["change"]
    assert asked["units"] == {"duration": "min"}
    assert sorted(asked["statistic_ids"]) == sorted([NETFLIX, YOUTUBE])


async def test_the_seven_days_are_the_seven_before_now(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rolling week: the question is what was watched, not which week it was."""
    socket = answering({})
    await by_television(home(Session(socket), monkeypatch), [television()])

    started = datetime.fromisoformat(socket.sent[-1]["start_time"])

    assert timedelta(days=DAYS) - (datetime.now(UTC) - started) < timedelta(minutes=1)


async def test_a_week_with_two_apps_comes_back_longest_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The question is what he has been watching, and the answer belongs at the top."""
    socket = answering({NETFLIX: days(60.0, 28.0), YOUTUBE: days(100.0, 90.0, 122.5)})

    written = await by_television(home(Session(socket), monkeypatch), [television()])

    assert written[DEVICE] == [
        {
            "package": "com.google.android.youtube.tv",
            "name": "YouTube",
            "minutes": 312.5,
        },
        {"package": "com.netflix.ninja", "name": "Netflix", "minutes": 88.0},
    ]


async def test_an_app_the_recorder_knows_nothing_about_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No history is a different answer from nothing watched, and a nought is not it."""
    socket = answering({NETFLIX: days(88.0)})

    written = await by_television(home(Session(socket), monkeypatch), [television()])

    assert [app["name"] for app in written[DEVICE]] == ["Netflix"]


async def test_an_empty_answer_is_an_empty_week(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Which is the ordinary case on a fresh install: nothing yet, rather than none."""
    written = await by_television(
        home(Session(answering({})), monkeypatch), [television()]
    )

    assert written[DEVICE] == []


async def test_a_socket_that_will_not_open_is_an_empty_week(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No page is worth losing over a week: the rest of it is still true."""
    session = Session(failure=ClientError("no route to Home Assistant"))

    written = await by_television(home(session, monkeypatch), [television()])

    assert written == {}


async def test_a_recorder_that_refuses_the_question_is_an_empty_week(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Home Assistant with the recorder switched off answers, and says no."""
    socket = Socket(
        {"type": "auth_required"},
        {"type": "auth_ok"},
        {
            "id": 1,
            "type": "result",
            "success": False,
            "error": {"code": "unknown_command"},
        },
    )

    written = await by_television(home(Session(socket), monkeypatch), [television()])

    assert written == {}


async def test_a_token_that_is_refused_is_an_empty_week(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The page says that in its own words already; the week just goes quiet."""
    socket = Socket({"type": "auth_required"}, {"type": "auth_invalid"})

    written = await by_television(home(Session(socket), monkeypatch), [television()])

    assert written == {}


async def test_the_answer_to_another_message_is_not_this_ones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The socket carries events too, and the first one along is not the answer."""
    socket = Socket(
        {"type": "auth_required"},
        {"type": "auth_ok"},
        {"id": 8, "type": "event", "event": {"a": "state change"}},
        {"id": 1, "type": "result", "success": True, "result": {NETFLIX: days(88.0)}},
    )

    written = await by_television(home(Session(socket), monkeypatch), [television()])

    assert [app["minutes"] for app in written[DEVICE]] == [88.0]


async def test_a_television_with_no_apps_is_not_worth_a_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A set that has reported nothing has no statistic to ask about."""
    session = Session()

    written = await by_television(
        home(session, monkeypatch), [Television(device_id=DEVICE, name="TV Salon")]
    )

    assert written == {}
    assert session.connected == 0


def test_the_days_of_one_statistic_add_up_to_its_week() -> None:
    """Seven daily figures rather than one, because a week here is not a calendar."""
    assert totals({NETFLIX: days(10.0, 20.5, 30.0)}) == {NETFLIX: 60.5}


def test_a_statistic_with_no_days_is_absent_rather_than_nought() -> None:
    """The recorder returns nothing for an app it has never seen, and so does this."""
    assert totals({NETFLIX: [], YOUTUBE: days(4.0)}) == {YOUTUBE: 4.0}


def test_a_day_the_recorder_has_a_gap_in_adds_nothing() -> None:
    """A null change is a hole in the history, not an evening with nothing watched."""
    assert totals({NETFLIX: days(10.0, None, 5.0)}) == {NETFLIX: 15.0}


def test_a_week_of_nothing_but_gaps_has_no_figures_in_it() -> None:
    """Rows the recorder could put no number in say as little as no rows at all."""
    assert totals({NETFLIX: days(None, None)}) == {}


def test_the_arithmetic_does_not_leave_a_tail_on_the_wire() -> None:
    """Seven added floats land on 312.50000000000006, which is nobody's week."""
    assert totals({NETFLIX: days(0.1, 0.2)}) == {NETFLIX: 0.3}


def test_anything_that_is_not_an_answer_is_no_figures() -> None:
    """It arrives over a socket, so it is checked rather than trusted."""
    assert totals(None) == {}
    assert totals([{"change": 5}]) == {}
    assert totals({NETFLIX: "an afternoon"}) == {}
    assert totals({NETFLIX: [{"change": "an afternoon"}, {"change": True}]}) == {}


def test_an_app_with_nothing_watched_all_week_is_left_off() -> None:
    """A row of noughts is a page a parent reads past; the daily list keeps them."""
    assert listed(television(), {NETFLIX: 0.0, YOUTUBE: 12.0}) == [
        {
            "package": "com.google.android.youtube.tv",
            "name": "YouTube",
            "minutes": 12.0,
        }
    ]


def test_the_names_are_the_ones_the_television_gave_its_apps() -> None:
    """The same place the daily list takes them from, so one app reads the same."""
    assert [app["name"] for app in listed(television(), {NETFLIX: 3.0})] == ["Netflix"]


def test_two_apps_on_the_same_figure_keep_their_order() -> None:
    """Otherwise they swap places between one refresh of the page and the next."""
    written = listed(television(), {NETFLIX: 5.0, YOUTUBE: 5.0})

    assert [app["name"] for app in written] == ["Netflix", "YouTube"]


def test_the_week_starts_seven_days_before_it_is_asked_for() -> None:
    """Which is what the page says it is showing."""
    now = datetime(2026, 8, 30, 13, 0, tzinfo=UTC)

    assert since(now) == datetime(2026, 8, 23, 13, 0, tzinfo=UTC)
