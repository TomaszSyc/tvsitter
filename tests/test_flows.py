"""The config flows, driven through Home Assistant itself.

Everything here needs a real `hass`, which is what
pytest-homeassistant-custom-component provides. The pure helpers behind these flows are
tested in test_config_flow.py without one.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from collections.abc import Generator
from http import HTTPStatus
from ipaddress import ip_address
from typing import Any
from unittest.mock import patch

import aiohttp
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.tvsitter.const import DOMAIN
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

TV_HOST = "192.0.2.6"
TV_PORT = 33519
PAIR_URL = f"http://{TV_HOST}:{TV_PORT}/pair"
DEVICE_ID = "dd17356d"

# An address that needs no substituting, so most tests exercise one thing at a time.
ROUTABLE_BROKER = "192.0.2.10"


def discovered(**properties: Any) -> ZeroconfServiceInfo:
    """Build a discovery, with the TXT record PairingProtocol publishes."""
    txt: dict[str, Any] = {
        "id": DEVICE_ID,
        "name": "Salon",
        "version": "0.1.0-m0",
        "paired": "false",
    }
    txt.update(properties)
    return ZeroconfServiceInfo(
        ip_address=ip_address(TV_HOST),
        ip_addresses=[ip_address(TV_HOST)],
        port=TV_PORT,
        hostname="salon.local.",
        type="_tvsitter._tcp.local.",
        name=f"TV Sitter {DEVICE_ID}._tvsitter._tcp.local.",
        properties=txt,
    )


def add_mqtt_entry(hass: HomeAssistant, broker: str = ROUTABLE_BROKER) -> None:
    """Give the flow a Home Assistant MQTT entry to read the broker out of."""
    MockConfigEntry(
        domain="mqtt",
        data={
            "broker": broker,
            "port": 1883,
            "username": "ha-user",
            "password": "ha-secret",
        },
    ).add_to_hass(hass)


@pytest.fixture(autouse=True)
def mqtt_client_ready() -> Generator[None]:
    """Pretend MQTT is set up and connected, which is the normal case.

    The entry has to exist for the flow to read the broker out of it, but letting Home
    Assistant set it up for real opens a socket to a broker that is not there, which the
    harness blocks. Correctly.
    """
    with (
        patch(
            "homeassistant.components.mqtt.async_wait_for_mqtt_client",
            return_value=True,
        ),
        patch("homeassistant.components.mqtt.async_setup_entry", return_value=True),
        patch("homeassistant.components.mqtt.async_unload_entry", return_value=True),
    ):
        yield


@pytest.fixture(autouse=True)
def bypass_entry_setup() -> Generator[None]:
    """Stop a created entry from setting itself up.

    Entry setup subscribes to MQTT, which is a different thing from the flow and not
    what these tests are about.
    """
    with patch("custom_components.tvsitter.async_setup_entry", return_value=True):
        yield


async def start_zeroconf(hass: HomeAssistant, **properties: Any) -> dict[str, Any]:
    """Begin a discovery flow and return whatever it produced."""
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovered(**properties),
    )


def suggested_prefix(result: dict[str, Any]) -> str | None:
    """Read back the prefix the form is offering, however it was set."""
    for key in result["data_schema"].schema:
        if str(key) != "topic_prefix":
            continue
        if key.description and "suggested_value" in key.description:
            return key.description["suggested_value"]
        return key.default()
    return None


# --------------------------------------------------------------------------------------
# Adding a TV by hand
# --------------------------------------------------------------------------------------


async def test_user_flow_creates_an_entry(hass: HomeAssistant) -> None:
    """The path for a TV that is switched off."""
    started = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert started["type"] is FlowResultType.FORM
    assert started["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        started["flow_id"], {"name": "TV Salon", "topic_prefix": "tvsitter/salon"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "TV Salon"
    assert result["data"] == {"name": "TV Salon", "topic_prefix": "tvsitter/salon"}


@pytest.mark.parametrize("prefix", ["tvsitter/+", "tvsitter/#", "", "   ", "/"])
async def test_user_flow_rejects_an_unusable_prefix(
    hass: HomeAssistant, prefix: str
) -> None:
    """A wildcard would subscribe to other people's topics."""
    started = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        started["flow_id"], {"name": "TV Salon", "topic_prefix": prefix}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"topic_prefix": "invalid_topic_prefix"}


