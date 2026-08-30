"""Making the automation that answers a request for more time, and making one only.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from typing import Any

from panel.automations import (
    BLUEPRINT,
    Automations,
    answering,
    answers,
    automation_ids,
    body,
    chosen,
    configure,
    mobile_apps,
    notify_services,
    offer,
    ours,
    rewritten,
)
from panel.home_assistant import Television
import pytest

DEVICE = "b0fc4e4987a5b78b71faf37e6a219e9b"
OTHER = "9a1d5f2c4e8b47a3bc0e6d1f8a2b3c4d"
EVENT = "event.tv_salon_prosba_o_czas"
PHONE = "notify.mobile_app_pixel_9_pro"
WATCH = "notify.mobile_app_pixel_watch_4"


def services(*notify: str) -> list[dict[str, Any]]:
    """Build the shape `/api/services` answers with.

    A service is listed by its bare name inside its domain, which is why the panel puts
    the domain back on the front rather than reading `notify.mobile_app_x` off a list.
    """
    return [
        {"domain": "light", "services": {"turn_on": {}}},
        {
            "domain": "notify",
            "services": {name.removeprefix("notify."): {} for name in notify},
        },
    ]


def television(
    device_id: str = DEVICE,
    name: str = "TV Salon",
    event: str | None = EVENT,
    states: dict[str, dict[str, Any]] | None = None,
) -> Television:
    """Build one television as the registry would have handed it over."""
    one = Television(device_id=device_id, name=name)
    if event is not None:
        one.entities["time_request"] = event
    one.states = states if states is not None else {}
    return one


def automation(config_id: str, event: str = EVENT, **inputs: Any) -> dict[str, Any]:
    """Build one stored automation made from this project's blueprint."""
    return {
        "id": config_id,
        "alias": "whatever a parent called it",
        "use_blueprint": {
            "path": BLUEPRINT,
            "input": {"request_event": event, "notify_action": PHONE, **inputs},
        },
    }


def running(*config_ids: str) -> dict[str, dict[str, Any]]:
    """Build the states of the automations Home Assistant is running."""
    states: dict[str, dict[str, Any]] = {
        "sensor.something_else": {"state": "12", "attributes": {}}
    }
    for index, config_id in enumerate(config_ids):
        states[f"automation.number_{index}"] = {
            "state": "on",
            "attributes": {"id": config_id, "friendly_name": "an automation"},
        }
    return states


class Fake(Automations):
    """A Home Assistant keeping its automations in a dictionary.

    Filed by id and replaced under it, which is what Home Assistant's config API does
    with a post — so "twice under one id is one automation" is the real behaviour and
    not an assumption this test makes.
    """

    def __init__(self, *notify: str, **stored: dict[str, Any]) -> None:
        """Start with some phones registered and some automations already written."""
        self.automations = dict(stored)
        self.notify = list(notify) or [PHONE, WATCH]
        self.reads: list[str] = []

    async def services(self) -> list[dict[str, Any]]:
        """Answer with the phones this Home Assistant has."""
        return services(*self.notify, "persistent_notification", "send_message")

    async def stored(self, config_id: str) -> dict[str, Any] | None:
        """Answer with one automation, remembering that it was asked for."""
        self.reads.append(config_id)
        return self.automations.get(config_id)

    async def store(self, config_id: str, config: dict[str, Any]) -> None:
        """Keep one automation under its id, replacing whatever was there."""
        self.automations[config_id] = config


def test_only_the_phones_are_offered() -> None:
    """A notify entity would send the same sentence with nothing to tap on it.

    Which is the whole point of the notification, so the panel offers what carries
    buttons and nothing else — `notify.send_message` is the entity-shaped one.
    """
    found = services(WATCH, PHONE, "persistent_notification", "send_message")

    assert mobile_apps(found) == [PHONE, WATCH]
    assert notify_services(found) == [
        PHONE,
        WATCH,
        "notify.persistent_notification",
        "notify.send_message",
    ]


