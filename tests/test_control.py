"""The control planner and the controller, against the simulated cloud."""

from __future__ import annotations

import asyncio
import copy
import datetime as dt

from _cloud_sim import NORMAL, PEAK, CloudSim, live_raw, slow_raw

from custom_components.ferroamp_cloud_control import control, protocol
from custom_components.ferroamp_cloud_control.api import CloudError
from custom_components.ferroamp_cloud_control.const import (
    CONTROL_PREFIX,
    MODE_FORCED_CHARGE,
    MODE_IDLE,
    RETURN_SUMMARY,
    WINDOW_S,
)

TZ = "Europe/Stockholm"
NOW = dt.datetime(2026, 10, 27, 20, 0, 20, tzinfo=dt.UTC)     # the next whole minute is 20:01
START = dt.datetime(2026, 10, 27, 20, 1, 0, tzinfo=dt.UTC)
WINDOW = dt.timedelta(seconds=WINDOW_S)
INFO = protocol.parse_slow(slow_raw(), 12345).info
LIVE = protocol.parse_live(live_raw())
LIVE_FERROAI = protocol.parse_live(live_raw(ferroai=True))
LIVE_PEAK = protocol.parse_live(live_raw(config=PEAK))
# A poll during a command of the driver's: the configuration in force is manual.
LIVE_MANUAL = protocol.parse_live(live_raw(config={"systemMode": "Default"}))
NORMAL_INPUT = protocol.config_input(NORMAL)


def raw_schedule(sid: str, summary: str, config: dict = NORMAL, start: dt.datetime = START) -> dict:
    return {
        "id": sid, "summary": summary, "scheduleType": "NORMAL", "origin": "USER", "isActive": True,
        "appliedAt": None,
        "event": {"iCalendarEventJson": {"start": protocol.iso(start),
                                         "end": protocol.iso(start + WINDOW), "rruleStr": None}},
        "configuration": copy.deepcopy(config),
    }


def owned(*raws: dict) -> tuple[protocol.Schedule, ...]:
    return protocol.parse_schedules({"facility": {"configuration": {"configurationSchedule": {
        "schedules": list(raws)}}}})


def controller(sim: CloudSim, *, enabled: bool = True) -> control.Controller:
    ctl = control.Controller(sim, 12345)
    ctl.enabled = enabled
    return ctl


def names(sim: CloudSim) -> list[str]:
    return [name for name, _ in sim.calls]


# ---------------------------------------------------------------- planner


def test_next_start_is_the_first_whole_minute_at_least_the_lead_ahead():
    def at(second: int) -> dt.datetime:
        return dt.datetime(2026, 10, 27, 20, 0, second, tzinfo=dt.UTC)

    assert control.next_start(at(0)) == dt.datetime(2026, 10, 27, 20, 1, tzinfo=dt.UTC)
    assert control.next_start(at(30)) == dt.datetime(2026, 10, 27, 20, 1, tzinfo=dt.UTC)
    assert control.next_start(at(31)) == dt.datetime(2026, 10, 27, 20, 2, tzinfo=dt.UTC)
    assert control.next_start(at(59)) == dt.datetime(2026, 10, 27, 20, 2, tzinfo=dt.UTC)


def test_target_follows_ems_signs_and_never_exceeds_the_rating():
    assert control.target_for(2000, 15000) == control.Target(charge_w=2000, discharge_w=0)
    assert control.target_for(-1500, 15000) == control.Target(charge_w=0, discharge_w=1500)
    assert control.target_for(20000, 15000).charge_w == 15000
    assert control.target_for(-20000, 15000).discharge_w == 15000
    # EMS's hold is a 100 W charge (actuation.EV_HOLD_W).
    assert control.target_for(100, 15000) == control.Target(charge_w=100, discharge_w=0)


