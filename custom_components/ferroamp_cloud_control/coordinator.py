"""Polling: the live part every scan interval, the slow part every ten minutes,
and the battery control written on top of them (control.py).

The system information (system.py) rides along: its parts with the slow part,
the grid per phase with every poll. Each is read on its own and a failure of
one only leaves its values as they were; none of it is what EMS steers by.
"""

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

from . import protocol, system
from .api import AuthError, CloudError, FerroampCloud
from .const import (
    CONF_FACILITY_ID,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_S,
    DOMAIN,
    SLOW_INTERVAL_S,
)
from .control import Controller

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CloudData:
    live: protocol.Live
    slow: protocol.Slow | None
    slow_at: float | None   # monotonic time of the last good slow read
    system: system.SystemInfo | None = None
    grid: system.Grid | None = None


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
        self.control = Controller(client, self.facility_id)
        # A grid read that failed is not tried again for SLOW_INTERVAL_S, so a
        # part the cloud does not have costs one request per ten minutes, not
        # one per poll.
        self._grid_retry_at = 0.0
        self._stream_retry_at = 0.0

    @callback
    def store_refresh_token(self, token: str) -> None:
        """Keycloak rotated the offline token: keep the new one."""
        entry = self.config_entry
        if entry.data.get(CONF_REFRESH_TOKEN) != token:
            self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_REFRESH_TOKEN: token})

    async def async_set_setpoint(self, watts: float) -> None:
        """EMS's setpoint, or the owner's: written at once while control is on."""
        live, info = self._snapshot()
        await self.control.write(watts, live=live, info=info, now=dt_util.utcnow())
        self.async_update_listeners()

    async def async_set_enabled(self, enabled: bool) -> None:
        """The control switch. On writes the current setpoint; off hands the
        system back at once."""
        live, info = self._snapshot()
        now = dt_util.utcnow()
        if enabled:
            self.control.enabled = True
            await self.control.write(self.control.setpoint_w, live=live, info=info, now=now)
        else:
            self.control.enabled = False
            await self.control.release(live=live, info=info, now=now)
        self.async_update_listeners()

    async def async_set_mode(self, mode: str) -> None:
        """The mode select. Idle hands the battery back; the other modes follow the setpoint."""
        self.control.mode = mode
        live, info = self._snapshot()
        await self.control.write(self.control.setpoint_w, live=live, info=info, now=dt_util.utcnow())
        self.async_update_listeners()

    def async_set_grid_limit(self, watts: float) -> None:
        """EMS's import cap. Kept and reported; nothing is sent (see Controller.grid_limit_w)."""
        self.control.grid_limit_w = watts
        self.async_update_listeners()

    def _snapshot(self) -> tuple[protocol.Live, protocol.Info | None]:
        if self.data is None:
            return protocol.Live(), None
        return self.data.live, (self.data.slow.info if self.data.slow else None)

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
            slow_read = False
            if slow_at is None or time.monotonic() - slow_at >= SLOW_INTERVAL_S:
                try:
                    slow = protocol.parse_slow(
                        await self.client.query(
                            protocol.SLOW,
                            protocol.slow_variables(self.facility_id, self._now_local())),
                        self.facility_id)
                    slow_at = time.monotonic()
                    slow_read = True
                except CloudError as err:
                    # The live part is what EMS needs; the slow part waits
                    # for the next poll and keeps what it had.
                    _LOGGER.debug("Slow read failed, keeping the previous one: %s", err)
            info = previous.system if previous else None
            if slow_read or (info is None and slow is not None):
                info = await self._read_system(info)
            grid = await self._read_grid(previous.grid if previous else None)
            # The owner's configuration is kept while no command stands, and a
            # standing command is renewed here, on the driver's own timer.
            now = dt_util.utcnow()
            self.control.observe(live)
            if self.control.renewal_due(now):
                await self.control.write(
                    self.control.setpoint_w, live=live, info=slow.info if slow else None, now=now)
            elif slow_read:
                # With the switch off, the driver's leftovers go every ten minutes.
                await self.control.tidy(now)
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except CloudError as err:
            raise UpdateFailed(str(err)) from err
        return CloudData(live=live, slow=slow, slow_at=slow_at, system=info, grid=grid)

    async def _read_system(self, previous: system.SystemInfo | None) -> system.SystemInfo:
        """Every part of the system information, each on its own. A part that
        fails keeps what the previous read had for it, and its error is kept
        for the diagnostics download."""
        answers: dict = dict(previous.raw) if previous else {}
        errors: dict[str, str] = {}
        now = self._now_local()
        for name, document in system.PARTS.items():
            try:
                answers[name] = await self.client.query(
                    document, system.part_variables(name, self.facility_id, now))
                partial = getattr(self.client, "last_errors", None)
                if partial:
                    errors[name] = "; ".join(partial)
            except CloudError as err:
                _LOGGER.debug("System part %s not read: %s", name, err)
                errors[name] = str(err)
        answers["errors"] = errors
        try:
            return system.parse_system(answers)
        except Exception:  # noqa: BLE001 - the system information must never stop the live read
            _LOGGER.exception("The system information could not be read; the live values go on")
            return previous

    async def _read_grid(self, previous: system.Grid | None) -> system.Grid | None:
        if time.monotonic() < self._grid_retry_at:
            return previous
        try:
            grid = system.parse_grid(await self.client.query(system.GRID, {"id": self.facility_id}))
        except (CloudError, AttributeError, TypeError, ValueError) as err:
            _LOGGER.debug("Grid per phase not read: %s", err)
            self._grid_retry_at = time.monotonic() + SLOW_INTERVAL_S
            return previous
        if grid is None or grid.measured_at is None:
            grid = await self._read_phase_balance(grid)
        return grid if grid is not None else previous

    async def _read_phase_balance(self, grid: system.Grid | None) -> system.Grid | None:
        """Voltage and current per phase from the app's phase balancing
        stream, for a system whose latestGridData is empty. Without an event,
        the stream is left alone for SLOW_INTERVAL_S."""
        if time.monotonic() < self._stream_retry_at:
            return grid
        try:
            event = await self.client.subscribe_once(
                system.PHASE_BALANCE, {"facilityId": str(self.facility_id)})
        except CloudError as err:
            _LOGGER.debug("Phase balancing stream not read: %s", err)
            event = None
        if event is None:
            self._stream_retry_at = time.monotonic() + SLOW_INTERVAL_S
            return grid
        try:
            return system.with_phase_balance(grid, event, dt_util.utcnow())
        except (AttributeError, TypeError, ValueError) as err:
            _LOGGER.debug("Phase balancing event not understood: %s", err)
            return grid
