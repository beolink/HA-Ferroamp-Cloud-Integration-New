"""The Ferroamp page's layout: three tabs of cards, built from a plain
description of each running system (page.py collects it).

Free of Home Assistant imports, like page_texts.py, so the layout can be
checked without an installation (tests/test_page.py). The page uses two cards
of the integration's own (www/ferroamp-cloud-card.js), both of which put a
blue "i" after every name, and Home Assistant's own history graph. Nothing on
the page writes anything: a control opens Home Assistant's own dialog for its
entity, where it is changed the way it is everywhere else.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Final

from . import page_texts as t

URL_PATH: Final = "ferroamp-cloud"
TITLE: Final = "Ferroamp"
ICON: Final = "mdi:home-battery"

READINGS_CARD: Final = "custom:ferroamp-cloud-readings"
ROWS_CARD: Final = "custom:ferroamp-cloud-rows"


def _item(fac: Mapping[str, Any], key: str, lang: str, *, attribute: str | None = None,
          fmt: str | None = None, unit: str | None = None, words: str | None = None,
          source: str | None = None) -> dict[str, Any] | None:
    """One value on the page, or None when the system has no such entity."""
    entity = fac["entities"].get(key)
    if entity is None:
        return None
    explain_key = f"{key}.{attribute}" if attribute else key
    # A name the person gave the entity goes first, for the entity's own row.
    given = None if attribute else fac.get("names", {}).get(key)
    item: dict[str, Any] = {
        "entity": entity,
        "name": given or t.name(explain_key, lang),
        "explanation": t.explain(explain_key, lang),
    }
    if attribute:
        item["attribute"] = attribute
    if fmt:
        item["format"] = fmt
    if unit:
        item["unit"] = unit
    if words:
        item["states"] = t.words(words, lang)
    if source:
        item["source"] = source
    return item


def _items(*items: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [item for item in items if item is not None]


def _card(kind: str, title: str | None, items: list[dict[str, Any]], lang: str) -> dict[str, Any] | None:
    if not items:
        return None
    card: dict[str, Any] = {
        "type": kind,
        "items": items,
        "explain": t.text("explain", lang),
        "more_info": t.text("more_info", lang),
        "words": {k: t.text(k, lang) for k in (
            "yes", "no", "no_limit", "buying", "selling", "charging", "discharging", "still",
            "none", "unavailable", "once", "every_day", "every_week", "every_month", "every_year",
            "of", "no_alarms",
            "day_mo", "day_tu", "day_we", "day_th", "day_fr", "day_sa", "day_su")},
    }
    if title:
        card["title"] = title
    return card


def _cards(*cards: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [card for card in cards if card is not None]


def _sources(fac: Mapping[str, Any], lang: str) -> tuple[str, str, str]:
    live = t.text("source_live", lang).format(interval=fac.get("scan_interval", 30))
    return live, t.text("source_slow", lang), t.text("source_driver", lang)


def _heading(fac: Mapping[str, Any], several: bool) -> list[dict[str, Any]]:
    """With more than one system, each one's cards under its own name."""
    if not several:
        return []
    return [{"type": "heading", "heading": fac["name"], "heading_style": "title"}]


def overview_cards(fac: Mapping[str, Any], lang: str, several: bool = False) -> list[dict[str, Any]]:
    live, slow, _ = _sources(fac, lang)
    readings = _card(READINGS_CARD, t.text("now", lang), _items(
        _item(fac, "solar_power", lang, source=live),
        _item(fac, "consumption_power", lang, source=live),
        _item(fac, "grid_power", lang, fmt="power_grid", source=live),
        _item(fac, "battery_power", lang, fmt="power_battery", source=live),
        _item(fac, "soc", lang, source=live),
    ), lang)
    history_entities = [fac["entities"][key] for key in
                        ("solar_power", "consumption_power", "grid_power", "battery_power")
                        if key in fac["entities"]]
    history = ({
        "type": "history-graph",
        "title": t.text("history", lang),
        "hours_to_show": 24,
        "entities": history_entities,
    } if history_entities else None)
    today = _card(ROWS_CARD, t.text("today", lang), _items(
        _item(fac, "solar_energy_today", lang, source=slow),
        _item(fac, "consumption_energy_today", lang, source=slow),
        _item(fac, "grid_import_energy_today", lang, source=slow),
        _item(fac, "grid_export_energy_today", lang, source=slow),
        _item(fac, "battery_charged_energy_today", lang, source=slow),
        _item(fac, "battery_discharged_energy_today", lang, source=slow),
    ), lang)
    return _heading(fac, several) + _cards(readings, history, today)


