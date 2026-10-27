"""Ferroamp Cloud Control: a Ferroamp EnergyHub through Ferroamp's cloud.

For facilities the local APIs cannot reach: an EnergyHub with an ESO 15 kW
runs EnergyHub OS 7 or later, which has neither the MQTT ExtAPI nor Modbus.
The driver talks to the same cloud API as the Ferroamp user app
(PROTOCOL.md) and publishes the telemetry EMS Steward reads, under the same
entity names as ha-ferroamp-control and the Ferroamp MQTT integration
(``sensor.{prefix}_soc``, ``_battery_power``, ``_grid_power`` and so on).

This release reads only. Control (the EMS inverter contract's setpoint)
follows once a cloud schedule has been seen steering a live battery.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FerroampCloud
from .const import CONF_REFRESH_TOKEN
from .coordinator import FerroampCloudCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

type FerroampCloudConfigEntry = ConfigEntry[FerroampCloudCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: FerroampCloudConfigEntry) -> bool:
    coordinator: FerroampCloudCoordinator | None = None

    def _rotated(token: str) -> None:
        if coordinator is not None:
            coordinator.store_refresh_token(token)

    client = FerroampCloud(async_get_clientsession(hass), entry.data[CONF_REFRESH_TOKEN], _rotated)
    coordinator = FerroampCloudCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload on a changed option only: the update listener also fires when
    # a rotated refresh token is written to entry.data, and that must not
    # restart the integration.
    options = dict(entry.options)

    async def _options_changed(hass: HomeAssistant, entry: FerroampCloudConfigEntry) -> None:
        if dict(entry.options) != options:
            await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_options_changed))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FerroampCloudConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
