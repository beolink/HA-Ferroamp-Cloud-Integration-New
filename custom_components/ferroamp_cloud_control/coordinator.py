"""Polling: the live part every scan interval, the slow part every ten minutes."""

from __future__ import annotations

import datetime as dt
import logging
import time
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import protocol
from .api import AuthError, CloudError, FerroampCloud
from .const import (
    CONF_FACILITY_ID,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_S,
    DOMAIN,
    SLOW_INTERVAL_S,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CloudData:
    live: protocol.Live
    slow: protocol.Slow | None
    slow_at: float | None   # monotonic time of the last good slow read


class FerroampCloudCoordinator(DataUpdateCoordinator[CloudData]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: FerroampCloud) -> None:
        config = {**entry.data, **entry.options}
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=dt.timedelta(
                seconds=int(config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_S))),
        )
        self.client = client
        self.facility_id = int(entry.data[CONF_FACILITY_ID])

    @callback
    def store_refresh_token(self, token: str) -> None:
        """Keycloak rotated the offline token: keep the new one."""
        entry = self.config_entry
        if entry.data.get(CONF_REFRESH_TOKEN) != token:
            self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_REFRESH_TOKEN: token})

    def _now_local(self) -> dt.datetime:
        tz = None
        slow = self.data.slow if self.data else None
        if slow and slow.info.timezone:
            try:
                tz = ZoneInfo(slow.info.timezone)
            except (KeyError, ValueError):
                tz = None
        now = dt_util.now()
        return now.astimezone(tz) if tz else now

    async def _async_update_data(self) -> CloudData:
        try:
            live = protocol.parse_live(
                await self.client.query(protocol.LIVE, {"id": self.facility_id}))
            previous = self.data
            slow, slow_at = (previous.slow, previous.slow_at) if previous else (None, None)
            if slow_at is None or time.monotonic() - slow_at >= SLOW_INTERVAL_S:
                try:
                    slow = protocol.parse_slow(
                        await self.client.query(
                            protocol.SLOW,
                            protocol.slow_variables(self.facility_id, self._now_local())),
                        self.facility_id)
                    slow_at = time.monotonic()
                except CloudError as err:
                    # The live part is what EMS needs; the slow part waits
                    # for the next poll and keeps what it had.
                    _LOGGER.debug("Slow read failed, keeping the previous one: %s", err)
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except CloudError as err:
            raise UpdateFailed(str(err)) from err
        return CloudData(live=live, slow=slow, slow_at=slow_at)
