"""What the system is and how it fares, beyond the live values: its software,
its state and alarms, the grid per phase, the batteries and the solar strings,
FerroAI's settings and forecast and the spot price, as the Ferroamp app shows
them.

Every part is its own query (PARTS), read every SLOW_INTERVAL_S, except the
grid, which is read with every poll (GRID). A part the cloud refuses or does
not have is left out, and the others are kept: none of it is what EMS steers
by. The answers are kept raw as well, for the diagnostics download.

Free of Home Assistant imports, like protocol.py, so the parsing can be checked
without an installation (tests/test_system.py).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from .protocol import _float, iso, parse_time

# The basics, split the way the account may read them: the user app itself
# never asks for systemState or the control computer's change log, and asks
# for singleBoardComputer only in the installer's views, so each of those is
# a part of its own and a refusal of one leaves the others.
BASICS: Final = """
query SystemBasics($id: Int!) { facility(where: {id: {equals: $id}}) {
  hostname installedOn info { version } capacity { installedPv }
} }"""

LIFECYCLE: Final = """
query SystemLifecycle($id: Int!) { facility(where: {id: {equals: $id}}) {
  lifeCycle { current { stage updatedAt } }
} }"""

STATE: Final = """
query SystemState($id: Int!) { facility(where: {id: {equals: $id}}) {
  systemState { active { state createdAt updatedAt } }
} }"""

CONTROLLER: Final = """
query SystemController($id: Int!) { facility(where: {id: {equals: $id}}) {
  singleBoardComputer { productId generation version lastSeenAt
    versionChangeLog { fromVersion toVersion updatedAt } }
} }"""

TOPOLOGY: Final = """
query SystemTopology($id: Int!) { facility(where: {id: {equals: $id}}) {
  topology {
    system { mainFuse phases aceThreshold powerRatingPositive powerRatingNegative }
    inverters { id enabled attributes { powerRating currentRating } }
    batteries { id enabled manufacturer
      attributes { capactyRating powerRating socLimitLow socLimitHigh }
      esos { id generation enabled } }
  }
} }"""

ALARMS: Final = """
query SystemAlarms($id: Int!) { facility(where: {id: {equals: $id}}) {
  alarm { entries { code status productId activatedAt updatedAt } }
} }"""

BATTERIES: Final = """
query SystemBatteries($id: Int!) { facility(where: {id: {equals: $id}}) {
  batteries { productId manufacturer
    attributes { ratedCapacity ratedPower }
    state { current { primary secondary updatedAt } }
    log { current { stateOfCharge stateOfHealth batteryVoltage batteryCurrent
      cellTemperatureMin cellTemperatureMax cellVoltageMin cellVoltageMax updatedAt } } }
} }"""

# Without `enabled`: on a system with an older OS the cloud answered it with
# "Unexpected error" for every string, which made each string null.
STRINGS: Final = """
query SystemStrings($id: Int!) { facility(where: {id: {equals: $id}}) {
  ssos { id displayName generation attributes { powerRating }
    state { active { primary secondary updatedAt } } }
} }"""

# FerroAI's settings as the app's own GetFacilityOptimizationOptions reads
# them, the bidding zone, and which outside services (a flexibility provider's
# Remote API, ancillary services) are active.
OPTIMIZATION: Final = """
query SystemOptimization($id: Int!) { facility(where: {id: {equals: $id}}) {
  optimization { activatedAt enabled limitExportThreshold limitImportThreshold minimumEarnings
    optimizationVariant tariffOptions }
  location { energyBiddingZone }
  uiComponents { activeServices }
} }"""

# The spot price the system is optimised against, as the app's GetSpotPrice.
PRICES: Final = """
query SystemPrices($id: Int!, $period: FindSpotPricesWhereDay!) { facility(where: {id: {equals: $id}}) {
  spotPrices { current { price startTimestamp endTimestamp }
    entries(where: $period) { price startTimestamp endTimestamp } }
  misc { currencyCode }
} }"""

# FerroAI's forecast of the state of charge, solar and consumption, as the
# app's overview reads it.
FORECAST: Final = """
query SystemForecast($id: Int!, $range: DatetimeRangeQuery!) { facility(where: {id: {equals: $id}}) {
  measurements { predictions(where: {timestamp: $range}, unit: W) {
    timestamp stateOfCharge solarPower consumptionPower } }
} }"""

# Read with every poll: the grid per phase, phase balancing per phase, and the
# power per phase. PowerData has two sets per phase (D and Q); the driver takes
# the one that adds up to the total (see _per_phase).
GRID: Final = """
query SystemGrid($id: Int!) { facility(where: {id: {equals: $id}}) {
  measurements {
    latestGridData { timestamp u1 u2 u3 iExtRms1 iExtRms2 iExtRms3 aceActive
      acePhase1 { beforeCorrection correction result }
      acePhase2 { beforeCorrection correction result }
      acePhase3 { beforeCorrection correction result } }
    latestPower { timestamp gridPower loadPower
      pExtD1 pExtD2 pExtD3 pExtQ1 pExtQ2 pExtQ3 pLoadD1 pLoadD2 pLoadD3 pLoadQ1 pLoadQ2 pLoadQ3 }
  }
} }"""

# On a system whose latestGridData is empty (an ESO 15 on OS 7 was), the
# voltage and current per phase come from the stream the app's phase
# balancing view listens to; one event is read, and the stream closed.
PHASE_BALANCE: Final = """
subscription PhaseBalancingStream($facilityId: FacilityID!) { newPhaseBalanceData(facilityId: $facilityId) {
  facilityId timestamp
  phase1 { gridVoltage result beforeCorrection correction }
  phase2 { gridVoltage result beforeCorrection correction }
  phase3 { gridVoltage result beforeCorrection correction }
} }"""

#: The parts read every SLOW_INTERVAL_S, by name.
PARTS: Final[dict[str, str]] = {
    "basics": BASICS,
    "lifecycle": LIFECYCLE,
    "state": STATE,
    "controller": CONTROLLER,
    "topology": TOPOLOGY,
    "alarms": ALARMS,
    "batteries": BATTERIES,
    "strings": STRINGS,
    "optimization": OPTIMIZATION,
    "prices": PRICES,
    "forecast": FORECAST,
}

#: How far ahead the forecast is read.
FORECAST_HOURS: Final = 36


def part_variables(name: str, facility_id: int, now: dt.datetime) -> dict[str, Any]:
    """The variables for part ``name``; ``now`` is aware, in the facility's
    time zone. Prices for today and tomorrow (tomorrow's come in the
    afternoon), the forecast from the start of this hour."""
    variables: dict[str, Any] = {"id": facility_id}
    if name == "prices":
        today = now.date()
        variables["period"] = {"day": {"gte": today.isoformat(),
                                       "lte": (today + dt.timedelta(days=1)).isoformat()}}
    elif name == "forecast":
        hour = now.replace(minute=0, second=0, microsecond=0)
        variables["range"] = {"gte": iso(hour), "lt": iso(hour + dt.timedelta(hours=FORECAST_HOURS))}
    return variables


def _facility(answer: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(((answer or {}).get("facility")) or {})


def _items(value: Any) -> list[dict[str, Any]]:
    """The entries of a list the cloud answered, without the null ones: a
    system's list of strings has been seen with a null in it."""
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def _round(value: Any, digits: int) -> float | None:
    """Ferroamp sends floats as 6.400001525878906; the values are tenths."""
    number = _float(value)
    return None if number is None else round(number, digits)


