"""Telemetry sensors under the names EMS Steward reads.

Power is in W in Ferroamp's own signs, the same as the Ferroamp MQTT
integration: ``battery_power`` is positive while the battery discharges
(EMS's "invert battery sign" default handles that), ``grid_power`` positive
for import. The power sensors go unavailable when the cloud's latest sample
is older than STALE_AFTER_S, so EMS reads a dead link as stale, not as a
house standing still.

The system information (system.py) gets sensors of its own: the software, the
system's state and alarms, the grid's voltage, current and power per phase,
the consumption per phase, the batteries' health, state and cell
temperatures, the solar strings, the spot price and FerroAI's forecast.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import FerroampCloudConfigEntry
from . import system as sysinfo
from .const import STALE_AFTER_S
from .coordinator import CloudData, FerroampCloudCoordinator
from .entity import FerroampCloudEntity


@dataclass(frozen=True, kw_only=True)
class CloudSensorDescription(SensorEntityDescription):
    value: Callable[[CloudData], Any]
    attributes: Callable[[CloudData], dict[str, Any] | None] = lambda _: None
    live_power: bool = False   # unavailable while the power sample is stale
    live_grid: bool = False    # unavailable while the grid sample is stale
    unit: Callable[[CloudData], str | None] | None = None   # a unit read from the cloud


def _info(data: CloudData):
    return data.slow.info if data.slow else None


def _energy(data: CloudData):
    return data.slow.energy if data.slow else None


def _kwh(key: str, attr: str) -> CloudSensorDescription:
    return CloudSensorDescription(
        key=key,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value=lambda d: getattr(_energy(d), attr, None) if _energy(d) else None,
    )


def _power(key: str, attr: str, extra: Callable[[CloudData], dict] | None = None) -> CloudSensorDescription:
    return CloudSensorDescription(
        key=key,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value=lambda d: getattr(d.live, attr),
        attributes=lambda d: {
            "measured_at": d.live.measured_at.isoformat() if d.live.measured_at else None,
            **(extra(d) if extra else {}),
        },
        live_power=True,
    )


def _active_schedule(data: CloudData) -> str | None:
    schedule = data.slow.active_schedule if data.slow else None
    return schedule.summary if schedule else None


def _active_schedule_attributes(data: CloudData) -> dict[str, Any] | None:
    schedule = data.slow.active_schedule if data.slow else None
    if schedule is None:
        return None
    return schedule.as_attributes()


def _lower(value: str | None) -> str | None:
    """Ferroamp's own state names, lower case, as Home Assistant states go."""
    return value.lower() if isinstance(value, str) else None


def _software(data: CloudData) -> sysinfo.Software | None:
    return data.system.software if data.system else None


def _iso(value: dt.datetime | None) -> str | None:
    return value.isoformat() if value else None


def _software_attributes(data: CloudData) -> dict[str, Any] | None:
    software = _software(data)
    if software is None:
        return None
    return {
        "controller_version": software.controller_version,
        "controller_generation": software.controller_generation,
        "last_update_from": software.last_update_from,
        "last_update_to": software.last_update_to,
        "last_update_at": _iso(software.last_update_at),
        "hostname": software.hostname,
    }


def _system_attributes(data: CloudData) -> dict[str, Any] | None:
    info = data.system
    if info is None:
        return None
    return {
        "since": _iso(info.state_since),
        "lifecycle": _lower(info.lifecycle),
        "installed_on": _iso(info.installed_on),
        "main_fuse_a": info.main_fuse_a,
        "phases": _lower(info.phases),
        "inverter_power_rating_w": sum(info.inverter_ratings_w) if info.inverter_ratings_w else None,
        "eso_generation": ", ".join(info.eso_generations) or None,
        "active_services": [sysinfo.service_name(x) for x in info.active_services]
        if info.active_services is not None else None,
    }


def _battery_attributes(data: CloudData) -> dict[str, Any] | None:
    info = data.system
    if info is None or info.batteries is None:
        return None
    first = info.batteries[0] if info.batteries else None
    return {
        "manufacturer": first.manufacturer if first else None,
        "cell_voltage_min_v": first.cell_voltage_min_v if first else None,
        "cell_voltage_max_v": first.cell_voltage_max_v if first else None,
        "battery_voltage_v": first.voltage_v if first else None,
        "battery_current_a": first.current_a if first else None,
        "batteries": [b.as_dict() for b in info.batteries],
    }


def _battery_state_attributes(data: CloudData) -> dict[str, Any] | None:
    info = data.system
    if info is None or info.batteries is None:
        return None
    worst = sysinfo.battery_state(info)
    reasons = sorted({r for b in info.batteries if b.state == worst for r in b.reasons})
    return {"reasons": [_lower(r) for r in reasons]}


