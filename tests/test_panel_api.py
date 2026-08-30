"""The shape the panel's page is served, checked against the contract it was agreed.

Written from the contract rather than the implementation, deliberately: the page and
the server were built to the same document by different hands, and the only thing that
catches a disagreement between them is a test that believes neither.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from typing import Any

from panel.api import apply, snapshot
from panel.home_assistant import WEEK, Television
import pytest

DEVICE = "b0fc4e4987a5b78b71faf37e6a219e9b"


def television(**states: Any) -> Television:
    """Build a television saying the given things, keyed by translation key."""
    one = Television(device_id=DEVICE, name="TV Salon")
    for key, value in states.items():
        entity_id = f"x.{key}"
        one.entities[key] = entity_id
        one.states[entity_id] = {"state": str(value), "attributes": {}}
    return one


def only(one: Television) -> dict[str, Any]:
    """Pull the one television out of a snapshot."""
    answer = snapshot([one])
    assert answer["error"] is None
    return answer["televisions"][0]


def test_the_snapshot_names_the_television_and_its_device() -> None:
    """The name is what a parent reads; the id is what a change has to name."""
    written = only(television(rules="52"))

    assert written["id"] == DEVICE
    assert written["name"] == "TV Salon"


def test_on_and_off_arrive_as_booleans() -> None:
    """The page renders; it should not also parse Home Assistant's vocabulary."""
    written = only(television(reporting="on", screen="off", lock="on"))

    assert written["reporting"] is True
    assert written["screen"] is False
    assert written["locked"] is True


def test_durations_arrive_as_minutes_for_the_page_to_format() -> None:
    """One place decides how a length reads, and it is the one with the screen."""
    written = only(television(used_today="167.95", daily_limit="60"))

    assert written["used_today"] == 167.95
    assert written["daily_limit"] == 60.0


def test_unset_is_null_and_zero_is_zero() -> None:
    """Zero is a real setting here — no viewing today — so it is never null."""
    written = only(television(daily_limit="0", sleep_timer="unknown"))

    assert written["daily_limit"] == 0.0
    assert written["sleep_timer"] is None


