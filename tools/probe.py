"""Read-only probe of a Ferroamp facility through the user app's cloud API.

Logs in the way the Ferroamp user app does (Keycloak client ``user-app``,
PKCE), runs the app's own read-only GraphQL queries against
api.eu.prod.ferroamp.com, listens to the live power stream for a few
seconds, and writes what comes back to a JSON file. See PROTOCOL.md.

Nothing is written to the facility: no mutation is ever sent. The password
is read with getpass and never printed; tokens are never printed or saved,
and the session is logged out at the end.

    python3 tools/probe.py 12345 [--email you@example.com] [--out probe.json]
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import getpass
import hashlib
import html
import http.cookiejar
import json
import re
import secrets
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

AUTH = "https://auth.eu.prod.ferroamp.com/realms/public/protocol/openid-connect"
CLIENTS = {
    "app": ("user-app", "ferroampuser://app/auth/login", "openid offline_access"),
    "portal": ("portal-frontend-ng-production", "https://portal.ferroamp.com/", "openid"),
}
GRAPHQL = "https://api.eu.prod.ferroamp.com/graphql"
STREAM = "https://api.eu.prod.ferroamp.com/graphql/stream"
UA = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Mobile Safari/537.36"

EMS_V1 = """
  ... on EmsConfigurationV1 {
    __typename systemMode
    systemSettingsPv { pvMode }
    systemSettingsGrid { aceMode aceThreshold limitImport limitExport powerThresholdHigh powerThresholdLow }
    systemSettingsBattery { powerRefCharge powerRefDischarge socRefHigh socRefLow }
  }
"""

# The app's own documents (PROTOCOL.md), trimmed of names, addresses and
# users. Each runs on its own, so one the schema refuses does not hide the
# answers to the others.
QUERIES: dict[str, str] = {
    "facility": """
query ($id: Int!) { facility(where: {id: {equals: $id}}) {
  id timezone createdAt installedOn info { version }
  myRelation { relation }
  capacity { installedPv }
  topology { system { aceThreshold } }
  configuration { capabilities { resourceType } }
  uiComponents {
    activeServices usesNewScheduler
    flowChart { enabledComponents }
    ferroAi { available description }
    capacities {
      ... on UIMainFuseCapacity { __typename capacity unit }
      ... on UIMaxInverterPowerCapacity { __typename capacity unit }
      ... on UIEnergyStorageRatedPowerCapacity { __typename capacity unit }
      ... on UIEnergyStorageRatedCapacity { __typename capacity unit }
      ... on UIMaxInverterCurrentCapacity { __typename capacity unit }
    }
  }
} }""",
    "connectivity": """
query ($id: Int!) { facility(where: {id: {equals: $id}}) {
  connectivity { isOnline lastSeenAt offlineSecondsFromNow onlineUpdatePollAt }
  maintenance { ongoingSystemUpgrade }
} }""",
    "schedules": """
query ($id: Int!, $period: SchedulePeriod!) { facility(where: {id: {equals: $id}}) {
  configuration { configurationSchedule {
    schedules(period: $period, where: {scheduleType: {not: {equals: FALLBACK}}}) {
      id contentVersion scheduleType origin generation summary description
      event { iCalendarEventJson { start end rruleStr } }
      action { action }
      configuration { %s }
    }
  } }
} }""" % EMS_V1,
    "fallback_schedules": """
query ($id: Int!) { facility(where: {id: {equals: $id}}) {
  configuration { configurationSchedule {
    schedules(where: {scheduleType: {equals: FALLBACK}}) {
      id contentVersion scheduleType origin generation summary isActive
      event { iCalendarEventJson { start end rruleStr rrule { freq byweekday until } } }
      action { action }
      configuration { %s }
    }
  } }
} }""" % EMS_V1,
    "ems_configuration_current": """
query ($id: Int) { facility(where: {id: {equals: $id}}) {
  configuration { emsConfiguration { current {
    name state
    status { overallStatus { status } }
    config { __typename %s }
  } } }
} }""" % EMS_V1,
    "ems_config_legacy": """
query ($id: Int!) { facility(where: {id: {equals: $id}}) {
  emsConfig { mode pv { mode }
    grid { ace { mode threshold } thresholds { low high } limitImport limitExport }
    battery { powerRef { charge discharge } socRef { low high } } }
} }""",
    "optimization": """
query ($id: Int) { facility(where: {id: {equals: $id}}) {
  optimization { activatedAt enabled limitExportThreshold limitImportThreshold
    minimumEarnings optimizationVariant tariffOptions updatedAt
    activeAction { start end action title description } }
  location { energyBiddingZone }
  misc { currencyCode }
} }""",
    "power_and_soc": """
query ($id: Int!, $timestamp: DatetimeRangeQuery!) { facility(where: {id: {equals: $id}}) {
  measurements {
    lastAverage: power(resolution: Minutely, timeRange: $timestamp, last: 1) {
      timestamp pvPower loadPower inverterPower gridPower batteryPower
    }
    currentStateOfCharge { stateOfCharge timestamp }
  }
} }""",
    "energy_today": """
