"""The Ferroamp page: its layout and its texts, without Home Assistant."""

from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess

import pytest

from custom_components.ferroamp_cloud_control import page_texts as t
from custom_components.ferroamp_cloud_control import page_views as views

PKG = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "ferroamp_cloud_control"


def entity_keys() -> set[str]:
    """Every entity key the integration creates, read off its sources, so a new
    entity without a place on the page fails here."""
    keys: set[str] = set()
    for source in PKG.glob("*.py"):
        text = source.read_text()
        keys.update(re.findall(r'super\(\).__init__\(coordinator, "\w+", "(\w+)"\)', text))
        keys.update(re.findall(r'\bkey="(\w+)"', text))
        keys.update(re.findall(r'_(?:power|kwh)\("(\w+)"', text))
        for prefix in re.findall(r'_phase\("(\w+)"', text):
            keys.update(f"{prefix}_l{n}" for n in (1, 2, 3))
    return keys


def facility(**overrides):
    keys = entity_keys()
    domains = {"control_enabled": "switch", "mode": "select", "battery_power_setpoint": "number",
               "grid_power_limit": "number", "online": "binary_sensor", "ferroai": "binary_sensor",
               "following": "binary_sensor", "phase_balancing_active": "binary_sensor"}
    fac = {
        "name": "Hus",
        "entities": {key: f"{domains.get(key, 'sensor')}.ferroamp_{key}" for key in keys},
        "names": {},
        "scan_interval": 30,
    }
    fac.update(overrides)
    return fac


def items(config):
    for view in config["views"]:
        for card in view["cards"]:
            yield from card.get("items", [])


def test_the_integration_still_has_the_entities_the_page_was_written_for():
    assert {"soc", "battery_power", "grid_power", "solar_power", "consumption_power",
            "control_enabled", "mode", "battery_power_setpoint", "grid_power_limit",
            "following", "last_command", "system_mode", "active_schedule"} <= entity_keys()


def test_every_entity_has_a_place_on_the_page():
    config = views.build_dashboard([facility()], t.SWEDISH)
    shown = {item["entity"] for item in items(config)}
    missing = {key for key, entity in facility()["entities"].items() if entity not in shown}
    assert missing == set()


@pytest.mark.parametrize("lang", [t.SWEDISH, t.ENGLISH])
def test_every_value_has_a_name_and_an_explanation(lang):
    config = views.build_dashboard([facility()], lang)
    for item in items(config):
        assert item["name"] and item["explanation"], item
        assert len(item["explanation"]) > 40, item


def test_names_and_explanations_cover_the_same_keys():
    assert set(t.NAMES) == set(t.EXPLAIN)


@pytest.mark.parametrize("table", [t.UI, t.NAMES, t.EXPLAIN])
def test_every_text_is_written_in_both_languages_without_dashes(table):
    for key, (sv, en) in table.items():
        assert sv.strip() and en.strip(), key
        for text in (sv, en):
            # No dash as punctuation; the minus in "minus en miljon" is a word.
            assert "—" not in text and " – " not in text and " - " not in text, (key, text)


def test_the_words_exist_in_both_languages():
    for kind, pairs in t.WORDS.items():
        for value, (sv, en) in pairs.items():
            assert sv and en, (kind, value)


def test_the_page_follows_the_language():
    sv = views.build_dashboard([facility()], t.SWEDISH)
    en = views.build_dashboard([facility()], t.ENGLISH)
    assert [v["title"] for v in sv["views"]] == ["Översikt", "Styrning", "Anläggning"]
    assert [v["title"] for v in en["views"]] == ["Overview", "Control", "System"]
    assert t.language("sv-SE") == t.SWEDISH and t.language("en") == t.ENGLISH
    assert t.language(None) == t.ENGLISH


def test_attribute_rows_name_the_attributes_the_entities_carry():
    protocol = (PKG / "protocol.py").read_text()
    sensor = (PKG / "sensor.py").read_text() + (PKG / "binary_sensor.py").read_text()
    # protocol.py's attributes, and every attribute sensor.py writes itself.
    carried = set(re.findall(r'"(\w+)": self\.', protocol)) | set(re.findall(r'^\s*"(\w+)": ', sensor, re.M)) \
        | set(re.findall(r'\{"(\w+)": ', sensor))
    config = views.build_dashboard([facility()], t.ENGLISH)
    for item in items(config):
        if "attribute" in item:
            assert item["attribute"] in carried, item["attribute"]


def test_a_missing_entity_leaves_its_row_out_and_a_given_name_goes_first():
    fac = facility()
    del fac["entities"]["grid_power_limit"]
    fac["names"] = {"soc": "Batteriet i garaget"}
    config = views.build_dashboard([fac], t.SWEDISH)
    names = {item["name"] for item in items(config)}
    assert "Gräns för köp" not in names
    assert "Batteriet i garaget" in names


def test_no_system_gives_a_page_that_says_so():
    config = views.build_dashboard([], t.SWEDISH)
    assert len(config["views"]) == 1
    assert "Ferroamp Cloud Control" in config["views"][0]["cards"][0]["content"]


def test_two_systems_each_get_a_heading():
    config = views.build_dashboard([facility(name="A"), facility(name="B")], t.SWEDISH)
    headings = [c["heading"] for c in config["views"][0]["cards"] if c["type"] == "heading"]
    assert headings == ["A", "B"]


def test_entity_ids_covers_rows_and_the_history_graph():
    config = views.build_dashboard([facility()], t.SWEDISH)
    found = views.entity_ids(config)
    assert "sensor.ferroamp_battery_power" in found and "switch.ferroamp_control_enabled" in found


