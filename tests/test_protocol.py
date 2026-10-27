"""The protocol module: login pieces, answer parsing, units and signs."""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import urllib.parse
from zoneinfo import ZoneInfo

import pytest

from custom_components.ferroamp_cloud_control import protocol

LOGIN_PAGE = """
<html><body>
<form id="kc-form-login" onsubmit="login.disabled = true; return true;"
      action="https://auth.example/realms/public/login-actions/authenticate?session_code=abc&amp;execution=e1&amp;client_id=user-app&amp;tab_id=t1"
      method="post">
  <input tabindex="1" id="username" name="username" value="" type="text" autofocus />
  <input tabindex="2" id="password" name="password" type="password" />
  <input tabindex="3" id="rememberMe" name="rememberMe" type="checkbox">
  <input type="hidden" id="id-hidden-input" name="credentialId" value="cred&amp;1"/>
  <input tabindex="4" name="login" id="kc-login" type="submit" value="Sign In"/>
</form>
</body></html>
"""


def test_pkce_challenge_is_s256_of_the_verifier():
    verifier, challenge = protocol.pkce_pair()
    assert len(verifier) == 43
    digest = hashlib.sha256(verifier.encode()).digest()
    assert challenge == base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def test_auth_url_is_the_user_apps():
    url = protocol.auth_url("https://auth.example/oidc", "s1", "n1", "c1")
    parsed = urllib.parse.urlparse(url)
    q = urllib.parse.parse_qs(parsed.query)
    assert parsed.path == "/oidc/auth"
    assert q["client_id"] == ["user-app"]
    assert q["redirect_uri"] == ["ferroampuser://app/auth/login"]
    assert q["scope"] == ["openid offline_access"]
    assert q["code_challenge_method"] == ["S256"]
    assert q["state"] == ["s1"] and q["code_challenge"] == ["c1"]


def test_login_form_fills_credentials_and_keeps_hidden_fields():
    action, fields = protocol.login_form(LOGIN_PAGE, "a@example.com", "pw")
    assert action.endswith("execution=e1&client_id=user-app&tab_id=t1")
    assert fields["username"] == "a@example.com"
    assert fields["password"] == "pw"
    assert fields["credentialId"] == "cred&1"
    assert "rememberMe" not in fields


def test_login_form_missing_raises():
    with pytest.raises(protocol.LoginError):
        protocol.login_form("<html>maintenance</html>", "a", "b")


def test_page_error_reads_keycloaks_message():
    page = '<span id="input-error" class="pf-c-form__helper-text" aria-live="polite">\n  Invalid username or password.\n</span>'
    assert protocol.page_error(page) == "Invalid username or password."
    assert protocol.page_error(LOGIN_PAGE) is None


def test_code_from_redirect():
    loc = "ferroampuser://app/auth/login?state=s1&session_state=x&iss=y&code=the-code"
    assert protocol.code_from_redirect(loc, "s1") == "the-code"
    assert protocol.code_from_redirect("ferroampuser://app/auth/login#state=s1&code=c2", "s1") == "c2"
    with pytest.raises(protocol.LoginError):
        protocol.code_from_redirect(loc, "other")
    with pytest.raises(protocol.LoginError):
        protocol.code_from_redirect(
            "ferroampuser://app/auth/login?error=access_denied&error_description=nope&state=s1", "s1")


def test_data_of_raises_only_without_data():
    with pytest.raises(protocol.GraphQLError) as err:
        protocol.data_of({"errors": [{"message": "no", "extensions": {"code": "UNAUTHENTICATED"}}]})
    assert err.value.unauthenticated
    partial = protocol.data_of({"errors": [{"message": "MISSING_DATA"}], "data": {"facility": {"a": 1}}})
    assert partial == {"facility": {"a": 1}}
    assert protocol.data_of({"data": None}) == {}


# Shaped like what a live facility answered on 2026-10-27 (PROTOCOL.md).
LIVE = {
    "facility": {
        "connectivity": {"isOnline": True, "lastSeenAt": "2026-10-27T15:33:45.370Z"},
        "maintenance": {"ongoingSystemUpgrade": False},
        "measurements": {
            "latestPower": {
                "timestamp": "2026-10-27T15:34:30.000Z",
                "batteryPower": 3570, "gridPower": 120, "loadPower": 3500,
                "pvPower": 0, "inverterPower": -3500,
            },
            "currentStateOfCharge": {"stateOfCharge": 54.0, "timestamp": "2026-10-27T15:34:00.000Z"},
        },
        "configuration": {"emsConfiguration": {"current": {
            "generation": "g7", "state": "CURRENT",
            "config": {
                "systemMode": "SelfConsumption",
                "systemSettingsPv": {"pvMode": True},
                "systemSettingsGrid": {"aceMode": True, "aceThreshold": 15, "limitImport": False,
                                       "limitExport": False, "powerThresholdHigh": 0,
                                       "powerThresholdLow": -1000000},
                "systemSettingsBattery": {"powerRefCharge": 100000, "powerRefDischarge": 100000,
                                          "socRefHigh": 100, "socRefLow": 10},
            },
        }}},
        "optimization": {"enabled": False, "activeAction": None},
    }
}


def test_parse_live_reads_w_and_keeps_ferroamps_signs():
    live = protocol.parse_live(LIVE)
    assert live.battery_w == 3570.0      # + = discharging, as the MQTT integration
    assert live.grid_w == 120.0          # + = import
    assert live.load_w == 3500.0
    assert live.solar_w == 0.0
    assert live.inverter_w == -3500.0
    assert live.soc == 54.0
    assert live.online is True
    assert live.ferroai_enabled is False
    assert live.config_state == "CURRENT"
    assert live.config.mode == "self_consumption"
    assert live.config.pv_on is True and live.config.ace_on is True
    assert live.config.threshold_low_w == -1000000
    assert live.config.charge_ref_w == 100000