def test_a_charge_is_a_manual_schedule_then_a_return_to_the_owners_configuration():
    plan = control.plan_write(2000, now=NOW, start=START, rated_w=15000, timezone=TZ, normal=NORMAL_INPUT, owned=())
    assert [role for role, _ in plan.creates] == ["return", "manual"]
    _, back = plan.creates[0]
    _, manual = plan.creates[1]
    assert manual["summary"] == f"{CONTROL_PREFIX} charge 2000 W"
    assert manual["iCalendarEventJson"]["start"] == protocol.iso(START)
    assert manual["iCalendarEventJson"]["end"] == protocol.iso(START + WINDOW)
    assert manual["iCalendarEventJson"]["timezone"] == TZ
    assert "rrule" not in manual["iCalendarEventJson"]
    assert back["summary"] == RETURN_SUMMARY
    assert back["iCalendarEventJson"]["start"] == protocol.iso(START + WINDOW)
    assert back["configuration"]["emsConfigurationV1"] == NORMAL_INPUT
    config = manual["configuration"]["emsConfigurationV1"]
    assert config["systemMode"] == "Default"
    assert config["systemSettingsBattery"]["powerRefCharge"] == 2000
    assert config["systemSettingsBattery"]["powerRefDischarge"] == 0
    assert config["systemSettingsBattery"]["socRefLow"] == 10 and config["systemSettingsBattery"]["socRefHigh"] == 100
    # PV and phase balancing stay as the owner has them.
    assert config["systemSettingsPv"] == {"pvMode": True}
    assert config["systemSettingsGrid"]["aceMode"] is True
    assert plan.removes == () and plan.target == control.Target(charge_w=2000, discharge_w=0)


def test_a_discharge_is_the_other_reference():
    plan = control.plan_write(-1500, now=NOW, start=START, rated_w=15000, timezone=TZ, normal=NORMAL_INPUT, owned=())
    _, manual = plan.creates[1]
    assert manual["summary"] == f"{CONTROL_PREFIX} discharge 1500 W"
    battery = manual["configuration"]["emsConfigurationV1"]["systemSettingsBattery"]
    assert battery["powerRefDischarge"] == 1500 and battery["powerRefCharge"] == 0


def test_a_write_removes_what_the_previous_one_left_behind():
    old = owned(raw_schedule("7", RETURN_SUMMARY), raw_schedule("8", f"{CONTROL_PREFIX} charge 2000 W"))
    plan = control.plan_write(2000, now=NOW, start=START, rated_w=15000, timezone=TZ, normal=NORMAL_INPUT, owned=old)
    assert plan.removes == ("7", "8")


def test_hand_back_without_schedules_of_ours_writes_nothing():
    plan = control.plan_write(0, now=NOW, start=START, rated_w=15000, timezone=TZ, normal=NORMAL_INPUT, owned=())
    assert plan.creates == () and plan.removes == () and plan.target is None


def test_hand_back_returns_now_and_removes_ours():
    old = owned(raw_schedule("7", f"{CONTROL_PREFIX} charge 2000 W"), raw_schedule("8", RETURN_SUMMARY))
    plan = control.plan_write(0, now=NOW, start=START, rated_w=15000, timezone=TZ, normal=NORMAL_INPUT, owned=old)
    assert [role for role, _ in plan.creates] == ["return"]
    assert plan.creates[0][1]["iCalendarEventJson"]["start"] == protocol.iso(START)
    assert plan.removes == ("7", "8") and plan.target is None


def test_a_setpoint_under_half_a_watt_is_a_hand_back():
    assert control.is_hand_back(0.4) and not control.is_hand_back(0.6)


def test_the_configuration_input_is_refused_when_a_part_is_missing():
    assert protocol.config_input(None) is None
    assert protocol.config_input({"systemMode": "SelfConsumption"}) is None
    assert protocol.config_input(NORMAL) == NORMAL_INPUT


# ---------------------------------------------------------------- controller


def test_switch_off_writes_nothing():
    sim = CloudSim()

    async def go():
        ctl = controller(sim, enabled=False)
        await ctl.write(2000, live=LIVE, info=INFO, now=NOW)
        return ctl

    ctl = asyncio.run(go())
    assert sim.calls == []
    assert ctl.result == "idle" and ctl.setpoint_w == 2000


def test_the_first_write_creates_the_return_then_the_manual_and_is_acknowledged():
    sim = CloudSim()

    async def go():
        ctl = controller(sim)
        await ctl.write(2000, live=LIVE, info=INFO, now=NOW)
        return ctl

    ctl = asyncio.run(go())
    assert names(sim) == ["schedules", "create", "create"]
    assert [v["data"]["summary"] for v in sim.calls_named("create")] == [
        RETURN_SUMMARY, f"{CONTROL_PREFIX} charge 2000 W"]
    assert ctl.result == "ack" and ctl.reason is None
    assert ctl.command["action"] == "charge" and ctl.command["charge_w"] == 2000
    assert ctl.command["window_start"] == protocol.iso(START)
    assert ctl.command["window_end"] == protocol.iso(START + WINDOW)
    assert {s["id"] for s in sim.schedules} == {ctl.command["manual_id"], ctl.command["return_id"]}


