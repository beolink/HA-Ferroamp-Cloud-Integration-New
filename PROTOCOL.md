# Ferroamp cloud protocol (OS 7 and later, ESO 15)

Read out of the Ferroamp user app, `com.ferroamp.userapp` 1.30.0 (version code
177, APKPure XAPK, 2026-10-27), and the web portal's `app.bundle` the same
day. The app is React Native (Expo) with Hermes bytecode 98; GraphQL
documents are plain strings in the bundle, the rest was read from
`hbc-decompiler` (hermes-dec 0.1.8) output. Nothing here is documented by
Ferroamp. Everything marked *unverified* still has to be seen on a live
facility.

## Why the cloud

An EnergyHub with an ESO 15 kW needs EnergyHub OS 7 or later. OS 7 has no
ExtAPI (MQTT) and no Modbus; Ferroamp has promised an ExtAPI for OS 7 in
Q1 2027 (henricm/ha-ferroamp#926). The web portal refuses these facilities
("Åtkomsten är begränsad ... använd Ferroamps mobilapp"), so the user app is
the only client that manages them, and its API is the one to follow.

The official Cloud API (spec rev C, 2024-10-21, `GET /api?type=...&api_key=`)
only reads, at most 300 calls a day. It is not used here; see
[The official Cloud API](#the-official-cloud-api) for what it gives.

Where a system has the local MQTT ExtAPI or Modbus, the local interface is
always the one to use; this driver is for systems that only the cloud can
reach. By default an EnergyHub has no inbound ports at all (Ferroamp's
network description, rev C, 2021-12-02): it sits behind a NAT router of its
own, every connection starts from inside it (MQTT and the eCloud gateway to
Ferroamp, an SSH tunnel to Ferroamp's service gateway), and Modbus TCP or the
ExtAPI can only be reached through port forwards Ferroamp sets up on request.
Other parts of such a system can still have local sources, such as a
Pylontech battery stack read through its own logger.

## Login: Keycloak, public client `user-app`

| | |
|---|---|
| Issuer | `https://auth.eu.prod.ferroamp.com/realms/public` |
| Endpoints | `.../protocol/openid-connect/{auth,token,logout}` |
| Client | `user-app` (production and pre-production), `user-app-dev` otherwise |
| Redirect | `ferroampuser://app/auth/login` |
| Scopes | `openid offline_access` |
| Flow | authorization code with PKCE (expo-auth-session) |

`offline_access` gives an offline refresh token, so an integration can log in
once in its config flow and keep only that token, never the password. The web
portal uses client `portal-frontend-ng-production` with redirect
`https://portal.ferroamp.com/` and scope `openid` only.

The login page also offers Apple, Google and "Ferroamp Employee login";
an account that only signs in with Apple or Google has no password for the
form login, and needs a browser-based flow instead (*unverified*).

## API: GraphQL

- Queries and mutations: `POST https://api.eu.prod.ferroamp.com/graphql`,
  `Authorization: Bearer <access token>`.
- Subscriptions: `POST https://api.eu.prod.ferroamp.com/graphql/stream` with
  `Accept: text/event-stream` (server-sent events, `data:` lines carrying
  `{"data": {...}}`). The app also knows the `graphql-transport-ws` protocol.
- Facility id = the system id shown in the portal URL (`?id=`).

### Live power

```graphql
subscription FlowChartStream($facilityId: FacilityID!) {
  newPowerData(facilityId: $facilityId) {
    loadPower pvPower gridPower batteryPower ehubPower
  }
}
```

The portal's variant also asks for `gridSign`, `facilityId` and `timestamp`.
Units are kW according to the Homey app that uses the same stream; the sign of
`batteryPower` and `gridPower` is *unverified*.

Polled alternative (the app's overview):

```graphql
measurements {
  lastAverage: power(resolution: Minutely, timeRange: $timestamp, last: 1) {
    timestamp pvPower loadPower inverterPower gridPower batteryPower
  }
  currentStateOfCharge { stateOfCharge }
}
```

### Energy

`measurements.energy(period: {dateTime: {resolution: Hourly, range: $range}},
unit: Wh, dataSeriesType: Relative)` returns per period
`pvProduced`, `consumptionL1..L3`, `consumptionProducedL1..L3`, `gridImport`,
`gridExport` (`... on SystemEnergyDateTime { timeperiodStart }`).

### Facility and capabilities

```graphql
facility(where: {id: {equals: $facilityId}}) {
  info { version }
  configuration { capabilities { resourceType } }   # ASYNCAPI | VARIANT_X
  uiComponents {
    activeServices usesNewScheduler
    ferroAi { available description }
    capacities {                                     # union, one per kind
      ... on UIEnergyStorageRatedCapacity { capacity unit }
      ... on UIEnergyStorageRatedPowerCapacity { capacity unit }
      ... on UIMaxInverterPowerCapacity { capacity unit }
      ... on UIMainFuseCapacity { capacity unit }
    }
  }
  connectivity { isOnline lastSeenAt offlineSecondsFromNow }
  maintenance { ongoingSystemUpgrade }
}
```

`VARIANT_X` is what the portal calls "VX": the OS 7 generation.

### The system itself (0.5)

The app's system pages read these fields of `facility` (`system.py` holds the
queries; each is asked on its own, so one the server refuses leaves the rest).
On an ESO 15 system on OS 7 (2026-11-22) the basics asked together came back
as `facility: null`, so they are four parts: the basics, `lifeCycle`,
`systemState` and `singleBoardComputer` (the user app never asks for
`systemState` or `versionChangeLog`, and asks for `singleBoardComputer` only
in the installer's views):

- `hostname`, `installedOn`, `info { version }`, `lifeCycle { current { stage } }`,
  `systemState { active { state createdAt } }` and
  `singleBoardComputer { generation version versionChangeLog { fromVersion toVersion updatedAt } }`:
  the software and the system's state (`RUNNING`, `IDLE`, `DEGRADED`, `FAULT`,
  `OFFLINE`, `UNKNOWN_SET_BY_ECLOUD`).
- `topology { system { mainFuse phases aceThreshold } inverters { attributes { powerRating } } batteries { esos { generation } } }`:
  how the system is built. The battery's capacity attribute is spelt
  `capactyRating` in the schema.
- `alarm { entries { code status productId activatedAt } }`: the alarms; only
  `status: ACTIVE` counts. Codes seen in the schema: `SYSTEM_OFFLINE`,
  `SSO_OFFLINE`.
- `batteries { manufacturer attributes { ratedCapacity ratedPower } state { current { primary secondary } } log { current { stateOfHealth batteryVoltage batteryCurrent cellTemperatureMin cellTemperatureMax cellVoltageMin cellVoltageMax } } }`:
  per battery. `secondary` lists reasons such as `BAT_SOC_POWER_DERATING`.
  `ratedCapacity` is in Wh (27 500 on a 27.5 kWh system, 2026-11-22). The
  cell temperatures and voltages matched the battery's own BMS, read locally
  at the same time.
- `ssos { displayName enabled generation attributes { powerRating } state { active { primary secondary } } }`:
  the solar string optimisers.
- `measurements { latestGridData { timestamp u1 u2 u3 iExtRms1 iExtRms2 iExtRms3 aceActive acePhase1..3 { beforeCorrection correction result } } }`:
  the grid per phase (V and A), whether phase balancing works right now and
  its correction per phase (the app's PhaseBalancingStream shows the same).
- On that ESO 15 system `latestGridData` was empty and the per-phase fields
  of `latestPower` null. The voltage and current per phase come from the
  stream the app's phase balancing view listens to instead:
  `subscription { newPhaseBalanceData(facilityId) { timestamp phase1..3 { gridVoltage result beforeCorrection correction } } }`
  on `/graphql/stream`; `result` is the current at the connection after
  phase balancing. The subscriptions are not in the introspection of
  `/graphql`, so this shape is the app's own, not the schema's.
- `measurements { latestPower { gridPower loadPower pExtD1..3 pExtQ1..3 pLoadD1..3 pLoadQ1..3 } }`:
  power per phase. There are two sets per phase; in the official Cloud API's
  example the `Q` set adds up to the total, so the driver takes `Q` unless
  `D` is the set that adds up on the system. To be confirmed live.
- `optimization { activatedAt enabled limitExportThreshold limitImportThreshold minimumEarnings optimizationVariant tariffOptions }`,
  `location { energyBiddingZone }`, `uiComponents { activeServices }`:
  FerroAI's settings as the app's GetFacilityOptimizationOptions reads them,
  and the outside services that are active (`RemoteApi`, `AncillaryService`).
- `spotPrices { current { price startTimestamp endTimestamp } entries(where: {day: {gte, lte}}) { ... } } misc { currencyCode }`:
  the spot price, as the app's GetSpotPrice. The unit is taken to be the
  currency per kWh; to be confirmed live.
- `measurements { predictions(where: {timestamp: {gte, lt}}, unit: W) { timestamp stateOfCharge solarPower consumptionPower } }`:
  FerroAI's forecast, as the app's overview.
- Not read: `settings { cloudApi { apiKey bindIp allowedRequests } }` (it
  holds the official Cloud API's key) and the per-string power and energy
  (`ssos { power(...) }`, `unitEnergy(...)` per string), whose arguments are
  not yet seen in use.

## Control: configuration schedules

OS 7 has no "do this now" command in the app. The system follows
**configuration schedules**: calendar events, each carrying one EMS
configuration. Type `NORMAL` is a user's (or FerroAI's) schedule, `FALLBACK`
the standard schedule that applies when nothing else does (OS 7.1: "batteries
favour self-use in summer and peak shaving in winter"). Origins seen as
enum values: `USER`, `FERRO_AI`, `SPOT_PRICE_OPTIMIZATION`, `OTHER`.

### Read

```graphql
query GetConfigurationSchedules($facilityId: Int!, $period: SchedulePeriod!) {
  facility(where: {id: {equals: $facilityId}}) { configuration { configurationSchedule {
    schedules(period: $period, where: {scheduleType: {not: {equals: FALLBACK}}}) {
      id contentVersion scheduleType origin generation summary description
      event { iCalendarEventJson { start end rruleStr } }
      action { action }
      configuration { ... on EmsConfigurationV1 { ...EmsV1 } }
    }
  } } }
}
```

The app's `period` is `{start: <start of yesterday>, end: <start of the day
after tomorrow>}` as ISO strings. `GetDefaultConfigurationSchedules` is the
same with `where: {scheduleType: {equals: FALLBACK}}` and `isActive`.

```graphql
fragment EmsV1 on EmsConfigurationV1 {
  systemMode                                   # Default | PeakShaving | SelfConsumption
  systemSettingsPv { pvMode }
  systemSettingsGrid { aceMode aceThreshold limitImport limitExport
                       powerThresholdHigh powerThresholdLow }
  systemSettingsBattery { powerRefCharge powerRefDischarge socRefLow socRefHigh }
}
```

### Write

```graphql
mutation CreateOneNormalConfigurationSchedule($facilityId: Int!, $data: ConfigurationScheduleDataInput!) {
  createOneNormalConfigurationSchedule(where: {facilityId: $facilityId}, data: $data) {
    success schedule { id } message code
  }
}
mutation updateOneConfigurationSchedule($data: ConfigurationScheduleDataInput!,
                                        $where: UpdateConfigurationScheduleWhereInput!) {
  updateOneConfigurationSchedule(data: $data, where: $where) {   # where: {facilityId, id}
    success message code errors { ... on ValidationError { code message path } }
  }
}
mutation RemoveOneNormalConfigurationSchedule($facilityId: Int!, $id: ID!) {
  removeOneNormalConfigurationSchedule(where: {facilityId: $facilityId, id: $id}) { success message code }
}
mutation setDefaultFallbackSchedulesV2($facilityId: Int!) {
  setDefaultFallbackSchedules(where: {facilityId: $facilityId}) { code message success }
}
```

`ConfigurationScheduleDataInput`, as the app's `buildConfigurationScheduleData`
builds it:

```json
{
  "summary": "<title>",
  "description": "<optional>",
  "iCalendarEventJson": {
    "start": "<ISO>", "end": "<ISO>",
    "summary": "<title>", "description": "<optional>",
    "timezone": "<facility timezone>",
    "rrule": {"byweekday": ["MO", "..."], "until": "<ISO, optional>"}
  },
  "configuration": {
    "emsConfigurationV1": {
      "systemMode": "Default",
      "systemSettingsPv": {"pvMode": "<from solarEnabled>"},
      "systemSettingsGrid": {
        "aceMode": "<from phaseBalancingEnabled>", "aceThreshold": 0,
        "limitExport": false, "limitImport": false,
        "powerThresholdHigh": 0, "powerThresholdLow": 0
      },
      "systemSettingsBattery": {
        "powerRefCharge": 3000, "powerRefDischarge": 0,
        "socRefLow": 10, "socRefHigh": 100
      }
    }
  }
}
```

- `rrule` is left out for a one-off event; the end is clamped by the app's
  `clampEventEnd` (*unverified* how).
- Grid thresholds are typed in kW and sent as W (`× 1000`, rounded).
  `limitExport` is always false in peak-shaving mode.
- Battery, manual mode (`systemMode: Default`): charge or discharge power in
  W in the matching `powerRef`, the other 0; battery off = both 0.
  Self-consumption and peak shaving: both `powerRef` 100000 (no limit).
  `socRefLow` 10, `socRefHigh` 100 in every mode.
- The types of `pvMode` and `aceMode` (boolean or enum) are *unverified*;
  the form fields are booleans.

### FerroAI

```graphql
mutation EnableOptimization($facilityId: Int, $optimizationVariant: FerroOptimizationVariant = FERRO_OPTIMIZER_V1) {
  enabledOptimizationControl(data: {optimizationVariant: $optimizationVariant},
                             where: {facilityId: $facilityId}) { code success message }
}
mutation DisableOptimization($facilityId: Int) {
  disableOptimizationControl(where: {facilityId: $facilityId}) { code success message }
}
```

`optimization { enabled activeAction { start end action title } ... }` shows
what FerroAI does now; its actions include `REGULAR_CHARGE`,
`REGULAR_DISCHARGE`, `PEAK_SHAVING`, `VANILLA_SELF_CONSUMPTION`,
`SOLAR_EXPORT_LIMIT`.

### Applying a configuration (portal)

The portal also has a direct, versioned path:
`upsertEmsConfigurationV1(data: EmsConfigurationInputV1!, where: {id})` returning
a `generation`, then `emsConfiguration { poll(generation) { state rejection
status { overallStatus { status } } } }`. A `ConfigurationCapabilityVersionMismatchError
{ expectedVersion }` says the facility wants another version. The schema also
has `SystemModeV2`/`SystemModeV3`, which add `Measurement` and
`AcPowerReference`. Whether a VARIANT_X facility accepts this path is
*unverified*; the user app does not use it.

## The official Cloud API

Ferroamp's documented, read-only API (spec rev C, 2024-10-21). The spec gives
only the path; the host was found by asking with a made-up key (2026-11-22):
`https://portal.ferroamp.com/api` and `https://api.eu.prod.ferroamp.com/api`
both answer, the latter being the app's API host. Without a registered key
the answer is HTTP 401 `"No api authentication could be found. Have you
registred your API at https://portal.ferroamp.com? Else context support."`

- `GET /api?type=<type>&fid=<facility id>&api_key=<40 characters>`; the key is
  activated per facility by Ferroamp support and registered in the EnergyCloud
  portal. 401 also when the key does not match the facility or the calling IP
  address is not allowed; 429 past 300 calls in 24 hours. Every answer carries
  `requests` and `max_requests`.
- `pvdisplay`: `pve` (Wh, lifetime), `pvp` (W, now), `pvetoday` (Wh).
- `totalenergy`: lifetime counters per phase, `wExtProdQ1..3`/`wExtConsQ1..3`
  (grid export/import), `wInvProdQ1..3`/`wInvConsQ1..3`, `wLoadProdQ1..3`/
  `wLoadConsQ1..3`, `wPv`, `wBatProd`, `wBatCons`, each `{val, ts}`. The spec's
  table says kWh, its examples are far larger; to be read off a live answer.
- `mixeddisplay`: `totalenergy` as above, `uidata` (now: `pvPower`, `batPower`,
  `extPower`, `invPower`, `loadPower`, per phase `pLoadQn`, `pInvQn`, `pExtQn`,
  `u1..3` (V), `iExtRms1..3`, `iExtD1..3`, `iExtQ1..3`, `iInvRms1..3`,
  `iInvD1..3`, `iInvQ1..3` (A), `uPos`/`uNeg` (DC link, V)) and `batterydata`
  (`ratedCapacity` 28416 in the example, so Wh, `soc`, `soh`, `ts`).
- `energy`: per hour between `startdate` and `enddate` (`YYYY-MM-DDTHH`, at
  most 32 days), `ep1..3`/`ec1..3` (grid), `ip1..3`/`ic1..3` (inverter),
  `lp1..3`/`lc1..3` (load), `pve`, `ts`, unit `wH`.

It neither controls nor shows the system's state, alarms, battery cells or
solar strings; the app's API does. `tools/cloudapi_probe.py` reads all four
types once (four calls) with a key given at the prompt.

## Remote API (OS 8.0.1)

The app knows a `RemoteApi` ancillary service with providers `Elvy`,
`Varberg1`, `Vattenfall1` (and a redacted one), states
`Disabled`/`PendingEnabledConnect`/`EnabledConnected`/..., resource type
`ASYNCAPI`, configuration errors `InvalidMqttUrl`/`InvalidMqttTopicPrefix`,
a notification `REMOTE_API_ADDED` and a user relation `INTEGRATOR`. It is an
MQTT link to a named flexibility provider, set up on Ferroamp's side, not an
API a third party can switch on. Worth asking Ferroamp whether an integrator
role can be granted for EMS Steward.

## Seen on a live facility (2026-10-27, an ESO 15 facility)

From `tools/probe.py`, read only, client `user-app`:

- **Login works** with the form login; the refresh token is an offline token
  (`refresh_expires_in` 0). Access token lifetime 3600 s.
- **Scopes granted to `user-app`** include `scheduling`, `optimization` and
  `facility` (writable) but only `ems-configuration.readonly`: the app cannot
  apply a configuration directly, it goes through schedules.
- `info.version` an 8.0.1 beta;
  `capabilities.resourceType` `EMS_CONFIGURATION`,
  `SYSTEM_CONTROL_TOPOLOGY_CONFIGURATION`, `REMOTE_API_CONFIGURATION`;
  `uiComponents.usesNewScheduler` true; legacy `emsConfig` is null.
- `emsConfiguration.current` answers with `EmsConfigurationV1`
  (`state: CURRENT`, `status: null`): the configuration in force now.
- **`pvMode` and `aceMode` are booleans.** Self-consumption here is
  `powerThresholdHigh 0, powerThresholdLow -1000000`, both `powerRef` 100000.
- The owner's schedules are three weekly NORMAL ones (`origin: USER`,
  `contentVersion: V1`, `generation: null`); the two FALLBACK schedules are
  "Standardschema för hög/låg solproduktion" (yearly, summer
  self-consumption, winter peak shaving 6235/2771 W).
- **`newPowerData` is in kW, a new sample every 15 s.** `batteryPower`
  positive = discharging (+3.57 with load 3.5, grid 0, no sun), the same sign
  as henricm's MQTT sensor. `ehubPower` is the hub's view (−3.5).
  `gridSign` came as −1 with `gridPower` 0; its meaning is still open.
- **Introspection is on.** The schema has `upsertRemoteApi`,
  `disableRemoteApi`, `replaceFallbackSchedules`, `EmsConfigurationInputV2`
  and a `ConfigurationScheduleAiEnabledError` (schedules are refused while
  FerroAI is on). `ConfigurationScheduleDataInput` =
  `{summary!, description, iCalendarEventJson: ICalendarEventJsonInput,
  configuration!: ScheduleConfigurationInput}`.
- **`measurements.latestPower` is in W, not kW** (`batteryPower 2080`,
  `inverterPower -2050`, `loadPower 2014`, `gridPower -35` while the stream
  said `batteryPower 2`, `loadPower 1.99`). Its `gridPower` is negative for
  export: the battery gave 66 W more than the load and the grid read
  −35 to −69 W.
- The owner's Self-consumption schedule (14:30 local) has `appliedAt`
  13:30:01Z: the cloud marks a schedule applied a second after its start.
  `emsConfiguration.current.generation` is a time-based UUID.
- `emsConfiguration.pending` with nothing pending answers
  `INTERNAL_SERVER_ERROR` on its non-null `generation`; leave that field out.
- `DatetimeRangeQuery` takes `gt`/`gte`/`lt`/`lte`, not `start`/`end`.
- `systemControlTopologyConfiguration` answered `MISSING_DATA`.

## Compared with the local MQTT ExtAPI (2026-11-22)

On a second system, one with the MQTT ExtAPI (1.2.1), a third-party battery
of 30.6 kWh and four solar strings, this driver (0.4.1, read-only, control
off) ran beside the local MQTT integration. Ten samples 30 s apart, at night:

- Live power agrees: median grid 2 009 W locally against 2 003 W from the
  cloud, consumption 1 890 against 1 884 W, battery -77.2 W on both (same
  sign: + = discharging), solar 0 on both. The cloud's sample is 25 to 40 s
  old when read, so single samples can differ by several hundred watts while
  the house load moves; each cloud value matches the local one about 30 s
  earlier.
- SoC (57 %) and rated capacity (30.6 kWh, the hub's 30 600 Wh) agree.
- Today's energy: grid import 98.67 kWh locally against 98.15, consumption
  78.45 against 77.95, solar 1.23 on both. Export 1.28 against 0.51: the hub
  counts each phase on its own; the difference fits the cloud netting the
  phases, as the meter does (not confirmed).
- Battery energy today: 30.97 kWh charged and 11.64 discharged locally, 0.00
  and 0.00 from the cloud. 0.5.0 shows a quantity the cloud gives no value
  for as unknown; whether this system's cloud data is null or zero is not yet
  known.
- The configuration in force and the active schedule are empty on this
  system: the app's configuration schedules (OS 7 and later) do not cover it,
  so control through the cloud does not apply. It is controlled locally, as
  it should be.

## Schedule test (2026-10-27, an ESO 15 facility, schedules made in the app)

`tools/monitor.py` read every 10 s while the owner laid out one-off
schedules on top of his weekly Self-consumption schedule (14:30 to 23:00):
17:30 to 17:45 manual charge 2 kW, 17:45 to 18:00 manual charge 1 kW, and
(after the finding below) 18:15 to 23:00 Self-consumption.

| Local time | `current` configuration | Battery (W, + discharging) | Grid (W) |
|---|---|---|---|
| 17:29:45 | SelfConsumption | +2731 | −83 |
| 17:30:00 | Default, charge 2000 (applied 17:30:01) | +2648 | −41 |
| 17:30:15 | | +279 | +2889 |
| 17:30:30 | | −1958 | +4616 |
| 17:45:00 | Default, charge 1000 (applied 17:45:00) | −1930 | +3914 |
| 17:45:30 | | −962 | +2865 |
| 18:00 to 18:15 | **still Default, charge 1000** | −963 | +2100 |
| 18:15:00 | SelfConsumption (applied 18:15:00) | −963 | +2172 |
| 18:15:30 | | +429 | +832 |
| 18:16:00 | | +2308 | −153 |

- **A schedule takes effect at its start.** `emsConfiguration.current`
  changes within a second of the start (`appliedAt` = start + 0 to 1 s),
  and a fixed battery setpoint is reached 15 to 30 s later. Self-consumption
  settles on the house load within about a minute.
- **A one-off schedule wins over a recurring one.** Overlap is allowed:
  the cloud moved the owner's Self-consumption `intendedStartAt` to the
  test schedule's end without being asked.
- **The end of a schedule does nothing.** At 18:00 the 1 kW schedule stayed
  `isActive` and in force, and the overlapped Self-consumption did *not*
  resume: its next `intendedStartAt` was tomorrow 14:30. The configuration
  of the last schedule that *started* stands until the next start, here
  00:15. A controller that stops writing leaves its last command in
  force for hours.
- A fixed charge reference is met within 2 to 4 % on the AC side
  (2000 W gave −1958 to −1971 W, 1000 W gave −962 W).
- `emsConfiguration.pending` never held anything in 212 reads: the cloud
  writes `current` directly at a schedule's start.
- The app offers start and end times on whole quarter-hours only (whether
  the API does too is untested), and no name of one's own: a manual
  schedule is called "Manual".

### What this means for control

The driver cannot rely on a schedule running out. Every command has to be
followed by a schedule that **starts** the owner's normal configuration
again: when EMS hands back (setpoint 0), and also as a dead man's switch
while it commands, by keeping a "return to normal" schedule a short while
ahead and moving it on at every write. If Home Assistant stops, that
schedule starts and the system goes back to its own configuration. "The
owner's normal configuration" is the recurring schedule that would be in
force now, else the fallback.

### How the driver writes (0.2)

`control.py` writes what the paragraphs above call for, and nothing else:

- A setpoint `P` (EMS's sign, + charges) creates the return first: a one-off
  schedule from `T + 10 min` with the owner's `EmsConfigurationV1`. Then it
  creates the manual schedule from `T` to `T + 10 min` (`systemMode: Default`,
  `powerRefCharge` or `powerRefDischarge` = |P| up to the rated power, the other
  0, SoC 10 to 100). `T` is the first whole minute at least 30 s ahead.
- The owner's configuration is the one `emsConfiguration.current` shows while no
  command stands. While one does, it is the configuration the driver's last
  return schedule carries, so a restart does not lose it.
- A renewal comes every 300 s while a command stands. It creates the new pair,
  then removes what is no longer needed: schedules not yet started, and earlier
  ones. It never removes the schedule in force, the one that started last, so the
  cloud never falls back to an older one.
- `P = 0` creates a return from `T` and removes the rest. Nothing is written when
  there is nothing to undo.
- FerroAI on, or a system without the new scheduler, refuses the write before
  anything is created.

The driver relies on these, none of which a live run has confirmed yet: a
schedule may start on a whole minute (the app offers quarter-hours only); a
schedule starting 30 to 90 s ahead is accepted; removing a schedule that is not
in force changes nothing; a discharge reference is obeyed the way the charge
reference is (the schedule test saw charging only).

## Still open

1. Whether the API takes start and end times off the quarter-hour.
2. How quickly an edit of a schedule already in force reaches the battery
   (the test used two schedules back to back instead).
3. Discharge with export (forced discharge above the house load).
