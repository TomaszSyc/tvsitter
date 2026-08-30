"""The shape the panel's page is served, checked against the contract it was agreed.

Written from the contract rather than the implementation, deliberately: the page and
the server were built to the same document by different hands, and the only thing that
catches a disagreement between them is a test that believes neither.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import traceback
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


def only(one: Television, by_app: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Pull the one television out of a snapshot, with the seven days it was handed."""
    answer = snapshot([one], {DEVICE: by_app} if by_app else None)
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


async def test_the_following_can_be_stopped_from_the_panel() -> None:
    """The way out of a read-only grid, taken here rather than in a helper dialog."""
    home = Recorder()
    one = with_rules(following_schedule="schedule.viewing_hours")

    await apply(home, [one], {"id": DEVICE, "action": "stop_following"})

    assert home.calls == [("tvsitter", "forget_schedule", {"entity_id": "sensor.r"})]


async def test_stopping_the_following_writes_no_hours_at_all() -> None:
    """The hours in force are kept: one call goes out, and it is not a rule write."""
    home = Recorder()
    one = with_rules(following_schedule="schedule.viewing_hours", windows=[SCHOOL])

    await apply(home, [one], {"id": DEVICE, "action": "stop_following"})

    assert [service for _, service, _ in home.calls] == ["forget_schedule"]
    assert only(one)["hours"]["mon"] == SCHOOL_SLOTS


async def test_stopping_the_following_is_safe_with_nothing_followed() -> None:
    """The page offers it against a state one poll old, so it cannot be a refusal."""
    home = Recorder()

    await apply(home, [with_rules()], {"id": DEVICE, "action": "stop_following"})

    assert home.calls == [("tvsitter", "forget_schedule", {"entity_id": "sensor.r"})]


async def test_stopping_the_following_needs_a_rules_sensor_to_stop_it_on() -> None:
    """An older integration is missing one control rather than broken."""
    with pytest.raises(ValueError) as refusal:
        await apply(
            Recorder(), [television()], {"id": DEVICE, "action": "stop_following"}
        )

    assert "rules" in str(refusal.value)


async def test_the_hours_go_through_once_nothing_is_followed_any_more() -> None:
    """Which is the whole point of stopping: the grid becomes ours to write."""
    assert await saved(with_rules(), grid_of(mon=["16:00"])) == [
        {"id": "1600-1630", "from": "16:00", "to": "16:30", "days": ["mon"]}
    ]


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


HELD = {"windows": [{"id": "1600-1930", "from": "16:00", "to": "19:30"}]}


def test_nothing_is_waiting_until_the_integration_says_so() -> None:
    """The ordinary case is a television that took the change, so it says nothing."""
    assert only(with_rules(windows=[SCHOOL]))["pending_rules"] is None


def test_a_change_the_set_slept_through_is_handed_on_whole() -> None:
    """The page names the rules that are waiting, so it is given all of them."""
    written = only(with_rules(pending_rules=HELD))

    assert written["pending_rules"] == HELD


def test_a_change_of_no_rules_at_all_is_nothing_waiting() -> None:
    """A warning about an empty object would be a warning about nothing."""
    assert only(with_rules(pending_rules={}))["pending_rules"] is None


def test_something_that_is_not_a_change_is_nothing_waiting() -> None:
    """It arrives from a sensor attribute, so it is read rather than trusted."""
    assert only(with_rules(pending_rules=["windows"]))["pending_rules"] is None
    assert only(with_rules(pending_rules="windows"))["pending_rules"] is None


def test_waiting_and_following_are_two_different_questions() -> None:
    """One is a change that has not landed; the other is where the hours come from."""
    written = only(
        with_rules(
            pending_rules=HELD,
            following_schedule="schedule.viewing_hours",
            windows=[SCHOOL],
        )
    )

    assert written["pending_rules"] == HELD
    assert written["following_schedule"] == "schedule.viewing_hours"
    # And what is drawn is still what the television is enforcing, not what is coming.
    assert written["hours"]["mon"] == SCHOOL_SLOTS


async def test_a_waiting_change_can_be_thrown_away_from_the_panel() -> None:
    """For a set that is not coming back, which is the only way the warning ends."""
    home = Recorder()

    await apply(home, [with_rules(pending_rules=HELD)], forget())

    assert home.calls == [
        ("tvsitter", "forget_pending_rules", {"entity_id": "sensor.r"})
    ]


