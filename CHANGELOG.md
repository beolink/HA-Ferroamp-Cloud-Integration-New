# Changelog

## 0.5.0 (unreleased)

What the Ferroamp app shows about the system itself, read from the same cloud:

- Software: `sensor.ferroamp_firmware_version` (the system's EnergyHub OS), with
  the control computer's version and generation, the latest update (from, to,
  when) and the host name as attributes.
- State and alarms: `sensor.ferroamp_system_state` (running, idle, degraded,
  fault, offline) with since when, the life cycle, the main fuse, the number of
  phases, the inverters' rated power and the ESO generation as attributes, and
  `sensor.ferroamp_active_alarms`, the number of active alarms with each one's
  code, product and start as an attribute.
- The grid per phase: voltage and current on L1, L2 and L3, and
  `binary_sensor.ferroamp_phase_balancing_active`, whether phase balancing
  (ACE) is working right now. Read on every poll.
- The battery: health (SoH, the weakest battery's), state with Ferroamp's
  reasons (such as power derating at a high or low charge), the highest and
  lowest cell temperature, and as attributes the manufacturer, the lowest and
  highest cell voltage and the battery's voltage and current.
- The solar strings: `sensor.ferroamp_solar_strings`, how many of them are
  running, with each string's name, state and rated power as an attribute.
- Power per phase: the grid's (`sensor.ferroamp_grid_power_l1` to `_l3`, + =
  import) and the house's consumption (`sensor.ferroamp_consumption_power_l1`
  to `_l3`), read on every poll with the grid's voltage and current. Phase
  balancing's correction per phase is an attribute of
  `binary_sensor.ferroamp_phase_balancing_active`.
- FerroAI and the price: `sensor.ferroamp_spot_price`, the spot price the
  system is optimised against, in the app's currency per kWh, with today's
  and tomorrow's prices as an attribute; `sensor.ferroamp_forecast_soc`,
  FerroAI's forecast of the state of charge for this hour, with the whole
  forecast (state of charge, solar and consumption, hour by hour about a day
  and a half ahead) as an attribute; FerroAI's settings (variant, grid tariff,
  minimum earnings, its import and export limits, bidding zone) as attributes
  of `binary_sensor.ferroamp_ferroai`; and whether an outside service (a
  flexibility provider's Remote API, ancillary services) is active, as an
  attribute of `sensor.ferroamp_system_state`.
- The System tab of the Ferroamp page shows the system information in five
  cards: Software, State and alarms, The grid, The battery and The solar
  panels. The Control tab has a card of its own for FerroAI and the price.
  Every row has its blue "i" as before.
- Today's energy leaves a quantity unknown when the cloud gives no hour of the
  day a value for it, instead of showing 0 kWh. On a system with an older
  EnergyHub OS and a third-party battery the driver showed 0 kWh charged and
  discharged while the hub's own MQTT counters had 31 and 12 kWh.
- The system information is read every ten minutes, part by part: a part the
  cloud does not answer leaves its values as they were and the rest is read as
  usual. The diagnostics download carries every part as the cloud answered it,
  and the error of each part the cloud refused.

0.5.0-beta.1 is for checking the new values on live systems: which of them a
system's cloud data fills in, the unit of the spot price, which of the two
power series per phase adds up, and the battery's rated capacity unit.

0.5.0-beta.2, after beta.1 on an ESO 15 system on OS 7:

- The basics are four parts (the basics, the life cycle, the system's state,
  the control computer): on that system one field of them made the cloud
  answer the whole part with nothing. The software version falls back to the
  one the regular read has.
- A part the cloud answers in part keeps its errors (which field, why) in the
  diagnostics download; they used to be dropped.
- Voltage and current per phase come from the stream the app's phase
  balancing view listens to (one event per poll), on a system whose grid
  data in the regular API is empty, as it was on that system. Without an
  event the stream is left alone for ten minutes.
- Cell temperatures and voltages are rounded to what they are (6.4 °C, not
  6.400001525878906).
- A system without solar strings shows the strings as unknown, not as 0 of 0.
- Confirmed on that system: the battery's rated capacity is in Wh (27 500 for
  27.5 kWh), the cell values match the battery's own BMS read locally, and
  the spot price comes per quarter hour. FerroAI's forecast is empty while
  FerroAI is off.

0.5.0-beta.3, after beta.2 on a system with an older OS:

- That system's list of solar strings had a null in it, and reading it
  stopped the whole poll, the live values too, so the integration did not
  start. Null entries are skipped in every list now, and the system
  information can no longer stop the live values: a part the driver cannot
  read keeps what it had and goes into the log.
- The diagnostics download works while the integration is not set up.
- Seen on the ESO 15 system: the account may not read the control computer
  or the life cycle ("Insufficient scopes"); the system's state and the
  basics it may.

0.5.0-beta.4, after beta.3 on both systems:

- The solar strings are read without `enabled`, which the cloud answered with
  "Unexpected error" for every string on the system with an older OS, so
  that no string came through.
- The spot price is Nord Pool's price for the bidding zone without VAT
  (1.167 against Nord Pool's 1.16647 SEK/kWh, 2026-11-22), and its
  explanation says so. The current per phase comes signed from the cloud
  (negative while the phase sells), and its explanation says that too.
- The alarm code `SYSTEM_IDLE` has words of its own.
- Seen on the system with an older OS (6.1.3) and a third-party battery: the
  cloud's battery energy for the day is 0, not missing, while the hub's own
  counters had 31 kWh charged; the driver shows what the cloud says.

0.5.0-beta.5, after beta.4: the product list of strings failed field by
field on the system with OS 6.1.3 (`enabled`, then `generation`). The strings
are now read the way the app lists them, from the topology, and their state
as a part of its own; where that part does not answer, a string counts as
running unless an SSO_OFFLINE alarm is active for it, as the app shows it.
The strings no longer carry a generation or a rated power.

## 0.4.1 (2026-11-22)

- A command's manual schedule keeps the owner's phase balancing limit. It kept
  whether phase balancing (ACE) was on but sent its limit as 0 A, so while a
  command stood the system ran with phase balancing on and a limit of 0 A instead
  of the owner's (15 A on the facility it was seen on).
- The options are a menu: Settings, with the poll interval and a new switch for
  whether the system is on the Ferroamp page (on by default; off takes the page
  out of the sidebar when no system is left on it), and Build the Ferroamp page
  anew, which takes the page out of the sidebar and puts it back, with a new
  address for its cards so that every browser loads them afresh.

## 0.4.0 (2026-11-22)

A page of its own in the sidebar, Ferroamp, in the manner of CTC Local Easyconf's:

- Three tabs: Overview (power right now, the last day's power, today's energy),
  Control (the control entities, the configuration the system runs now, the active
  schedule and FerroAI) and System (connection and the battery).
- A blue "i" after every value and option writes out what it is, where it comes
  from and how often it is read, with a way into Home Assistant's own dialog for the
  entity. Swedish on a Swedish Home Assistant, English otherwise.
- Built afresh each time it is opened, from the integration's current entities;
  nothing is stored and the page writes nothing: a control is changed in Home
  Assistant's own dialog.

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
