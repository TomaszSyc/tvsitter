"""Writing rules: the revision, and why one place owns it.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from collections.abc import Awaitable
import json
from unittest.mock import patch

import pytest

from custom_components.tvsitter.button import ClearLimitButton
from custom_components.tvsitter.coordinator import TvSitterClient
from custom_components.tvsitter.models import StateSnapshot
from custom_components.tvsitter.number import (
    AppLimitNumber,
    DailyLimitNumber,
    SleepTimerNumber,
    WarnBeforeNumber,
)
from custom_components.tvsitter.sensor import RulesSensor
from custom_components.tvsitter.switch import BlockSettingsSwitch
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

PREFIX = "tvsitter/salon"


def make_client(hass: HomeAssistant, available: bool = True) -> TvSitterClient:
    """Build a client with nothing subscribed; these tests only publish.

    Marked as listening, because that is what these tests are about. Writing to a
    television that is not is refused on purpose (#90), and has its own tests.
    """
    client = TvSitterClient(hass, name="TV Salon", topic_prefix=PREFIX)
    client.available = available
    return client


async def written(change: Awaitable[None]) -> dict:
    """Run one change and hand back the command that went out.

    A helper rather than the revision list above, because these tests are about what
    was written rather than about which revision carried it.
    """
    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await change
    return json.loads(publish.call_args.args[2])["rules"]


def snapshot(**overrides: object) -> StateSnapshot:
    """Build a state payload of the shape the TV sends."""
    payload: dict[str, object] = {
        "schema": 1,
        "ts": 1,
        "fw": "0.4.1",
        "screen_on": True,
        "locked": False,
    }
    payload.update(overrides)
    return StateSnapshot.from_payload(json.dumps(payload))


def revisions(publish: object) -> list[int]:
    """Pull the revision out of every command that went out."""
    return [json.loads(call.args[2])["rev"] for call in publish.call_args_list]


async def test_two_changes_in_a_row_do_not_share_a_revision(
    hass: HomeAssistant,
) -> None:
    """#72. The TV ignores a revision no higher than the one it has.

    A parent moving the limit and then clearing it, both before the TV has had a chance
    to republish, used to compute the same number twice — and the second was dropped on
    arrival with nothing said anywhere.
    """
    client = make_client(hass)
    client.snapshot = snapshot(rules_rev=7)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await DailyLimitNumber(client).async_set_native_value(45)
        await ClearLimitButton(client).async_press()

    assert revisions(publish) == [8, 9]


async def test_a_burst_from_one_control_keeps_climbing(hass: HomeAssistant) -> None:
    """No round trip to wait for, so it cannot be waited for."""
    client = make_client(hass)
    client.snapshot = snapshot(rules_rev=3)
    number = DailyLimitNumber(client)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        for minutes in (30, 45, 60):
            await number.async_set_native_value(minutes)

    assert revisions(publish) == [4, 5, 6]


async def test_the_television_wins_when_it_is_ahead(hass: HomeAssistant) -> None:
    """Something else has been writing rules, or Home Assistant has restarted.

    Carrying on from our own count would send a revision the TV has already passed,
    which it would ignore — the failure this exists to prevent, one step along.
    """
    client = make_client(hass)
    client.snapshot = snapshot(rules_rev=2)
    number = DailyLimitNumber(client)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await number.async_set_native_value(30)
        client.snapshot = snapshot(rules_rev=20)
        await number.async_set_native_value(45)

    assert revisions(publish) == [3, 21]


async def test_a_television_that_has_never_reported_starts_at_one(
    hass: HomeAssistant,
) -> None:
    """Zero would be ignored: it is not higher than the zero a fresh TV holds."""
    client = make_client(hass)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await client.async_set_rules({"daily_limit_s": 600})
        await client.async_set_rules({"daily_limit_s": None})

    assert revisions(publish) == [1, 2]


async def test_clearing_a_limit_names_one_key_and_nothing_else(
    hass: HomeAssistant,
) -> None:
    """set_rules merges, so naming one key with null removes exactly that rule."""
    client = make_client(hass)
    client.snapshot = snapshot(rules_rev=1)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await ClearLimitButton(client).async_press()

    payload = json.loads(publish.call_args.args[2])
    assert payload == {"op": "set_rules", "rev": 2, "rules": {"daily_limit_s": None}}
    assert publish.call_args.kwargs["retain"] is False
    assert publish.call_args.kwargs["qos"] == 1


def with_rules(
    client: TvSitterClient, rules: dict[str, object] | None
) -> TvSitterClient:
    """Hand the client the rules the TV would have published."""
    client.rules = rules
    return client


async def test_the_warning_reads_the_nearest_rung(hass: HomeAssistant) -> None:
    """#39. Two warnings in an evening is a ladder; this box shows the last one."""
    client = with_rules(make_client(hass), {"warn_before_s": [900, 300]})

    warn = WarnBeforeNumber(client)

    assert warn.native_value == 5
    assert warn.extra_state_attributes == {"all_warnings_s": [900, 300]}


async def test_one_rung_needs_no_footnote(hass: HomeAssistant) -> None:
    """The attribute exists to explain a ladder, so one warning does not get one."""
    client = with_rules(make_client(hass), {"warn_before_s": [300]})

    assert WarnBeforeNumber(client).extra_state_attributes is None


async def test_never_set_means_the_default_and_not_silence(hass: HomeAssistant) -> None:
    """The reverse of the daily limit, and the reason it is worth a test.

    Somebody who has never touched this should still be warned before the end.
    """
    client = with_rules(make_client(hass), {"daily_limit_s": 3600})

    assert WarnBeforeNumber(client).native_value == 5


async def test_zero_is_no_warning_at_all(hass: HomeAssistant) -> None:
    """And it is what an empty list means, which is what setting zero writes."""
    client = with_rules(make_client(hass), {"warn_before_s": []})

    assert WarnBeforeNumber(client).native_value == 0


async def test_setting_zero_asks_for_silence_rather_than_removing_the_rule(
    hass: HomeAssistant,
) -> None:
    """A null would restore the default, which is the opposite of what zero means."""
    client = with_rules(make_client(hass), {"warn_before_s": [300]})

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await WarnBeforeNumber(client).async_set_native_value(0)

    assert json.loads(publish.call_args.args[2])["rules"] == {"warn_before_s": []}


async def test_setting_a_warning_writes_seconds(hass: HomeAssistant) -> None:
    """Minutes on the dial, seconds on the wire, like every other rule."""
    client = with_rules(make_client(hass), {"warn_before_s": [300]})

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await WarnBeforeNumber(client).async_set_native_value(15)

    assert json.loads(publish.call_args.args[2])["rules"] == {"warn_before_s": [900]}


async def test_nothing_is_shown_before_the_rules_arrive(hass: HomeAssistant) -> None:
    """Guessing five minutes at a television that has not spoken invents one."""
    assert WarnBeforeNumber(with_rules(make_client(hass), None)).native_value is None


async def test_the_sleep_timer_arms_a_deadline_rather_than_locking(
    hass: HomeAssistant,
) -> None:
    """#74. Minutes on the command make it a bedtime, not a lock."""
    client = make_client(hass)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await SleepTimerNumber(client).async_set_native_value(30)

    assert json.loads(publish.call_args.args[2]) == {"op": "lock", "in_minutes": 30}
    assert publish.call_args.kwargs["retain"] is False


async def test_zero_cancels_a_bedtime_already_set(hass: HomeAssistant) -> None:
    """Which is what a control at zero has to mean, or it could only ever add one."""
    client = make_client(hass)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await SleepTimerNumber(client).async_set_native_value(0)

    assert json.loads(publish.call_args.args[2]) == {"op": "lock", "in_minutes": 0}


async def test_the_sleep_timer_reads_back_nothing(hass: HomeAssistant) -> None:
    """A control, not a reading: the countdown is until_s, for whatever binds."""
    assert SleepTimerNumber(make_client(hass)).native_value is None


async def test_the_settings_switch_reads_the_television(hass: HomeAssistant) -> None:
    """#107. What the TV says it is enforcing, not what was last sent from here."""
    on = with_rules(make_client(hass), {"block_settings": True})
    off = with_rules(make_client(hass), {"daily_limit_s": 3600})

    assert BlockSettingsSwitch(on).is_on is True
    assert BlockSettingsSwitch(off).is_on is False, "absent means reachable"
    assert BlockSettingsSwitch(with_rules(make_client(hass), None)).is_on is None


async def test_blocking_settings_names_one_key(hass: HomeAssistant) -> None:
    """set_rules merges, so this must not disturb a limit or a schedule."""
    client = with_rules(make_client(hass), {"daily_limit_s": 3600})

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await BlockSettingsSwitch(client).async_turn_on()

    assert json.loads(publish.call_args.args[2])["rules"] == {"block_settings": True}


async def test_handing_settings_back_writes_false_rather_than_null(
    hass: HomeAssistant,
) -> None:
    """A null would read the same here, but false says somebody decided it."""
    client = with_rules(make_client(hass), {"block_settings": True})

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await BlockSettingsSwitch(client).async_turn_off()

    assert json.loads(publish.call_args.args[2])["rules"] == {"block_settings": False}


async def test_one_app_gets_its_own_budget(hass: HomeAssistant) -> None:
    """#114. Setting Netflix to half an hour has to be a control, not a payload."""
    client = make_client(hass)
    limit = AppLimitNumber(client, "com.netflix.ninja")

    assert await written(limit.async_set_native_value(30)) == {
        "app_limits_s": {"com.netflix.ninja": 1800}
    }


async def test_zero_minutes_is_the_block(hass: HomeAssistant) -> None:
    """One mechanism rather than two: a blocked app is an app with no time."""
    client = make_client(hass)

    blocked = AppLimitNumber(client, "com.twitch.android.app")

    assert await written(blocked.async_set_native_value(0)) == {
        "app_limits_s": {"com.twitch.android.app": 0}
    }


async def test_an_app_without_a_budget_of_its_own_reads_as_nothing(
    hass: HomeAssistant,
) -> None:
    """Unset is not zero: one runs on the day's allowance, the other cannot run."""
    client = make_client(hass)
    client.rules = {"app_limits_s": {"com.netflix.ninja": 1800}}

    assert AppLimitNumber(client, "com.netflix.ninja").native_value == 30
    assert AppLimitNumber(client, "com.youtube.tv").native_value is None


async def test_a_day_of_the_week_gets_its_own_allowance(hass: HomeAssistant) -> None:
    """#114. Saturday differs from Monday, and the week is not retyped to say so."""
    client = make_client(hass)

    assert await written(RulesSensor(client).async_set_schedule("sat", 120)) == {
        "days": {"sat": 7200}
    }


async def test_leaving_the_minutes_out_removes_the_override(
    hass: HomeAssistant,
) -> None:
    """A null removes the key at any depth, which hands the day back to the limit."""
    client = make_client(hass)

    assert await written(RulesSensor(client).async_set_schedule("sat")) == {
        "days": {"sat": None}
    }


async def test_the_viewing_hours_are_sent_whole(hass: HomeAssistant) -> None:
    """Windows have no key a parent names, so there is nothing to merge onto."""
    client = make_client(hass)
    windows = [{"id": "school", "from": "16:00", "to": "19:30", "days": ["mon"]}]

    assert await written(RulesSensor(client).async_set_windows(windows)) == {
        "windows": windows
    }


async def test_an_empty_list_is_no_restriction(hass: HomeAssistant) -> None:
    """D27, on the wire as well as in the engine: no windows is not a closed day."""
    client = make_client(hass)

    assert await written(RulesSensor(client).async_set_windows([])) == {"windows": []}


async def test_a_rule_change_needs_a_television_that_is_listening(
    hass: HomeAssistant,
) -> None:
    """Refuse rather than write into the dark: a lost rule change is silent."""
    client = make_client(hass, available=False)

    with pytest.raises(ServiceValidationError):
        await RulesSensor(client).async_set_windows([])
    with pytest.raises(ServiceValidationError):
        await AppLimitNumber(client, "com.netflix.ninja").async_set_native_value(30)


async def test_an_app_limit_can_be_taken_away(hass: HomeAssistant) -> None:
    """The one thing a number cannot say: zero blocks, absent is no budget at all."""
    client = make_client(hass)
    sensor = RulesSensor(client)

    assert await written(sensor.async_set_app_limit("com.netflix.ninja")) == {
        "app_limits_s": {"com.netflix.ninja": None}
    }
    assert await written(sensor.async_set_app_limit("com.disney.disneyplus", 45)) == {
        "app_limits_s": {"com.disney.disneyplus": 2700}
    }


async def test_following_a_schedule_does_not_need_a_listening_tv(
    hass: HomeAssistant,
) -> None:
    """#119. What this sets up is the following, which outlives the set being asleep.

    The other rule writes refuse rather than write into the dark, and should. This one
    would refuse to remember a helper — and the hours would then never arrive, because
    nothing would be watching the grid to send them when the television woke up.
    """
    client = make_client(hass, available=False)
    client.rules = {}

    with patch.object(client, "async_follow_schedule") as followed:
        await RulesSensor(client).async_use_schedule("schedule.hours")

    followed.assert_called_once_with("schedule.hours")