def test_a_renewal_creates_the_new_pair_before_it_removes_the_superseded_return():
    sim = CloudSim()

    async def go():
        ctl = controller(sim)
        await ctl.write(2000, live=LIVE, info=INFO, now=NOW)
        await ctl.write(2000, live=LIVE, info=INFO, now=NOW + dt.timedelta(minutes=5))

    asyncio.run(go())
    assert names(sim) == ["schedules", "create", "create", "schedules", "create", "create", "remove"]
    # The manual in force (2) stays until the new one has started; the next write removes it.
    assert [v["id"] for v in sim.calls_named("remove")] == ["1"]
    assert [s["id"] for s in sim.schedules] == ["2", "3", "4"]


def test_a_charge_never_removes_the_schedule_in_force():
    sim = CloudSim()
    sim.schedules = [raw_schedule("9", f"{CONTROL_PREFIX} charge 1000 W", start=NOW - dt.timedelta(minutes=10))]

    async def go():
        ctl = controller(sim)
        await ctl.write(2000, live=LIVE, info=INFO, now=NOW)

    asyncio.run(go())
    assert names(sim) == ["schedules", "create", "create"]
    assert [s["id"] for s in sim.schedules] == ["9", "1", "2"]


def test_a_hand_back_while_the_return_is_in_force_writes_nothing_more():
    sim = CloudSim()
    sim.schedules = [raw_schedule("9", RETURN_SUMMARY, start=NOW - dt.timedelta(hours=1))]

    async def go():
        ctl = controller(sim)
        await ctl.write(0, live=LIVE, info=INFO, now=NOW)
        return ctl

    ctl = asyncio.run(go())
    assert ctl.result == "ack" and names(sim) == ["schedules"]
    assert [s["id"] for s in sim.schedules] == ["9"]


def test_tidy_does_nothing_while_enabled_and_keeps_what_is_in_force_or_not_due():
    sim = CloudSim()

    async def go():
        ctl = controller(sim)
        await ctl.write(2000, live=LIVE, info=INFO, now=NOW)
        await ctl.tidy(NOW + dt.timedelta(minutes=1))
        enabled_calls = len(sim.calls)
        ctl.enabled = False
        await ctl.tidy(NOW + dt.timedelta(minutes=1))
        return enabled_calls

    enabled_calls = asyncio.run(go())
    assert enabled_calls == 3          # nothing read or removed while enabled
    assert names(sim) == ["schedules", "create", "create", "schedules"]
    assert [s["id"] for s in sim.schedules] == ["1", "2"]   # 2 is in force, 1 is not due


def test_the_owners_configuration_seen_in_a_poll_is_the_one_the_return_gives_back():
    sim = CloudSim()

    async def go():
        ctl = controller(sim)
        await ctl.write(-1500, live=LIVE_PEAK, info=INFO, now=NOW)

    asyncio.run(go())
    back = sim.calls_named("create")[0]["data"]["configuration"]["emsConfigurationV1"]
    assert back["systemMode"] == "PeakShaving"


def test_a_manual_configuration_in_a_poll_is_not_taken_for_the_owners():
    sim = CloudSim()

    async def go():
        ctl = controller(sim)
        await ctl.write(2000, live=LIVE_MANUAL, info=INFO, now=NOW)
        return ctl

    ctl = asyncio.run(go())
    assert ctl.result == "nak" and "not known yet" in ctl.reason
    assert names(sim) == ["schedules"]


def test_after_a_restart_the_owners_configuration_comes_from_our_last_return():
    sim = CloudSim()
    sim.schedules = [
        raw_schedule("5", RETURN_SUMMARY, config=PEAK, start=START - WINDOW),
        raw_schedule("6", f"{CONTROL_PREFIX} charge 2000 W", config=NORMAL),
    ]

    async def go():
        ctl = controller(sim)
        await ctl.write(-1500, live=LIVE_MANUAL, info=INFO, now=NOW)

    asyncio.run(go())
    back = sim.calls_named("create")[0]["data"]["configuration"]["emsConfigurationV1"]
    assert back["systemMode"] == "PeakShaving"
    # The return started at 19:51 and is the one in force, so it stays; the command not yet due goes.
    assert [v["id"] for v in sim.calls_named("remove")] == ["6"]