def test_the_page_is_plain_json():
    json.dumps(views.build_dashboard([facility()], t.SWEDISH))


# ---------------------------------------------------------------- the card's formatting

CARD = PKG / "www" / "ferroamp-cloud-card.js"
WORDS = {"yes": "Ja", "no": "Nej", "no_limit": "ingen gräns", "buying": "köper", "selling": "säljer",
         "charging": "laddar", "discharging": "laddar ur", "still": "står still",
         "none": "ingen uppgift", "unavailable": "otillgänglig", "once": "en gång",
         "every_day": "varje dag", "every_week": "varje vecka", "every_year": "varje år",
         "day_mo": "mån", "day_we": "ons", "day_fr": "fre", "of": "av", "no_alarms": "inga larm"}


def card_format(cases):
    """Run the card's formatValue in node on (item, raw, unit) cases."""
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = f"""
      const {{ formatValue }} = require({json.dumps(str(CARD))});
      const cases = {json.dumps(cases)};
      const words = {json.dumps(WORDS)};
      const out = cases.map(([item, raw, unit, attrs]) =>
        formatValue(item, raw, unit, words, "sv", (d) => "TIME " + d.toISOString(), attrs));
      console.log(JSON.stringify(out));
    """
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(run.stdout)


def test_the_card_writes_power_with_a_word_for_its_direction():
    out = card_format([
        [{"format": "power_grid"}, "1200", "W"],
        [{"format": "power_grid"}, "-450", "W"],
        [{"format": "power_battery"}, "1656", "W"],
        [{"format": "power_battery"}, "-963", "W"],
        [{"format": "power_battery"}, "5", "W"],
    ])
    assert [o[1] for o in out] == ["köper", "säljer", "laddar ur", "laddar", "står still"]
    assert out[1][0].replace(" ", " ") == "450 W"


def test_the_card_writes_limits_booleans_states_and_gaps():
    out = card_format([
        [{"format": "limit"}, 100000, "W"],
        [{"format": "limit"}, -1000000, "W"],
        [{"format": "limit"}, 6235, "W"],
        [{"format": "bool"}, True, None],
        [{"format": "bool"}, False, None],
        [{"states": {"ack": "Kvitterat"}}, "ack", None],
        [{}, None, None],
        [{}, "unavailable", None],
        [{}, "unknown", None],
        [{"format": "time"}, "2026-10-28T07:00:00+00:00", None],
    ])
    texts = [o[0].replace(" ", " ") for o in out]
    assert texts[:2] == ["ingen gräns", "ingen gräns"]
    assert texts[2] == "6 235 W"
    assert texts[3:6] == ["Ja", "Nej", "Kvitterat"]
    assert texts[6:9] == ["ingen uppgift", "otillgänglig", "ingen uppgift"]
    assert texts[9].startswith("TIME 2026-10-28T07:00")


def test_the_card_writes_a_repeat_rule_in_words():
    out = card_format([
        [{"format": "rrule"}, None, None],
        [{"format": "rrule"}, "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR,SA,SU", None],
        [{"format": "rrule"}, "RRULE:FREQ=WEEKLY;BYDAY=FR,MO,WE", None],
        [{"format": "rrule"}, "RRULE:FREQ=YEARLY", None],
        [{"format": "rrule"}, "RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=MO", None],
    ])
    assert [o[0] for o in out] == ["en gång", "varje dag", "varje vecka: mån, ons, fre", "varje år",
                                   "RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=MO"]


def test_the_card_writes_lists_one_per_line():
    # Strings carry lowercase states (sensor.py), alarms Ferroamp's own codes.
    states = {"running": "i drift", "offline": "frånkopplad", "SSO_OFFLINE": "en solcellsoptimerare är frånkopplad"}
    out = card_format([
        [{"format": "codes"}, ["bat_soc_power_derating", "x_y"], None],
        [{"format": "codes"}, [], None],
        [{"format": "alarms", "states": states}, [], None],
        [{"format": "alarms", "states": states},
         [{"code": "SSO_OFFLINE", "product_id": "SSO2", "since": "2026-11-22T10:00:00+00:00"},
          {"code": "NEW_CODE", "product_id": None, "since": None}], None],
        [{"format": "strings", "states": states},
         [{"name": "Söder", "state": "running", "rating_w": 4500},
          {"name": "SSO 2", "state": "offline", "rating_w": None}], None],
        [{"format": "of_total"}, "1", None, {"total": 2}],
        [{"format": "of_total"}, "1", None, {}],
        [{"format": "of_total"}, "unavailable", None, {"total": 2}],
        [{"format": "volts"}, 3.312, "V"],
    ])
    texts = [o[0].replace("\u202f", " ").replace("\u00a0", " ") for o in out]
    assert texts[0] == "bat soc power derating, x y"
    assert texts[1] == "ingen uppgift"
    assert texts[2] == "inga larm"
    assert texts[3].split("\n") == ["en solcellsoptimerare är frånkopplad (SSO2), TIME 2026-11-22T10:00:00.000Z",
                                     "new code"]
    assert texts[4].split("\n") == ["Söder: i drift, 4 500 W", "SSO 2: frånkopplad"]
    assert texts[5:8] == ["1 av 2", "1", "otillgänglig"]
    assert texts[8] == "3,312 V"


def test_the_card_writes_codes_in_words_where_it_has_them():
    out = card_format([
        [{"format": "codes", "states": {"remote_api": "Remote API"}}, ["remote_api", "new_service"], None],
    ])
    assert out[0][0] == "Remote API, new service"
