"""Config flow, set-up and sensors in a real Home Assistant, cloud faked."""

from __future__ import annotations

import copy
import datetime as dt
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.ferroamp_cloud_control import api, protocol
from custom_components.ferroamp_cloud_control.const import DOMAIN

NOW = dt.datetime(2026, 10, 27, 15, 35, 0, tzinfo=dt.UTC)


def live(battery=3570, grid=120, at="2026-10-27T15:34:30.000Z"):
    return {"facility": {
        "connectivity": {"isOnline": True, "lastSeenAt": "2026-10-27T15:34:45.000Z"},
        "maintenance": {"ongoingSystemUpgrade": False},
        "measurements": {
            "latestPower": {"timestamp": at, "batteryPower": battery, "gridPower": grid,
                            "loadPower": 3500, "pvPower": 0, "inverterPower": -3500},
            "currentStateOfCharge": {"stateOfCharge": 54.0, "timestamp": at},
        },
        "configuration": {"emsConfiguration": {"current": {
            "generation": "g7", "state": "CURRENT",
            "config": {"systemMode": "SelfConsumption",
                       "systemSettingsPv": {"pvMode": True},
                       "systemSettingsGrid": {"aceMode": True, "aceThreshold": 15},
                       "systemSettingsBattery": {"powerRefCharge": 100000, "powerRefDischarge": 100000,
                                                 "socRefLow": 10, "socRefHigh": 100}}}}},
        "optimization": {"enabled": False, "activeAction": None},
    }}


SLOW = {"facility": {
    "id": "12345", "name": "Hus", "timezone": "Europe/Stockholm", "info": {"version": "8.0.1"},
    "uiComponents": {"usesNewScheduler": True, "ferroAi": {"available": True}, "capacities": [
        {"__typename": "UIEnergyStorageRatedCapacity", "capacity": 27.5, "unit": "kWh"},
        {"__typename": "UIEnergyStorageRatedPowerCapacity", "capacity": 15, "unit": "kW"},
    ]},
    "configuration": {"configurationSchedule": {"schedules": [
        {"id": "s1", "summary": "Self-consumption", "scheduleType": "NORMAL", "origin": "USER",
         "isActive": True, "configuration": {"systemMode": "SelfConsumption"},
         "event": {"iCalendarEventJson": {"start": "2026-10-18T12:30:00.000Z",
                                          "end": "2026-10-18T21:00:00.000Z", "rruleStr": "RRULE:FREQ=DAILY"}}},
    ]}},
    "measurements": {"energy": [
        {"pvProduced": 0.0, "consumption": 4000.0, "gridImport": 2500.0, "gridExport": 0.0,
         "batteryCharged": 0.0, "batteryDischarged": 1500.0},
    ]},
}}

FACILITIES = {"facilities": [{"id": "12345", "name": "Hus", "myRelation": {"relation": "FACILITY_ADMIN"},
                              "uiComponents": {"usesNewScheduler": True}, "info": {"version": "8.0.1"}}]}


class FakeCloud:
    """Stands in for api.FerroampCloud: answers by document."""

    def __init__(self, session, refresh_token, on_refresh_token=None, **_):
        self.refresh_token = refresh_token
        self.on_refresh_token = on_refresh_token
        FakeCloud.instance = self

    live_answer = live()
    fail_with: Exception | None = None
    rotate_to: str | None = None

    async def query(self, document, variables=None):
        if FakeCloud.fail_with is not None:
            raise FakeCloud.fail_with
        if FakeCloud.rotate_to and self.on_refresh_token:
            self.refresh_token = FakeCloud.rotate_to
            self.on_refresh_token(FakeCloud.rotate_to)
            FakeCloud.rotate_to = None
        if document is protocol.FACILITIES:
            return copy.deepcopy(FACILITIES)
        if document is protocol.LIVE:
            return copy.deepcopy(FakeCloud.live_answer)
        if document is protocol.SLOW:
            return copy.deepcopy(SLOW)
        if document is protocol.SCHEDULES:
            return {"facility": {"configuration": {"configurationSchedule": {"schedules": []}}}}
        raise AssertionError("unexpected document")


