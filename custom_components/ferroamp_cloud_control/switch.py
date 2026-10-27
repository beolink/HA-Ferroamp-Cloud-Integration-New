"""The control switch: the EMS inverter contract's gate. Off, the driver writes
nothing; turning it off hands the system back to the owner's configuration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import FerroampCloudConfigEntry
from .coordinator import FerroampCloudCoordinator
from .entity import FerroampCloudEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: FerroampCloudConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([ControlSwitch(coordinator)])


class ControlSwitch(FerroampCloudEntity, SwitchEntity, RestoreEntity):
    """Restored as it was, but nothing is written on a restart: EMS's next
    write (or the owner's) starts control again."""

    def __init__(self, coordinator: FerroampCloudCoordinator) -> None:
        super().__init__(coordinator, "switch", "control_enabled")

    @property
    def is_on(self) -> bool:
        return self.coordinator.control.enabled

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state == "on":
            self.coordinator.control.enabled = True

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_enabled(False)