async def test_user_flow_aborts_when_mqtt_is_missing(hass: HomeAssistant) -> None:
    """The whole point of #12: name MQTT instead of failing generically later."""
    with patch(
        "homeassistant.components.mqtt.async_wait_for_mqtt_client", return_value=False
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "mqtt_unavailable"


async def test_the_same_prefix_cannot_be_added_twice(hass: HomeAssistant) -> None:
    """Two entries on one prefix would send commands to the same TV."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="tvsitter/salon",
        data={"name": "TV Salon", "topic_prefix": "tvsitter/salon"},
    ).add_to_hass(hass)

    started = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        started["flow_id"], {"name": "Another name", "topic_prefix": "tvsitter/salon"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# --------------------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------------------


async def test_discovery_offers_the_pairing_form(hass: HomeAssistant) -> None:
    """A TV that is on should turn up without anybody adding it."""
    add_mqtt_entry(hass)
    result = await start_zeroconf(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["description_placeholders"] == {"name": "Salon"}


async def test_discovery_defaults_the_prefix_from_the_tv_name(
    hass: HomeAssistant,
) -> None:
    """With nothing advertised, the owner recognises the name rather than the id."""
    add_mqtt_entry(hass)
    result = await start_zeroconf(hass, name="Salon telewizor")

    assert suggested_prefix(result) == "tvsitter/salon_telewizor"


async def test_discovery_prefers_the_prefix_the_tv_is_already_using(
    hass: HomeAssistant,
) -> None:
    """Re-pairing a working TV must not invite a new prefix (#33).

    The derived value would be `tvsitter/salon_telewizor` here, and accepting it would
    move the TV onto a prefix Home Assistant had just invented, leaving the entities
    behind.
    """
    add_mqtt_entry(hass)
    result = await start_zeroconf(
        hass, name="Salon telewizor", prefix="tvsitter/parter/salon"
    )

    assert suggested_prefix(result) == "tvsitter/parter/salon"


@pytest.mark.parametrize("advertised", ["tvsitter/+", "tvsitter/#", "", "   ", "/"])
async def test_an_unusable_advertised_prefix_falls_back_to_the_name(
    hass: HomeAssistant, advertised: str
) -> None:
    """A wildcard would subscribe to other TVs' topics, so it is not offered."""
    add_mqtt_entry(hass)
    result = await start_zeroconf(hass, name="Salon", prefix=advertised)

    assert suggested_prefix(result) == "tvsitter/salon"


async def test_discovery_ignores_a_tv_that_is_already_paired(
    hass: HomeAssistant,
) -> None:
    """A stale mDNS record must not offer to pair a TV that has been."""
    result = await start_zeroconf(hass, paired="true")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_paired"


async def test_discovery_ignores_something_that_is_not_ours(
    hass: HomeAssistant,
) -> None:
    """Our service type with none of our TXT record."""
    result = await start_zeroconf(hass, id="")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_tvsitter"


async def test_discovery_of_a_configured_tv_stops_there(hass: HomeAssistant) -> None:
    """Rediscovery must not offer a second entry for the same television."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE_ID,
        data={"name": "Salon", "topic_prefix": "tvsitter/salon"},
    ).add_to_hass(hass)

    result = await start_zeroconf(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# --------------------------------------------------------------------------------------
# Pairing
# --------------------------------------------------------------------------------------


async def test_pairing_sends_the_broker_details_and_creates_an_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The success path, including what actually goes over the wire."""
    add_mqtt_entry(hass)
    aioclient_mock.post(
        PAIR_URL, json={"ok": True, "device_id": DEVICE_ID, "name": "Salon"}
    )

    started = await start_zeroconf(hass)
    result = await hass.config_entries.flow.async_configure(
        started["flow_id"],
        {"pin": "927745", "topic_prefix": "tvsitter/salon", "broker": {}},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Salon"
    assert result["data"] == {
        "name": "Salon",
        "topic_prefix": "tvsitter/salon",
        "device_id": DEVICE_ID,
    }

    assert len(aioclient_mock.mock_calls) == 1
    _method, _url, sent, _headers = aioclient_mock.mock_calls[0]
    assert sent == {
        "pin": "927745",
        "host": ROUTABLE_BROKER,
        "port": 1883,
        "username": "ha-user",
        "password": "ha-secret",
        "topic_prefix": "tvsitter/salon",
        "use_tls": False,
    }


async def test_pairing_adopts_a_tv_that_was_added_by_hand(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """One television must not become two entries.

    The manual step keys its entry on the topic prefix, because that is all it knows;
    pairing keys on the device id. Whichever came first, the second has to find it.
    """
    add_mqtt_entry(hass)
    aioclient_mock.post(
        PAIR_URL, json={"ok": True, "device_id": DEVICE_ID, "name": "Salon"}
    )
    by_hand = MockConfigEntry(
        domain=DOMAIN,
        unique_id="tvsitter/salon",
        title="Added by hand",
        data={"name": "Added by hand", "topic_prefix": "tvsitter/salon"},
    )
    by_hand.add_to_hass(hass)

    started = await start_zeroconf(hass)
    result = await hass.config_entries.flow.async_configure(
        started["flow_id"],
        {"pin": "927745", "topic_prefix": "tvsitter/salon", "broker": {}},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "updated_existing"

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].entry_id == by_hand.entry_id
    assert entries[0].unique_id == DEVICE_ID
    assert entries[0].data["device_id"] == DEVICE_ID
    # The prefix is what the entities are keyed on, so it must survive untouched.
    assert entries[0].data["topic_prefix"] == "tvsitter/salon"
    # And so must the name, which somebody chose. Pairing writes identity, not labels.
    assert entries[0].title == "Added by hand"
    assert entries[0].data["name"] == "Added by hand"


async def test_pairing_a_different_tv_still_creates_its_own_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Adopting must key on the prefix, not merely on there being an entry."""
    add_mqtt_entry(hass)
    aioclient_mock.post(
        PAIR_URL, json={"ok": True, "device_id": DEVICE_ID, "name": "Salon"}
    )
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="tvsitter/kitchen",
        data={"name": "Kitchen", "topic_prefix": "tvsitter/kitchen"},
    ).add_to_hass(hass)

    started = await start_zeroconf(hass)
    result = await hass.config_entries.flow.async_configure(
        started["flow_id"],
        {"pin": "927745", "topic_prefix": "tvsitter/salon", "broker": {}},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


async def test_a_container_local_broker_address_is_replaced(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """D18. core-mosquitto would give a TV that can never connect."""
    add_mqtt_entry(hass, broker="core-mosquitto")
    aioclient_mock.post(
        PAIR_URL, json={"ok": True, "device_id": DEVICE_ID, "name": "Salon"}
    )

    with patch(
        "custom_components.tvsitter.broker._local_address_towards",
        return_value="192.0.2.20",
    ):
        started = await start_zeroconf(hass)
        result = await hass.config_entries.flow.async_configure(
            started["flow_id"],
            {"pin": "927745", "topic_prefix": "tvsitter/salon", "broker": {}},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    _method, _url, sent, _headers = aioclient_mock.mock_calls[0]
    assert sent["host"] == "192.0.2.20"
    # Credentials still come from Home Assistant; only the address was wrong.
    assert sent["username"] == "ha-user"


async def test_a_dedicated_account_is_sent_as_typed(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The SECURITY.md option: an account scoped to this TV's topics."""
    add_mqtt_entry(hass)
    aioclient_mock.post(
        PAIR_URL, json={"ok": True, "device_id": DEVICE_ID, "name": "Salon"}
    )

    started = await start_zeroconf(hass)
    await hass.config_entries.flow.async_configure(
        started["flow_id"],
        {
            "pin": "927745",
            "topic_prefix": "tvsitter/salon",
            "broker": {"username": "tv-salon", "password": "tv-only", "use_tls": True},
        },
    )

    _method, _url, sent, _headers = aioclient_mock.mock_calls[0]
    assert sent["username"] == "tv-salon"
    assert sent["password"] == "tv-only"
    assert sent["use_tls"] is True


async def test_a_wrong_pin_says_how_many_attempts_are_left(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The code is on the screen in front of them, so the count leaks nothing."""
    add_mqtt_entry(hass)
    aioclient_mock.post(
        PAIR_URL,
        status=HTTPStatus.FORBIDDEN,
        json={"ok": False, "error": "wrong_pin", "attempts_remaining": 3},
    )

    started = await start_zeroconf(hass)
    result = await hass.config_entries.flow.async_configure(
        started["flow_id"],
        {"pin": "000000", "topic_prefix": "tvsitter/salon", "broker": {}},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"pin": "wrong_pin_attempts"}
    assert result["description_placeholders"]["attempts"] == "3"


async def test_an_expired_pin_is_reported_as_itself(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Each refusal has its own message; a generic one would not say what to do."""
    add_mqtt_entry(hass)
    aioclient_mock.post(
        PAIR_URL, status=HTTPStatus.FORBIDDEN, json={"ok": False, "error": "expired"}
    )

    started = await start_zeroconf(hass)
    result = await hass.config_entries.flow.async_configure(
        started["flow_id"],
        {"pin": "927745", "topic_prefix": "tvsitter/salon", "broker": {}},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"pin": "expired"}


async def test_a_refusal_carrying_a_bad_request_status_is_still_read(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """PairingServer sends 400 with a JSON body, and the body says what went wrong."""
    add_mqtt_entry(hass)
    aioclient_mock.post(
        PAIR_URL,
        status=HTTPStatus.BAD_REQUEST,
        json={"ok": False, "error": "bad_request"},
    )

    started = await start_zeroconf(hass)
    result = await hass.config_entries.flow.async_configure(
        started["flow_id"],
        {"pin": "927745", "topic_prefix": "tvsitter/salon", "broker": {}},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"pin": "bad_request"}


async def test_a_tv_that_does_not_answer_is_reported_as_such(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Switched off mid-pairing, or the endpoint already closed."""
    add_mqtt_entry(hass)
    aioclient_mock.post(PAIR_URL, exc=aiohttp.ClientError("nobody home"))

    started = await start_zeroconf(hass)
    result = await hass.config_entries.flow.async_configure(
        started["flow_id"],
        {"pin": "927745", "topic_prefix": "tvsitter/salon", "broker": {}},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"pin": "cannot_connect"}


async def test_something_else_on_that_port_is_not_mistaken_for_a_tv(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A cached mDNS record can point at whatever took the port next."""
    add_mqtt_entry(hass)
    aioclient_mock.post(PAIR_URL, text="<html>hello</html>")

    started = await start_zeroconf(hass)
    result = await hass.config_entries.flow.async_configure(
        started["flow_id"],
        {"pin": "927745", "topic_prefix": "tvsitter/salon", "broker": {}},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"pin": "cannot_connect"}


async def test_pairing_refuses_a_wildcard_prefix_before_sending_anything(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The TV would store it and subscribe to topics that are not its own."""
    add_mqtt_entry(hass)

    started = await start_zeroconf(hass)
    result = await hass.config_entries.flow.async_configure(
        started["flow_id"],
        {"pin": "927745", "topic_prefix": "tvsitter/#", "broker": {}},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"topic_prefix": "invalid_topic_prefix"}
    assert aioclient_mock.mock_calls == []


async def test_pairing_gives_up_when_there_is_no_broker_to_name(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Better to say so than to pair a TV against an address that is not there."""
    started = await start_zeroconf(hass)
    result = await hass.config_entries.flow.async_configure(
        started["flow_id"],
        {"pin": "927745", "topic_prefix": "tvsitter/salon", "broker": {}},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_broker"
    assert aioclient_mock.mock_calls == []