def test_without_any_configuration_known_the_write_is_refused():
    sim = CloudSim()

    async def go():
        ctl = controller(sim)
        await ctl.write(2000, live=LIVE_MANUAL, info=INFO, now=NOW)
        return ctl

    ctl = asyncio.run(go())
    assert ctl.result == "nak" and "not known yet" in ctl.reason
    assert names(sim) == ["schedules"]


def test_ferroai_on_refuses_the_write_and_writes_no_schedule():
    sim = CloudSim(live=live_raw(ferroai=True))

    async def go():
        ctl = controller(sim)
        await ctl.write(2000, live=LIVE_FERROAI, info=INFO, now=NOW)
        return ctl

    ctl = asyncio.run(go())
    assert ctl.result == "nak" and "FerroAI" in ctl.reason
    assert names(sim) == ["schedules"] and sim.schedules == []


def test_a_hand_back_with_nothing_of_ours_is_no_write_even_under_ferroai():
    sim = CloudSim(live=live_raw(ferroai=True))

    async def go():
        ctl = controller(sim)
        await ctl.write(0, live=LIVE_FERROAI, info=INFO, now=NOW)
        return ctl

    ctl = asyncio.run(go())
    assert ctl.result == "ack" and names(sim) == ["schedules"]


def test_a_system_without_configuration_schedules_is_refused():
    sim = CloudSim(slow=slow_raw(new_scheduler=False))

    async def go():
        ctl = controller(sim)
        await ctl.write(2000, live=LIVE, info=protocol.parse_slow(slow_raw(new_scheduler=False), 1).info, now=NOW)
        return ctl

    ctl = asyncio.run(go())
    assert ctl.result == "nak" and "OS 7" in ctl.reason
    assert names(sim) == ["schedules"] and sim.schedules == []


def test_a_refused_return_leaves_nothing_behind():
    sim = CloudSim()
    sim.create_refusals = ["Schedule overlaps a fixed slot"]

    async def go():
        ctl = controller(sim)
        await ctl.write(2000, live=LIVE, info=INFO, now=NOW)
        return ctl

    ctl = asyncio.run(go())
    assert ctl.result == "nak" and ctl.reason == "Schedule overlaps a fixed slot"
    assert names(sim) == ["schedules", "create"] and sim.schedules == []


def test_a_refused_manual_leaves_the_return_for_the_next_write_to_remove():
    sim = CloudSim()
    sim.create_refusals = [None, "refused"]

    async def go():
        ctl = controller(sim)
        await ctl.write(2000, live=LIVE, info=INFO, now=NOW)
        first = ctl.result
        sim.create_refusals = []
        await ctl.write(2000, live=LIVE, info=INFO, now=NOW + dt.timedelta(minutes=5))
        return first, ctl.result

    first, second = asyncio.run(go())
    assert first == "nak" and second == "ack"
    assert [v["id"] for v in sim.calls_named("remove")] == ["1"]
    assert len(sim.schedules) == 2


def test_a_failed_removal_is_a_nak_and_the_next_write_removes_it():
    sim = CloudSim()

    async def go():
        ctl = controller(sim)
        await ctl.write(2000, live=LIVE, info=INFO, now=NOW)
        sim.remove_refusals = ["busy"]
        await ctl.write(2000, live=LIVE, info=INFO, now=NOW + dt.timedelta(minutes=5))
        failed = (ctl.result, ctl.reason, ctl.command.get("manual_id"))
        sim.remove_refusals = []
        await ctl.write(2000, live=LIVE, info=INFO, now=NOW + dt.timedelta(minutes=10))
        return failed, ctl.result

    (result, reason, manual_id), again = asyncio.run(go())
    assert result == "nak" and reason.startswith("1 earlier schedule(s) could not be removed")
    assert manual_id is not None
    assert again == "ack"
    # 4 is the manual in force at the third write; the pair from the third write stays with it.
    assert [s["id"] for s in sim.schedules] == ["4", "5", "6"]


def test_the_cloud_being_down_is_a_nak_with_the_reason():
    sim = CloudSim()
    sim.fail = CloudError("unreachable")

    async def go():
        ctl = controller(sim)
        await ctl.write(2000, live=LIVE, info=INFO, now=NOW)
        return ctl

    ctl = asyncio.run(go())
    assert ctl.result == "nak" and ctl.reason.startswith("the cloud did not answer")


