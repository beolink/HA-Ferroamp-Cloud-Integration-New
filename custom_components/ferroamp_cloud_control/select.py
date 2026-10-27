"""The mode select of the EMS inverter contract, named as in ha-ferroamp-control. Idle hands the battery
back; the other modes follow the setpoint."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import FerroampCloudConfigEntry
from .const import MODE_SELF_CONSUMPTION, MODES
from .coordinator import FerroampCloudCoordinator
from .entity import FerroampCloudEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: FerroampCloudConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([ModeSelect(coordinator)])


class ModeSelect(FerroampCloudEntity, SelectEntity, RestoreEntity):
    """Restored as it was, without a write, like the setpoint: a restart waits for EMS."""

    _attr_options = MODES

    def __init__(self, coordinator: FerroampCloudCoordinator) -> None:
        super().__init__(coordinator, "select", "mode")

    @property
    def current_option(self) -> str:
        return self.coordinator.control.mode or MODE_SELF_CONSUMPTION

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in MODES:
            self.coordinator.control.mode = last.state

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_mode(option)
