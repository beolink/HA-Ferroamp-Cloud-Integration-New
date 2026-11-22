"""A stand-in for the cloud's GraphQL endpoint that keeps configuration
schedules the way PROTOCOL.md describes them: a created schedule gets an id and
shows up in SCHEDULES, a removed one goes. Every call is recorded, so a test
can check what was asked and in which order."""

from __future__ import annotations

import copy
import itertools
from typing import Any

from custom_components.ferroamp_cloud_control import protocol, system

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


# The system information's parts, shaped as the schema has them (system.py).
SYSTEM_ANSWERS: dict[str, dict[str, Any]] = {
    "basics": {"facility": {
        "hostname": "eh-12345", "installedOn": "2026-10-15T00:00:00.000Z",
        "info": {"version": "8.0.1"}, "capacity": {"installedPv": None},
    }},
    "lifecycle": {"facility": {
        "lifeCycle": {"current": {"stage": "ACTIVE", "updatedAt": "2026-10-15T14:38:44.561Z"}},
    }},
    "state": {"facility": {
        "systemState": {"active": {"state": "RUNNING", "createdAt": "2026-11-22T18:56:40.000Z",
                                   "updatedAt": None}},
    }},
    "controller": {"facility": {
        "singleBoardComputer": {"productId": "SBC1", "generation": "CORE", "version": "8.0.1",
                                "lastSeenAt": "2026-11-22T19:00:00.000Z", "versionChangeLog": [
                                    {"fromVersion": "7.1.2", "toVersion": "8.0.0", "updatedAt": "2026-10-19T09:00:00.000Z"},
                                    {"fromVersion": "8.0.0", "toVersion": "8.0.1", "updatedAt": "2026-10-24T09:00:00.000Z"},
                                ]},
    }},
    "topology": {"facility": {"topology": {
        "system": {"mainFuse": 20, "phases": "Three", "aceThreshold": 15,
                   "powerRatingPositive": 14000, "powerRatingNegative": 14000},
        "inverters": [{"id": "INV1", "enabled": True, "attributes": {"powerRating": 14000, "currentRating": 20}}],
        "batteries": [{"id": "B1", "enabled": True, "manufacturer": "Pylontech",
                       "attributes": {"capactyRating": 27.5, "powerRating": 15000, "socLimitLow": 10,
                                      "socLimitHigh": 100},
                       "esos": [{"id": "ESO1", "generation": "ESO15", "enabled": True}]}],
    }}},
    "alarms": {"facility": {"alarm": {"entries": [
        {"code": "SSO_OFFLINE", "status": "ACTIVE", "productId": "SSO2",
         "activatedAt": "2026-11-22T10:00:00.000Z", "updatedAt": "2026-11-22T10:00:00.000Z"},
        {"code": "SYSTEM_OFFLINE", "status": "INACTIVE", "productId": "SBC1",
         "activatedAt": "2026-11-01T10:00:00.000Z", "updatedAt": "2026-11-01T11:00:00.000Z"},
    ]}}},
    "batteries": {"facility": {"batteries": [
        {"productId": "B1", "manufacturer": "Pylontech",
         "attributes": {"ratedCapacity": 27500, "ratedPower": 15000},
         "state": {"current": {"primary": "RUNNING", "secondary": ["BAT_SOC_POWER_DERATING"],
                               "updatedAt": "2026-11-22T19:00:00.000Z"}},
         "log": {"current": {"stateOfCharge": 57, "stateOfHealth": 98, "batteryVoltage": 480.2,
                             "batteryCurrent": -2.1, "cellTemperatureMin": 17, "cellTemperatureMax": 21,
                             "cellVoltageMin": 3.31, "cellVoltageMax": 3.34,
                             "updatedAt": "2026-11-22T19:00:00.000Z"}}},
    ]}},
    "strings": {"facility": {"ssos": [
        {"id": "SSO1", "displayName": "Söder", "enabled": True, "generation": "SSO8",
         "attributes": {"powerRating": 4500}, "state": {"active": {
             "primary": "RUNNING", "secondary": [], "updatedAt": "2026-11-22T08:00:00.000Z"}}},
        {"id": "SSO2", "displayName": None, "enabled": True, "generation": "SSO8",
         "attributes": {"powerRating": 4500}, "state": {"active": {
             "primary": "OFFLINE", "secondary": [], "updatedAt": "2026-11-22T10:00:00.000Z"}}},
    ]}},
    "optimization": {"facility": {
        "optimization": {"activatedAt": "2026-05-01T10:00:00.000Z", "enabled": False,
                         "limitExportThreshold": 0, "limitImportThreshold": 11000, "minimumEarnings": 0.2,
                         "optimizationVariant": "SPOT_PRICE_OPTIMIZATION_V1", "tariffOptions": "NO_TARIFF"},
        "location": {"energyBiddingZone": "SE3"},
        "uiComponents": {"activeServices": []},
    }},
    "prices": {"facility": {
        "spotPrices": {
            "current": {"price": 0.84, "startTimestamp": "2026-10-27T15:30:00.000Z",
                        "endTimestamp": "2026-10-27T15:45:00.000Z"},
            "entries": [
                {"price": 0.91, "startTimestamp": "2026-10-27T15:45:00.000Z", "endTimestamp": "2026-10-27T16:00:00.000Z"},
                {"price": 0.84, "startTimestamp": "2026-10-27T15:30:00.000Z", "endTimestamp": "2026-10-27T15:45:00.000Z"},
            ]},
        "misc": {"currencyCode": "SEK"},
    }},
    "forecast": {"facility": {"measurements": {"predictions": [
        {"timestamp": "2026-10-27T16:00:00.000Z", "stateOfCharge": 50, "solarPower": 0, "consumptionPower": 2400},
        {"timestamp": "2026-10-27T15:00:00.000Z", "stateOfCharge": 54, "solarPower": 120, "consumptionPower": 2100},
    ]}}},
}

