"""Turning a schedule helper's weekly grid into windows the engine understands.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from custom_components.tvsitter.schedules import windows_from

WEEK = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def test_an_empty_schedule_is_no_restriction() -> None:
    """D27 on this side of the conversion too: no windows is not a closed week."""
    assert windows_from({day: [] for day in WEEK}) == []


def test_one_day_carries_the_day_it_applies_on() -> None:
    """A window with no days applies all week, which is not what was drawn."""
    windows = windows_from({"monday": [{"from": "16:00:00", "to": "19:30:00"}]})

    assert windows == [
        {"id": "1600-1930", "from": "16:00", "to": "19:30", "days": ["mon"]}
    ]


def test_days_sharing_their_hours_become_one_window() -> None:
    """Five near-identical windows is a rules object nobody can read at a glance."""
    grid = {day: [{"from": "16:00:00", "to": "19:30:00"}] for day in WEEK[:5]}

    assert windows_from(grid) == [
        {
            "id": "1600-1930",
            "from": "16:00",
            "to": "19:30",
            "days": ["mon", "tue", "wed", "thu", "fri"],
        }
    ]


def test_a_whole_week_drops_the_days_altogether() -> None:
    """Every day is what an absent `days` key means, and it is what the rule says."""
    grid = {day: [{"from": "09:00:00", "to": "21:00:00"}] for day in WEEK}

    assert windows_from(grid) == [{"id": "0900-2100", "from": "09:00", "to": "21:00"}]


def test_two_blocks_on_one_day_are_two_windows() -> None:
    """A morning and an evening with lunch in between is the point of allowing both."""
    grid = {
        "saturday": [
            {"from": "09:00:00", "to": "12:00:00"},
            {"from": "15:00:00", "to": "21:00:00"},
        ]
    }

    assert [window["id"] for window in windows_from(grid)] == ["0900-1200", "1500-2100"]


def test_a_block_running_to_the_end_of_the_day_closes_at_midnight() -> None:
    """The helper allows 24:00, which is not a time anything can parse."""
    windows = windows_from({"friday": [{"from": "18:00:00", "to": "24:00:00"}]})

    assert windows[0]["to"] == "00:00"


def test_a_malformed_block_is_dropped_and_the_rest_survive() -> None:
    """Another integration's stored data, so one bad entry must not lose the week."""
    grid = {
        "monday": [
            {"from": "nonsense", "to": "19:30:00"},
            "not a block",
            {"to": "10:00"},
        ],
        "tuesday": [{"from": "16:00:00", "to": "19:30:00"}],
    }

    assert windows_from(grid) == [
        {"id": "1600-1930", "from": "16:00", "to": "19:30", "days": ["tue"]}
    ]


def test_the_days_come_out_in_the_order_a_week_runs() -> None:
    """Sunday first would be a rules object that reads wrong on sight."""
    grid = {
        day: [{"from": "16:00:00", "to": "18:00:00"}] for day in ["sunday", "monday"]
    }

    assert windows_from(grid)[0]["days"] == ["mon", "sun"]