def _strings_attributes(data: CloudData) -> dict[str, Any] | None:
    info = data.system
    if info is None or not info.strings:
        return None
    return {
        "total": len(info.strings),
        "installed_pv": info.installed_pv,
        "strings": [{**s.as_dict(), "state": _lower(s.state), "reasons": [_lower(r) for r in s.reasons]}
                    for s in info.strings],
    }


#: Per phase, from the grid read (system.Grid): which series and its time stamp.
_PHASE_SERIES: dict[str, tuple[Callable[[sysinfo.Grid], tuple], Callable[[sysinfo.Grid], Any]]] = {
    "grid_voltage": (lambda g: g.voltage_v, lambda g: g.measured_at),
    "grid_current": (lambda g: g.current_a, lambda g: g.measured_at),
    "grid_power": (lambda g: g.grid_power_w, lambda g: g.power_measured_at),
    "consumption_power": (lambda g: g.load_power_w, lambda g: g.power_measured_at),
}


def _phase(prefix: str, number: int, device_class: SensorDeviceClass, unit: str) -> CloudSensorDescription:
    index = number - 1
    series, stamp = _PHASE_SERIES[prefix]
    return CloudSensorDescription(
        key=f"{prefix}_l{number}",
        device_class=device_class,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=unit,
        suggested_display_precision=0 if unit == UnitOfPower.WATT else 1,
        value=lambda d: series(d.grid)[index] if d.grid else None,
        attributes=lambda d: {"measured_at": _iso(stamp(d.grid))} if d.grid else None,
        live_grid=True,
    )


def _prices_attributes(data: CloudData) -> dict[str, Any] | None:
    prices = data.system.prices if data.system else None
    if prices is None:
        return None
    current = prices.current
    return {
        "currency": prices.currency,
        "start": _iso(current.start) if current else None,
        "end": _iso(current.end) if current else None,
        "prices": [p.as_dict() for p in prices.periods],
    }


def _forecast_point(data: CloudData) -> sysinfo.ForecastPoint | None:
    return sysinfo.forecast_now(data.system, dt_util.utcnow()) if data.system else None


def _forecast_attributes(data: CloudData) -> dict[str, Any] | None:
    if data.system is None or data.system.forecast is None:
        return None
    point = _forecast_point(data)
    return {
        "time": _iso(point.at) if point else None,
        "solar_w": point.solar_w if point else None,
        "consumption_w": point.consumption_w if point else None,
        "forecast": [p.as_dict() for p in data.system.forecast],
    }