def test_a_home_assistant_with_no_phone_offers_nothing_rather_than_breaking() -> None:
    """A fresh instance has the companion app on nothing yet."""
    assert mobile_apps([{"domain": "light", "services": {"turn_on": {}}}]) == []
    assert notify_services([]) == []


def test_the_automations_are_listed_out_of_the_states_already_fetched() -> None:
    """The config id rides along in the state, so the list costs no request."""
    states = running("1755000000000", "tvsitter_more_time_x")
    states["automation.written_by_hand"] = {"state": "on", "attributes": {}}

    assert automation_ids(states) == ["1755000000000", "tvsitter_more_time_x"]


def test_an_automation_from_another_blueprint_is_not_ours() -> None:
    """Matched on the blueprint's path, which is how Home Assistant names one."""
    theirs = automation("x")
    theirs["use_blueprint"]["path"] = "somebody/motion_light.yaml"

    assert answers(theirs, EVENT) is False
    assert answers({"alias": "no blueprint at all", "triggers": []}, EVENT) is False
    assert answers(None, EVENT) is False


def test_an_automation_answers_the_television_it_is_pointed_at() -> None:
    """The input is the only thing in the configuration that names a television."""
    assert answers(automation("x"), EVENT) is True
    assert answers(automation("x"), "event.tv_kuchnia_prosba_o_czas") is False


def test_a_hand_written_list_of_events_still_names_this_television() -> None:
    """The selector gives a string; a person editing YAML can give a list."""
    both = automation("x", event=[EVENT, "event.tv_kuchnia_prosba_o_czas"])

    assert answers(both, EVENT) is True
    assert answers(both, "event.tv_dzieci_prosba_o_czas") is False


def test_the_second_device_is_read_back_only_when_it_is_switched_on() -> None:
    """The blueprint has a default for it, and a default nothing is sent to is a lie."""
    assert chosen(automation("x")) == (PHONE, None)
    assert chosen(automation("x", also_notify=False, second_notify_action=WATCH)) == (
        PHONE,
        None,
    )
    assert chosen(automation("x", also_notify=True, second_notify_action=WATCH)) == (
        PHONE,
        WATCH,
    )


def test_the_id_is_the_television_rather_than_the_clock() -> None:
    """A new id every time is a new automation every time, which is #104 itself."""
    assert ours(DEVICE) == ours(DEVICE)
    assert ours(DEVICE) != ours(OTHER)
    assert DEVICE in ours(DEVICE)


def test_the_automation_is_the_blueprint_and_the_answers_to_its_inputs() -> None:
    """Nothing of what it does is written here — that is the blueprint's, once."""
    written = body("TV Salon", EVENT, PHONE, None)

    assert written["use_blueprint"] == {
        "path": BLUEPRINT,
        "input": {"request_event": EVENT, "notify_action": PHONE},
    }
    assert "TV Salon" in written["alias"]
    assert "triggers" not in written
    assert "actions" not in written


def test_the_offers_and_the_expiry_are_left_to_the_blueprint() -> None:
    """Written here they would be pinned to whatever the panel thought once."""
    asked = body("TV Salon", EVENT, PHONE, WATCH)["use_blueprint"]["input"]

    assert "first_offer" not in asked
    assert "second_offer" not in asked
    assert "expiry_seconds" not in asked


def test_a_watch_is_switched_on_as_well_as_named() -> None:
    """The blueprint runs the second action only when the boolean beside it is on."""
    asked = body("TV Salon", EVENT, PHONE, WATCH)["use_blueprint"]["input"]

    assert asked["also_notify"] is True
    assert asked["second_notify_action"] == WATCH


def test_no_watch_leaves_the_switch_out_rather_than_writing_it_off() -> None:
    """A post replaces the whole automation, so absent is off and stays off."""
    asked = body("TV Salon", EVENT, PHONE, None)["use_blueprint"]["input"]

    assert "also_notify" not in asked
    assert "second_notify_action" not in asked


