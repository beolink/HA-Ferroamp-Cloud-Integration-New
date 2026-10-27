"""The Ferroamp cloud protocol without I/O: login pieces, GraphQL documents
and the parsers that turn answers into plain values.

Nothing here imports Home Assistant or aiohttp, so the tests run on a bare
Python. PROTOCOL.md in the repository says where each piece comes from and
what has been seen on a live facility.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import html
import re
import secrets
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

from .const import CLIENT_ID, REDIRECT_URI, SCOPE

# ---------------------------------------------------------------- login


class LoginError(Exception):
    """The login page did not hand out a code. ``reason`` is the page's own
    message when it has one (a wrong password), else what went wrong."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def pkce_pair() -> tuple[str, str]:
    """A PKCE verifier and its S256 challenge."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def auth_url(auth_base: str, state: str, nonce: str, challenge: str) -> str:
    return f"{auth_base}/auth?" + urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })


_FORM = re.compile(r'<form[^>]*id="kc-form-login"[^>]*action="([^"]+)"')
_INPUT = re.compile(r'<input[^>]*name="([^"]+)"(?:[^>]*value="([^"]*)")?')
_FIELD_ERROR = re.compile(r'id="input-error[^"]*"[^>]*>\s*([^<]+?)\s*<')


def login_form(page: str, email: str, password: str) -> tuple[str, dict[str, str]]:
    """The form action and the fields to post, from Keycloak's login page."""
    action = _FORM.search(page)
    if not action:
        raise LoginError("login form not found")
    fields = {m.group(1): html.unescape(m.group(2) or "") for m in _INPUT.finditer(page)}
    fields.pop("rememberMe", None)
    fields.update({"username": email, "password": password})
    return html.unescape(action.group(1)), fields


def page_error(page: str) -> str | None:
    """The message Keycloak shows under the form (wrong password, locked)."""
    found = _FIELD_ERROR.search(page)
    return html.unescape(found.group(1)) if found else None


def code_from_redirect(location: str, state: str) -> str:
    """The authorization code from the app redirect after a good login."""
    parsed = urllib.parse.urlparse(location)
    params = urllib.parse.parse_qs(parsed.query or parsed.fragment)
    if "error" in params:
        raise LoginError(params.get("error_description", params["error"])[0])
    if params.get("state", [None])[0] != state:
        raise LoginError("state mismatch in the login redirect")
    if "code" not in params:
        raise LoginError("no code in the login redirect")
    return params["code"][0]


def token_request(code: str, verifier: str) -> dict[str, str]:
    return {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "code": code,
        "code_verifier": verifier,
    }


def refresh_request(refresh_token: str) -> dict[str, str]:
    return {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": refresh_token,
    }


# ---------------------------------------------------------------- GraphQL

_EMS_V1 = """
  ... on EmsConfigurationV1 {
    systemMode
    systemSettingsPv { pvMode }
    systemSettingsGrid { aceMode aceThreshold limitImport limitExport powerThresholdHigh powerThresholdLow }
    systemSettingsBattery { powerRefCharge powerRefDischarge socRefHigh socRefLow }
  }
"""

FACILITIES = """
query Facilities {
  facilities(take: 50, orderBy: {id: asc}) {
    id name timezone myRelation { relation } info { version }
    uiComponents { usesNewScheduler }
  }
}"""

# Every poll: power, SoC, whether the facility is online, the configuration
# in force and what FerroAI does. One request.
LIVE = """
query Live($id: Int!) { facility(where: {id: {equals: $id}}) {
  connectivity { isOnline lastSeenAt }
  maintenance { ongoingSystemUpgrade }
  measurements {
    latestPower { timestamp batteryPower gridPower loadPower pvPower inverterPower }
    currentStateOfCharge { stateOfCharge timestamp }
  }
  configuration { emsConfiguration { current { generation state config { %s } } } }
  optimization { enabled activeAction { action title start end } }
} }""" % _EMS_V1