@pytest.fixture(autouse=True)
def fake_cloud(freezer):
    freezer.move_to(NOW)
    FakeCloud.live_answer = live()
    FakeCloud.fail_with = None
    FakeCloud.rotate_to = None
    with patch("custom_components.ferroamp_cloud_control.FerroampCloud", FakeCloud), \
         patch("custom_components.ferroamp_cloud_control.config_flow.FerroampCloud", FakeCloud):
        yield


def entry_for(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", title="Hus", data={
        "facility_id": 12345, "refresh_token": "offline-1", "email": "a@example.com", "prefix": "ferroamp",
    })
    entry.add_to_hass(hass)
    return entry


async def test_config_flow_keeps_the_token_never_the_password(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    with patch("custom_components.ferroamp_cloud_control.config_flow.login",
               return_value={"refresh_token": "offline-1", "access_token": "a"}):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {
            "email": "a@example.com", "password": "secret", "prefix": "ferroamp"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hus"
    assert result["data"] == {"facility_id": 12345, "refresh_token": "offline-1",
                              "email": "a@example.com", "prefix": "ferroamp"}
    assert "secret" not in str(result["data"])
    await hass.async_block_till_done()


async def test_config_flow_wrong_password(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    with patch("custom_components.ferroamp_cloud_control.config_flow.login",
               side_effect=api.AuthError("Invalid username or password.")):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {
            "email": "a@example.com", "password": "wrong", "prefix": "ferroamp"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_sensors_under_the_ems_names_in_ferroamps_signs(hass: HomeAssistant):
    entry = entry_for(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    def state(entity_id):
        st = hass.states.get(entity_id)
        assert st is not None, entity_id
        return st

    assert state("sensor.ferroamp_soc").state == "54.0"
    battery = state("sensor.ferroamp_battery_power")
    assert battery.state == "3570.0" and battery.attributes["unit_of_measurement"] == "W"
    assert state("sensor.ferroamp_grid_power").state == "120.0"
    assert state("sensor.ferroamp_consumption_power").state == "3500.0"
    assert state("sensor.ferroamp_solar_power").state == "0.0"
    assert state("sensor.ferroamp_battery_capacity").state == "27.5"
    assert state("sensor.ferroamp_max_charge_power").state == "15000.0"
    assert state("sensor.ferroamp_grid_import_energy_today").state == "2.5"
    assert state("sensor.ferroamp_battery_discharged_energy_today").state == "1.5"
    assert state("sensor.ferroamp_system_mode").state == "self_consumption"
    assert state("sensor.ferroamp_active_schedule").state == "Self-consumption"
    assert state("binary_sensor.ferroamp_online").state == "on"
    assert state("binary_sensor.ferroamp_ferroai").state == "off"


async def test_stale_power_goes_unavailable(hass: HomeAssistant, freezer):
    entry = entry_for(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.ferroamp_battery_power").state == "3570.0"

    freezer.move_to(NOW + dt.timedelta(minutes=11))       # no new sample from the cloud
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass.states.get("sensor.ferroamp_battery_power").state == "unavailable"
    assert hass.states.get("sensor.ferroamp_soc").state == "54.0"   # SoC is not a power sample


async def test_rotated_token_is_stored_without_a_reload(hass: HomeAssistant, freezer):
    entry = entry_for(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    FakeCloud.rotate_to = "offline-2"
    with patch.object(hass.config_entries, "async_reload") as reload:
        freezer.move_to(NOW + dt.timedelta(seconds=31))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
    assert entry.data["refresh_token"] == "offline-2"
    reload.assert_not_called()


async def test_a_refused_token_starts_reauth(hass: HomeAssistant, freezer):
    entry = entry_for(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    FakeCloud.fail_with = api.AuthError("Offline session not active")
    freezer.move_to(NOW + dt.timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == config_entries.SOURCE_REAUTH for f in flows)


async def test_cloud_down_at_start_retries(hass: HomeAssistant):
    FakeCloud.fail_with = api.CloudError("unreachable")
    entry = entry_for(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY
