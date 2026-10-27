"""Whether the facility is online, whether FerroAI steers it."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FerroampCloudConfigEntry
from .coordinator import FerroampCloudCoordinator
from .entity import FerroampCloudEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: FerroampCloudConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([OnlineSensor(coordinator), FerroAiSensor(coordinator)])


class OnlineSensor(FerroampCloudEntity, BinarySensorEntity):
    """The cloud's own word on whether the EnergyHub reports in."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: FerroampCloudCoordinator) -> None:
        super().__init__(coordinator, "binary_sensor", "online")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.live.online

    @property
    def extra_state_attributes(self) -> dict:
        live = self.coordinator.data.live
        return {
            "last_seen": live.last_seen.isoformat() if live.last_seen else None,
            "system_upgrade": live.upgrading,
        }


class FerroAiSensor(FerroampCloudEntity, BinarySensorEntity):
    """On while FerroAI steers the facility. The cloud refuses an owner's
    schedules while it is on, so a future control release needs it off."""

    def __init__(self, coordinator: FerroampCloudCoordinator) -> None:
        super().__init__(coordinator, "binary_sensor", "ferroai")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.live.ferroai_enabled