def test_every_day_of_the_week_is_present_even_when_unset() -> None:
    """A page drawing seven rows should not have to know which keys were omitted."""
    written = only(television(limit_sat="120"))

    assert set(written["week"]) == {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
    assert written["week"]["sat"] == 120.0
    assert written["week"]["mon"] is None


def with_apps() -> Television:
    """Build a television that has watched three things today, one of them briefly."""
    one = television(rules="52")
    for package, name, minutes in (
        ("com.netflix", "Netflix", "14.8"),
        ("com.youtube", "YouTube", "40.9"),
        ("com.spotify", "Spotify", "4.7"),
    ):
        one.apps[package] = {"sensor": f"sensor.{name}", "limit": f"number.{name}"}
        one.states[f"sensor.{name}"] = {
            "state": minutes,
            "attributes": {"friendly_name": f"TV Salon {name}"},
        }
        one.states[f"number.{name}"] = {"state": "unknown", "attributes": {}}
    return one


def test_the_apps_come_back_longest_first() -> None:
    """The question is what he is watching, and the answer belongs at the top."""
    written = only(with_apps())

    assert [app["name"] for app in written["apps"]] == ["YouTube", "Netflix", "Spotify"]


def test_every_app_is_allowed_while_the_allow_list_is_empty() -> None:
    """An empty allow-list is no restriction (D35). The page must not read it as one."""
    written = only(with_apps())

    assert written["allowed_apps"] == []
    assert all(app["allowed"] for app in written["apps"])


def test_an_allow_list_marks_the_apps_that_are_not_on_it() -> None:
    """The page draws a tick per app, so the answer has to be per app."""
    one = with_apps()
    one.entities["rules"] = "sensor.r"
    one.states["sensor.r"] = {
        "state": "52",
        "attributes": {"apps_allowed": ["com.netflix"]},
    }

    written = only(one)
    allowed = {app["package"]: app["allowed"] for app in written["apps"]}

    assert allowed == {"com.netflix": True, "com.youtube": False, "com.spotify": False}


def test_the_windows_come_through_as_the_television_wrote_them() -> None:
    """Read-only on this page: they are drawn on a Schedule helper (D33)."""
    one = television()
    one.entities["rules"] = "sensor.r"
    one.states["sensor.r"] = {
        "state": "52",
        "attributes": {
            "windows": [{"id": "1600-1930", "from": "16:00", "to": "19:30"}]
        },
    }

    assert only(one)["windows"][0]["from"] == "16:00"


def test_all_is_well_is_an_empty_list_rather_than_a_sentence() -> None:
    """So the page has one thing to check, and nothing to match against."""
    written = only(television(reporting="on", pin_set="on"))

    assert written["trouble"] == []


def test_what_is_wrong_is_said_in_words() -> None:
    """A parent reads this. `reporting: off` is a state, not an answer."""
    written = only(television(reporting="off", pin_set="off"))

    assert written["trouble"]
    assert all(isinstance(line, str) and line.strip() for line in written["trouble"])


def with_noise() -> Television:
    """Build a television whose per-app list is mostly not apps.

    Which is what a real one reports: the set charges the odd second to `android` and to
    the system UI between one app and the next, and it charges time to this app too.
    """
    one = television(rules="52")
    for package, name, minutes in (
        ("com.netflix", "Netflix", "74.5"),
        ("android", "android", "0"),
        ("com.android.systemui", "com.android.systemui", "0"),
        ("app.tvsitter.tv", "TV Sitter", "28.3"),
    ):
        one.apps[package] = {
            "sensor": f"sensor.{package}",
            "limit": f"number.{package}",
        }
        one.states[f"sensor.{package}"] = {
            "state": minutes,
            "attributes": {"friendly_name": f"TV Salon {name}"},
        }
        one.states[f"number.{package}"] = {"state": "unknown", "attributes": {}}
    return one


def test_this_app_is_never_offered_as_something_to_block() -> None:
    """The engine exempts it (D35), so a control for it would do nothing at all."""
    written = only(with_noise())

    assert "app.tvsitter.tv" not in [app["package"] for app in written["apps"]]


def test_a_package_nobody_watched_is_not_an_app() -> None:
    """`android` on nought minutes is the set drawing breath, not something watched."""
    written = only(with_noise())

    assert [app["package"] for app in written["apps"]] == ["com.netflix"]


def test_an_app_a_parent_has_decided_about_stays_however_little_it_ran() -> None:
    """A budget of zero is a blocked app, and a blocked app has to remain visible."""
    one = with_noise()
    one.states["number.android"] = {"state": "0", "attributes": {}}

    assert "android" in [app["package"] for app in only(one)["apps"]]


def test_an_allow_listed_app_stays_even_with_nothing_watched() -> None:
    """It is named in a rule, so it is a row a parent expects to find and untick."""
    one = with_noise()
    one.entities["rules"] = "sensor.r"
    one.states["sensor.r"] = {
        "state": "52",
        "attributes": {"apps_allowed": ["com.android.systemui"]},
    }

    assert "com.android.systemui" in [app["package"] for app in only(one)["apps"]]


def with_rules(**attributes: Any) -> Television:
    """Build a television whose rules sensor says the given things."""
    one = television()
    one.entities["rules"] = "sensor.r"
    one.states["sensor.r"] = {"state": "52", "attributes": attributes}
    return one


SCHOOL = {"id": "1600-1930", "from": "16:00", "to": "19:30", "days": ["mon"]}
SCHOOL_SLOTS = [
    "16:00",
    "16:30",
    "17:00",
    "17:30",
    "18:00",
    "18:30",
    "19:00",
]


def test_a_window_becomes_the_half_hours_it_covers() -> None:
    """The grid is boxes to tick; the windows are intervals. Same rule, drawn."""
    written = only(with_rules(windows=[SCHOOL]))

    assert written["hours"]["mon"] == SCHOOL_SLOTS


def test_a_window_is_only_on_the_days_it_names() -> None:
    """A `days` list is the difference between a school night and every night."""
    written = only(with_rules(windows=[SCHOOL]))

    assert written["hours"]["tue"] == []
    assert written["hours"]["sun"] == []


def test_a_window_with_no_days_is_on_every_one_of_them() -> None:
    """An absent `days` means the whole week, which is the ordinary case (D27)."""
    every_day = {key: value for key, value in SCHOOL.items() if key != "days"}

    written = only(with_rules(windows=[every_day]))

    assert all(written["hours"][day] == SCHOOL_SLOTS for day in WEEK)


def test_a_window_past_midnight_stays_on_the_day_it_belongs_to() -> None:
    """The small hours after Saturday evening are Saturday's, not Sunday's."""
    late = {"id": "2200-0100", "from": "22:00", "to": "01:00", "days": ["sat"]}

    written = only(with_rules(windows=[late]))

    assert written["hours"]["sat"] == [
        "00:00",
        "00:30",
        "22:00",
        "22:30",
        "23:00",
        "23:30",
    ]
    assert written["hours"]["sun"] == []


def test_no_windows_is_a_week_of_empty_days() -> None:
    """Which is no restriction rather than a closed week — the page says which."""
    written = only(with_rules())

    assert set(written["hours"]) == set(WEEK)
    assert all(written["hours"][day] == [] for day in WEEK)


def test_nothing_is_being_followed_until_the_integration_says_so() -> None:
    """An older integration says nothing about it, which is not a helper."""
    assert only(with_rules(windows=[SCHOOL]))["following_schedule"] is None


def test_a_followed_schedule_is_named_so_the_grid_can_go_read_only() -> None:
    """The page needs the entity id to say which helper the hours come from."""
    written = only(with_rules(following_schedule="schedule.viewing_hours"))

    assert written["following_schedule"] == "schedule.viewing_hours"


class Recorder:
    """A Home Assistant that writes down what it was asked to do.

    The panel changes nothing by itself — every action is a service call (D34) — so
    what an action does is exactly the call it makes, and that is what is checked.
    """

    def __init__(self) -> None:
        """Start with nothing asked of it."""
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def call(self, domain: str, service: str, data: dict[str, Any]) -> None:
        """Remember one service call instead of making it."""
        self.calls.append((domain, service, data))


async def saved(one: Television, days: dict[str, list[str]]) -> list[dict[str, Any]]:
    """Save a grid, and hand back the windows that went out to the television."""
    home = Recorder()
    await apply(home, [one], {"id": DEVICE, "action": "hours", "days": days})

    assert [(domain, service) for domain, service, _ in home.calls] == [
        ("tvsitter", "set_windows")
    ]
    data = home.calls[0][2]
    assert data["entity_id"] == "sensor.r"
    return data["windows"]


def grid_of(**days: list[str]) -> dict[str, list[str]]:
    """Build a whole week of ticked half hours, empty where nothing is given."""
    return {day: days.get(day, []) for day in WEEK}


async def test_the_half_hours_go_back_as_the_windows_they_came_from() -> None:
    """The grid is a drawing of the windows, so the drawing has to survive a save."""
    week = [
        {
            "id": "1600-1930",
            "from": "16:00",
            "to": "19:30",
            "days": ["mon", "tue", "wed", "thu", "fri"],
        },
        {"id": "0900-2100", "from": "09:00", "to": "21:00", "days": ["sat", "sun"]},
    ]
    one = with_rules(windows=week)

    assert await saved(one, only(one)["hours"]) == [week[1], week[0]]


async def test_a_window_past_midnight_survives_the_round_trip_whole() -> None:
    """Two windows meeting at midnight would warn the child that time was up."""
    late = [{"id": "2200-0100", "from": "22:00", "to": "01:00", "days": ["fri"]}]
    one = with_rules(windows=late)

    assert await saved(one, only(one)["hours"]) == late


async def test_a_gap_in_a_day_is_two_windows() -> None:
    """An hour before school and the evening are two permissions, not one long one."""
    written = await saved(
        with_rules(), grid_of(wed=["07:00", "07:30", "17:00", "17:30", "18:00"])
    )

    assert written == [
        {"id": "0700-0800", "from": "07:00", "to": "08:00", "days": ["wed"]},
        {"id": "1700-1830", "from": "17:00", "to": "18:30", "days": ["wed"]},
    ]


async def test_days_with_the_same_hours_share_one_window() -> None:
    """Five identical windows is a rules object nobody can read when a lock lands."""
    school = ["16:00", "16:30"]
    written = await saved(
        with_rules(), grid_of(mon=school, tue=school, wed=school, thu=school)
    )

    assert written == [
        {
            "id": "1600-1700",
            "from": "16:00",
            "to": "17:00",
            "days": ["mon", "tue", "wed", "thu"],
        }
    ]


async def test_a_window_on_the_whole_week_says_nothing_about_days() -> None:
    """An absent `days` is what the rules mean by every day, so it is left out."""
    written = await saved(with_rules(), {day: ["19:00"] for day in WEEK})

    assert written == [{"id": "1900-1930", "from": "19:00", "to": "19:30"}]


async def test_the_last_half_hour_of_the_day_closes_at_midnight() -> None:
    """`23:30` runs to `00:00`; `24:00` is not a time the television can parse."""
    written = await saved(with_rules(), grid_of(sat=["23:00", "23:30"]))

    assert written == [
        {"id": "2300-0000", "from": "23:00", "to": "00:00", "days": ["sat"]}
    ]


async def test_an_empty_grid_takes_the_hours_away() -> None:
    """No windows is no restriction (D27), which is a thing a parent may want to say."""
    assert await saved(with_rules(), grid_of()) == []


async def test_a_whole_week_of_ticks_is_no_restriction_rather_than_windows() -> None:
    """Every hour of every day is a permission the rules already have a word for."""
    all_day = [
        time for hour in range(24) for time in (f"{hour:02d}:00", f"{hour:02d}:30")
    ]

    assert await saved(with_rules(), {day: all_day for day in WEEK}) == []


async def test_a_whole_day_of_ticks_is_never_one_window() -> None:
    """A window that starts when it ends is dropped by the television.

    Which would lock the day a parent had just opened entirely.
    """
    all_day = [
        time for hour in range(24) for time in (f"{hour:02d}:00", f"{hour:02d}:30")
    ]

    written = await saved(with_rules(), grid_of(sun=all_day))

    assert written == [
        {"id": "0000-1200", "from": "00:00", "to": "12:00", "days": ["sun"]},
        {"id": "1200-0000", "from": "12:00", "to": "00:00", "days": ["sun"]},
    ]


async def test_the_hours_are_refused_while_a_schedule_is_followed() -> None:
    """The next import would undo them without a word, which is worse than a refusal."""
    one = with_rules(following_schedule="schedule.viewing_hours")
    home = Recorder()

    with pytest.raises(ValueError) as refusal:
        await apply(home, [one], {"id": DEVICE, "action": "hours", "days": grid_of()})

    assert "schedule.viewing_hours" in str(refusal.value)
    assert str(refusal.value).endswith(".")
    assert home.calls == []


async def test_a_day_that_is_not_a_day_is_refused_in_words() -> None:
    """A misread key would take an evening away silently, so nothing is guessed."""
    with pytest.raises(ValueError) as refusal:
        await saved(with_rules(), {"funday": ["16:00"]})

    assert "funday" in str(refusal.value)


async def test_a_time_that_is_not_a_half_hour_is_refused_in_words() -> None:
    """The grid has no box for 16:20, and inventing one writes hours nobody drew."""
    with pytest.raises(ValueError) as refusal:
        await saved(with_rules(), grid_of(mon=["16:20"]))

    assert "16:20" in str(refusal.value)


async def test_a_grid_that_is_not_a_grid_is_refused_in_words() -> None:
    """It arrives over HTTP, so it is checked rather than trusted."""
    with pytest.raises(ValueError) as refusal:
        await saved(with_rules(), ["16:00"])

    assert str(refusal.value).endswith(".")
