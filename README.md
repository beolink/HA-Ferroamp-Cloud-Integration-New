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

## Status: 0.2, control written, not yet run on a live facility

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

### Control

On OS 7 and later the app does not command the battery directly; it lays out
*configuration schedules* that the system follows. The driver takes the EMS
inverter contract's setpoint and writes it that way, so EMS Steward needs no
change to use it:

| Entity | Purpose |
|--------|---------|
| `switch.ferroamp_control_enabled` | The gate, **off** after install. Off, nothing is written. Turning it off hands the system back at once. |
| `number.ferroamp_battery_power_setpoint` | W, signed: positive charges, negative discharges, 0 hands the system back to the owner's configuration. EMS writes it every tick. |
| `select.ferroamp_mode` | `self_consumption`, `peak_shaving`, `forced_charge`, `forced_discharge` or `idle`, as in ha-ferroamp-control. `idle` hands the battery back whatever the setpoint says; the other modes follow the setpoint. |
| `number.ferroamp_grid_power_limit` | W, an import cap. Kept and reported, never sent: the cloud has no import-cap command here, as in ha-ferroamp-control. Writing the maximum releases it. |
| `binary_sensor.ferroamp_following` | On when the cloud took the latest write, off when it refused it. `last_nak` says why. |
| `sensor.ferroamp_last_command` | `idle`, `pending`, `ack` or `nak`, with the command and the reason as attributes. |

A command is a one-off *manual* schedule that starts at the next whole minute
and runs ten minutes, followed by a *return* schedule that starts when that
window ends and gives the owner's configuration back. A command stands only
while it is renewed, every five minutes, by EMS or by the driver's own timer.
If Home Assistant stops, or the renewals stop, the return starts and the system
goes back to what the owner set. The driver removes only schedules whose name
starts with `EMS control:`, and never the one in force.

The mode is restored after a restart without a write, like the setpoint. The cloud's own
self-consumption and peak-shaving configurations are not used yet: those modes follow the
setpoint, as they do in ha-ferroamp-control.

Writes are refused, and the reason is shown, while FerroAI is on (the cloud
refuses owner schedules then), on a system without configuration schedules, and
until the owner's configuration has been seen once. After a restart no command
is sent until EMS writes again, and a command still standing from before the
restart ends on its own: its return starts when the window does.

Known side effects:

- While a command stands, the owner's recurring schedules wait behind it. The
  cloud moves them (PROTOCOL.md, the schedule test), so they resume at their
  next start after control ends.
- If EMS stops writing while the switch is on, the driver keeps renewing the
  last command. Turn the switch off to hand back.
- Discharge has not been seen on a live system yet (PROTOCOL.md, still open).

### Verify on your system first

The write path is tested against a simulated cloud. It has not run on a live
facility yet. On a system where a short charge or discharge is harmless, check
in this order:

1. Switch control on and set the setpoint to 100 W (EMS's hold).
   `sensor.ferroamp_last_command` should read `ack`, the app should list
   `EMS control: charge 100 W` and `EMS control: return to normal`, and the
   battery should stay near 0 W.
2. Set -500 W and check that the battery discharges.
3. Turn the switch off. The return should give the owner's configuration back,
   and no `EMS control:` schedule should remain in force.

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

`tests/_cloud_sim.py` stands in for the cloud and keeps configuration schedules
the way PROTOCOL.md describes them; the control tests run against it.

## Disclaimer

Not affiliated with Ferroamp AB. Ferroamp says that third-party control
affects the system's own control and FerroAI.

## License

Apache License 2.0, see [LICENSE](LICENSE).