def _iso(value: dt.datetime | None) -> str | None:
    return value.isoformat() if value else None


@dataclass(frozen=True)
class Software:
    version: str | None = None             # the system's OS (info.version)
    controller_version: str | None = None  # the EnergyHub's own computer
    controller_generation: str | None = None
    last_update_from: str | None = None
    last_update_to: str | None = None
    last_update_at: dt.datetime | None = None
    hostname: str | None = None


@dataclass(frozen=True)
class Battery:
    product_id: str | None
    manufacturer: str | None
    rated_capacity_kwh: float | None
    rated_power_w: float | None
    state: str | None
    reasons: tuple[str, ...] = ()
    soc: float | None = None
    soh: float | None = None
    voltage_v: float | None = None
    current_a: float | None = None
    cell_temp_min_c: float | None = None
    cell_temp_max_c: float | None = None
    cell_voltage_min_v: float | None = None
    cell_voltage_max_v: float | None = None
    updated_at: dt.datetime | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id, "manufacturer": self.manufacturer,
            "rated_capacity_kwh": self.rated_capacity_kwh, "rated_power_w": self.rated_power_w,
            "state": self.state, "reasons": list(self.reasons), "soc": self.soc, "soh": self.soh,
            "voltage_v": self.voltage_v, "current_a": self.current_a,
            "cell_temp_min_c": self.cell_temp_min_c, "cell_temp_max_c": self.cell_temp_max_c,
            "cell_voltage_min_v": self.cell_voltage_min_v, "cell_voltage_max_v": self.cell_voltage_max_v,
            "updated_at": _iso(self.updated_at),
        }