def control_cards(fac: Mapping[str, Any], lang: str, several: bool = False) -> list[dict[str, Any]]:
    live, slow, driver = _sources(fac, lang)
    control = _card(ROWS_CARD, t.text("control_entities", lang), _items(
        _item(fac, "control_enabled", lang, words="on_off", source=driver),
        _item(fac, "mode", lang, words="control_mode", source=driver),
        _item(fac, "battery_power_setpoint", lang, source=driver),
        _item(fac, "grid_power_limit", lang, source=driver),
        _item(fac, "following", lang, words="following", source=driver),
        _item(fac, "last_command", lang, words="last_command", source=driver),
        _item(fac, "last_command", lang, attribute="reason", source=driver),
    ), lang)
    in_force = _card(ROWS_CARD, t.text("in_force", lang), _items(
        _item(fac, "system_mode", lang, words="mode_in_force", source=live),
        *[_item(fac, "system_mode", lang, attribute=attr, fmt=fmt, unit=unit, source=live)
          for attr, fmt, unit in (
              ("pv_on", "bool", None),
              ("phase_balancing_on", "bool", None),
              ("phase_balancing_threshold_a", None, "A"),
              ("limit_import", "bool", None),
              ("limit_export", "bool", None),
              ("threshold_high_w", "limit", "W"),
              ("threshold_low_w", "limit", "W"),
              ("charge_reference_w", "limit", "W"),
              ("discharge_reference_w", "limit", "W"),
              ("soc_low", None, "%"),
              ("soc_high", None, "%"),
          )],
    ), lang)
    schedule = _card(ROWS_CARD, t.text("schedule", lang), _items(
        _item(fac, "active_schedule", lang, source=slow),
        _item(fac, "active_schedule", lang, attribute="origin", words="origin", source=slow),
        _item(fac, "active_schedule", lang, attribute="schedule_type", words="schedule_type", source=slow),
        _item(fac, "active_schedule", lang, attribute="start", fmt="time", source=slow),
        _item(fac, "active_schedule", lang, attribute="end", fmt="time", source=slow),
        _item(fac, "active_schedule", lang, attribute="rrule", fmt="rrule", source=slow),
        _item(fac, "active_schedule", lang, attribute="applied_at", fmt="time", source=slow),
    ), lang)
    ferroai = _card(ROWS_CARD, t.text("ferroai_price", lang), _items(
        _item(fac, "ferroai", lang, words="on_off", source=live),
        _item(fac, "ferroai_action", lang, source=live),
        _item(fac, "ferroai", lang, attribute="variant", words="ferroai_variant", source=slow),
        _item(fac, "ferroai", lang, attribute="activated_at", fmt="time", source=slow),
        _item(fac, "ferroai", lang, attribute="tariff_option", words="tariff_option", source=slow),
        _item(fac, "ferroai", lang, attribute="minimum_earnings", source=slow),
        _item(fac, "ferroai", lang, attribute="limit_import_threshold", source=slow),
        _item(fac, "ferroai", lang, attribute="limit_export_threshold", source=slow),
        _item(fac, "ferroai", lang, attribute="bidding_zone", source=slow),
        _item(fac, "spot_price", lang, source=slow),
        _item(fac, "forecast_soc", lang, source=slow),
        _item(fac, "forecast_soc", lang, attribute="solar_w", unit="W", source=slow),
        _item(fac, "forecast_soc", lang, attribute="consumption_w", unit="W", source=slow),
    ), lang)
    return _heading(fac, several) + _cards(control, in_force, schedule, ferroai)


