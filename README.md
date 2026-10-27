# Ferroamp Cloud Control for Home Assistant

A Home Assistant driver for **Ferroamp EnergyHub systems that only the cloud
can reach**, the sibling of
[ha-ferroamp-control](https://github.com/beolink/ha-ferroamp-control), which
uses the hub's local MQTT ExtAPI.

An EnergyHub with an ESO 15 kW battery optimizer needs EnergyHub OS 7 or
later, and OS 7 has neither the MQTT ExtAPI nor Modbus (Ferroamp has said
an ExtAPI for OS 7 is planned for Q1 2027). The web portal does not manage
these systems either; only the Ferroamp app does. This driver talks to the
same cloud API as the app.

## Status: 0.1, reads only

- Telemetry under the names [EMS Steward](https://github.com/beolink/ha-ems)
  reads, so EMS finds them on its own: `sensor.ferroamp_soc`,
  `_battery_power`, `_grid_power`, `_solar_power`, `_consumption_power`,
  `_battery_capacity`, `_max_charge_power`.
- Today's energy: solar, consumption, grid import and export, battery
  charged and discharged (kWh, resets at midnight).
- What the system does: the configuration in force (`sensor.ferroamp_system_mode`
  with its settings as attributes), the active schedule, FerroAI's action,
  whether FerroAI is on, whether the system is online and when it was last
  heard from.

**Control is not in this release.** On OS 7 and later the app does not
command the battery directly; it lays out *configuration schedules* that the
system follows. Control through such schedules (the EMS inverter contract's
`number.ferroamp_battery_power_setpoint`) comes once a schedule has been
seen steering a live battery, and how quickly it does so.

### Signs and units

Power is in W in Ferroamp's own signs, the same as the Ferroamp MQTT
integration: `battery_power` is **positive while discharging** (EMS's
"Invert battery sign" default, which stays on), `grid_power` positive for
import. The cloud reports a new sample every 15 s; the driver polls every
30 s by default (15 s at the least). The power sensors go unavailable when
the cloud's latest sample is more than 10 minutes old, so EMS reads a lost
link as stale telemetry.

## Install

With HACS: *HACS, the three dots, Custom repositories*, add
`https://github.com/beolink/HA-Ferroamp-Cloud-Integration-New` as type
*Integration*, then install *Ferroamp Cloud Control* and restart Home
Assistant. Without HACS, copy `custom_components/ferroamp_cloud_control`
into your configuration directory and restart.

Then *Settings, Devices and services, Add integration, Ferroamp Cloud
Control*.

Log in with the account you use in the Ferroamp app. The password is sent
to Ferroamp's login page once and is **not stored**: Home Assistant keeps
the login token Ferroamp hands out (an offline token, as the app's), the
system id and the e-mail. When Ferroamp stops accepting the token, Home
Assistant asks you to log in again. An account that signs in with Apple or
Google only has no password for this login.

The entity prefix (default `ferroamp`) must match the one EMS reads. If the
Ferroamp MQTT integration runs on the same Home Assistant for another
system, give this one another prefix.

## How it works

[PROTOCOL.md](PROTOCOL.md) describes the API: the login, the GraphQL
queries, the schedule model and what has been seen on a live ESO 15
system. Nothing of it is documented by Ferroamp; it was read out of the
Ferroamp app and checked against a live system, and Ferroamp can change it
without notice.

`tools/probe.py` (one read of everything) and `tools/monitor.py` (a running
log while schedules are tried in the app) read a system from the command
line. Neither writes anything.

## Development

```bash
pytest                                   # protocol and client, no Home Assistant needed
pytest -c tests_ha/pytest.ini tests_ha   # with pytest-homeassistant-custom-component installed
```

## Disclaimer

Not affiliated with Ferroamp AB. Ferroamp says that third-party control
affects the system's own control and FerroAI.

## License

Apache License 2.0, see [LICENSE](LICENSE).
