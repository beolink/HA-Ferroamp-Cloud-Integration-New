# Changelog

## 0.2.0 (unreleased)

Battery control, written as configuration schedules. Tested against a
simulated cloud; not yet run on a live facility (see the README).

- The EMS inverter contract: `number.{prefix}_battery_power_setpoint` (signed W),
  `switch.{prefix}_control_enabled` (off after install), `binary_sensor.{prefix}_following`
  and `sensor.{prefix}_last_command`.
- A command is a one-off manual schedule from the next whole minute, running ten
  minutes, followed by a return schedule with the owner's configuration. A command
  stands while it is renewed every five minutes; without renewals the return starts.
- Each write creates the new schedules before it removes any, never removes the
  schedule in force, and removes only schedules named `EMS control: ...`.
- Refused, with the reason shown, while FerroAI is on, on a system without
  configuration schedules, and until the owner's configuration has been seen.
- Turning the switch off hands the system back at once. After a restart no command
  is sent until EMS writes again.
- Diagnostics include the control state.

## 0.1.0 (unreleased)

First version, reads only.

- Logs in as the Ferroamp app does (Keycloak client `user-app`, PKCE,
  offline token); stores the token, never the password; re-authentication
  when Ferroamp refuses the token; a rotated token is stored without a reload.
- Telemetry under the EMS Steward names: SoC, battery, grid, solar and
  consumption power (W, Ferroamp's signs), battery capacity and rated power.
- Today's energy from the hourly series.
- The configuration in force, the active schedule, FerroAI's action and
  state, online and last seen.
- Power sensors unavailable when the cloud's sample is over 10 minutes old.
