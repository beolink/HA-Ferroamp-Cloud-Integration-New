"""Constants for the Ferroamp Cloud Control driver."""

from __future__ import annotations

DOMAIN = "ferroamp_cloud_control"

# Config keys
CONF_FACILITY_ID = "facility_id"
CONF_REFRESH_TOKEN = "refresh_token"   # Keycloak offline token; the password is never stored
CONF_EMAIL = "email"                   # shown again when the login has to be renewed
CONF_PREFIX = "prefix"                 # entity prefix, must match what EMS reads
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_PREFIX = "ferroamp"
DEFAULT_SCAN_INTERVAL_S = 30
MIN_SCAN_INTERVAL_S = 15

# Facility info, today's schedules and today's energy change slowly; they
# are read on the first update and then once per this interval.
SLOW_INTERVAL_S = 600

# A power sample the cloud has not renewed for this long makes the power
# sensors unavailable, so EMS sees stale telemetry for what it is. The
# facility reports a new sample every 15 s while it is online.
STALE_AFTER_S = 600

# Keycloak, as the Ferroamp user app logs in (PROTOCOL.md).
AUTH_BASE = "https://auth.eu.prod.ferroamp.com/realms/public/protocol/openid-connect"
CLIENT_ID = "user-app"
REDIRECT_URI = "ferroampuser://app/auth/login"
SCOPE = "openid offline_access"

GRAPHQL_URL = "https://api.eu.prod.ferroamp.com/graphql"

# Refresh the access token this long before it runs out.
TOKEN_MARGIN_S = 60

# Battery control, written as configuration schedules (control.py). Only
# schedules whose summary starts with CONTROL_PREFIX are ever removed.
CONTROL_PREFIX = "EMS control:"
RETURN_SUMMARY = "EMS control: return to normal"
# A command stands this long after it was written. When nothing renews it,
# the return schedule at the end of the window gives the system back to the
# owner's configuration (PROTOCOL.md: the end of a schedule does nothing).
WINDOW_S = 600
# EMS writes the setpoint every tick (five minutes). The driver renews a
# standing command on its own timer when nothing writes it.
REFRESH_S = 300
# A schedule starts at the first whole minute at least this far ahead.
START_LEAD_S = 30
# The number's range when the battery's rated power is not known yet.
RATED_FALLBACK_W = 15000

# The modes of the EMS inverter contract (select.{prefix}_mode), named as in
# ha-ferroamp-control. Only idle changes what the driver does: it hands the
# battery back whatever the setpoint says. The others follow the setpoint.
MODE_SELF_CONSUMPTION = "self_consumption"
MODE_PEAK_SHAVING = "peak_shaving"
MODE_FORCED_CHARGE = "forced_charge"
MODE_FORCED_DISCHARGE = "forced_discharge"
MODE_IDLE = "idle"
MODES = [MODE_SELF_CONSUMPTION, MODE_PEAK_SHAVING, MODE_FORCED_CHARGE, MODE_FORCED_DISCHARGE, MODE_IDLE]
