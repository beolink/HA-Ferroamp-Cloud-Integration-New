"""The control entities in a real Home Assistant, with the cloud simulated."""

from __future__ import annotations

from unittest.mock import patch

from _cloud_sim import CloudSim, live_raw
from homeassistant.core import HomeAssistant, State
from pytest_homeassistant_custom_component.common import MockConfigEntry, mock_restore_cache

from custom_components.ferroamp_cloud_control.const import CONTROL_PREFIX, DOMAIN, RETURN_SUMMARY

SWITCH = "switch.ferroamp_control_enabled"
SETPOINT = "number.ferroamp_battery_power_setpoint"
LAST_COMMAND = "sensor.ferroamp_last_command"
FOLLOWING = "binary_sensor.ferroamp_following"


async def set_up(hass: HomeAssistant, sim: CloudSim) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", title="Hus", data={
        "facility_id": 12345, "refresh_token": "offline-1", "email": "a@example.com", "prefix": "ferroamp",
    })
    entry.add_to_hass(hass)
    with patch("custom_components.ferroamp_cloud_control.FerroampCloud", return_value=sim):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def call(hass: HomeAssistant, domain: str, service: str, data: dict) -> None:
    await hass.services.async_call(domain, service, data, blocking=True)
    await hass.async_block_till_done()


async def test_switch_and_setpoint_write_the_schedules_and_say_so(hass: HomeAssistant):
    sim = CloudSim()
    await set_up(hass, sim)

    await call(hass, "switch", "turn_on", {"entity_id": SWITCH})
    await call(hass, "number", "set_value", {"entity_id": SETPOINT, "value": 2000})

    assert hass.states.get(SWITCH).state == "on"
    assert float(hass.states.get(SETPOINT).state) == 2000.0
    assert [s["summary"] for s in sim.schedules] == [RETURN_SUMMARY, f"{CONTROL_PREFIX} charge 2000 W"]
    assert hass.states.get(LAST_COMMAND).state == "ack"
    assert hass.states.get(FOLLOWING).state == "on"


async def test_switch_off_hands_the_system_back_at_once(hass: HomeAssistant):
    sim = CloudSim()
    await set_up(hass, sim)
    await call(hass, "switch", "turn_on", {"entity_id": SWITCH})
    await call(hass, "number", "set_value", {"entity_id": SETPOINT, "value": -1500})
    assert [s["summary"] for s in sim.schedules][-1] == f"{CONTROL_PREFIX} discharge 1500 W"

    await call(hass, "switch", "turn_off", {"entity_id": SWITCH})

    assert hass.states.get(SWITCH).state == "off"
    assert [s["summary"] for s in sim.schedules] == [RETURN_SUMMARY]
    assert hass.states.get(LAST_COMMAND).state == "idle"


async def test_a_write_with_switch_off_is_kept_and_sends_nothing(hass: HomeAssistant):
    sim = CloudSim()
    await set_up(hass, sim)

    await call(hass, "number", "set_value", {"entity_id": SETPOINT, "value": 2000})

    assert float(hass.states.get(SETPOINT).state) == 2000.0
    assert sim.schedules == []
    assert hass.states.get(LAST_COMMAND).state == "idle"
    assert hass.states.get(FOLLOWING).state == "unknown"


async def test_ferroai_refuses_and_the_following_sensor_says_why(hass: HomeAssistant):
    sim = CloudSim(live=live_raw(ferroai=True))
    await set_up(hass, sim)

    await call(hass, "switch", "turn_on", {"entity_id": SWITCH})
    await call(hass, "number", "set_value", {"entity_id": SETPOINT, "value": 2000})

    assert sim.schedules == []
    assert hass.states.get(LAST_COMMAND).state == "nak"
    assert hass.states.get(FOLLOWING).state == "off"
    assert "FerroAI" in hass.states.get(FOLLOWING).attributes["last_nak"]


async def test_a_restart_restores_the_switch_and_setpoint_and_writes_nothing(hass: HomeAssistant):
    mock_restore_cache(hass, [State(SWITCH, "on"), State(SETPOINT, "-1500")])
    sim = CloudSim()

    await set_up(hass, sim)

    assert hass.states.get(SWITCH).state == "on"
    assert float(hass.states.get(SETPOINT).state) == -1500.0
    # Nothing is written until EMS writes again: no schedule is created or removed.
    assert [name for name, _ in sim.calls if name in ("create", "remove")] == []


SELECT = "select.ferroamp_mode"
GRID_LIMIT = "number.ferroamp_grid_power_limit"


async def test_mode_idle_hands_the_battery_back_and_the_other_modes_follow_the_setpoint(hass: HomeAssistant):
    sim = CloudSim()
    await set_up(hass, sim)
    assert hass.states.get(SELECT).attributes["options"] == [
        "self_consumption", "peak_shaving", "forced_charge", "forced_discharge", "idle"]
    await call(hass, "switch", "turn_on", {"entity_id": SWITCH})
    await call(hass, "number", "set_value", {"entity_id": SETPOINT, "value": 2000})
    assert sim.schedules[-1]["summary"] == f"{CONTROL_PREFIX} charge 2000 W"

    await call(hass, "select", "select_option", {"entity_id": SELECT, "option": "idle"})

    assert hass.states.get(SELECT).state == "idle"
    assert hass.states.get(LAST_COMMAND).attributes["command"]["action"] == "return"
    assert sim.schedules[-1]["summary"] == RETURN_SUMMARY


async def test_the_grid_power_limit_is_kept_and_nothing_is_sent(hass: HomeAssistant):
    sim = CloudSim()
    await set_up(hass, sim)

    await call(hass, "number", "set_value", {"entity_id": GRID_LIMIT, "value": 5000})

    assert float(hass.states.get(GRID_LIMIT).state) == 5000.0
    assert sim.calls_named("create") == []
