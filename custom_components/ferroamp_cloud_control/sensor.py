"""Telemetry sensors under the names EMS Steward reads.

Power is in W in Ferroamp's own signs, the same as the Ferroamp MQTT
integration: ``battery_power`` is positive while the battery discharges
(EMS's "invert battery sign" default handles that), ``grid_power`` positive
for import. The power sensors go unavailable when the cloud's latest sample
is older than STALE_AFTER_S, so EMS reads a dead link as stale, not as a
house standing still.
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
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import FerroampCloudConfigEntry
from .const import STALE_AFTER_S
from .coordinator import CloudData, FerroampCloudCoordinator
from .entity import FerroampCloudEntity


@dataclass(frozen=True, kw_only=True)
class CloudSensorDescription(SensorEntityDescription):
    value: Callable[[CloudData], Any]
    attributes: Callable[[CloudData], dict[str, Any] | None] = lambda _: None
    live_power: bool = False   # unavailable while the power sample is stale


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
)


async def async_setup_entry(
    hass: HomeAssistant, entry: FerroampCloudConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(CloudSensor(coordinator, description) for description in SENSORS)


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
        return True

    @property
    def native_value(self) -> Any:
        value = self.entity_description.value(self.coordinator.data)
        if isinstance(value, dt.datetime) and self.entity_description.device_class != SensorDeviceClass.TIMESTAMP:
            return value.isoformat()
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return self.entity_description.attributes(self.coordinator.data)