# Every SLOW_INTERVAL_S: what the facility is, today's schedules and
# today's energy. One request.
SLOW = """
query Slow($id: Int!, $period: SchedulePeriod!, $range: DatetimeRangeQuery!) {
  facility(where: {id: {equals: $id}}) {
    id name timezone info { version }
    uiComponents {
      usesNewScheduler
      ferroAi { available }
      capacities {
        ... on UIMainFuseCapacity { __typename capacity unit }
        ... on UIMaxInverterPowerCapacity { __typename capacity unit }
        ... on UIEnergyStorageRatedPowerCapacity { __typename capacity unit }
        ... on UIEnergyStorageRatedCapacity { __typename capacity unit }
      }
    }
    configuration { configurationSchedule {
      schedules(period: $period) {
        id summary scheduleType origin isActive appliedAt intendedStartAt nextIntendedStartAt
        event { iCalendarEventJson { start end rruleStr } }
        configuration { %s }
      }
    } }
    measurements {
      energy(period: {dateTime: {resolution: Hourly, range: $range}}, unit: Wh, dataSeriesType: Relative) {
        pvProduced consumption gridImport gridExport batteryCharged batteryDischarged
      }
    }
  }
}""" % _EMS_V1

# The schedules alone, for the control: what the driver made and what the
# owner has, to remove its own and to read the owner's configuration.
SCHEDULES = """
query Schedules($id: Int!, $period: SchedulePeriod!) { facility(where: {id: {equals: $id}}) {
  configuration { configurationSchedule {
    schedules(period: $period) {
      id summary scheduleType origin isActive appliedAt
      event { iCalendarEventJson { start end rruleStr } }
      configuration { %s }
    }
  } }
} }""" % _EMS_V1


def schedule_variables(facility_id: int, now: dt.datetime) -> dict[str, Any]:
    """Variables for SCHEDULES: a day either side of now, which covers every
    schedule the driver makes (each lies a few minutes ahead)."""
    return {
        "id": facility_id,
        "period": {
            "start": iso(now - dt.timedelta(days=1)),
            "end": iso(now + dt.timedelta(days=1)),
        },
    }


def slow_variables(facility_id: int, now: dt.datetime) -> dict[str, Any]:
    """Variables for SLOW: schedules from yesterday to the day after
    tomorrow (the app's window), energy from local midnight until now.
    ``now`` must be aware and in the facility's time zone."""
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "id": facility_id,
        "period": {
            "start": iso(midnight - dt.timedelta(days=1)),
            "end": iso(midnight + dt.timedelta(days=2)),
        },
        "range": {"gte": iso(midnight), "lt": iso(now)},
    }


