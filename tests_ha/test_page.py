"""The Ferroamp page in a real Home Assistant, with the cloud simulated."""

from __future__ import annotations

from unittest.mock import patch

from _cloud_sim import CloudSim
from homeassistant.components import frontend
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ferroamp_cloud_control import page_views as views
from custom_components.ferroamp_cloud_control.const import DOMAIN


async def set_up(hass: HomeAssistant) -> MockConfigEntry:
    assert await async_setup_component(hass, "lovelace", {})
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", title="Hus", data={
        "facility_id": 12345, "refresh_token": "offline-1", "email": "a@example.com", "prefix": "ferroamp",
    })
    entry.add_to_hass(hass)
    with patch("custom_components.ferroamp_cloud_control.FerroampCloud", return_value=CloudSim()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_the_page_is_in_the_sidebar_and_built_from_the_entities(hass: HomeAssistant, hass_ws_client):
    await set_up(hass)
    assert views.URL_PATH in hass.data[frontend.DATA_PANELS]

    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "lovelace/config", "url_path": views.URL_PATH})
    answer = await client.receive_json()
    assert answer["success"], answer
    config = answer["result"]
    assert [v["path"] for v in config["views"]] == ["overview", "control", "system"]
    rows = [item for view in config["views"] for card in view["cards"] for item in card.get("items", [])]
    entities = {item["entity"] for item in rows}
    assert {"sensor.ferroamp_battery_power", "switch.ferroamp_control_enabled",
            "number.ferroamp_battery_power_setpoint", "sensor.ferroamp_system_mode"} <= entities
    assert all(item["explanation"] for item in rows)


async def test_unloading_the_last_system_takes_the_page_away(hass: HomeAssistant):
    entry = await set_up(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert views.URL_PATH not in hass.data[frontend.DATA_PANELS]


async def test_the_card_is_served(hass: HomeAssistant, hass_client):
    await set_up(hass)
    client = await hass_client()
    resp = await client.get("/ferroamp_cloud_control/ferroamp-cloud-card.js")
    assert resp.status == 200
    assert "ferroamp-cloud-rows" in await resp.text()


def card_urls(hass: HomeAssistant) -> set[str]:
    return {url for url in hass.data[frontend.DATA_EXTRA_MODULE_URL].urls if "ferroamp-cloud-card" in url}


async def test_a_system_set_not_to_show_the_page_leaves_the_sidebar_alone(hass: HomeAssistant):
    assert await async_setup_component(hass, "lovelace", {})
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", title="Hus", data={
        "facility_id": 12345, "refresh_token": "offline-1", "email": "a@example.com", "prefix": "ferroamp",
    }, options={"show_page": False})
    entry.add_to_hass(hass)
    with patch("custom_components.ferroamp_cloud_control.FerroampCloud", return_value=CloudSim()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert views.URL_PATH not in hass.data[frontend.DATA_PANELS]
    assert card_urls(hass) == set()


async def test_the_options_hide_and_show_the_page(hass: HomeAssistant):
    entry = await set_up(hass)
    with patch("custom_components.ferroamp_cloud_control.FerroampCloud", return_value=CloudSim()):
        for show in (False, True):
            result = await hass.config_entries.options.async_init(entry.entry_id)
            assert result["type"] == "menu" and result["menu_options"] == ["settings", "rebuild_page"]
            result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "settings"})
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"scan_interval": 30, "show_page": show})
            assert result["type"] == "create_entry"
            await hass.async_block_till_done()
            assert (views.URL_PATH in hass.data[frontend.DATA_PANELS]) is show
    assert entry.options["show_page"] is True


async def test_rebuilding_puts_the_page_back_with_a_new_card_address(hass: HomeAssistant):
    await set_up(hass)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    before = card_urls(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "rebuild_page"})
    assert result["type"] == "form" and result["step_id"] == "rebuild_page"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] == "abort" and result["reason"] == "page_rebuilt"
    assert views.URL_PATH in hass.data[frontend.DATA_PANELS]
    after = card_urls(hass)
    assert len(after) == 1 and after != before
