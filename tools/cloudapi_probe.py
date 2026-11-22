"""Read-only probe of Ferroamp's official Cloud API (spec rev C, 2024-10-21).

The Cloud API is the documented, read-only one: ``GET /api?type=...`` with a
40-character key that Ferroamp support activates per facility and that is
registered in the EnergyCloud portal (https://portal.ferroamp.com). At most
300 calls a day; a key can also be tied to IP addresses. It is not the API the
app uses (see PROTOCOL.md); this probe is for comparing the two, and both with
the local MQTT ExtAPI where a system has one.

One run makes four calls: pvdisplay, totalenergy, mixeddisplay and the last
day's energy per hour. The key is read with getpass (or from the environment
variable FERROAMP_API_KEY), never printed and never saved; the answers are
written to a JSON file without it.

    python3 tools/cloudapi_probe.py 12345 [--out cloudapi.json] [--host portal.ferroamp.com]
"""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HOSTS = ("portal.ferroamp.com", "api.eu.prod.ferroamp.com")


def call(host: str, key: str, fid: int, kind: str, **params: str) -> tuple[int, object]:
    query = urllib.parse.urlencode({"type": kind, "fid": fid, "api_key": key, **params})
    req = urllib.request.Request(f"https://{host}/api?{query}", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", "replace")
        try:
            return err.code, json.loads(body)
        except ValueError:
            return err.code, body[:500]


def val(block: object) -> object:
    """A field's value: Ferroamp writes most as {"val": .., "ts": ..}."""
    return block.get("val") if isinstance(block, dict) else block


def summary(answers: dict[str, dict]) -> None:
    mixed = answers.get("mixeddisplay", {}).get("body")
    if not isinstance(mixed, dict) or "data" not in mixed:
        return
    data = mixed["data"]
    ui = data.get("uidata", {})
    print("\nNow (mixeddisplay uidata), Ferroamp's signs:")
    for key, label in (("pvPower", "solar W"), ("loadPower", "load W"), ("extPower", "grid W"),
                       ("batPower", "battery W"), ("invPower", "inverter W")):
        print(f"  {label:12} {val(ui.get(key))}")
    for n in (1, 2, 3):
        print(f"  L{n}: {val(ui.get(f'u{n}'))} V, grid {val(ui.get(f'iExtRms{n}'))} A, "
              f"grid {val(ui.get(f'pExtQ{n}'))} W, load {val(ui.get(f'pLoadQ{n}'))} W")
    print(f"  DC link: +{val(ui.get('uPos'))} V / {val(ui.get('uNeg'))} V")
    stamp = (ui.get("pvPower") or {}).get("ts") if isinstance(ui.get("pvPower"), dict) else None
    print(f"  measured at {stamp}")
    print(f"Battery (batterydata): {data.get('batterydata')}")
    total = data.get("totalenergy", {})
    print("Energy counters (totalenergy):")
    for key in sorted(total):
        print(f"  {key:12} {val(total[key])}")
    print(f"Calls used today: {mixed.get('requests')} of {mixed.get('max_requests')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("facility_id", type=int)
    parser.add_argument("--out", default="cloudapi.json")
    parser.add_argument("--host", default=HOSTS[0], choices=HOSTS)
    args = parser.parse_args()

    key = os.environ.get("FERROAMP_API_KEY") or getpass.getpass("Cloud API key (not shown): ")
    key = key.strip()
    if len(key) != 40:
        print(f"The key should be 40 characters; this one is {len(key)}.", file=sys.stderr)

    now = dt.datetime.now(dt.UTC).replace(minute=0, second=0, microsecond=0)
    calls = {
        "pvdisplay": {},
        "totalenergy": {},
        "mixeddisplay": {},
        "energy": {"resolution": "hour", "startdate": (now - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H"),
                   "enddate": now.strftime("%Y-%m-%dT%H")},
    }
    answers: dict[str, dict] = {}
    for kind, params in calls.items():
        status, body = call(args.host, key, args.facility_id, kind, **params)
        answers[kind] = {"status": status, "params": params, "body": body}
        print(f"{kind:13} HTTP {status}")
        if status == 401 and kind == "pvdisplay":
            print(f"  {body}\nStopping: the key is not accepted for this facility (or from this IP address).")
            break
        if status == 429:
            print("  Over the daily quota of 300 calls; stopping.")
            break

    record = {"read_at": dt.datetime.now(dt.UTC).isoformat(), "host": args.host,
              "facility_id": args.facility_id, "answers": answers}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, ensure_ascii=False)
    print(f"\nWritten to {args.out} (the key is not in it).")
    summary(answers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
