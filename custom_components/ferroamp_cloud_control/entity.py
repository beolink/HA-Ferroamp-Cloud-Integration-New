"""The device and the base entity every platform shares."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_FACILITY_ID, CONF_PREFIX, DEFAULT_PREFIX, DOMAIN
from .coordinator import FerroampCloudCoordinator


class FerroampCloudEntity(CoordinatorEntity[FerroampCloudCoordinator]):
    """An entity with a fixed entity id under the driver prefix, so EMS
    finds it by name (``sensor.{prefix}_soc`` and so on) whatever the
    device is called."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FerroampCloudCoordinator, platform: str, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        prefix = entry.data.get(CONF_PREFIX) or DEFAULT_PREFIX
        facility_id = entry.data[CONF_FACILITY_ID]
        self._attr_unique_id = f"{facility_id}_{key}"
        self._attr_translation_key = key
        self.entity_id = f"{platform}.{prefix}_{key}"
        slow = coordinator.data.slow if coordinator.data else None
        info = slow.info if slow else None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(facility_id))},
            name=(info.name if info and info.name else entry.title),
            manufacturer="Ferroamp",
            model="EnergyHub (cloud)",
            sw_version=info.version if info else None,
            configuration_url="https://portal.ferroamp.com/",
        )
