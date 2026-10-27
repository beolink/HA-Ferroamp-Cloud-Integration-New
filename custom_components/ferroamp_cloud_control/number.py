"""The battery power setpoint of the EMS inverter contract: positive charges,
negative discharges, and 0 hands the system back to its own configuration."""

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
    async_add_entities([BatterySetpoint(coordinator)])


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
    def _rated_w(self) -> float:
        slow = self.coordinator.data.slow if self.coordinator.data else None
        if slow and slow.info.battery_max_w:
            return slow.info.battery_max_w
        return RATED_FALLBACK_W

    @property
    def native_min_value(self) -> float:
        return -self._rated_w

    @property
    def native_max_value(self) -> float:
        return self._rated_w

    @property
    def native_value(self) -> float:
        return self.coordinator.control.setpoint_w

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                self.coordinator.control.setpoint_w = float(last.state)
            except ValueError:
                pass

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_setpoint(value)
