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

from panel.api import snapshot
from panel.home_assistant import Television

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
