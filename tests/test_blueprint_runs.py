"""The blueprints run as automations, against the events they are written for.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

from pytest_homeassistant_custom_component.common import async_mock_service

from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

SOURCE = Path(__file__).resolve().parent.parent / "blueprints"
REQUESTS = "event.tv_time_request"
TAMPER = "event.tv_tamper"
PARENT = "u-parent"
CHILD = "u-child"


async def running(hass: HomeAssistant, blueprint: str, **inputs: Any) -> None:
    """Install the repository's blueprint and make one automation out of it."""
    shutil.copytree(SOURCE, hass.config.path("blueprints"), dirs_exist_ok=True)
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "use_blueprint": {
                    "path": f"tvsitter/{blueprint}",
                    "input": inputs,
                }
            }
        },
    )
    await hass.async_block_till_done()


async def answering(hass: HomeAssistant, **inputs: Any) -> list[ServiceCall]:
    """Run the request blueprint and hand back the grants it makes."""
    grants = async_mock_service(hass, "tvsitter", "grant_time")
    async_mock_service(hass, "tvsitter", "deny_time")
    async_mock_service(hass, "notify", "phone")
    hass.states.async_set("person.parent", "home", {"user_id": PARENT})
    await running(
        hass,
        "more_time_request.yaml",
        request_event=REQUESTS,
        notify_action="notify.phone",
        **inputs,
    )
    return grants


async def tapped(hass: HomeAssistant, action: str, user_id: str) -> None:
    """Press a notification button, as the companion app reports it."""
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": action},
        context=Context(user_id=user_id),
    )
    await hass.async_block_till_done()


async def test_an_offered_answer_grants_its_minutes(hass: HomeAssistant) -> None:
    """The ordinary case, and the control for the two below."""
    grants = await answering(hass)

    await tapped(hass, "TVSITTER-GRANT-15-abc", PARENT)

    assert [(call.data["minutes"], call.data["req_id"]) for call in grants] == [
        (15, "abc")
    ]


async def test_minutes_nobody_offered_are_not_granted(hass: HomeAssistant) -> None:
    """The request id is readable off the event entity, and the minutes are typed.

    Anything with the companion app could fire this event, so the button is held to
    what was on it.
    """
    grants = await answering(hass)

    await tapped(hass, "TVSITTER-GRANT-240-abc", PARENT)

    assert grants == []


async def test_an_answer_from_outside_the_parents_is_ignored(
    hass: HomeAssistant,
) -> None:
    """A child's tablet signed in as the child is not a parent pressing a button."""
    grants = await answering(hass, parents=["person.parent"])

    await tapped(hass, "TVSITTER-GRANT-15-abc", CHILD)
    await tapped(hass, "TVSITTER-GRANT-15-abd", PARENT)

    assert [call.data["req_id"] for call in grants] == ["abd"]


async def test_the_first_alarm_after_a_restart_is_told(hass: HomeAssistant) -> None:
    """An event entity comes back `unknown`; guarding that side is #117 again."""
    told = async_mock_service(hass, "notify", "phone")
    hass.states.async_set(TAMPER, "unknown", {"event_type": None})
    await running(
        hass, "tamper_alarm.yaml", tamper_event=TAMPER, notify_action="notify.phone"
    )

    hass.states.async_set(
        TAMPER,
        dt_util.utcnow().isoformat(),
        {"event_type": "usage_lost", "id": "a1", "kind": "usage_lost"},
    )
    await hass.async_block_till_done()

    assert len(told) == 1


async def test_an_old_alarm_restored_is_not_told_again(hass: HomeAssistant) -> None:
    """A restart re-reads the entity, and an alarm hours old needs nobody now."""
    told = async_mock_service(hass, "notify", "phone")
    hass.states.async_set(TAMPER, "unavailable")
    await running(
        hass, "tamper_alarm.yaml", tamper_event=TAMPER, notify_action="notify.phone"
    )

    hass.states.async_set(
        TAMPER,
        "2026-01-01T08:00:00+00:00",
        {"event_type": "usage_lost", "id": "a1", "kind": "usage_lost"},
    )
    await hass.async_block_till_done()

    assert told == []
