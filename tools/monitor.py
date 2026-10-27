"""Read-only log of a facility while schedules are tried in the Ferroamp app.

Every --every seconds it reads, through the user app's cloud API, the power
and SoC, the configuration in force, every schedule
in today's window with its active flag and applied time, and FerroAI's
state, and prints one line per read. Each read is also appended to a JSON
lines file for later analysis. At the start it listens to the live stream
for a few seconds, to compare its units with the polled power.

It sends no mutation: the schedules themselves are made by hand in the
app. Stops with Ctrl-C or after --minutes; logs out at the end.

    python3 tools/monitor.py 12345 [--every 10] [--minutes 120] [--out monitor.jsonl]
"""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import json
import time
from zoneinfo import ZoneInfo

from probe import AUTH, CLIENTS, _form_post, graphql, login, logout, sample_stream

EMS_V1 = """
  ... on EmsConfigurationV1 {
    systemMode
    systemSettingsPv { pvMode }
    systemSettingsGrid { aceMode aceThreshold limitImport limitExport powerThresholdHigh powerThresholdLow }
    systemSettingsBattery { powerRefCharge powerRefDischarge socRefHigh socRefLow }
  }
"""

READ = """
query ($id: Int!, $period: SchedulePeriod!) { facility(where: {id: {equals: $id}}) {
  connectivity { isOnline lastSeenAt }
  measurements {
    latestPower { timestamp batteryPower gridPower loadPower pvPower inverterPower }
    currentStateOfCharge { stateOfCharge timestamp }
  }
  optimization { enabled activeAction { action start end } }
  configuration {
    emsConfiguration {
      current { generation state verb status { overallStatus { status failureReason } } config { %s } }
    }
    configurationSchedule {
      schedules(period: $period, includeAll: true) {
        id summary scheduleType origin isActive appliedAt configuredAt intendedStartAt
        nextIntendedStartAt generation contentVersion
        event { iCalendarEventJson { start end rruleStr } }
        configuration { %s }
      }
    }
  }
} }""" % (EMS_V1, EMS_V1)

TZ = ZoneInfo("Europe/Stockholm")


def describe(cfg: dict | None) -> str:
    """A configuration in a few words: mode and battery references."""
    if not cfg:
        return "-"
    bat = cfg.get("systemSettingsBattery") or {}
    grid = cfg.get("systemSettingsGrid") or {}
    words = [str(cfg.get("systemMode"))]
    charge, discharge = bat.get("powerRefCharge"), bat.get("powerRefDischarge")
    if cfg.get("systemMode") == "Default":
        words.append(f"ladda {charge} W" if charge else (f"ur {discharge} W" if discharge else "batteri av"))
    if grid.get("limitImport") or cfg.get("systemMode") == "PeakShaving":
        words.append(f"tak {grid.get('powerThresholdHigh')}/{grid.get('powerThresholdLow')} W")
    return " ".join(words)


def w(value) -> str:
    """latestPower is already W (the stream is kW)."""
    return "?" if value is None else f"{value:+.0f}"


def summarize(sample: dict, previous: dict | None) -> tuple[str, dict]:
    fac = (sample.get("data") or {}).get("facility") or {}
    m = fac.get("measurements") or {}
    p = m.get("latestPower") or {}
    soc = (m.get("currentStateOfCharge") or {}).get("stateOfCharge")
    ems = ((fac.get("configuration") or {}).get("emsConfiguration") or {})
    cur, pend = ems.get("current") or {}, ems.get("pending") or {}
    scheds = (((fac.get("configuration") or {}).get("configurationSchedule") or {}).get("schedules") or [])
    active = [s for s in scheds if s.get("isActive")]
    key = {
        "gen": cur.get("generation"),
        "cfg": describe(cur.get("config")),
        "pending": describe(pend.get("config")) if pend else None,
        "active": sorted(s.get("id") for s in active),
        "ids": sorted(s.get("id") for s in scheds),
        "ai": (fac.get("optimization") or {}).get("enabled"),
    }
    now = dt.datetime.now(TZ).strftime("%H:%M:%S")
    line = (f"{now}  SoC {soc if soc is not None else '?'}%  batt {w(p.get('batteryPower'))} W  "
            f"nät {w(p.get('gridPower'))} W  last {w(p.get('loadPower'))} W  sol {w(p.get('pvPower'))} W"
            f"  (mätt {(p.get('timestamp') or '?')[11:19]}Z)\n"
            f"          gäller: {key['cfg']}  [{cur.get('state')} gen {str(cur.get('generation'))[:8]}]"
            + (f"  väntar: {describe(pend.get('config'))} [{pend.get('state')}]" if pend else "")
            + "\n          aktiva scheman: "
            + (", ".join(f"{s.get('summary')} ({s.get('scheduleType')}, applied "
                         f"{(s.get('appliedAt') or '-')[11:19]})" for s in active) or "inga"))
    if sample.get("errors"):
        line += f"\n          FEL: {[e.get('message') for e in sample['errors']][:2]}"
    if previous is not None:
        changes = [k for k in key if key[k] != previous.get(k)]
        if changes:
            line = "*** ÄNDRING: " + ", ".join(changes) + "\n" + line
    return line, key


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("facility_id", type=int)
    ap.add_argument("--email", help="asked for when left out")
    ap.add_argument("--every", type=float, default=10)
    ap.add_argument("--minutes", type=float, default=120)
    ap.add_argument("--out", default="monitor.jsonl")
    args = ap.parse_args()

    email = args.email or input("Ferroamp e-mail: ").strip()
    password = getpass.getpass("Ferroamp password (not shown): ")
    tokens = login("app", email, password)
    del password
    token, token_at = tokens["access_token"], time.monotonic()
    print("Inloggad. Läser var", args.every, "s i högst", args.minutes, "min. Avbryt med Ctrl-C.")

    stream = sample_stream(token, args.facility_id, 8)
    print("Strömmen (kW) under 8 s:", [e.get("data", {}).get("newPowerData") for e in stream[:2]])

    previous = None
    deadline = time.monotonic() + args.minutes * 60
    try:
        with open(args.out, "a") as fh:
            fh.write(json.dumps({"stream_start": stream}) + "\n")
            while time.monotonic() < deadline:
                if time.monotonic() - token_at > 3000:
                    fresh = _form_post(f"{AUTH}/token", {
                        "grant_type": "refresh_token",
                        "client_id": CLIENTS["app"][0],
                        "refresh_token": tokens["refresh_token"],
                    })
                    tokens.update(fresh)
                    token, token_at = tokens["access_token"], time.monotonic()
                midnight = dt.datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
                period = {
                    "start": (midnight - dt.timedelta(days=1)).astimezone(dt.UTC).isoformat(),
                    "end": (midnight + dt.timedelta(days=2)).astimezone(dt.UTC).isoformat(),
                }
                sample = graphql(token, READ, {"id": args.facility_id, "period": period})
                fh.write(json.dumps({"at": dt.datetime.now(dt.UTC).isoformat(), "sample": sample},
                                    ensure_ascii=False) + "\n")
                fh.flush()
                line, previous = summarize(sample, previous)
                print(line, flush=True)
                time.sleep(args.every)
    except KeyboardInterrupt:
        print("\nAvbruten.")
    finally:
        logout("app", tokens)
    print("Loggen ligger i", args.out)


if __name__ == "__main__":
    main()