def test_live_age():
    live = protocol.parse_live(LIVE)
    now = dt.datetime(2026, 10, 27, 15, 35, 30, tzinfo=dt.UTC)
    assert live.age_s(now) == 60.0
    assert protocol.Live().age_s(now) is None


def test_parse_live_survives_an_empty_facility():
    live = protocol.parse_live({"facility": None})
    assert live.battery_w is None and live.config is None and live.online is None


def test_unknown_mode_is_lower_cased_not_dropped():
    config = protocol.EmsConfig.from_api({"systemMode": "AcPowerReference"})
    assert config.mode == "acpowerreference"
    assert protocol.EmsConfig.from_api(None) is None
    assert protocol.EmsConfig.from_api({}) is None


def _schedule(sid, kind, active, mode="PeakShaving"):
    return {
        "id": sid, "summary": f"s-{sid}", "scheduleType": kind, "origin": "USER",
        "isActive": active, "appliedAt": None,
        "event": {"iCalendarEventJson": {"start": "2026-10-18T09:00:00.000Z",
                                         "end": "2026-10-18T12:30:00.000Z",
                                         "rruleStr": "RRULE:FREQ=WEEKLY;BYDAY=MO"}},
        "configuration": {"systemMode": mode},
    }


SLOW = {
    "facility": {
        "id": "12345", "name": "Hus", "timezone": "Europe/Stockholm",
        "info": {"version": "8.0.1"},
        "uiComponents": {
            "usesNewScheduler": True,
            "ferroAi": {"available": True},
            "capacities": [
                {"__typename": "UIMainFuseCapacity", "capacity": 20, "unit": "A"},
                {"__typename": "UIMaxInverterPowerCapacity", "capacity": 14, "unit": "kW"},
                {"__typename": "UIEnergyStorageRatedCapacity", "capacity": 27.5, "unit": "kWh"},
                {"__typename": "UIEnergyStorageRatedPowerCapacity", "capacity": 15, "unit": "kW"},
            ],
        },
        "configuration": {"configurationSchedule": {"schedules": [
            _schedule("fb", "FALLBACK", True, "SelfConsumption"),
            _schedule("n1", "NORMAL", False),
            _schedule("n2", "NORMAL", True),
        ]}},
        "measurements": {"energy": [
            {"pvProduced": 1200.0, "consumption": 900.0, "gridImport": 100.0, "gridExport": 400.0,
             "batteryCharged": 300.0, "batteryDischarged": None},
            {"pvProduced": None, "consumption": 1100.0, "gridImport": 1100.0, "gridExport": 0.0,
             "batteryCharged": 0.0, "batteryDischarged": 50.0},
        ]},
    }
}


def test_parse_slow_capacities_in_kwh_and_w():
    slow = protocol.parse_slow(SLOW, 12345)
    info = slow.info
    assert info.battery_kwh == 27.5
    assert info.battery_max_w == 15000.0
    assert info.inverter_max_w == 14000.0
    assert info.main_fuse_a == 20.0
    assert info.version == "8.0.1" and info.uses_new_scheduler is True


def test_active_schedule_prefers_a_normal_one_over_the_fallback():
    slow = protocol.parse_slow(SLOW, 12345)
    assert slow.active_schedule.id == "n2"
    assert slow.active_schedule.config.mode == "peak_shaving"
    only_fallback = protocol.Slow(info=slow.info, schedules=(slow.schedules[0],))
    assert only_fallback.active_schedule.id == "fb"
    assert protocol.Slow(info=slow.info).active_schedule is None


def test_energy_is_summed_to_kwh_with_nulls_as_zero():
    energy = protocol.parse_slow(SLOW, 12345).energy
    assert energy.solar_kwh == 1.2
    assert energy.consumption_kwh == 2.0
    assert energy.grid_import_kwh == 1.2
    assert energy.grid_export_kwh == 0.4
    assert energy.battery_charged_kwh == 0.3
    assert energy.battery_discharged_kwh == 0.05
    assert energy.hours == 2


def test_slow_without_energy_leaves_it_none():
    data = {"facility": {**SLOW["facility"], "measurements": {"energy": None}}}
    assert protocol.parse_slow(data, 12345).energy is None


def test_slow_variables_use_local_midnight():
    now = dt.datetime(2026, 10, 27, 16, 40, tzinfo=ZoneInfo("Europe/Stockholm"))
    v = protocol.slow_variables(12345, now)
    assert v["id"] == 12345
    assert v["range"] == {"gte": "2026-10-26T23:00:00.000Z", "lt": "2026-10-27T15:40:00.000Z"}
    # Midnight a day back is 26 October, already winter time (+01:00).
    assert v["period"] == {"start": "2026-10-25T23:00:00.000Z", "end": "2026-10-28T23:00:00.000Z"}


def test_parse_facilities():
    out = protocol.parse_facilities({"facilities": [
        {"id": "12345", "name": "Hus", "myRelation": {"relation": "FACILITY_ADMIN"},
         "uiComponents": {"usesNewScheduler": True}, "info": {"version": "8.0.1"}},
        {"id": "7", "name": None, "myRelation": {"relation": "FACILITY_READER"}},
    ]})
    assert out[0] == {"id": 12345, "name": "Hus", "admin": True, "new_scheduler": True, "version": "8.0.1"}
    assert out[1]["name"] == "Ferroamp 7" and out[1]["admin"] is False