def system_cards(fac: Mapping[str, Any], lang: str, several: bool = False) -> list[dict[str, Any]]:
    live, slow, _ = _sources(fac, lang)
    software = _card(ROWS_CARD, t.text("software", lang), _items(
        _item(fac, "firmware_version", lang, source=slow),
        _item(fac, "firmware_version", lang, attribute="controller_version", source=slow),
        _item(fac, "firmware_version", lang, attribute="controller_generation", source=slow),
        _item(fac, "firmware_version", lang, attribute="last_update_from", source=slow),
        _item(fac, "firmware_version", lang, attribute="last_update_to", source=slow),
        _item(fac, "firmware_version", lang, attribute="last_update_at", fmt="time", source=slow),
        _item(fac, "firmware_version", lang, attribute="hostname", source=slow),
    ), lang)
    state = _card(ROWS_CARD, t.text("state_alarms", lang), _items(
        _item(fac, "system_state", lang, words="ferro_state", source=slow),
        _item(fac, "system_state", lang, attribute="since", fmt="time", source=slow),
        _item(fac, "system_state", lang, attribute="lifecycle", words="lifecycle", source=slow),
        _item(fac, "active_alarms", lang, source=slow),
        _item(fac, "active_alarms", lang, attribute="alarms", fmt="alarms", words="alarm_code", source=slow),
        _item(fac, "system_state", lang, attribute="active_services", fmt="codes", words="active_service",
              source=slow),
        _item(fac, "online", lang, words="online", source=live),
        _item(fac, "last_seen", lang, fmt="time", source=live),
    ), lang)
    grid = _card(ROWS_CARD, t.text("grid", lang), _items(
        *[_item(fac, f"grid_voltage_l{n}", lang, source=live) for n in (1, 2, 3)],
        *[_item(fac, f"grid_current_l{n}", lang, source=live) for n in (1, 2, 3)],
        *[_item(fac, f"grid_power_l{n}", lang, source=live) for n in (1, 2, 3)],
        *[_item(fac, f"consumption_power_l{n}", lang, source=live) for n in (1, 2, 3)],
        _item(fac, "phase_balancing_active", lang, words="working", source=live),
        *[_item(fac, "phase_balancing_active", lang, attribute=f"ace_correction_l{n}", unit="A", source=live)
          for n in (1, 2, 3)],
        _item(fac, "system_state", lang, attribute="main_fuse_a", unit="A", source=slow),
        _item(fac, "system_state", lang, attribute="phases", words="phases", source=slow),
        _item(fac, "system_state", lang, attribute="inverter_power_rating_w", unit="W", source=slow),
    ), lang)
    battery = _card(ROWS_CARD, t.text("battery", lang), _items(
        _item(fac, "battery_capacity", lang, source=slow),
        _item(fac, "max_charge_power", lang, source=slow),
        _item(fac, "battery_state", lang, words="ferro_state", source=slow),
        _item(fac, "battery_state", lang, attribute="reasons", fmt="codes", source=slow),
        _item(fac, "battery_health", lang, source=slow),
        _item(fac, "battery_cell_temperature_min", lang, source=slow),
        _item(fac, "battery_cell_temperature_max", lang, source=slow),
        _item(fac, "battery_health", lang, attribute="cell_voltage_min_v", unit="V", fmt="volts", source=slow),
        _item(fac, "battery_health", lang, attribute="cell_voltage_max_v", unit="V", fmt="volts", source=slow),
        _item(fac, "battery_health", lang, attribute="battery_voltage_v", unit="V", source=slow),
        _item(fac, "battery_health", lang, attribute="battery_current_a", unit="A", source=slow),
        _item(fac, "battery_health", lang, attribute="manufacturer", source=slow),
        _item(fac, "system_state", lang, attribute="eso_generation", source=slow),
    ), lang)
    strings = _card(ROWS_CARD, t.text("strings", lang), _items(
        _item(fac, "solar_strings", lang, fmt="of_total", source=slow),
        _item(fac, "solar_strings", lang, attribute="strings", fmt="strings", words="ferro_state", source=slow),
    ), lang)
    return _heading(fac, several) + _cards(software, state, grid, battery, strings)


def _view(path: str, title_key: str, cards: list[dict[str, Any]], lang: str) -> dict[str, Any]:
    return {
        "title": t.text(title_key, lang),
        "path": path,
        "type": "masonry",
        "cards": cards,
    }


def message_dashboard(message: str, lang: str) -> dict[str, Any]:
    """A page with one line on it, when there is nothing else to show."""
    return {"title": TITLE, "views": [_view("overview", "overview", [
        {"type": "markdown", "content": message}], lang)]}


def build_dashboard(facilities: Iterable[Mapping[str, Any]], lang: str) -> dict[str, Any]:
    """The whole page for ``facilities``, in ``lang``."""
    facs = list(facilities)
    if not facs:
        return message_dashboard(t.text("empty", lang), lang)
    several = len(facs) > 1
    return {
        "title": TITLE,
        "views": [
            _view("overview", "overview",
                  [c for fac in facs for c in overview_cards(fac, lang, several)], lang),
            _view("control", "control",
                  [c for fac in facs for c in control_cards(fac, lang, several)], lang),
            _view("system", "system",
                  [c for fac in facs for c in system_cards(fac, lang, several)], lang),
        ],
    }


def entity_ids(config: Mapping[str, Any]) -> set[str]:
    """Every entity the page refers to, so a change to one of them can be noticed."""
    found: set[str] = set()
    for view in config.get("views", []):
        for card in view.get("cards", []):
            for item in card.get("items", []):
                found.add(item["entity"])
            found.update(card.get("entities", []))
    return found
