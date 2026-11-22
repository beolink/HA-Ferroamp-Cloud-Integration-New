"""Diagnostics download: what the driver last read, without the token."""

from __future__ import annotations

import dataclasses
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import FerroampCloudConfigEntry
from .const import CONF_EMAIL, CONF_REFRESH_TOKEN

TO_REDACT = {CONF_REFRESH_TOKEN, CONF_EMAIL}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FerroampCloudConfigEntry
) -> dict[str, Any]:
    coordinator = getattr(entry, "runtime_data", None)   # absent while the entry is not set up
    data = coordinator.data if coordinator else None
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "state": str(entry.state),
        "live": dataclasses.asdict(data.live) if data else None,
        "slow": dataclasses.asdict(data.slow) if data and data.slow else None,
        "control": coordinator.control.as_dict() if coordinator else None,
        # The system information as the cloud answered it, part by part, and
        # the grid per phase as read (system.py).
        "system_raw": data.system.raw if data and data.system else None,
        "grid": dataclasses.asdict(data.grid) if data and data.grid else None,
    }