SENSORS: tuple[CloudSensorDescription, ...] = (
    CloudSensorDescription(
        key="soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value=lambda d: d.live.soc,
        attributes=lambda d: {"measured_at": d.live.soc_at.isoformat() if d.live.soc_at else None},
    ),
    _power("battery_power", "battery_w", lambda d: {"sign": "positive = discharging"}),
    _power("grid_power", "grid_w", lambda d: {"sign": "positive = import"}),
    _power("solar_power", "solar_w"),
    _power("consumption_power", "load_w"),
    CloudSensorDescription(
        key="battery_capacity",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value=lambda d: _info(d).battery_kwh if _info(d) else None,
    ),
    CloudSensorDescription(
        key="max_charge_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda d: _info(d).battery_max_w if _info(d) else None,
    ),
    _kwh("solar_energy_today", "solar_kwh"),
    _kwh("consumption_energy_today", "consumption_kwh"),
    _kwh("grid_import_energy_today", "grid_import_kwh"),
    _kwh("grid_export_energy_today", "grid_export_kwh"),
    _kwh("battery_charged_energy_today", "battery_charged_kwh"),
    _kwh("battery_discharged_energy_today", "battery_discharged_kwh"),
    # A plain text sensor, not an enum: a mode the cloud adds later
    # (SystemModeV2 already has AcPowerReference) must not break it.
    CloudSensorDescription(
        key="system_mode",
        value=lambda d: d.live.config.mode if d.live.config else None,
        attributes=lambda d: {
            **(d.live.config.as_attributes() if d.live.config else {}),
            "generation": d.live.config_generation,
            "state": d.live.config_state,
        },
    ),
    CloudSensorDescription(
        key="active_schedule",
        value=_active_schedule,
        attributes=_active_schedule_attributes,
    ),
    CloudSensorDescription(
        key="ferroai_action",
        value=lambda d: (d.live.ferroai_action or {}).get("action"),
        attributes=lambda d: d.live.ferroai_action,
    ),
    CloudSensorDescription(
        key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda d: d.live.last_seen,
    ),
    # ------------------------------------------------------------ the system
    CloudSensorDescription(
        key="firmware_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        # The version the regular read has, when the system's own part does not answer.
        value=lambda d: (_software(d).version if _software(d) and _software(d).version
                         else (_info(d).version if _info(d) else None)),
        attributes=_software_attributes,
    ),
    CloudSensorDescription(
        key="system_state",
        value=lambda d: _lower(d.system.state) if d.system else None,
        attributes=_system_attributes,
    ),
    CloudSensorDescription(
        key="active_alarms",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: len(d.system.alarms) if d.system and d.system.alarms is not None else None,
        attributes=lambda d: {"alarms": [a.as_dict() for a in d.system.alarms]}
        if d.system and d.system.alarms is not None else None,
    ),
    *[_phase("grid_voltage", n, SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT) for n in (1, 2, 3)],
    *[_phase("grid_current", n, SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE) for n in (1, 2, 3)],
    *[_phase("grid_power", n, SensorDeviceClass.POWER, UnitOfPower.WATT) for n in (1, 2, 3)],
    *[_phase("consumption_power", n, SensorDeviceClass.POWER, UnitOfPower.WATT) for n in (1, 2, 3)],
    CloudSensorDescription(
        key="battery_health",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value=lambda d: sysinfo.battery_health(d.system) if d.system else None,
        attributes=_battery_attributes,
    ),
    CloudSensorDescription(
        key="battery_state",
        value=lambda d: _lower(sysinfo.battery_state(d.system)) if d.system else None,
        attributes=_battery_state_attributes,
    ),
    CloudSensorDescription(
        key="battery_cell_temperature_max",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        value=lambda d: sysinfo.cell_temperature(d.system, highest=True) if d.system else None,
    ),
    CloudSensorDescription(
        key="battery_cell_temperature_min",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        value=lambda d: sysinfo.cell_temperature(d.system, highest=False) if d.system else None,
    ),
    CloudSensorDescription(
        key="solar_strings",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: sysinfo.strings_running(d.system) if d.system else None,
        attributes=_strings_attributes,
    ),
    # The price the system is optimised against, in the currency the app shows.
    CloudSensorDescription(
        key="spot_price",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value=lambda d: d.system.prices.current.price
        if d.system and d.system.prices and d.system.prices.current else None,
        unit=lambda d: f"{d.system.prices.currency}/kWh"
        if d.system and d.system.prices and d.system.prices.currency else None,
        attributes=_prices_attributes,
    ),
    CloudSensorDescription(
        key="forecast_soc",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value=lambda d: _forecast_point(d).soc if _forecast_point(d) else None,
        attributes=_forecast_attributes,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: FerroampCloudConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([
        *(CloudSensor(coordinator, description) for description in SENSORS),
        LastCommandSensor(coordinator),
    ])


class CloudSensor(FerroampCloudEntity, SensorEntity):
    entity_description: CloudSensorDescription

    def __init__(self, coordinator: FerroampCloudCoordinator, description: CloudSensorDescription) -> None:
        super().__init__(coordinator, "sensor", description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        if not super().available or self.coordinator.data is None:
            return False
        if self.entity_description.live_power:
            age = self.coordinator.data.live.age_s(dt_util.utcnow())
            return age is not None and age <= STALE_AFTER_S
        if self.entity_description.live_grid:
            grid = self.coordinator.data.grid
            if grid is None or grid.measured_at is None:
                return False
            return (dt_util.utcnow() - grid.measured_at).total_seconds() <= STALE_AFTER_S
        return True

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.unit is not None:
            return self.entity_description.unit(self.coordinator.data) if self.coordinator.data else None
        return super().native_unit_of_measurement

    @property
    def native_value(self) -> Any:
        value = self.entity_description.value(self.coordinator.data)
        if isinstance(value, dt.datetime) and self.entity_description.device_class != SensorDeviceClass.TIMESTAMP:
            return value.isoformat()
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return self.entity_description.attributes(self.coordinator.data)


class LastCommandSensor(FerroampCloudEntity, SensorEntity):
    """What the driver last asked the cloud for, and whether the cloud took it.
    The following sensor is EMS's own check; this one says what was asked."""

    def __init__(self, coordinator: FerroampCloudCoordinator) -> None:
        super().__init__(coordinator, "sensor", "last_command")

    @property
    def native_value(self) -> str:
        return self.coordinator.control.result

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        control = self.coordinator.control
        return {
            "command": control.command,
            "reason": control.reason,
            "setpoint_w": control.setpoint_w,
            "enabled": control.enabled,
        }
