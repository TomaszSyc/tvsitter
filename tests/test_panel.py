"""What the parent panel finds, and what it puts on the page.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from typing import Any

from panel.home_assistant import Television, collect
from panel.page import render

DEVICE = "b0fc4e4987a5b78b71faf37e6a219e9b"


def device(name: str = "TV Salon", device_id: str = DEVICE) -> dict[str, Any]:
    """Build a device registry row of the shape Home Assistant serves."""
    return {"id": device_id, "name": name, "name_by_user": None}


def entity(
    entity_id: str,
    translation_key: str | None,
    platform: str = "tvsitter",
    device_id: str = DEVICE,
) -> dict[str, Any]:
    """Build an entity registry row of the shape Home Assistant serves."""
    return {
        "entity_id": entity_id,
        "translation_key": translation_key,
        "platform": platform,
        "device_id": device_id,
    }


def test_a_television_is_found_through_the_registry() -> None:
    """Through the registry, never through entity ids.

    This house's are Polish. Matching on a `_rules` suffix finds every television in
    English and none anywhere else, which is what the first draft of #100 did.
    """
    found = collect(
        [device()],
        [
            entity("sensor.tv_salon_reguly", "rules"),
            entity("binary_sensor.tv_salon_ekran", "screen"),
        ],
    )

    assert [one.name for one in found] == ["TV Salon"]
    assert found[0].entities == {
        "rules": "sensor.tv_salon_reguly",
        "screen": "binary_sensor.tv_salon_ekran",
    }


def test_other_integrations_are_not_televisions() -> None:
    """The registry holds the whole house, and most of it is not ours."""
    found = collect(
        [device(), device("Kuchnia", "other")],
        [
            entity("sensor.tv_salon_reguly", "rules"),
            entity("light.kuchnia", None, platform="hue", device_id="other"),
        ],
    )

    assert len(found) == 1


def test_two_televisions_with_one_name_are_still_two() -> None:
    """Keyed by device, so two sets sharing a name are still two televisions."""
    found = collect(
        [device(device_id="a"), device(device_id="b")],
        [
            entity("sensor.one_reguly", "rules", device_id="a"),
            entity("sensor.two_reguly", "rules", device_id="b"),
        ],
    )

    assert len(found) == 2


def test_a_renamed_television_keeps_the_name_the_parent_gave_it() -> None:
    """`name_by_user` is the one on screen everywhere else, so it is the one here."""
    row = device()
    row["name_by_user"] = "Salon dzieci"

    assert (
        collect([row], [entity("sensor.x_reguly", "rules")])[0].name == "Salon dzieci"
    )


def test_an_entity_without_a_device_is_skipped_rather_than_crashing() -> None:
    """The registry allows it, so the panel has to survive it."""
    orphan = entity("sensor.stray", "rules")
    orphan["device_id"] = None

    assert collect([device()], [orphan]) == []


def make(**states: str) -> Television:
    """Build a television whose entities say the given things."""
    television = Television(device_id=DEVICE, name="TV Salon")
    for key, value in states.items():
        television.entities[key] = f"sensor.{key}"
        television.values[f"sensor.{key}"] = value
    return television


def test_the_page_says_yes_and_no_rather_than_on_and_off() -> None:
    """A parent should never have to learn Home Assistant's vocabulary."""
    page = render([make(reporting="on", screen="off", active_app="Netflix")])

    assert ">yes<" in page
    assert ">no<" in page
    assert ">Netflix<" in page


def test_nothing_to_say_reads_as_a_dash() -> None:
    """`unknown` and `unavailable` are words for a log, not for a page."""
    page = render([make(reporting="unavailable", active_app="unknown")])

    assert "unavailable" not in page
    assert "unknown" not in page
    assert "—" in page


def test_a_name_with_markup_in_it_is_escaped() -> None:
    """Device names are typed by people, and this page is built by hand."""
    television = Television(device_id=DEVICE, name="<script>alert(1)</script>")

    assert "<script>" not in render([television])


def test_no_televisions_says_where_they_come_from() -> None:
    """An empty list is a question, and the answer is the integration."""
    assert "integration" in render([])


def test_trouble_replaces_the_list_rather_than_sitting_under_it() -> None:
    """A page listing nothing under an error reads as a house with no televisions."""
    page = render([make(reporting="on")], "Home Assistant did not answer.")

    assert "did not answer" in page
    assert "Reporting" not in page