async def test_throwing_a_waiting_change_away_writes_no_rules_at_all() -> None:
    """What goes is what never reached the set; what it is enforcing is untouched."""
    home = Recorder()
    one = with_rules(pending_rules=HELD, windows=[SCHOOL])

    await apply(home, [one], forget())

    assert [service for _, service, _ in home.calls] == ["forget_pending_rules"]
    assert only(one)["hours"]["mon"] == SCHOOL_SLOTS


async def test_throwing_away_is_safe_with_nothing_waiting() -> None:
    """The page offers it against a state one poll old, so it cannot be a refusal."""
    home = Recorder()

    await apply(home, [with_rules()], forget())

    assert home.calls == [
        ("tvsitter", "forget_pending_rules", {"entity_id": "sensor.r"})
    ]


async def test_throwing_a_waiting_change_away_needs_a_rules_sensor() -> None:
    """An older integration is missing one control rather than broken."""
    with pytest.raises(ValueError) as refusal:
        await apply(Recorder(), [television()], forget())

    assert "rules" in str(refusal.value)


def forget() -> dict[str, Any]:
    """Build the one request that throws a waiting change away."""
    return {"id": DEVICE, "action": "forget_pending"}


LAST_SEVEN_DAYS = [
    {"package": "com.youtube", "name": "YouTube", "minutes": 312.5},
    {"package": "com.netflix", "name": "Netflix", "minutes": 88.0},
]


def test_the_seven_days_arrive_beside_the_day_and_keep_their_order() -> None:
    """Two weeks on one television: what each day allows, and what happened."""
    written = only(with_apps(), by_app=LAST_SEVEN_DAYS)

    assert [app["name"] for app in written["week_by_app"]] == ["YouTube", "Netflix"]
    assert set(written["week"]) == set(WEEK)


def test_a_television_the_recorder_has_nothing_on_has_seven_empty_days() -> None:
    """Which reads as "nothing yet" — the ordinary case on a fresh install (#103)."""
    assert only(with_apps())["week_by_app"] == []


def test_the_seven_days_leave_out_what_no_rule_reaches() -> None:
    """This app draws its own lock screen, and nobody sat down to watch that."""
    ours = {"package": "app.tvsitter.tv", "name": "TV Sitter", "minutes": 900.0}

    written = only(with_noise(), by_app=[ours, *LAST_SEVEN_DAYS])

    assert [app["name"] for app in written["week_by_app"]] == ["YouTube", "Netflix"]


def exempting(one: Television, *packages: str) -> Television:
    """Have the television report which packages no rule of its own can reach."""
    one.entities["active_app"] = "sensor.app"
    one.states["sensor.app"] = {
        "state": "Netflix",
        "attributes": {"exempt_apps": list(packages)},
    }
    return one


def test_the_apps_the_television_exempts_are_dropped_from_the_list() -> None:
    """A budget beside one of them would be a control the engine ignores (D35)."""
    one = exempting(with_noise(), "app.tvsitter.tv", "com.netflix")

    written = only(one)

    assert written["apps"] == []
    assert written["exempt_apps"] == ["app.tvsitter.tv", "com.netflix"]


def test_a_television_that_names_none_still_has_this_app_dropped() -> None:
    """Empty means none are known, not that none exist — so the constant stands."""
    written = only(with_noise())

    assert [app["package"] for app in written["apps"]] == ["com.netflix"]
    assert written["exempt_apps"] == ["app.tvsitter.tv"]


def test_an_exempt_app_is_named_so_the_page_can_say_why_it_is_missing() -> None:
    """An app that vanishes without a word reads as a panel that lost it."""
    written = only(exempting(with_noise(), "com.android.systemui"))

    assert written["exempt_apps"] == ["com.android.systemui"]
    assert "com.android.systemui" not in [app["package"] for app in written["apps"]]


def with_pin() -> Television:
    """Build a television with the two controls a parent PIN is changed by."""
    return television(parent_pin="unknown", clear_pin="unknown")


async def test_a_new_pin_goes_to_the_television_as_a_value_to_hash() -> None:
    """Home Assistant hashes it on the way through; the PIN reaches no broker."""
    home = Recorder()

    await apply(home, [with_pin()], {"id": DEVICE, "action": "set_pin", "pin": "4213"})

    assert home.calls == [
        ("text", "set_value", {"entity_id": "x.parent_pin", "value": "4213"})
    ]


