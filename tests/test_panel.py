"""What the parent panel finds in a Home Assistant, and what it does with it.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from typing import Any

from panel.home_assistant import Television, collect

DEVICE = "b0fc4e4987a5b78b71faf37e6a219e9b"


def device(name: str = "TV Salon", device_id: str = DEVICE) -> dict[str, Any]:
    """Build a device registry row of the shape Home Assistant serves."""
    return {"id": device_id, "name": name, "name_by_user": None}


def entity(
    entity_id: str,
    translation_key: str | None = None,
    platform: str = "tvsitter",
    device_id: str = DEVICE,
    unique_id: str = "",
) -> dict[str, Any]:
    """Build an entity registry row of the shape Home Assistant serves."""
    return {
        "entity_id": entity_id,
        "translation_key": translation_key,
        "platform": platform,
        "device_id": device_id,
        "unique_id": unique_id,
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
            entity("light.kuchnia", platform="hue", device_id="other"),
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


def test_the_per_app_entities_are_filed_under_their_package() -> None:
    """They carry no translation key, being named after apps a television reported.

    The package comes out of the unique id, the one identifier in the chain that nothing
    translates. The sensor and the number for one app have to land together, and
    `_app_limit_` has to win over `_app_`, or a budget files itself as `limit_netflix`.
    """
    found = collect(
        [device()],
        [
            entity("sensor.tv_salon_reguly", "rules"),
            entity("sensor.tv_salon_netflix", unique_id=f"{DEVICE}_app_com.netflix"),
            entity(
                "number.tv_salon_netflix_limit",
                unique_id=f"{DEVICE}_app_limit_com.netflix",
            ),
        ],
    )

    assert found[0].apps == {
        "com.netflix": {
            "sensor": "sensor.tv_salon_netflix",
            "limit": "number.tv_salon_netflix_limit",
        }
    }


def make(**states: str) -> Television:
    """Build a television whose entities say the given things."""
    television = Television(device_id=DEVICE, name="TV Salon")
    for key, value in states.items():
        television.entities[key] = f"sensor.{key}"
        television.states[f"sensor.{key}"] = {"state": value, "attributes": {}}
    return television


def test_nothing_to_say_is_nothing_rather_than_a_word() -> None:
    """`unknown` and `unavailable` are Home Assistant's vocabulary, not a parent's."""
    television = make(active_app="unavailable", used_today="unknown", screen="on")

    assert television.state("active_app") is None
    assert television.number("used_today") is None
    assert television.state("screen") == "on"


def test_an_unset_number_is_not_zero() -> None:
    """Zero is a real setting here — no viewing today — so it must stay tellable."""
    television = make(daily_limit="0", sleep_timer="unknown")

    assert television.number("daily_limit") == 0.0
    assert television.number("sleep_timer") is None


def test_an_app_is_called_what_the_television_calls_it() -> None:
    """The label lives on the set, and arrives with the device name in front of it."""
    television = Television(device_id=DEVICE, name="TV Salon")
    television.apps["com.netflix"] = {"sensor": "sensor.n", "limit": "number.n"}
    television.states["sensor.n"] = {
        "state": "14.8",
        "attributes": {"friendly_name": "TV Salon Netflix"},
    }

    assert television.app_name("com.netflix") == "Netflix"
    assert television.app_minutes("com.netflix") == 14.8


def test_an_app_with_no_budget_of_its_own_reads_as_nothing() -> None:
    """Unset runs on the day's allowance; zero is blocked. Never the same answer."""
    television = Television(device_id=DEVICE, name="TV Salon")
    television.apps["a"] = {"sensor": "sensor.a", "limit": "number.a"}
    television.apps["b"] = {"sensor": "sensor.b", "limit": "number.b"}
    television.states["number.a"] = {"state": "unknown", "attributes": {}}
    television.states["number.b"] = {"state": "0", "attributes": {}}

    assert television.app_limit("a") is None
    assert television.app_limit("b") == 0.0


def test_the_rules_come_from_the_television_without_the_name_tacked_on() -> None:
    """`friendly_name` is Home Assistant's, not a rule, and it is not one to show."""
    television = Television(device_id=DEVICE, name="TV Salon")
    television.entities["rules"] = "sensor.r"
    television.states["sensor.r"] = {
        "state": "52",
        "attributes": {"daily_limit_s": 3600, "friendly_name": "TV Salon Wersja reguł"},
    }

    assert television.rules == {"daily_limit_s": 3600}