def test_renewal_is_due_five_minutes_after_the_last_write_while_a_command_stands():
    sim = CloudSim()

    async def go():
        ctl = controller(sim)
        await ctl.write(2000, live=LIVE, info=INFO, now=NOW)
        due = (ctl.renewal_due(NOW + dt.timedelta(seconds=299)), ctl.renewal_due(NOW + dt.timedelta(seconds=300)))
        await ctl.write(0, live=LIVE, info=INFO, now=NOW + dt.timedelta(minutes=6))
        after_hand_back = ctl.renewal_due(NOW + dt.timedelta(minutes=20))
        return due, after_hand_back

    due, after_hand_back = asyncio.run(go())
    assert due == (False, True)
    assert after_hand_back is False


def test_switch_off_hands_the_system_back_at_once_when_a_command_stands():
    sim = CloudSim()

    async def go():
        ctl = controller(sim)
        await ctl.write(2000, live=LIVE, info=INFO, now=NOW)
        ctl.enabled = False
        await ctl.release(live=LIVE, info=INFO, now=NOW + dt.timedelta(minutes=2))
        after_release = [s["summary"] for s in sim.schedules]
        await ctl.tidy(NOW + dt.timedelta(minutes=11))     # the return has started by now
        return ctl, after_release

    ctl, after_release = asyncio.run(go())
    assert ctl.result == "idle" and ctl.reason.startswith("control is off; the owner's configuration is back")
    assert after_release == [f"{CONTROL_PREFIX} charge 2000 W", RETURN_SUMMARY]
    assert [s["summary"] for s in sim.schedules] == [RETURN_SUMMARY]
    assert ctl.command["action"] == "return"


def test_switch_off_without_a_command_of_ours_writes_nothing():
    sim = CloudSim()

    async def go():
        ctl = controller(sim, enabled=False)
        await ctl.release(live=LIVE, info=INFO, now=NOW)
        return ctl

    ctl = asyncio.run(go())
    assert ctl.result == "idle" and names(sim) == ["schedules"]


def test_as_dict_says_what_the_driver_last_did():
    sim = CloudSim()

    async def go():
        ctl = controller(sim)
        await ctl.write(2000, live=LIVE, info=INFO, now=NOW)
        return ctl.as_dict()

    state = asyncio.run(go())
    assert state["result"] == "ack" and state["setpoint_w"] == 2000 and state["enabled"] is True
    assert state["command"]["action"] == "charge"


# ---------------------------------------------------------------- modes (select.{prefix}_mode)


def test_idle_hands_the_battery_back_whatever_the_setpoint():
    sim = CloudSim()
    sim.schedules = [raw_schedule("9", f"{CONTROL_PREFIX} charge 2000 W", start=NOW - dt.timedelta(minutes=5))]

    async def go():
        ctl = controller(sim)
        ctl.mode = MODE_IDLE
        await ctl.write(2000, live=LIVE, info=INFO, now=NOW)
        return ctl

    ctl = asyncio.run(go())
    assert [v["data"]["summary"] for v in sim.calls_named("create")] == [RETURN_SUMMARY]
    assert ctl.result == "ack" and ctl.command["action"] == "return"
    assert sim.schedules[0]["id"] == "9"    # the charge in force stays until the return starts


def test_the_other_modes_follow_the_setpoint_as_in_the_mqtt_driver():
    sim = CloudSim()

    async def go():
        ctl = controller(sim)
        ctl.mode = MODE_FORCED_CHARGE
        await ctl.write(-1500, live=LIVE, info=INFO, now=NOW)

    asyncio.run(go())
    assert [v["data"]["summary"] for v in sim.calls_named("create")] == [
        RETURN_SUMMARY, f"{CONTROL_PREFIX} discharge 1500 W"]


def test_renewal_stops_while_idle():
    sim = CloudSim()

    async def go():
        ctl = controller(sim)
        ctl.mode = MODE_IDLE
        await ctl.write(2000, live=LIVE, info=INFO, now=NOW)
        return ctl.renewal_due(NOW + dt.timedelta(minutes=6))

    assert asyncio.run(go()) is False


def test_the_grid_power_limit_is_reported_and_never_sent():
    sim = CloudSim()

    async def go():
        ctl = controller(sim)
        ctl.grid_limit_w = 5000.0
        return ctl.as_dict()

    state = asyncio.run(go())
    assert state["grid_limit_w"] == 5000.0 and state["mode"] == "self_consumption"
    assert sim.calls == []