async def test_clearing_the_pin_presses_the_button_that_clears_it() -> None:
    """There is nothing to write: a null hash is what the button sends."""
    home = Recorder()

    await apply(home, [with_pin()], {"id": DEVICE, "action": "clear_pin"})

    assert home.calls == [("button", "press", {"entity_id": "x.clear_pin"})]


async def test_a_set_pin_with_no_pin_is_refused_in_words() -> None:
    """And in words that could not carry one, because there is none to carry."""
    home = Recorder()

    with pytest.raises(ValueError) as refusal:
        await apply(home, [with_pin()], {"id": DEVICE, "action": "set_pin"})

    assert str(refusal.value).endswith(".")
    assert home.calls == []


async def test_a_refused_pin_is_never_written_down_anywhere() -> None:
    """Home Assistant quotes the value it refused, and the panel logs its refusals."""

    class Refusing(Recorder):
        """A Home Assistant that refuses a PIN the way the text entity does."""

        async def call(self, domain: str, service: str, data: dict[str, Any]) -> None:
            """Refuse, quoting the value, as `TextEntity.async_set_value` does."""
            raise RuntimeError(
                f"text.set_value was refused: Value {data['value']} for "
                "text.tv_salon_parent_pin doesn't match pattern [0-9]{4}$"
            )

    with pytest.raises(ValueError) as refusal:
        await apply(
            Refusing(), [with_pin()], {"id": DEVICE, "action": "set_pin", "pin": "4213"}
        )

    assert "4213" not in str(refusal.value)
    # Dropped rather than chained: `from None` is what keeps Home Assistant's own
    # refusal, and the PIN it quotes, out of a traceback and out of the log with it.
    assert refusal.value.__cause__ is None
    assert "doesn't match pattern" not in "".join(
        traceback.format_exception(refusal.value)
    )


async def test_a_television_without_the_pin_controls_says_which_it_has_not() -> None:
    """An older integration is missing one control rather than broken."""
    with pytest.raises(ValueError) as refusal:
        await apply(
            Recorder(),
            [television()],
            {"id": DEVICE, "action": "set_pin", "pin": "4213"},
        )

    assert "parent_pin" in str(refusal.value)
    assert "4213" not in str(refusal.value)


def test_home_assistants_own_sentence_survives_a_refusal() -> None:
    """A parent painting a week while the set is asleep needs to know that is why.

    The refusal used to come back as "Home Assistant would not make that change",
    which answers nothing. The integration's own sentence names the television and
    says it is not listening, and that is the one worth showing.
    """
    from panel.home_assistant import said

    body = '{"message": "TV Salon is not listening; the change would go nowhere"}'

    assert said(body) == "TV Salon is not listening; the change would go nowhere"


def test_a_refusal_that_says_nothing_useful_gives_nothing() -> None:
    """Rather than a page carrying somebody else's stack trace."""
    from panel.home_assistant import said

    assert said("<html>500</html>") is None
    assert said('{"message": "   "}') is None
    assert said('{"code": 500}') is None


@pytest.mark.parametrize(
    "drawn",
    [
        grid_of(mon=["16:00", "16:30", "17:00"]),
        grid_of(sat=[f"{hour:02d}:00" for hour in range(9, 21)]),
        # Friday evening running into Saturday morning. Written from midnight because
        # that is how the page sends it: the boxes go out in the order they sit in the
        # row, so an evening past midnight arrives at both ends of Friday.
        grid_of(fri=["00:00", "00:30", "22:00", "22:30", "23:00", "23:30"]),
        grid_of(wed=["07:00", "07:30", "17:00", "17:30"], thu=["07:00", "07:30"]),
        grid_of(**{day: ["20:00", "20:30"] for day in WEEK}),
        grid_of(),
    ],
)
async def test_a_week_that_was_drawn_comes_back_exactly_as_it_was_drawn(
    drawn: dict[str, list[str]],
) -> None:
    """The panel holds the boxes a parent painted until the television reports them.

    It decides the television has caught up by comparing the two weeks half hour for
    half hour (#136), so a save that came back saying the same thing in different words
    would leave the grid waiting for a set that had already agreed — for as long as the
    wait lasts, and then it would redraw underneath them. Every window written here is
    read straight back so that the comparison the page makes is one that can succeed.
    """
    written = await saved(with_rules(), drawn)

    assert only(with_rules(windows=written))["hours"] == drawn
