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
    data = entry.runtime_data.data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "live": dataclasses.asdict(data.live) if data else None,
        "slow": dataclasses.asdict(data.slow) if data and data.slow else None,
        "control": entry.runtime_data.control.as_dict(),
    }