def test_changing_the_phones_changes_nothing_else() -> None:
    """An automation somebody wrote is theirs; the panel was asked about a phone."""
    theirs = automation("x", event=[EVENT, "event.tv_kuchnia_prosba_o_czas"])
    theirs["description"] = "mine, written by hand"

    changed = rewritten(theirs, WATCH, None)

    assert changed["alias"] == theirs["alias"]
    assert changed["description"] == "mine, written by hand"
    assert changed["use_blueprint"]["input"]["request_event"] == [
        EVENT,
        "event.tv_kuchnia_prosba_o_czas",
    ]
    assert changed["use_blueprint"]["input"]["notify_action"] == WATCH


def test_switching_the_second_device_off_takes_it_out() -> None:
    """Left in, the watch keeps buzzing for a parent who turned it off."""
    on = automation("x", also_notify=True, second_notify_action=WATCH)

    off = rewritten(on, PHONE, None)

    assert "also_notify" not in off["use_blueprint"]["input"]
    assert "second_notify_action" not in off["use_blueprint"]["input"]
    assert chosen(off) == (PHONE, None)


def test_the_original_is_not_changed_underneath_whoever_read_it() -> None:
    """A refusal further down would otherwise leave a half-changed copy in hand."""
    theirs = automation("x")

    rewritten(theirs, WATCH, PHONE)

    assert theirs["use_blueprint"]["input"]["notify_action"] == PHONE
    assert "also_notify" not in theirs["use_blueprint"]["input"]


async def test_the_first_run_makes_one_automation() -> None:
    """Under an id derived from the television, which is what the next run finds."""
    home = Fake()

    await configure(home, [television()], {"id": DEVICE, "notify": PHONE})

    assert list(home.automations) == [ours(DEVICE)]
    kept = home.automations[ours(DEVICE)]["use_blueprint"]
    assert kept == {
        "path": BLUEPRINT,
        "input": {"request_event": EVENT, "notify_action": PHONE},
    }


async def test_running_it_again_leaves_one_automation_and_not_two() -> None:
    """The failure #104 asks not to ship: two notifications for one request.

    Both would work, and answering either would settle it — leaving the other on the
    phone as a button that silently does nothing.
    """
    home = Fake()
    one = television()

    await configure(home, [one], {"id": DEVICE, "notify": PHONE})
    await configure(home, [one], {"id": DEVICE, "notify": WATCH})

    assert list(home.automations) == [ours(DEVICE)]
    assert chosen(home.automations[ours(DEVICE)]) == (WATCH, None)


async def test_an_automation_made_by_hand_is_written_over_rather_than_doubled() -> None:
    """`docs/setup.md` asked for one by hand for four milestones, so they exist.

    Found by what it is pointed at rather than by its id, and kept under the id it
    already had: a new id would be a second automation, and both would notify.
    """
    home = Fake(**{"1755000000000": automation("1755000000000")})
    one = television(states=running("1755000000000"))

    await configure(home, [one], {"id": DEVICE, "notify": WATCH})

    assert list(home.automations) == ["1755000000000"]
    assert chosen(home.automations["1755000000000"]) == (WATCH, None)
    # What a parent called it is theirs. The panel was asked about a phone.
    assert home.automations["1755000000000"]["alias"] == "whatever a parent called it"


async def test_another_television_gets_an_automation_of_its_own() -> None:
    """One per request, not one per house."""
    home = Fake()
    salon = television()
    kitchen = television(OTHER, "TV Kuchnia", "event.tv_kuchnia_prosba_o_czas")

    await configure(home, [salon, kitchen], {"id": DEVICE, "notify": PHONE})
    await configure(home, [salon, kitchen], {"id": OTHER, "notify": PHONE})

    assert sorted(home.automations) == sorted([ours(DEVICE), ours(OTHER)])