@dataclass(frozen=True)
class SolarString:
    name: str
    enabled: bool | None
    generation: str | None
    rating_w: float | None
    state: str | None
    reasons: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "enabled": self.enabled, "generation": self.generation,
                "rating_w": self.rating_w, "state": self.state, "reasons": list(self.reasons)}


@dataclass(frozen=True)
class Alarm:
    code: str
    product_id: str | None
    since: dt.datetime | None

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "product_id": self.product_id, "since": _iso(self.since)}


Phases = tuple[float | None, float | None, float | None]
NO_PHASES: Final[Phases] = (None, None, None)


@dataclass(frozen=True)
class Grid:
    measured_at: dt.datetime | None = None
    voltage_v: Phases = NO_PHASES
    current_a: Phases = NO_PHASES
    ace_active: bool | None = None
    # Phase balancing per phase: the current before it, its correction, the result.
    ace_before_a: Phases = NO_PHASES
    ace_correction_a: Phases = NO_PHASES
    ace_result_a: Phases = NO_PHASES
    # Power per phase, W in Ferroamp's signs (grid + = import).
    power_measured_at: dt.datetime | None = None
    grid_power_w: Phases = NO_PHASES
    load_power_w: Phases = NO_PHASES


@dataclass(frozen=True)
class Optimization:
    enabled: bool | None
    activated_at: dt.datetime | None
    variant: str | None
    tariff_option: str | None
    minimum_earnings: float | None
    limit_import_threshold: float | None
    limit_export_threshold: float | None
    bidding_zone: str | None


@dataclass(frozen=True)
class PricePeriod:
    start: dt.datetime | None
    end: dt.datetime | None
    price: float | None

    def as_dict(self) -> dict[str, Any]:
        return {"start": _iso(self.start), "end": _iso(self.end), "price": self.price}


@dataclass(frozen=True)
class Prices:
    currency: str | None
    current: PricePeriod | None
    periods: tuple[PricePeriod, ...] = ()


@dataclass(frozen=True)
class ForecastPoint:
    at: dt.datetime | None
    soc: float | None
    solar_w: float | None
    consumption_w: float | None

    def as_dict(self) -> dict[str, Any]:
        return {"time": _iso(self.at), "soc": self.soc, "solar_w": self.solar_w,
                "consumption_w": self.consumption_w}


@dataclass(frozen=True)
class SystemInfo:
    """Everything the parts answered; a part that did not answer is None."""

    software: Software | None = None
    state: str | None = None
    state_since: dt.datetime | None = None
    lifecycle: str | None = None
    installed_on: dt.datetime | None = None
    installed_pv: float | None = None
    main_fuse_a: float | None = None
    phases: str | None = None
    inverter_ratings_w: tuple[float, ...] = ()
    eso_generations: tuple[str, ...] = ()
    alarms: tuple[Alarm, ...] | None = None
    batteries: tuple[Battery, ...] | None = None
    strings: tuple[SolarString, ...] | None = None
    optimization: Optimization | None = None
    active_services: tuple[str, ...] | None = None
    prices: Prices | None = None
    forecast: tuple[ForecastPoint, ...] | None = None
    raw: dict[str, Any] = field(default_factory=dict, compare=False)