# Per-phase power as in the official Cloud API's example: the Q set adds up to
# the total (26.95 + 313.34 + 236.52 = 576.81), the D set does not.
# One newPhaseBalanceData event, as the app's phase balancing view gets it.
PHASE_BALANCE_EVENT: dict[str, Any] = {"newPhaseBalanceData": {
    "facilityId": "12345", "timestamp": "2026-10-27T20:00:05.000Z",
    "phase1": {"gridVoltage": 230.1, "result": 6.2, "beforeCorrection": 8.0, "correction": -1.8},
    "phase2": {"gridVoltage": 231.4, "result": 6.0, "beforeCorrection": 4.1, "correction": 1.9},
    "phase3": {"gridVoltage": 229.7, "result": 6.1, "beforeCorrection": 6.2, "correction": -0.1},
}}

GRID_ANSWER: dict[str, Any] = {"facility": {"measurements": {
    "latestGridData": {
        "timestamp": "2026-10-27T20:00:00.000Z", "u1": 231.2, "u2": 229.8, "u3": 232.4,
        "iExtRms1": 5.1, "iExtRms2": 3.9, "iExtRms3": 7.4, "aceActive": False,
        "acePhase1": {"beforeCorrection": 5.1, "correction": 0.0, "result": 5.1},
        "acePhase2": {"beforeCorrection": 3.9, "correction": 0.0, "result": 3.9},
        "acePhase3": {"beforeCorrection": 7.4, "correction": 0.0, "result": 7.4}},
    "latestPower": {
        "timestamp": "2026-10-27T20:00:00.000Z", "gridPower": 576.81, "loadPower": 683.69,
        "pExtD1": 1.2, "pExtD2": 0.4, "pExtD3": 0.5, "pExtQ1": 26.95, "pExtQ2": 313.34, "pExtQ3": 236.52,
        "pLoadD1": 3.0, "pLoadD2": 2.0, "pLoadD3": 1.0, "pLoadQ1": 65.27, "pLoadQ2": 348.78, "pLoadQ3": 269.64},
}}}

_SYSTEM_DOCS = {document: name for name, document in system.PARTS.items()}


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
        if document in _SYSTEM_DOCS:
            return copy.deepcopy(SYSTEM_ANSWERS[_SYSTEM_DOCS[document]])
        if document is system.GRID:
            return copy.deepcopy(GRID_ANSWER)
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
