"""A stand-in for the cloud's GraphQL endpoint that keeps configuration
schedules the way PROTOCOL.md describes them: a created schedule gets an id and
shows up in SCHEDULES, a removed one goes. Every call is recorded, so a test
can check what was asked and in which order."""

from __future__ import annotations

import copy
import itertools
from typing import Any

from custom_components.ferroamp_cloud_control import protocol

# The owner's configuration, as the live query answers it.
NORMAL: dict[str, Any] = {
    "systemMode": "SelfConsumption",
    "systemSettingsPv": {"pvMode": True},
    "systemSettingsGrid": {"aceMode": True, "aceThreshold": 15, "limitImport": False,
                           "limitExport": False, "powerThresholdHigh": 0, "powerThresholdLow": -1000000},
    "systemSettingsBattery": {"powerRefCharge": 100000, "powerRefDischarge": 100000,
                              "socRefLow": 10, "socRefHigh": 100},
}

PEAK: dict[str, Any] = {**NORMAL, "systemMode": "PeakShaving"}

_NAMES = {
    protocol.LIVE: "live",
    protocol.SLOW: "slow",
    protocol.SCHEDULES: "schedules",
    protocol.CREATE_SCHEDULE: "create",
    protocol.REMOVE_SCHEDULE: "remove",
}


def live_raw(*, ferroai: bool = False, config: dict[str, Any] | None = NORMAL) -> dict[str, Any]:
    """The LIVE answer for a facility on OS 7 with the owner's configuration in force."""
    return {"facility": {
        "connectivity": {"isOnline": True, "lastSeenAt": "2026-10-27T20:00:00.000Z"},
        "maintenance": {"ongoingSystemUpgrade": False},
        "measurements": {
            "latestPower": {"timestamp": "2026-10-27T20:00:00.000Z", "batteryPower": 0, "gridPower": 0,
                            "loadPower": 3500, "pvPower": 0, "inverterPower": -3500},
            "currentStateOfCharge": {"stateOfCharge": 54.0, "timestamp": "2026-10-27T20:00:00.000Z"},
        },
        "configuration": {"emsConfiguration": {"current": {
            "generation": "g7", "state": "CURRENT", "config": config}}},
        "optimization": {"enabled": ferroai, "activeAction": None},
    }}


def slow_raw(*, timezone: str = "Europe/Stockholm", new_scheduler: bool = True,
             rated_w: float = 15000) -> dict[str, Any]:
    """The SLOW answer: what the facility is, with no schedules and no energy yet."""
    return {"facility": {
        "id": "12345", "name": "Hus", "timezone": timezone, "info": {"version": "8.0.1"},
        "uiComponents": {"usesNewScheduler": new_scheduler, "ferroAi": {"available": True}, "capacities": [
            {"__typename": "UIEnergyStorageRatedCapacity", "capacity": 27.5, "unit": "kWh"},
            {"__typename": "UIEnergyStorageRatedPowerCapacity", "capacity": rated_w / 1000, "unit": "kW"},
        ]},
        "configuration": {"configurationSchedule": {"schedules": []}},
        "measurements": {"energy": []},
    }}


class CloudSim:
    """Answers the driver's documents. ``create_refusals`` and
    ``remove_refusals`` each take one entry per call: a message refuses that
    call, None lets it through. ``fail`` makes every call raise (cloud down)."""

    def __init__(self, *, live: dict[str, Any] | None = None, slow: dict[str, Any] | None = None) -> None:
        self.live_answer = live if live is not None else live_raw()
        self.slow_answer = slow if slow is not None else slow_raw()
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.schedules: list[dict[str, Any]] = []
        self.create_refusals: list[str | None] = []
        self.remove_refusals: list[str | None] = []
        self.fail: Exception | None = None
        self._ids = itertools.count(1)

    def calls_named(self, name: str) -> list[dict[str, Any]]:
        return [variables for call, variables in self.calls if call == name]

    async def query(self, document: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        variables = copy.deepcopy(variables or {})
        name = _NAMES.get(document, "other")
        self.calls.append((name, variables))
        if self.fail is not None:
            raise self.fail
        if document is protocol.LIVE:
            return copy.deepcopy(self.live_answer)
        if document is protocol.SLOW:
            return copy.deepcopy(self.slow_answer)
        if document is protocol.SCHEDULES:
            return {"facility": {"configuration": {"configurationSchedule": {
                "schedules": copy.deepcopy(self.schedules)}}}}
        if document is protocol.CREATE_SCHEDULE:
            return {"createOneNormalConfigurationSchedule": self._create(variables["data"])}
        if document is protocol.REMOVE_SCHEDULE:
            return {"removeOneNormalConfigurationSchedule": self._remove(variables["id"])}
        raise AssertionError(f"unexpected document: {name}")

    def _create(self, data: dict[str, Any]) -> dict[str, Any]:
        refusal = self.create_refusals.pop(0) if self.create_refusals else None
        if refusal is not None:
            return {"success": False, "schedule": None, "message": refusal, "code": "REFUSED"}
        schedule_id = str(next(self._ids))
        event = data["iCalendarEventJson"]
        self.schedules.append({
            "id": schedule_id,
            "summary": data["summary"],
            "scheduleType": "NORMAL",
            "origin": "USER",
            "isActive": True,
            "appliedAt": None,
            "event": {"iCalendarEventJson": {"start": event["start"], "end": event["end"], "rruleStr": None}},
            "configuration": copy.deepcopy(data["configuration"]["emsConfigurationV1"]),
        })
        return {"success": True, "schedule": {"id": schedule_id}, "message": None, "code": None}

    def _remove(self, schedule_id: str) -> dict[str, Any]:
        refusal = self.remove_refusals.pop(0) if self.remove_refusals else None
        if refusal is not None:
            return {"success": False, "message": refusal, "code": "REFUSED"}
        before = len(self.schedules)
        self.schedules = [s for s in self.schedules if s["id"] != schedule_id]
        removed = len(self.schedules) < before
        return {"success": removed, "message": None if removed else "no such schedule", "code": None}