query ($id: Int!, $range: DatetimeRangeQuery!) { facility(where: {id: {equals: $id}}) {
  measurements {
    energy(period: {dateTime: {resolution: Hourly, range: $range}}, unit: Wh, dataSeriesType: Relative) {
      ... on SystemEnergyDateTime { timeperiodStart }
      pvProduced gridImport gridExport consumptionL1 consumptionL2 consumptionL3
    }
  }
} }""",
    "topology": """
query ($id: Int!) { facility(where: {id: {equals: $id}}) {
  systemControlTopologyConfiguration { transTs data {
    battery { id metadata { name } terminals { id attributes { manufacturer pid } } }
    pv { id metadata { name } terminals { id attributes { pid } } }
    grid { id metadata { name } terminals { id attributes { pid } } }
    evse { id metadata { name } terminals { id attributes { pid } } }
  } }
} }""",
    # Introspection is often off in production. If it answers, it settles
    # the input types the writes need (PROTOCOL.md, open questions).
    "schema_types": """
query { __schema {
  mutationType { fields { name } }
  types { name kind }
} }""",
    "schedule_input": """
query { __type(name: "ConfigurationScheduleDataInput") {
  inputFields { name type { kind name ofType { kind name ofType { name } } } }
} }""",
}

# The standard graphql-js introspection query: the whole schema, no facility
# data, written to its own file so the input types can be read offline.
FULL_INTROSPECTION = """
query IntrospectionQuery {
  __schema {
    queryType { name } mutationType { name } subscriptionType { name }
    types { ...FullType }
  }
}
fragment FullType on __Type {
  kind name description
  fields(includeDeprecated: true) {
    name description args { ...InputValue } type { ...TypeRef } isDeprecated deprecationReason
  }
  inputFields { ...InputValue }
  interfaces { ...TypeRef }
  enumValues(includeDeprecated: true) { name description isDeprecated deprecationReason }
  possibleTypes { ...TypeRef }
}
fragment InputValue on __InputValue { name description type { ...TypeRef } defaultValue }
fragment TypeRef on __Type {
  kind name ofType { kind name ofType { kind name ofType { kind name ofType {
    kind name ofType { kind name ofType { kind name ofType { kind name } } } } } } }
}
"""

TYPE_HINT = re.compile(
    r"Ems|Schedul|Capabilit|Configuration|Optimi|SystemMode|PvMode|AceMode|Remote|Command",
    re.I,
)


def pkce() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D401
        return None


def _open(opener, req: urllib.request.Request):
    """Open without following redirects; a 3xx comes back as the response."""
    try:
        return opener.open(req, timeout=30)
    except urllib.error.HTTPError as err:
        if 300 <= err.code < 400:
            return err
        raise


def _form_post(url: str, fields: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(fields).encode(),
        headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
    return json.loads(body) if body else {}


def login(client: str, email: str, password: str) -> dict:
    client_id, redirect_uri, scope = CLIENTS[client]
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), _NoRedirect())
    verifier, challenge = pkce()
    state = secrets.token_hex(16)
    url = f"{AUTH}/auth?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "state": state,
        "nonce": secrets.token_hex(16),
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    page = _open(opener, urllib.request.Request(url, headers={"User-Agent": UA}))
    body = page.read().decode()
    action = re.search(r'<form[^>]*id="kc-form-login"[^>]*action="([^"]+)"', body)
    if not action:
        sys.exit(f"Could not find the login form (HTTP {page.status}); has the login page changed?")
    form = {
        m.group(1): html.unescape(m.group(2) or "")
        for m in re.finditer(r'<input[^>]*name="([^"]+)"(?:[^>]*value="([^"]*)")?', body)
    }
    form.pop("rememberMe", None)
    form.update({"username": email, "password": password})
    post = urllib.request.Request(
        html.unescape(action.group(1)),
        data=urllib.parse.urlencode(form).encode(),
        headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"},
    )
    resp = _open(opener, post)
    location = resp.headers.get("Location") or ""
    if resp.status not in (302, 303) or "code=" not in location:
        text = resp.read().decode(errors="replace")
        hint = re.search(r'id="input-error[^"]*"[^>]*>\s*([^<]+)<', text)
        sys.exit(
            f"Login did not return a code (HTTP {resp.status})"
            + (f": {hint.group(1).strip()}" if hint else "; an extra step (OTP?) or a wrong password.")
        )
    parsed = urllib.parse.urlparse(location)
    params = urllib.parse.parse_qs(parsed.query or parsed.fragment)
    if params.get("state", [None])[0] != state:
        sys.exit("State mismatch in the login redirect")
    return _form_post(f"{AUTH}/token", {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code": params["code"][0],
        "code_verifier": verifier,
    })


def logout(client: str, tokens: dict) -> None:
    try:
        _form_post(f"{AUTH}/logout", {
            "client_id": CLIENTS[client][0],
            "refresh_token": tokens.get("refresh_token", ""),
        })
    except (urllib.error.URLError, json.JSONDecodeError):
        pass


def graphql(token: str, query: str, variables: dict) -> dict:
    req = urllib.request.Request(
        GRAPHQL,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"User-Agent": UA, "Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as err:
        return {"http_error": err.code, "body": err.read().decode(errors="replace")[:2000]}


def sample_stream(token: str, fid: int, seconds: float) -> list:
    """Collect newPowerData events from the SSE stream for a few seconds."""
    query = (
        "subscription ($facilityId: FacilityID!) { newPowerData(facilityId: $facilityId) "
        "{ timestamp loadPower pvPower gridPower gridSign batteryPower ehubPower } }"
    )
    req = urllib.request.Request(
        STREAM,
        data=json.dumps({"query": query, "variables": {"facilityId": str(fid)}}).encode(),
        headers={
            "User-Agent": UA,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {token}",
        },
    )
    events: list = []
    deadline = time.monotonic() + seconds
    try:
        with urllib.request.urlopen(req, timeout=seconds + 5) as r:
            try:
                r.fp.raw._sock.settimeout(2)  # type: ignore[attr-defined]
            except AttributeError:
                pass
            while time.monotonic() < deadline:
                try:
                    line = r.readline()
                except (socket.timeout, TimeoutError):
                    continue
                if not line:
                    break
                line = line.decode(errors="replace").strip()
                if line.startswith("data:"):
                    try:
                        events.append(json.loads(line[5:].strip()))
                    except json.JSONDecodeError:
                        events.append({"raw": line[:500]})
    except urllib.error.HTTPError as err:
        return [{"http_error": err.code, "body": err.read().decode(errors="replace")[:2000]}]
    except (urllib.error.URLError, OSError) as err:
        events.append({"error": str(err)})
    return events


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("facility_id", type=int)
    ap.add_argument("--email", help="asked for when left out")
    ap.add_argument("--client", choices=sorted(CLIENTS), default="app")
    ap.add_argument("--stream-seconds", type=float, default=20)
    ap.add_argument("--out", default="probe.json")
    ap.add_argument("--schema-out", default="schema.json")
    args = ap.parse_args()

    email = args.email or input("Ferroamp e-mail: ").strip()
    password = getpass.getpass("Ferroamp password (not shown): ")
    tokens = login(args.client, email, password)
    del password
    token = tokens["access_token"]
    print(f"Logged in as client {CLIENTS[args.client][0]}; "
          f"access token {tokens.get('expires_in')} s, refresh {tokens.get('refresh_expires_in')} s "
          f"(0 = offline token)")

    now = dt.datetime.now(dt.timezone.utc)
    midnight = now.astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    variables = {
        "schedules": {"period": {
            "start": (midnight - dt.timedelta(days=1)).astimezone(dt.timezone.utc).isoformat(),
            "end": (midnight + dt.timedelta(days=2)).astimezone(dt.timezone.utc).isoformat(),
        }},
        "power_and_soc": {"timestamp": {
            "start": (now - dt.timedelta(minutes=10)).isoformat(), "end": now.isoformat(),
        }},
        "energy_today": {"range": {
            "start": midnight.astimezone(dt.timezone.utc).isoformat(), "end": now.isoformat(),
        }},
    }

    result: dict = {
        "facility_id": args.facility_id,
        "client": CLIENTS[args.client][0],
        "token_lifetimes": {k: tokens.get(k) for k in ("expires_in", "refresh_expires_in", "scope")},
    }
    try:
        for name, query in QUERIES.items():
            if name in ("schema_types", "schedule_input"):
                vars_ = {}
            else:
                vars_ = {"id": args.facility_id, **variables.get(name, {})}
            answer = graphql(token, query, vars_)
            if name == "schema_types" and answer.get("data"):
                schema = answer["data"]["__schema"]
                answer = {
                    "mutations": [f["name"] for f in (schema.get("mutationType") or {}).get("fields", [])],
                    "types": sorted(t["name"] for t in schema["types"] if TYPE_HINT.search(t["name"])),
                }
            result[name] = answer
            ok = "errors" not in answer and "http_error" not in answer
            print(f"{name:28s} {'ok' if ok else 'ERROR'}")
        schema = graphql(token, FULL_INTROSPECTION, {})
        with open(args.schema_out, "w") as fh:
            json.dump(schema, fh, indent=1)
        print(f"{'full schema':28s} {'ok' if schema.get('data') else 'ERROR'} -> {args.schema_out}")
        print(f"listening to the power stream for {args.stream_seconds:.0f} s ...")
        result["stream"] = sample_stream(token, args.facility_id, args.stream_seconds)
        print(f"{'stream':28s} {len(result['stream'])} events")
    finally:
        logout(args.client, tokens)

    with open(args.out, "w") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
    print("Written to", args.out, "(no tokens or password in it)")


if __name__ == "__main__":
    main()
