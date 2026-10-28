# Changelog

## 0.3.1 (2026-10-28)

All of the battery control from 0.2.0 and 0.3.0, tested on a live ESO 15
facility, with one fix to what the entities say while the switch is off.

- The verdict on handing back now stands while the switch is off. EMS writes
  the setpoint every tick, also with the switch off, and each write replaced
  what the hand-back had said with "control is off": a failed hand-back showed
  as a nak for one tick at most, and `binary_sensor.{prefix}_following` went
  back to unknown. A failed hand-back now stays a nak until the return
  schedule is in force, and a good one keeps "the owner's configuration is
  back". Nothing more is sent to the cloud than before.
- With the switch off, the tidy-up of the driver's old schedules reports a
  removal it could not make as a nak, as a write does.
- README: the control is tested on a live ESO 15 facility, all the checks in
  "Verify on your system first" on the 0.3.0 beta, and runs there in
  production. The 0.2.0 note below ("not yet run on a live facility") was
  true for that release.

## 0.3.0 — 2026-10-28

Parity with the contract entities of ha-ferroamp-control.

- `select.{prefix}_mode` with the five modes. `idle` hands the battery back whatever the setpoint
  says; the other modes follow the setpoint, as in ha-ferroamp-control. The cloud's own
  self-consumption and peak-shaving configurations are not used yet.
- `number.{prefix}_grid_power_limit`: kept and reported, never sent (the cloud has no import cap
  to set). Writing the maximum releases it.
- The mode and the grid limit are restored after a restart without a write.

## 0.2.0 — 2026-10-27 (beta)

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
