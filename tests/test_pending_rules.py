"""A rule changed while the television sleeps, and where it waits until it wakes.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tvsitter.button import ClearLimitButton, ClearPinButton
from custom_components.tvsitter.const import (
    CONF_PENDING_RULES,
    CONF_SCHEDULE,
    DOMAIN,
    SCHEMA_VERSION,
)
from custom_components.tvsitter.coordinator import TvSitterClient, merge_pending
from custom_components.tvsitter.models import StateSnapshot
from custom_components.tvsitter.number import (
    AppLimitNumber,
    DailyLimitNumber,
    SleepTimerNumber,
)
from custom_components.tvsitter.sensor import RulesSensor
from custom_components.tvsitter.switch import BlockSettingsSwitch
from custom_components.tvsitter.text import ParentPinText
from homeassistant.components.schedule.const import DOMAIN as SCHEDULE_DOMAIN
from homeassistant.components.schedule.const import SERVICE_GET as SERVICE_GET_SCHEDULE
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

PREFIX = "tvsitter/salon"


def snapshot(**overrides: object) -> StateSnapshot:
    """Build a state payload of the shape the television sends."""
    payload: dict[str, object] = {
        "schema": 1,
        "ts": 1,
        "fw": "0.5.0",
        "screen_on": True,
        "locked": False,
    }
    payload.update(overrides)
    return StateSnapshot.from_payload(json.dumps(payload))


def sleeping(hass: HomeAssistant, **options: object) -> TvSitterClient:
    """Build a client for a television that is not listening.

    With a config entry Home Assistant knows about, because that is where a waiting
    change is kept — a client without one can hold a change and cannot remember it.
    """
    entry = MockConfigEntry(domain=DOMAIN, options=options)
    entry.add_to_hass(hass)
    client = TvSitterClient(hass, name="TV Salon", topic_prefix=PREFIX, entry=entry)
    client.snapshot = snapshot(rules_rev=4)
    client.available = False
    return client


async def wakes(hass: HomeAssistant, client: TvSitterClient) -> None:
    """Let the television say hello, and let what that starts finish."""
    client._handle_availability(
        SimpleNamespace(topic=f"{PREFIX}/availability", payload="online")
    )
    await hass.async_block_till_done()


def sent(publish: object) -> list[dict]:
    """Every command that went out, decoded."""
    return [json.loads(call.args[2]) for call in publish.call_args_list]


async def test_a_change_made_while_the_set_sleeps_is_accepted(
    hass: HomeAssistant,
) -> None:
    """#135. A parent has drawn a week; "come back later" is not an answer to that.

    Nothing goes on the wire, because `<p>/cmd` is not retained and a `set_rules`
    published to a sleeping television really is lost. The change is kept instead.
    """
    client = sleeping(hass)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await DailyLimitNumber(client).async_set_native_value(45)

    publish.assert_not_called()
    assert client.pending_rules == {"daily_limit_s": 2700}


async def test_the_waiting_change_goes_out_when_the_set_comes_back(
    hass: HomeAssistant,
) -> None:
    """The other half: it is sent on the reconnect, exactly like an imported grid."""
    client = sleeping(hass)
    await DailyLimitNumber(client).async_set_native_value(45)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await wakes(hass, client)

    assert sent(publish) == [
        {"op": "set_rules", "rev": 5, "rules": {"daily_limit_s": 2700}}
    ]
    assert client.pending_rules is None


async def test_three_changes_become_one_payload(hass: HomeAssistant) -> None:
    """They are deltas of one object, so they fold rather than queue.

    Three payloads would spend three revisions to arrive in an order nothing
    guarantees, and the television would have to accept all three for the evening to
    be what the parent asked for.
    """
    client = sleeping(hass)

    await DailyLimitNumber(client).async_set_native_value(45)
    await BlockSettingsSwitch(client).async_turn_on()
    await AppLimitNumber(client, "com.netflix.ninja").async_set_native_value(30)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await wakes(hass, client)

    assert publish.call_count == 1
    assert sent(publish)[0]["rules"] == {
        "daily_limit_s": 2700,
        "block_settings": True,
        "app_limits_s": {"com.netflix.ninja": 1800},
    }


async def test_the_last_word_on_a_key_wins(hass: HomeAssistant) -> None:
    """A parent who moves the limit twice meant the second number."""
    client = sleeping(hass)
    limit = DailyLimitNumber(client)

    await limit.async_set_native_value(45)
    await limit.async_set_native_value(90)

    assert client.pending_rules == {"daily_limit_s": 5400}


async def test_two_apps_do_not_displace_each_other(hass: HomeAssistant) -> None:
    """D26 on this side too: a shallow fold would drop the first app's budget.

    The television merges inside objects, so the payload this builds has to as well —
    otherwise Netflix's budget arrives having quietly removed Disney's.
    """
    client = sleeping(hass)

    await AppLimitNumber(client, "com.netflix.ninja").async_set_native_value(30)
    await AppLimitNumber(client, "com.disney.disneyplus").async_set_native_value(45)

    assert client.pending_rules == {
        "app_limits_s": {"com.netflix.ninja": 1800, "com.disney.disneyplus": 2700}
    }


async def test_a_removal_survives_the_wait(hass: HomeAssistant) -> None:
    """The one place this fold must not be the television's.

    `Rules.merge` reads a null as "remove this key" and leaves nothing behind. Doing
    that here would turn "set the limit, then clear it" into an empty payload — and an
    empty `set_rules` changes nothing, so the limit would still be standing.
    """
    client = sleeping(hass)

    await DailyLimitNumber(client).async_set_native_value(45)
    await ClearLimitButton(client).async_press()

    assert client.pending_rules == {"daily_limit_s": None}


async def test_a_removal_inside_an_object_survives_it_too(hass: HomeAssistant) -> None:
    """Same again one level down, which is where the app budgets live."""
    client = sleeping(hass)
    sensor = RulesSensor(client)

    await AppLimitNumber(client, "com.netflix.ninja").async_set_native_value(30)
    await sensor.async_set_app_limit("com.disney.disneyplus", 45)
    await sensor.async_set_app_limit("com.netflix.ninja")

    assert client.pending_rules == {
        "app_limits_s": {"com.netflix.ninja": None, "com.disney.disneyplus": 2700}
    }


def test_a_list_replaces_whole() -> None:
    """Windows have no key to merge on, so half a schedule must never be built."""
    folded = merge_pending(
        {"windows": [{"id": "a"}, {"id": "b"}]}, {"windows": [{"id": "c"}]}
    )

    assert folded == {"windows": [{"id": "c"}]}


def test_the_fold_stops_where_the_television_stops_merging() -> None:
    """D26 bounds its merge at four levels and replaces below that.

    Folding deeper than the set merges would build a payload that does not mean what
    it will do on arrival, which is the one thing this must never do.
    """
    earlier = {"a": {"b": {"c": {"d": {"kept": 1}}}}}
    later = {"a": {"b": {"c": {"d": {"fresh": 2}}}}}

    assert merge_pending(earlier, later) == {"a": {"b": {"c": {"d": {"fresh": 2}}}}}, (
        "the fifth level replaces, as the television's merge does"
    )


async def test_the_revision_is_the_one_at_send_time(hass: HomeAssistant) -> None:
    """Reserving it when the change was made is how the guard stops working.

    The television ignores a `set_rules` whose revision is not higher than the one it
    holds. It edits its own rules too (D31), so a number taken while it slept could be
    overtaken and arrive too low — dropped on arrival, with nothing said anywhere.
    """
    client = sleeping(hass)
    await DailyLimitNumber(client).async_set_native_value(45)

    # What the set had been up to on its own while nobody was listening.
    client.snapshot = snapshot(rules_rev=20)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await wakes(hass, client)

    assert sent(publish)[0]["rev"] == 21


async def test_nothing_is_sent_twice_when_the_television_flaps(
    hass: HomeAssistant,
) -> None:
    """Cleared as it is sent, like the lock switch's remembered intention.

    Waiting for the set to confirm would turn a change it declines into a payload
    resent for ever.
    """
    client = sleeping(hass)
    await DailyLimitNumber(client).async_set_native_value(45)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await wakes(hass, client)
        client.available = False
        await wakes(hass, client)

    assert publish.call_count == 1


async def test_a_publish_that_fails_leaves_the_change_waiting(
    hass: HomeAssistant,
) -> None:
    """The one moment where "sent" and "asked for" come apart.

    Clearing before the publish would drop a week somebody drew because the broker
    hiccuped, which is this feature failing at the only job it has.
    """
    client = sleeping(hass)
    await DailyLimitNumber(client).async_set_native_value(45)

    with (
        patch(
            "homeassistant.components.mqtt.async_publish",
            side_effect=HomeAssistantError,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await client.async_send_pending_rules()

    assert client.pending_rules == {"daily_limit_s": 2700}

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await wakes(hass, client)

    assert sent(publish)[0]["rules"] == {"daily_limit_s": 2700}


async def test_a_listening_television_is_written_to_at_once(
    hass: HomeAssistant,
) -> None:
    """Nothing is held that could simply be sent, or every change would be late."""
    client = sleeping(hass)
    client.available = True

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await DailyLimitNumber(client).async_set_native_value(45)

    assert sent(publish) == [
        {"op": "set_rules", "rev": 5, "rules": {"daily_limit_s": 2700}}
    ]
    assert client.pending_rules is None


async def test_a_command_is_still_refused(hass: HomeAssistant) -> None:
    """The line: a rule is a state, a command is a moment.

    A sleep timer armed tonight and delivered on Friday is a television locking itself
    at breakfast, and a PIN that never arrived is a parent finding out in front of the
    lock screen.
    """
    client = sleeping(hass)

    with pytest.raises(ServiceValidationError):
        await SleepTimerNumber(client).async_set_native_value(30)
    with pytest.raises(ServiceValidationError):
        await ClearPinButton(client).async_press()
    with pytest.raises(ServiceValidationError):
        await ParentPinText(client).async_set_value("1234")

    assert client.pending_rules is None


async def test_a_waiting_change_survives_a_client_built_again(
    hass: HomeAssistant,
) -> None:
    """A parent who drew a week must not lose it because Home Assistant restarted.

    The entry is what outlives the process here, so the change is kept on it and read
    back when the client is built — which is what a restart amounts to.
    """
    client = sleeping(hass)
    await DailyLimitNumber(client).async_set_native_value(45)
    entry = client.entry

    after_restart = TvSitterClient(
        hass, name="TV Salon", topic_prefix=PREFIX, entry=entry
    )

    assert after_restart.pending_rules == {"daily_limit_s": 2700}
    assert entry.options[CONF_PENDING_RULES] == {
        "schema": SCHEMA_VERSION,
        "rules": {"daily_limit_s": 2700},
    }


async def test_a_restarted_change_still_goes_out_on_the_reconnect(
    hass: HomeAssistant,
) -> None:
    """Restored is not enough on its own; it has to still be on the road out."""
    client = sleeping(hass)
    await DailyLimitNumber(client).async_set_native_value(45)
    after_restart = TvSitterClient(
        hass, name="TV Salon", topic_prefix=PREFIX, entry=client.entry
    )
    after_restart.snapshot = snapshot(rules_rev=4)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await wakes(hass, after_restart)

    assert sent(publish) == [
        {"op": "set_rules", "rev": 5, "rules": {"daily_limit_s": 2700}}
    ]


async def test_a_change_stored_for_another_schema_is_not_sent(
    hass: HomeAssistant,
) -> None:
    """Refused rather than guessed at, like every other payload read here.

    Past a schema change the meaning of the keys cannot be assumed, and a rules delta
    that means something else is a television enforcing something nobody asked for.
    """
    client = sleeping(
        hass,
        **{
            CONF_PENDING_RULES: {
                "schema": SCHEMA_VERSION + 7,
                "rules": {"daily_limit_s": 2700},
            }
        },
    )

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await wakes(hass, client)

    publish.assert_not_called()
    assert client.pending_rules is None


async def test_rubbish_where_a_waiting_change_should_be_is_dropped(
    hass: HomeAssistant,
) -> None:
    """Another process wrote the entry, or a hand edited it. Neither is a payload."""
    for stored in ("not an object", {"schema": SCHEMA_VERSION}, {"rules": {"a": 1}}):
        client = sleeping(hass, **{CONF_PENDING_RULES: stored})

        assert client.pending_rules is None


async def test_forgetting_throws_the_waiting_change_away(hass: HomeAssistant) -> None:
    """A television sold or a prefix retyped leaves a change that can never land.

    Without a way out it sits on the entry for ever, with the rules sensor promising a
    panel something that will never happen.
    """
    client = sleeping(hass)
    await DailyLimitNumber(client).async_set_native_value(45)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await RulesSensor(client).async_forget_pending_rules()
        await wakes(hass, client)

    publish.assert_not_called()
    assert client.pending_rules is None
    assert CONF_PENDING_RULES not in client.entry.options


async def test_forgetting_clears_a_change_this_build_would_not_restore(
    hass: HomeAssistant,
) -> None:
    """Otherwise the one change nobody can send is the one nobody can get rid of."""
    client = sleeping(
        hass,
        **{CONF_PENDING_RULES: {"schema": SCHEMA_VERSION + 7, "rules": {"a": 1}}},
    )

    await RulesSensor(client).async_forget_pending_rules()

    assert CONF_PENDING_RULES not in client.entry.options


async def test_forgetting_nothing_is_not_an_error(hass: HomeAssistant) -> None:
    """A panel offering the button cannot know what the entry holds.

    An action that fails for having already happened is one nobody dares press — the
    same reading `forget_schedule` was given.
    """
    client = sleeping(hass)

    await RulesSensor(client).async_forget_pending_rules()

    assert client.pending_rules is None
    assert dict(client.entry.options) == {}


async def test_forgetting_leaves_the_rest_of_the_entry(hass: HomeAssistant) -> None:
    """Options are written whole, so one key is removed by rebuilding the rest."""
    client = sleeping(hass, **{CONF_SCHEDULE: "schedule.viewing_hours"})
    await DailyLimitNumber(client).async_set_native_value(45)

    await RulesSensor(client).async_forget_pending_rules()

    assert dict(client.entry.options) == {CONF_SCHEDULE: "schedule.viewing_hours"}


async def test_forgetting_does_not_touch_the_rules_in_force(
    hass: HomeAssistant,
) -> None:
    """It throws away a change that never left. That is not undoing one that did."""
    client = sleeping(hass)
    client.rules = {"daily_limit_s": 3600}
    await DailyLimitNumber(client).async_set_native_value(45)

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await RulesSensor(client).async_forget_pending_rules()

    publish.assert_not_called()
    assert client.rules == {"daily_limit_s": 3600}


async def test_the_rules_sensor_says_what_is_waiting(hass: HomeAssistant) -> None:
    """Accepting a change that has not happened, silently, is worse than refusing it.

    So a panel can say what is waiting and for which television, beside the rules the
    set is actually enforcing.
    """
    client = sleeping(hass)
    client.rules = {"daily_limit_s": 3600}
    await DailyLimitNumber(client).async_set_native_value(45)

    attributes = RulesSensor(client).extra_state_attributes

    assert attributes["pending_rules"] == {"daily_limit_s": 2700}
    assert attributes["daily_limit_s"] == 3600, "the rule in force is still in force"


async def test_nothing_waiting_says_nothing(hass: HomeAssistant) -> None:
    """Absent rather than an empty object: a change with nothing in it is not one."""
    client = sleeping(hass)
    client.rules = {"daily_limit_s": 3600}

    assert "pending_rules" not in RulesSensor(client).extra_state_attributes


async def test_the_sensor_reports_it_before_any_rules_have_arrived(
    hass: HomeAssistant,
) -> None:
    """A set that has never published its rules can still be given some."""
    client = sleeping(hass)
    await DailyLimitNumber(client).async_set_native_value(45)

    assert RulesSensor(client).extra_state_attributes == {
        "pending_rules": {"daily_limit_s": 2700}
    }


async def test_a_television_cannot_claim_something_is_waiting(
    hass: HomeAssistant,
) -> None:
    """The rules are opaque, but this name is Home Assistant's answer, not the set's.

    A television echoing the word back would otherwise have a panel announce a change
    nobody made — or hide the one somebody did.
    """
    client = sleeping(hass)
    client.rules = {"pending_rules": {"daily_limit_s": 1}}

    claimed = RulesSensor(client).extra_state_attributes
    assert "pending_rules" not in claimed

    await DailyLimitNumber(client).async_set_native_value(45)

    assert RulesSensor(client).extra_state_attributes["pending_rules"] == {
        "daily_limit_s": 2700
    }


async def test_the_sensor_says_so_the_moment_the_change_is_made(
    hass: HomeAssistant,
) -> None:
    """Holding a change is not a payload arriving, so nothing else would say it.

    `forget_schedule` was found the hard way: the option really changed, and the sensor
    went on publishing the old answer until some unrelated payload came along.
    """
    client = sleeping(hass)
    told: list[int] = []
    client.async_add_listener(lambda: told.append(1))

    await DailyLimitNumber(client).async_set_native_value(45)
    assert told, "nothing was told a change was waiting"

    told.clear()
    client.forget_pending_rules()
    assert told, "nothing was told it had been thrown away"


async def test_a_client_without_an_entry_still_holds_and_sends(
    hass: HomeAssistant,
) -> None:
    """Nothing can remember one without an entry, and holding must not fail for it."""
    client = TvSitterClient(hass, name="TV Salon", topic_prefix=PREFIX)
    client.snapshot = snapshot(rules_rev=4)
    client.available = False

    await DailyLimitNumber(client).async_set_native_value(45)
    assert client.pending_rules == {"daily_limit_s": 2700}

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await wakes(hass, client)

    assert sent(publish)[0]["rules"] == {"daily_limit_s": 2700}


async def test_a_followed_grid_is_read_again_rather_than_held(
    hass: HomeAssistant,
) -> None:
    """The hours keep their own road, and it is the better one for them.

    A held payload would be a copy of the grid as it was; the helper may be drawn on
    again before the set wakes, and re-reading it then gives the hours as they are.
    """
    client = sleeping(hass, **{CONF_SCHEDULE: "schedule.viewing_hours"})

    async def read(_call: ServiceCall) -> dict:
        return {
            "schedule.viewing_hours": {
                "monday": [{"from": "16:00:00", "to": "19:30:00"}]
            }
        }

    hass.services.async_register(
        SCHEDULE_DOMAIN,
        SERVICE_GET_SCHEDULE,
        read,
        supports_response=SupportsResponse.ONLY,
    )

    with patch("homeassistant.components.mqtt.async_publish") as publish:
        await client.async_import_schedule("schedule.viewing_hours")

    publish.assert_not_called()
    assert client.pending_rules is None, "the hours are left for the reconnect"

    with patch.object(client, "async_import_schedule") as imported:
        await wakes(hass, client)

    imported.assert_called_once_with("schedule.viewing_hours")