def iso(value: dt.datetime) -> str:
    return value.astimezone(dt.UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class GraphQLError(Exception):
    """The API answered with errors. ``unauthenticated`` when a fresh
    token would help."""

    def __init__(self, errors: list[dict]) -> None:
        self.errors = errors
        messages = "; ".join(str(e.get("message", e)) for e in errors)
        super().__init__(messages or "GraphQL error")

    @property
    def unauthenticated(self) -> bool:
        return any(
            (e.get("extensions") or {}).get("code") in ("UNAUTHENTICATED", "FORBIDDEN")
            for e in self.errors
        )


def data_of(answer: dict) -> dict:
    """The ``data`` of a GraphQL answer; errors raise unless data came too
    (a partial answer is used, the missing part reads as None)."""
    errors = answer.get("errors") or []
    data = answer.get("data")
    if errors and not data:
        raise GraphQLError(errors)
    return data or {}


# ---------------------------------------------------------------- values

# measurements.latestPower answers in W (batteryPower 2080 while the live
# stream said 2 for the same discharge), although the stream is kW.
# Seen on a live ESO 15 facility, 2026-10-27.
POWER_SCALE_W = 1.0

MODES = {
    "Default": "manual",
    "PeakShaving": "peak_shaving",
    "SelfConsumption": "self_consumption",
    "Measurement": "measurement",
}


def _float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _watts(value: Any) -> float | None:
    number = _float(value)
    return None if number is None else round(number * POWER_SCALE_W, 1)


@dataclass(frozen=True)
class EmsConfig:
    """One EmsConfigurationV1: what the system is told to do."""

    mode: str | None
    pv_on: bool | None
    ace_on: bool | None
    ace_threshold_a: float | None
    limit_import: bool | None
    limit_export: bool | None
    threshold_high_w: int | None
    threshold_low_w: int | None
    charge_ref_w: int | None
    discharge_ref_w: int | None
    soc_low: float | None
    soc_high: float | None

    @classmethod
    def from_api(cls, raw: dict | None) -> EmsConfig | None:
        if not raw or "systemMode" not in raw:
            return None
        pv = raw.get("systemSettingsPv") or {}
        grid = raw.get("systemSettingsGrid") or {}
        bat = raw.get("systemSettingsBattery") or {}
        return cls(
            mode=MODES.get(raw.get("systemMode"), str(raw.get("systemMode")).lower()),
            pv_on=pv.get("pvMode"),
            ace_on=grid.get("aceMode"),
            ace_threshold_a=_float(grid.get("aceThreshold")),
            limit_import=grid.get("limitImport"),
            limit_export=grid.get("limitExport"),
            threshold_high_w=grid.get("powerThresholdHigh"),
            threshold_low_w=grid.get("powerThresholdLow"),
            charge_ref_w=bat.get("powerRefCharge"),
            discharge_ref_w=bat.get("powerRefDischarge"),
            soc_low=_float(bat.get("socRefLow")),
            soc_high=_float(bat.get("socRefHigh")),
        )

    def as_attributes(self) -> dict[str, Any]:
        return {
            "pv_on": self.pv_on,
            "phase_balancing_on": self.ace_on,
            "phase_balancing_threshold_a": self.ace_threshold_a,
            "limit_import": self.limit_import,
            "limit_export": self.limit_export,
            "threshold_high_w": self.threshold_high_w,
            "threshold_low_w": self.threshold_low_w,
            "charge_reference_w": self.charge_ref_w,
            "discharge_reference_w": self.discharge_ref_w,
            "soc_low": self.soc_low,
            "soc_high": self.soc_high,
        }


@dataclass(frozen=True)
class Live:
    """One poll. Power in W in Ferroamp's own signs: battery + = discharging
    (EMS's "invert battery sign" default), grid + = import."""

    measured_at: dt.datetime | None = None
    battery_w: float | None = None
    grid_w: float | None = None
    load_w: float | None = None
    solar_w: float | None = None
    inverter_w: float | None = None
    soc: float | None = None
    soc_at: dt.datetime | None = None
    online: bool | None = None
    last_seen: dt.datetime | None = None
    upgrading: bool | None = None
    config: EmsConfig | None = None
    config_generation: str | None = None
    config_state: str | None = None
    ferroai_enabled: bool | None = None
    ferroai_action: dict | None = None
    config_raw: dict | None = None   # the configuration in force, as the cloud answered it

    def age_s(self, now: dt.datetime) -> float | None:
        if self.measured_at is None:
            return None
        return (now - self.measured_at).total_seconds()


def parse_live(data: dict) -> Live:
    facility = data.get("facility") or {}
    connectivity = facility.get("connectivity") or {}
    measurements = facility.get("measurements") or {}
    power = measurements.get("latestPower") or {}
    soc = measurements.get("currentStateOfCharge") or {}
    current = (((facility.get("configuration") or {}).get("emsConfiguration") or {})
               .get("current") or {})
    optimization = facility.get("optimization") or {}
    return Live(
        measured_at=parse_time(power.get("timestamp")),
        battery_w=_watts(power.get("batteryPower")),
        grid_w=_watts(power.get("gridPower")),
        load_w=_watts(power.get("loadPower")),
        solar_w=_watts(power.get("pvPower")),
        inverter_w=_watts(power.get("inverterPower")),
        soc=_float(soc.get("stateOfCharge")),
        soc_at=parse_time(soc.get("timestamp")),
        online=connectivity.get("isOnline"),
        last_seen=parse_time(connectivity.get("lastSeenAt")),
        upgrading=(facility.get("maintenance") or {}).get("ongoingSystemUpgrade"),
        config=EmsConfig.from_api(current.get("config")),
        config_raw=current.get("config") or None,
        config_generation=current.get("generation"),
        config_state=current.get("state"),
        ferroai_enabled=optimization.get("enabled"),
        ferroai_action=optimization.get("activeAction"),
    )


@dataclass(frozen=True)
class Schedule:
    id: str
    summary: str | None
    schedule_type: str | None
    origin: str | None
    is_active: bool
    start: dt.datetime | None
    end: dt.datetime | None
    rrule: str | None
    applied_at: dt.datetime | None
    config: EmsConfig | None
    config_raw: dict | None = None   # the configuration as the cloud answered it

    def as_attributes(self) -> dict[str, Any]:
        return {
            "schedule_id": self.id,
            "schedule_type": self.schedule_type,
            "origin": self.origin,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "rrule": self.rrule,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "mode": self.config.mode if self.config else None,
        }


@dataclass(frozen=True)
class Info:
    """What the facility is: from the slow query."""

    facility_id: int
    name: str | None = None
    timezone: str | None = None
    version: str | None = None
    uses_new_scheduler: bool | None = None
    ferroai_available: bool | None = None
    battery_kwh: float | None = None
    battery_max_w: float | None = None
    inverter_max_w: float | None = None
    main_fuse_a: float | None = None


@dataclass(frozen=True)
class EnergyToday:
    """Today's energy in kWh, summed from the hourly series."""

    solar_kwh: float = 0.0
    consumption_kwh: float = 0.0
    grid_import_kwh: float = 0.0
    grid_export_kwh: float = 0.0
    battery_charged_kwh: float = 0.0
    battery_discharged_kwh: float = 0.0
    hours: int = 0


@dataclass(frozen=True)
class Slow:
    info: Info
    schedules: tuple[Schedule, ...] = field(default_factory=tuple)
    energy: EnergyToday | None = None

    @property
    def active_schedule(self) -> Schedule | None:
        """The schedule the cloud marks active; a NORMAL one before the
        fallback (standard) schedule."""
        active = [s for s in self.schedules if s.is_active]
        active.sort(key=lambda s: s.schedule_type == "FALLBACK")
        return active[0] if active else None


def _capacity(entry: dict) -> float | None:
    value = _float(entry.get("capacity"))
    if value is None:
        return None
    unit = (entry.get("unit") or "").lower()
    if unit in ("kw", "kwh"):
        return value * 1000.0 if unit == "kw" else value
    if unit == "wh":
        return value / 1000.0
    return value


def parse_schedules(data: dict) -> tuple[Schedule, ...]:
    """The schedules of a SLOW or SCHEDULES answer, in the order the cloud gives them."""
    facility = data.get("facility") or {}
    root = ((facility.get("configuration") or {}).get("configurationSchedule") or {})
    out = []
    for raw in root.get("schedules") or []:
        event = ((raw.get("event") or {}).get("iCalendarEventJson") or {})
        out.append(Schedule(
            id=str(raw.get("id")),
            summary=raw.get("summary"),
            schedule_type=raw.get("scheduleType"),
            origin=raw.get("origin"),
            is_active=bool(raw.get("isActive")),
            start=parse_time(event.get("start")),
            end=parse_time(event.get("end")),
            rrule=event.get("rruleStr"),
            applied_at=parse_time(raw.get("appliedAt")),
            config=EmsConfig.from_api(raw.get("configuration")),
            config_raw=raw.get("configuration") or None,
        ))
    return tuple(out)


def parse_slow(data: dict, facility_id: int) -> Slow:
    facility = data.get("facility") or {}
    ui = facility.get("uiComponents") or {}
    caps = {c.get("__typename"): c for c in ui.get("capacities") or [] if isinstance(c, dict)}
    info = Info(
        facility_id=facility_id,
        name=facility.get("name"),
        timezone=facility.get("timezone"),
        version=(facility.get("info") or {}).get("version"),
        uses_new_scheduler=ui.get("usesNewScheduler"),
        ferroai_available=(ui.get("ferroAi") or {}).get("available"),
        battery_kwh=_capacity(caps.get("UIEnergyStorageRatedCapacity", {})),
        battery_max_w=_capacity(caps.get("UIEnergyStorageRatedPowerCapacity", {})),
        inverter_max_w=_capacity(caps.get("UIMaxInverterPowerCapacity", {})),
        main_fuse_a=_capacity(caps.get("UIMainFuseCapacity", {})),
    )
    schedules = parse_schedules(data)
    rows = ((facility.get("measurements") or {}).get("energy"))
    return Slow(info=info, schedules=tuple(schedules),
                energy=None if rows is None else sum_energy(rows))


def sum_energy(rows: list[dict]) -> EnergyToday:
    """Sum hourly Wh rows into kWh. A field the API leaves null counts 0."""
    def total(key: str) -> float:
        return round(sum(_float(r.get(key)) or 0.0 for r in rows) / 1000.0, 3)

    return EnergyToday(
        solar_kwh=total("pvProduced"),
        consumption_kwh=total("consumption"),
        grid_import_kwh=total("gridImport"),
        grid_export_kwh=total("gridExport"),
        battery_charged_kwh=total("batteryCharged"),
        battery_discharged_kwh=total("batteryDischarged"),
        hours=len(rows),
    )


def parse_facilities(data: dict) -> list[dict[str, Any]]:
    """The facilities the account may see, for the config flow."""
    out = []
    for f in data.get("facilities") or []:
        out.append({
            "id": int(f["id"]),
            "name": f.get("name") or f"Ferroamp {f['id']}",
            "admin": ((f.get("myRelation") or {}).get("relation") == "FACILITY_ADMIN"),
            "new_scheduler": bool((f.get("uiComponents") or {}).get("usesNewScheduler")),
            "version": (f.get("info") or {}).get("version"),
        })
    return out


# ---------------------------------------------------------------- control

# systemMode of a fixed battery reference: the app's manual schedule.
MANUAL_MODE = "Default"

CREATE_SCHEDULE = """
mutation CreateOneNormalConfigurationSchedule($facilityId: Int!, $data: ConfigurationScheduleDataInput!) {
  createOneNormalConfigurationSchedule(where: {facilityId: $facilityId}, data: $data) {
    success schedule { id } message code
  }
}"""

REMOVE_SCHEDULE = """
mutation RemoveOneNormalConfigurationSchedule($facilityId: Int!, $id: ID!) {
  removeOneNormalConfigurationSchedule(where: {facilityId: $facilityId, id: $id}) { success message code }
}"""

_GRID_FIELDS = ("aceMode", "aceThreshold", "limitImport", "limitExport", "powerThresholdHigh", "powerThresholdLow")
_BATTERY_FIELDS = ("powerRefCharge", "powerRefDischarge", "socRefLow", "socRefHigh")


def config_input(raw: dict | None) -> dict | None:
    """A configuration as the cloud answered it, in the shape it takes back
    (``EmsConfigurationInputV1``). None when a part is missing, so that no
    schedule is ever built from a guess."""
    if not raw or raw.get("systemMode") is None:
        return None
    pv = raw.get("systemSettingsPv") or {}
    grid = raw.get("systemSettingsGrid") or {}
    battery = raw.get("systemSettingsBattery") or {}
    if pv.get("pvMode") is None:
        return None
    if any(grid.get(f) is None for f in _GRID_FIELDS) or any(battery.get(f) is None for f in _BATTERY_FIELDS):
        return None
    return {
        "systemMode": raw["systemMode"],
        "systemSettingsPv": {"pvMode": pv["pvMode"]},
        "systemSettingsGrid": {f: grid[f] for f in _GRID_FIELDS},
        "systemSettingsBattery": {f: battery[f] for f in _BATTERY_FIELDS},
    }


def manual_config_input(normal: dict, charge_w: int, discharge_w: int) -> dict:
    """The battery held at one reference: charging at ``charge_w`` or
    discharging at ``discharge_w``, the other 0 (PROTOCOL.md). PV and phase
    balancing stay as the owner has them; the rest is what the app writes
    for a manual schedule."""
    return {
        "systemMode": MANUAL_MODE,
        "systemSettingsPv": {"pvMode": normal["systemSettingsPv"]["pvMode"]},
        "systemSettingsGrid": {
            "aceMode": normal["systemSettingsGrid"]["aceMode"],
            "aceThreshold": 0,
            "limitExport": False,
            "limitImport": False,
            "powerThresholdHigh": 0,
            "powerThresholdLow": 0,
        },
        "systemSettingsBattery": {
            "powerRefCharge": charge_w,
            "powerRefDischarge": discharge_w,
            "socRefLow": 10,
            "socRefHigh": 100,
        },
    }


def schedule_input(summary: str, start: dt.datetime, end: dt.datetime, timezone: str,
                   configuration: dict) -> dict:
    """``ConfigurationScheduleDataInput`` for a one-off event, which has no rrule."""
    return {
        "summary": summary,
        "iCalendarEventJson": {"start": iso(start), "end": iso(end), "summary": summary, "timezone": timezone},
        "configuration": {"emsConfigurationV1": configuration},
    }
