"""The numbers of the EMS inverter contract: the battery power setpoint (signed W, + charges, 0 hands the
battery back) and the grid power limit (an import cap, kept and reported, never sent)."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import FerroampCloudConfigEntry
from .const import RATED_FALLBACK_W
from .coordinator import FerroampCloudCoordinator
from .entity import FerroampCloudEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: FerroampCloudConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([BatterySetpoint(coordinator), GridPowerLimit(coordinator)])


def _rated_w(coordinator: FerroampCloudCoordinator) -> float:
    slow = coordinator.data.slow if coordinator.data else None
    if slow and slow.info.battery_max_w:
        return slow.info.battery_max_w
    return RATED_FALLBACK_W


def _restored_float(last) -> float | None:
    if last is None or last.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return None
    try:
        return float(last.state)
    except ValueError:
        return None


class BatterySetpoint(FerroampCloudEntity, NumberEntity, RestoreEntity):
    """Kept as it was written. Written to the cloud only while the control
    switch is on, and restored without a write, so a restart waits for EMS."""

    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: FerroampCloudCoordinator) -> None:
        super().__init__(coordinator, "number", "battery_power_setpoint")

    @property
    def native_min_value(self) -> float:
        return -_rated_w(self.coordinator)

    @property
    def native_max_value(self) -> float:
        return _rated_w(self.coordinator)

    @property
    def native_value(self) -> float:
        return self.coordinator.control.setpoint_w

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        value = _restored_float(await self.async_get_last_state())
        if value is not None:
            self.coordinator.control.setpoint_w = value

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_setpoint(value)


class GridPowerLimit(FerroampCloudEntity, NumberEntity, RestoreEntity):
    """The import cap of the EMS inverter contract. Kept and reported, never sent: the cloud has no
    import-cap command here, as in ha-ferroamp-control. Writing the maximum releases the cap."""

    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: FerroampCloudCoordinator) -> None:
        super().__init__(coordinator, "number", "grid_power_limit")

    @property
    def native_min_value(self) -> float:
        return 0.0

    @property
    def native_max_value(self) -> float:
        return _rated_w(self.coordinator)

    @property
    def native_value(self) -> float | None:
        return self.coordinator.control.grid_limit_w

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        value = _restored_float(await self.async_get_last_state())
        if value is not None:
            self.coordinator.control.grid_limit_w = value

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.async_set_grid_limit(value)
