"""The system information: parsing what the cloud answers about the system."""

from __future__ import annotations

import copy
import datetime as dt

from custom_components.ferroamp_cloud_control import system
from _cloud_sim import GRID_ANSWER, PHASE_BALANCE_EVENT, SYSTEM_ANSWERS


def answers(**changes):
    found = copy.deepcopy(SYSTEM_ANSWERS)
    found.update(changes)
    return found


def test_the_software_is_the_systems_version_and_the_latest_update():
    info = system.parse_system(answers())
    assert info.software == system.Software(
        version="8.0.1", controller_version="8.0.1", controller_generation="CORE",
        last_update_from="8.0.0", last_update_to="8.0.1",
        last_update_at=dt.datetime(2026, 10, 24, 9, 0, tzinfo=dt.UTC),
        hostname="eh-12345",
    )


def test_state_lifecycle_and_topology():
    info = system.parse_system(answers())
    assert info.state == "RUNNING"
    assert info.state_since == dt.datetime(2026, 11, 22, 18, 56, 40, tzinfo=dt.UTC)
    assert info.lifecycle == "ACTIVE"
    assert info.main_fuse_a == 20 and info.phases == "Three"
    assert info.inverter_ratings_w == (14000,)
    assert info.eso_generations == ("ESO15",)


def test_only_active_alarms_count():
    info = system.parse_system(answers())
    assert [(a.code, a.product_id) for a in info.alarms] == [("SSO_OFFLINE", "SSO2")]
    assert info.alarms[0].as_dict()["since"] == "2026-11-22T10:00:00+00:00"


def test_batteries_carry_health_cells_and_their_state():
    info = system.parse_system(answers())
    (battery,) = info.batteries
    assert battery.manufacturer == "Pylontech"
    assert battery.rated_capacity_kwh == 27.5
    assert battery.state == "RUNNING" and battery.reasons == ("BAT_SOC_POWER_DERATING",)
    assert (battery.soh, battery.voltage_v, battery.current_a) == (98, 480.2, -2.1)
    assert (battery.cell_voltage_min_v, battery.cell_voltage_max_v) == (3.31, 3.34)
    assert system.battery_health(info) == 98
    assert system.cell_temperature(info, highest=True) == 21
    assert system.cell_temperature(info, highest=False) == 17


def test_the_worst_battery_state_wins():
    second = copy.deepcopy(SYSTEM_ANSWERS["batteries"]["facility"]["batteries"][0])
    second["productId"] = "B2"
    second["state"]["current"]["primary"] = "DEGRADED"
    second["log"]["current"]["stateOfHealth"] = 91
    found = answers()
    found["batteries"]["facility"]["batteries"].append(second)
    info = system.parse_system(found)
    assert system.battery_state(info) == "DEGRADED"
    assert system.battery_health(info) == 91


def test_strings_get_a_name_even_without_one():
    info = system.parse_system(answers())
    assert [s.name for s in info.strings] == ["Söder", "SSO 2"]
    assert system.strings_running(info) == 1
    assert info.strings[1].as_dict()["state"] == "OFFLINE"


def test_a_part_that_did_not_answer_leaves_its_values_empty():
    info = system.parse_system({"basics": SYSTEM_ANSWERS["basics"], "alarms": None,
                                "batteries": None, "strings": None, "topology": None})
    assert info.software is not None
    assert info.alarms is None and info.batteries is None and info.strings is None
    assert info.main_fuse_a is None and info.inverter_ratings_w == ()
    assert system.battery_health(info) is None and system.battery_state(info) is None
    assert system.strings_running(info) is None
    assert set(info.raw) == {"basics"}


def test_an_empty_answer_is_no_system_information():
    info = system.parse_system({})
    assert info == system.SystemInfo()


def test_the_grid_per_phase():
    grid = system.parse_grid(GRID_ANSWER)
    assert grid.voltage_v == (231.2, 229.8, 232.4)
    assert grid.current_a == (5.1, 3.9, 7.4)
    assert grid.ace_active is False
    assert grid.measured_at == dt.datetime(2026, 10, 27, 20, 0, tzinfo=dt.UTC)
    assert system.parse_grid(None) is None
    assert system.parse_grid({"facility": {"measurements": {"latestGridData": None}}}) is None


def test_power_per_phase_takes_the_set_that_adds_up_to_the_total():
    grid = system.parse_grid(GRID_ANSWER)
    assert grid.grid_power_w == (26.95, 313.34, 236.52)
    assert grid.load_power_w == (65.27, 348.78, 269.64)
    assert grid.power_measured_at == dt.datetime(2026, 10, 27, 20, 0, tzinfo=dt.UTC)
    # Should a system's D set be the one that adds up, that one is taken.
    swapped = copy.deepcopy(GRID_ANSWER)
    power = swapped["facility"]["measurements"]["latestPower"]
    for n in (1, 2, 3):
        power[f"pExtD{n}"], power[f"pExtQ{n}"] = power[f"pExtQ{n}"], power[f"pExtD{n}"]
    assert system.parse_grid(swapped).grid_power_w == (26.95, 313.34, 236.52)
    # Without a total to check against, the Q set.
    power["gridPower"] = None
    assert system.parse_grid(swapped).grid_power_w == (1.2, 0.4, 0.5)


