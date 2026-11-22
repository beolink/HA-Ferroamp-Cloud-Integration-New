"""Whether the facility is online, whether FerroAI steers it (with its
settings), whether phase balancing is working (with its correction per phase)."""

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
    async_add_entities([OnlineSensor(coordinator), FerroAiSensor(coordinator), FollowingSensor(coordinator),
                        PhaseBalancingActiveSensor(coordinator)])


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

    @property
    def extra_state_attributes(self) -> dict | None:
        info = self.coordinator.data.system
        opt = info.optimization if info else None
        if opt is None:
            return None
        return {
            "variant": opt.variant.lower() if opt.variant else None,
            "activated_at": opt.activated_at.isoformat() if opt.activated_at else None,
            "tariff_option": opt.tariff_option.lower() if opt.tariff_option else None,
            "minimum_earnings": opt.minimum_earnings,
            "limit_import_threshold": opt.limit_import_threshold,
            "limit_export_threshold": opt.limit_export_threshold,
            "bidding_zone": opt.bidding_zone,
        }


class FollowingSensor(FerroampCloudEntity, BinarySensorEntity):
    """EMS's verdict on the command: on while the cloud took the latest write,
    off when it refused it, unknown until the first write. EMS raises a
    Repairs issue after NAKs, so a refusal is never silent."""

    def __init__(self, coordinator: FerroampCloudCoordinator) -> None:
        super().__init__(coordinator, "binary_sensor", "following")

    @property
    def is_on(self) -> bool | None:
        return {"ack": True, "nak": False}.get(self.coordinator.control.result)

    @property
    def extra_state_attributes(self) -> dict:
        control = self.coordinator.control
        return {"last_nak": control.reason if control.result == "nak" else None}


class PhaseBalancingActiveSensor(FerroampCloudEntity, BinarySensorEntity):
    """On while phase balancing (ACE) is correcting the phases right now, read
    with the grid per phase (system.py)."""

    def __init__(self, coordinator: FerroampCloudCoordinator) -> None:
        super().__init__(coordinator, "binary_sensor", "phase_balancing_active")

    @property
    def is_on(self) -> bool | None:
        grid = self.coordinator.data.grid
        return grid.ace_active if grid else None

    @property
    def extra_state_attributes(self) -> dict | None:
        grid = self.coordinator.data.grid
        if grid is None:
            return None
        return {
            "ace_correction_l1": grid.ace_correction_a[0],
            "ace_correction_l2": grid.ace_correction_a[1],
            "ace_correction_l3": grid.ace_correction_a[2],
            "ace_before_l1": grid.ace_before_a[0],
            "ace_before_l2": grid.ace_before_a[1],
            "ace_before_l3": grid.ace_before_a[2],
            "ace_result_l1": grid.ace_result_a[0],
            "ace_result_l2": grid.ace_result_a[1],
            "ace_result_l3": grid.ace_result_a[2],
        }