async def test_an_automation_for_another_television_is_not_this_one_answered() -> None:
    """Two sets, one automation: the second still needs one of its own."""
    home = Fake(**{"1755000000000": automation("1755000000000")})
    kitchen = television(
        OTHER,
        "TV Kuchnia",
        "event.tv_kuchnia_prosba_o_czas",
        states=running("1755000000000"),
    )

    await configure(home, [kitchen], {"id": OTHER, "notify": PHONE})

    assert sorted(home.automations) == sorted(["1755000000000", ours(OTHER)])


async def test_a_television_that_has_one_is_not_searched_for_again() -> None:
    """Ours is one request per television; the rest of the house is the fallback."""
    home = Fake(**{ours(DEVICE): automation(ours(DEVICE))})
    one = television(states=running(ours(DEVICE), "1755000000000", "1755000000001"))

    found = await answering(home, [one])

    assert found[DEVICE].config_id == ours(DEVICE)
    assert home.reads == [ours(DEVICE)]


async def test_the_page_is_told_what_is_set_and_what_can_be_chosen() -> None:
    """So it opens on the phone already chosen rather than on empty pickers."""
    home = Fake(
        **{
            ours(DEVICE): automation(
                ours(DEVICE), also_notify=True, second_notify_action=WATCH
            )
        }
    )
    salon = television(states=running(ours(DEVICE)))
    kitchen = television(OTHER, "TV Kuchnia", "event.tv_kuchnia_prosba_o_czas")

    told = await offer(home, [salon, kitchen])

    assert told["notify"] == [PHONE, WATCH]
    assert told["error"] is None
    assert told["televisions"][0] == {
        "id": DEVICE,
        "name": "TV Salon",
        "ready": True,
        "configured": True,
        "notify": PHONE,
        "also_notify": WATCH,
    }
    assert told["televisions"][1]["configured"] is False
    assert told["televisions"][1]["notify"] is None


async def test_a_television_with_no_request_event_is_offered_nothing() -> None:
    """One set up by an older integration has none, and a picker for it would lie."""
    home = Fake()
    old = television(event=None)

    told = await offer(home, [old])

    assert told["televisions"][0]["ready"] is False
    with pytest.raises(ValueError) as refusal:
        await configure(home, [old], {"id": DEVICE, "notify": PHONE})

    assert "TV Salon" in str(refusal.value)
    assert home.automations == {}


async def test_a_phone_home_assistant_has_never_heard_of_is_refused_in_words() -> None:
    """An automation naming a service that does not exist fails silently every night."""
    home = Fake()

    with pytest.raises(ValueError) as refusal:
        await configure(
            home, [television()], {"id": DEVICE, "notify": "notify.mobile_app_gone"}
        )

    assert "notify.mobile_app_gone" in str(refusal.value)
    assert str(refusal.value).endswith(".")
    assert home.automations == {}


async def test_choosing_no_phone_at_all_is_refused_in_words() -> None:
    """The page can send nothing; the automation cannot be written without one."""
    home = Fake()

    with pytest.raises(ValueError) as refusal:
        await configure(home, [television()], {"id": DEVICE})

    assert str(refusal.value).endswith(".")
    assert home.automations == {}


async def test_the_same_device_twice_is_refused() -> None:
    """Two notifications on one phone: answering one leaves the other doing nothing."""
    home = Fake()

    with pytest.raises(ValueError):
        await configure(
            home,
            [television()],
            {"id": DEVICE, "notify": PHONE, "also_notify": PHONE},
        )

    assert home.automations == {}


async def test_a_television_that_is_gone_is_said_rather_than_guessed() -> None:
    """A page open while a set is removed asks about a device that is not here."""
    home = Fake()

    with pytest.raises(ValueError) as refusal:
        await configure(home, [television()], {"id": "not a device", "notify": PHONE})

    assert str(refusal.value).endswith(".")
    assert home.automations == {}