def test_phase_balancing_per_phase():
    grid = system.parse_grid(GRID_ANSWER)
    assert grid.ace_correction_a == (0.0, 0.0, 0.0)
    assert grid.ace_before_a == (5.1, 3.9, 7.4)


def test_the_grid_with_only_one_half_answered():
    only_power = {"facility": {"measurements": {"latestGridData": None,
                                                "latestPower": GRID_ANSWER["facility"]["measurements"]["latestPower"]}}}
    grid = system.parse_grid(only_power)
    assert grid.voltage_v == (None, None, None) and grid.grid_power_w[0] == 26.95


def test_ferroai_settings_and_outside_services():
    info = system.parse_system(answers())
    opt = info.optimization
    assert opt.variant == "SPOT_PRICE_OPTIMIZATION_V1" and opt.tariff_option == "NO_TARIFF"
    assert opt.limit_import_threshold == 11000 and opt.bidding_zone == "SE3"
    assert info.active_services == ()
    assert system.service_name("RemoteApi") == "remote_api"
    assert system.service_name("AncillaryService") == "ancillary_service"


def test_spot_prices_in_order_with_their_currency():
    prices = system.parse_system(answers()).prices
    assert prices.currency == "SEK" and prices.current.price == 0.84
    assert [p.price for p in prices.periods] == [0.84, 0.91]


def test_the_forecast_point_for_now():
    info = system.parse_system(answers())
    assert [p.soc for p in info.forecast] == [54, 50]
    at = dt.datetime(2026, 10, 27, 15, 35, tzinfo=dt.UTC)
    assert system.forecast_now(info, at).soc == 54
    assert system.forecast_now(info, at - dt.timedelta(hours=2)).soc == 54   # nothing before: the first ahead
    assert system.forecast_now(info, at + dt.timedelta(hours=2)).soc == 50
    assert system.forecast_now(system.SystemInfo(), at) is None


def test_part_variables():
    from zoneinfo import ZoneInfo
    now = dt.datetime(2026, 11, 22, 23, 10, tzinfo=ZoneInfo("Europe/Stockholm"))
    assert system.part_variables("basics", 7, now) == {"id": 7}
    assert system.part_variables("prices", 7, now)["period"] == {"day": {"gte": "2026-11-22", "lte": "2026-11-23"}}
    assert system.part_variables("forecast", 7, now)["range"] == {
        "gte": "2026-11-22T22:00:00.000Z", "lt": "2026-11-24T10:00:00.000Z"}


def test_the_basics_come_from_their_own_parts():
    # The state and the control computer refused, as the account may not read
    # them: the version and the host name still come from the basics.
    info = system.parse_system(answers(state={"facility": None}, controller={"facility": None}))
    assert info.software.version == "8.0.1" and info.software.controller_version is None
    assert info.state is None and info.lifecycle == "ACTIVE"
    # Only the control computer: its version, no system version.
    only = system.parse_system({"controller": SYSTEM_ANSWERS["controller"]})
    assert only.software.version is None and only.software.controller_version == "8.0.1"


def test_cell_values_are_rounded_to_what_they_are():
    found = answers()
    log = found["batteries"]["facility"]["batteries"][0]["log"]["current"]
    log["cellTemperatureMin"], log["cellVoltageMax"] = 6.400001525878906, 3.289000272750854
    (battery,) = system.parse_system(found).batteries
    assert battery.cell_temp_min_c == 6.4 and battery.cell_voltage_max_v == 3.289


def test_no_strings_is_unknown_not_none_running():
    info = system.parse_system(answers(strings={"facility": {"ssos": []}}))
    assert info.strings == () and system.strings_running(info) is None


def test_the_phase_balance_stream_fills_in_the_grid():
    received = dt.datetime(2026, 10, 27, 20, 0, 6, tzinfo=dt.UTC)
    empty_grid = system.parse_grid({"facility": {"measurements": {
        "latestGridData": None, "latestPower": GRID_ANSWER["facility"]["measurements"]["latestPower"]}}})
    assert empty_grid.measured_at is None
    grid = system.with_phase_balance(empty_grid, PHASE_BALANCE_EVENT, received)
    assert grid.voltage_v == (230.1, 231.4, 229.7)
    assert grid.current_a == (6.2, 6.0, 6.1)
    assert grid.ace_correction_a == (-1.8, 1.9, -0.1) and grid.ace_active is True
    assert grid.measured_at == dt.datetime(2026, 10, 27, 20, 0, 5, tzinfo=dt.UTC)
    assert grid.grid_power_w == (26.95, 313.34, 236.52)   # the power per phase stays
    # No grid read at all, and an event without a time: the time it came.
    event = {"newPhaseBalanceData": {**PHASE_BALANCE_EVENT["newPhaseBalanceData"], "timestamp": None}}
    assert system.with_phase_balance(None, event, received).measured_at == received
    # An empty event changes nothing.
    assert system.with_phase_balance(empty_grid, {"newPhaseBalanceData": None}, received) is empty_grid