def parse_system(answers: Mapping[str, Mapping[str, Any] | None]) -> SystemInfo:
    """Build SystemInfo from the parts' data, by part name. A missing or empty
    part leaves its values None."""
    basics = _facility(answers.get("basics"))
    sbc = (_facility(answers.get("controller")).get("singleBoardComputer")) or {}
    active = ((_facility(answers.get("state")).get("systemState") or {}).get("active")) or {}
    lifecycle = ((_facility(answers.get("lifecycle")).get("lifeCycle") or {}).get("current")) or {}
    topology = (_facility(answers.get("topology")).get("topology")) or {}
    info: dict[str, Any] = {"raw": {k: v for k, v in answers.items() if v is not None}}

    if basics or sbc:
        changes = sorted(_items(sbc.get("versionChangeLog")), key=lambda c: c.get("updatedAt") or "")
        last = changes[-1] if changes else {}
        info["software"] = Software(
            version=(basics.get("info") or {}).get("version"),
            controller_version=sbc.get("version"),
            controller_generation=sbc.get("generation"),
            last_update_from=last.get("fromVersion"),
            last_update_to=last.get("toVersion"),
            last_update_at=parse_time(last.get("updatedAt")),
            hostname=basics.get("hostname"),
        )
    if basics:
        info["installed_on"] = parse_time(basics.get("installedOn"))
        info["installed_pv"] = _float((basics.get("capacity") or {}).get("installedPv"))
    if active:
        info["state"] = active.get("state")
        info["state_since"] = parse_time(active.get("createdAt"))
    if lifecycle:
        info["lifecycle"] = lifecycle.get("stage")

    if topology:
        system = topology.get("system") or {}
        info["main_fuse_a"] = _float(system.get("mainFuse"))
        info["phases"] = system.get("phases")
        info["inverter_ratings_w"] = tuple(
            r for r in (_float((i.get("attributes") or {}).get("powerRating"))
                        for i in _items(topology.get("inverters"))) if r is not None)
        info["eso_generations"] = tuple(sorted({
            eso.get("generation") for b in _items(topology.get("batteries"))
            for eso in _items(b.get("esos")) if eso.get("generation")}))

    alarms = answers.get("alarms")
    if alarms is not None:
        entries = _items((_facility(alarms).get("alarm") or {}).get("entries"))
        info["alarms"] = tuple(
            Alarm(code=str(e.get("code")), product_id=e.get("productId"), since=parse_time(e.get("activatedAt")))
            for e in entries if e.get("status") == "ACTIVE")

    batteries = answers.get("batteries")
    if batteries is not None:
        found = []
        for b in _items(_facility(batteries).get("batteries")):
            attrs = b.get("attributes") or {}
            state = ((b.get("state") or {}).get("current")) or {}
            log = ((b.get("log") or {}).get("current")) or {}
            found.append(Battery(
                product_id=b.get("productId"),
                manufacturer=b.get("manufacturer"),
                # ratedCapacity in Wh, as the official Cloud API's batterydata has it
                # (28416 in its example); to be confirmed on a live system.
                rated_capacity_kwh=(None if _float(attrs.get("ratedCapacity")) is None
                                    else round(_float(attrs.get("ratedCapacity")) / 1000.0, 2)),
                rated_power_w=_float(attrs.get("ratedPower")),
                state=state.get("primary"),
                reasons=tuple(state.get("secondary") or ()),
                soc=_float(log.get("stateOfCharge")),
                soh=_float(log.get("stateOfHealth")),
                voltage_v=_float(log.get("batteryVoltage")),
                current_a=_float(log.get("batteryCurrent")),
                cell_temp_min_c=_round(log.get("cellTemperatureMin"), 1),
                cell_temp_max_c=_round(log.get("cellTemperatureMax"), 1),
                cell_voltage_min_v=_round(log.get("cellVoltageMin"), 3),
                cell_voltage_max_v=_round(log.get("cellVoltageMax"), 3),
                updated_at=parse_time(log.get("updatedAt") or state.get("updatedAt")),
            ))
        info["batteries"] = tuple(found)

    strings = answers.get("strings")
    if strings is not None:
        found_strings = []
        for number, s in enumerate(_items(_facility(strings).get("ssos")), start=1):
            active = ((s.get("state") or {}).get("active")) or {}
            found_strings.append(SolarString(
                name=s.get("displayName") or f"SSO {number}",
                enabled=s.get("enabled"),
                generation=s.get("generation"),
                rating_w=_float((s.get("attributes") or {}).get("powerRating")),
                state=active.get("primary"),
                reasons=tuple(active.get("secondary") or ()),
            ))
        info["strings"] = tuple(found_strings)

    optimization = answers.get("optimization")
    if optimization is not None:
        fac = _facility(optimization)
        opt = fac.get("optimization") or {}
        if opt:
            info["optimization"] = Optimization(
                enabled=opt.get("enabled"),
                activated_at=parse_time(opt.get("activatedAt")),
                variant=opt.get("optimizationVariant"),
                tariff_option=opt.get("tariffOptions"),
                minimum_earnings=_float(opt.get("minimumEarnings")),
                limit_import_threshold=_float(opt.get("limitImportThreshold")),
                limit_export_threshold=_float(opt.get("limitExportThreshold")),
                bidding_zone=(fac.get("location") or {}).get("energyBiddingZone"),
            )
        services = (fac.get("uiComponents") or {}).get("activeServices")
        if services is not None:
            info["active_services"] = tuple(str(s) for s in services)

    prices = answers.get("prices")
    if prices is not None:
        fac = _facility(prices)
        spot = fac.get("spotPrices") or {}
        current = spot.get("current") if isinstance(spot.get("current"), dict) else None
        periods = sorted((_price_period(e) for e in _items(spot.get("entries"))),
                         key=lambda p: p.start or dt.datetime.min.replace(tzinfo=dt.UTC))
        if current or periods:
            info["prices"] = Prices(
                currency=(fac.get("misc") or {}).get("currencyCode"),
                current=_price_period(current) if current else None,
                periods=tuple(periods),
            )

    forecast = answers.get("forecast")
    if forecast is not None:
        rows = (_facility(forecast).get("measurements") or {}).get("predictions")
        if rows is not None:
            points = [ForecastPoint(at=parse_time(r.get("timestamp")), soc=_float(r.get("stateOfCharge")),
                                    solar_w=_float(r.get("solarPower")),
                                    consumption_w=_float(r.get("consumptionPower"))) for r in _items(rows)]
            info["forecast"] = tuple(sorted(points, key=lambda p: p.at or dt.datetime.min.replace(tzinfo=dt.UTC)))

    return SystemInfo(**info)


