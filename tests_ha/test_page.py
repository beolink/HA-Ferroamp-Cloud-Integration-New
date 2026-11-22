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