def _price_period(entry: Mapping[str, Any]) -> PricePeriod:
    return PricePeriod(start=parse_time(entry.get("startTimestamp")), end=parse_time(entry.get("endTimestamp")),
                       price=_float(entry.get("price")))


def _phases(data: Mapping[str, Any], pattern: str) -> Phases:
    return tuple(_float(data.get(pattern.format(n=n))) for n in (1, 2, 3))  # type: ignore[return-value]


def _per_phase(power: Mapping[str, Any], prefix: str, total_key: str) -> Phases:
    """Power per phase from PowerData, which has two sets per phase, ``D`` and
    ``Q``. In the official Cloud API's example the ``Q`` set adds up to the
    total (pExtQ1..3 to extPower, pLoadQ1..3 to loadPower), so that one is
    taken, unless the ``D`` set is the one that adds up on this system."""
    d = _phases(power, prefix + "D{n}")
    q = _phases(power, prefix + "Q{n}")
    total = _float(power.get(total_key))

    def off(values: Phases) -> float | None:
        if total is None or None in values:
            return None
        return abs(sum(v for v in values if v is not None) - total)

    off_d, off_q = off(d), off(q)
    if off_d is not None and off_q is not None and off_d < off_q:
        return d
    if None not in q:
        return q
    if None not in d:
        return d
    return NO_PHASES


def _ace(data: Mapping[str, Any], key: str) -> Phases:
    return tuple(_float((data.get(f"acePhase{n}") or {}).get(key)) for n in (1, 2, 3))  # type: ignore[return-value]


def with_phase_balance(grid: Grid | None, event: Mapping[str, Any] | None, received_at: dt.datetime) -> Grid | None:
    """``grid`` with the voltage, current and phase balancing per phase from
    a newPhaseBalanceData event. ``result`` is the current at the connection
    after phase balancing, so it is the grid current. The event's own
    timestamp is used when it has one, else when it was received."""
    data = (event or {}).get("newPhaseBalanceData") or {}
    phases = [data.get(f"phase{n}") or {} for n in (1, 2, 3)]
    if not any(phases):
        return grid
    base = grid or Grid()

    def pick(key: str) -> Phases:
        return tuple(_float(p.get(key)) for p in phases)  # type: ignore[return-value]

    corrections = pick("correction")
    return Grid(
        measured_at=parse_time(data.get("timestamp")) or received_at,
        voltage_v=pick("gridVoltage"),
        current_a=pick("result"),
        ace_active=any(abs(c) > 0.05 for c in corrections if c is not None) if None not in corrections else None,
        ace_before_a=pick("beforeCorrection"),
        ace_correction_a=corrections,
        ace_result_a=pick("result"),
        power_measured_at=base.power_measured_at,
        grid_power_w=base.grid_power_w,
        load_power_w=base.load_power_w,
    )


def parse_grid(answer: Mapping[str, Any] | None) -> Grid | None:
    """The grid per phase from the GRID query, or None without an answer."""
    measurements = _facility(answer).get("measurements") or {}
    data = measurements.get("latestGridData") or {}
    power = measurements.get("latestPower") or {}
    if not data and not power:
        return None
    return Grid(
        measured_at=parse_time(data.get("timestamp")),
        voltage_v=_phases(data, "u{n}"),
        current_a=_phases(data, "iExtRms{n}"),
        ace_active=data.get("aceActive"),
        ace_before_a=_ace(data, "beforeCorrection"),
        ace_correction_a=_ace(data, "correction"),
        ace_result_a=_ace(data, "result"),
        power_measured_at=parse_time(power.get("timestamp")),
        grid_power_w=_per_phase(power, "pExt", "gridPower") if power else NO_PHASES,
        load_power_w=_per_phase(power, "pLoad", "loadPower") if power else NO_PHASES,
    )


# ---------------------------------------------------------------- summaries the sensors show


def battery_health(info: SystemInfo) -> float | None:
    """The weakest battery's state of health, in percent."""
    values = [b.soh for b in info.batteries or () if b.soh is not None]
    return min(values) if values else None


def cell_temperature(info: SystemInfo, highest: bool) -> float | None:
    """The highest (or lowest) cell temperature over every battery, in °C."""
    pick = max if highest else min
    values = [getattr(b, "cell_temp_max_c" if highest else "cell_temp_min_c") for b in info.batteries or ()]
    values = [v for v in values if v is not None]
    return pick(values) if values else None


#: How bad a state is, for picking the worst one of several.
_SEVERITY: Final = {"FAULT": 4, "OFFLINE": 3, "DEGRADED": 2, "UNKNOWN_SET_BY_ECLOUD": 1, "IDLE": 0, "RUNNING": 0}


def battery_state(info: SystemInfo) -> str | None:
    """The worst state among the batteries."""
    states = [b.state for b in info.batteries or () if b.state]
    return max(states, key=lambda s: _SEVERITY.get(s, 1)) if states else None


def strings_running(info: SystemInfo) -> int | None:
    """How many solar strings are running; None for a system without any."""
    if not info.strings:
        return None
    return sum(1 for s in info.strings if s.state == "RUNNING")


def forecast_now(info: SystemInfo, now: dt.datetime) -> ForecastPoint | None:
    """The forecast's point for now: the latest one not after ``now``, else
    the first one ahead."""
    points = [p for p in info.forecast or () if p.at is not None]
    if not points:
        return None
    past = [p for p in points if p.at <= now]
    return past[-1] if past else points[0]


def service_name(value: str) -> str:
    """Ferroamp's service name as a state: "RemoteApi" -> "remote_api"."""
    out = ""
    for i, ch in enumerate(value):
        if ch.isupper() and i:
            out += "_"
        out += ch.lower()
    return out
