"""The Ferroamp page in the sidebar, built afresh every time it is opened.

The layout is page_views.py; this file finds the entities and talks to Lovelace,
the way CTC Local Easyconf's page does. The page is a Lovelace dashboard that is
never stored: the frontend asks a dashboard for its config each time the page is
opened, and this one answers with a layout built there and then from the
integration's current entities, so it cannot go stale. While a page is open, a
change is announced with lovelace_updated, which the frontend already listens for.

Home Assistant offers no public call for adding a dashboard from an integration,
so the address is checked before use and a failure only means there is no page;
it never touches the integration itself. Read only: nothing is written to disk,
and an address that already holds a panel or a dashboard is left alone.

Each system's options say whether it is on the page (CONF_SHOW_PAGE). The page is
in the sidebar while at least one running system shows it, and the options flow
can build it anew (async_rebuild): out of the sidebar and back, with a new address
for the cards so that every browser loads them afresh.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.json import json_bytes, json_fragment

from . import page_texts as texts
from . import page_views as views
from .const import (
    CONF_FACILITY_ID,
    CONF_SCAN_INTERVAL,
    CONF_SHOW_PAGE,
    DEFAULT_SCAN_INTERVAL_S,
    DEFAULT_SHOW_PAGE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_DATA = f"{DOMAIN}_page"
_LOVELACE = "lovelace"
CARD_URL = f"/{DOMAIN}/ferroamp-cloud-card.js"
CARD_FILE = Path(__file__).parent / "www" / "ferroamp-cloud-card.js"


def _lovelace_dashboards(hass: HomeAssistant) -> dict | None:
    """Lovelace's dashboards by url path: a dict key before 2025, an attribute since."""
    data = hass.data.get(_LOVELACE)
    found = data.get("dashboards") if isinstance(data, dict) else getattr(data, "dashboards", None)
    return found if isinstance(found, dict) else None


def shows_page(entry: ConfigEntry) -> bool:
    """Whether this system is on the Ferroamp page (its options say)."""
    return bool({**entry.data, **entry.options}.get(CONF_SHOW_PAGE, DEFAULT_SHOW_PAGE))


@callback
def page_wanted(hass: HomeAssistant, *, starting: ConfigEntry | None = None,
                stopping: ConfigEntry | None = None) -> bool:
    """Whether the page belongs in the sidebar: some running system shows it.
    ``starting`` counts as running (it is being set up), ``stopping`` does not."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if stopping is not None and entry.entry_id == stopping.entry_id:
            continue
        running = entry.state is ConfigEntryState.LOADED or (
            starting is not None and entry.entry_id == starting.entry_id)
        if running and shows_page(entry):
            return True
    return False


@callback
def collect(hass: HomeAssistant) -> list[dict[str, Any]]:
    """One plain dict per running system the page shows, as page_views expects."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    found: list[dict[str, Any]] = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is not ConfigEntryState.LOADED or not shows_page(entry):
            continue
        prefix = f"{entry.data[CONF_FACILITY_ID]}_"
        entities: dict[str, str] = {}
        names: dict[str, str] = {}
        for item in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
            # Leave out what a person switched off or hid, as the built-in
            # dashboards do.
            if item.disabled_by or item.hidden_by or not item.unique_id.startswith(prefix):
                continue
            key = item.unique_id[len(prefix):]
            entities[key] = item.entity_id
            if item.name:
                names[key] = item.name
        device = next(iter(dr.async_entries_for_config_entry(dev_reg, entry.entry_id)), None)
        found.append({
            "name": (device and (device.name_by_user or device.name)) or entry.title,
            "entities": entities,
            "names": names,
            "scan_interval": int({**entry.data, **entry.options}.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_S)),
        })
    return found


@callback
def build_config(hass: HomeAssistant) -> dict[str, Any]:
    """The page as it should look right now. Never raises: a broken page says so."""
    lang = texts.language(hass.config.language)
    try:
        return views.build_dashboard(collect(hass), lang)
    except Exception:  # the page must never break the frontend
        _LOGGER.exception("Could not build the Ferroamp page")
        return views.message_dashboard(texts.text("failed", lang), lang)


def _page_class() -> type:
    """A Lovelace dashboard whose config is built on request. Made on first use,
    so a Lovelace that has moved on only loses the page, not the integration."""
    from homeassistant.components.lovelace.dashboard import LovelaceConfig

    class FerroampPage(LovelaceConfig):
        def __init__(self, hass: HomeAssistant) -> None:
            super().__init__(hass, views.URL_PATH, {
                "mode": "yaml",
                "title": views.TITLE,
                "icon": views.ICON,
                "show_in_sidebar": True,
                "require_admin": False,
            })

        @property
        def mode(self) -> str:
            return "yaml"

        async def async_get_info(self) -> dict[str, Any]:
            # "auto-gen" rather than "yaml", so system health does not report
            # Lovelace itself as running in YAML mode because of this page.
            return {"mode": "auto-gen", "views": len(build_config(self.hass).get("views", []))}

        async def async_load(self, force: bool) -> dict[str, Any]:
            return build_config(self.hass)

        async def async_json(self, force: bool) -> json_fragment:
            return json_fragment(json_bytes(build_config(self.hass)))

        @callback
        def announce(self) -> None:
            """Tell open pages to fetch the layout again."""
            self._config_updated()

    return FerroampPage


async def async_register(hass: HomeAssistant, version: str, cache_key: str | None = None) -> None:
    """Serve the cards and put the page in the sidebar. Once, until unregistered.
    ``cache_key`` goes into the cards' address beside the version, so a browser
    that has them already loads them anew (async_rebuild)."""
    if _DATA in hass.data:
        return
    js_url = f"{CARD_URL}?v={version}" + (f"-{cache_key}" if cache_key else "")
    registered: dict[str, Any] = {"page": None, "js": js_url}
    hass.data[_DATA] = registered
    try:
        await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(CARD_FILE), False)])
    except (RuntimeError, ValueError) as err:
        _LOGGER.debug("Static path for the card not registered: %s", err)  # served already
    # With the version in the address, a browser picks up a new card after an update.
    frontend.add_extra_js_url(hass, js_url)

    dashboards = _lovelace_dashboards(hass)
    if dashboards is None:
        _LOGGER.info("Lovelace is not loaded, so there is no Ferroamp page")
        return
    if views.URL_PATH in dashboards or frontend.async_panel_exists(hass, views.URL_PATH):
        _LOGGER.info("/%s is already taken, so the Ferroamp page is not added", views.URL_PATH)
        return
    page = None
    try:
        page = _page_class()(hass)
        dashboards[views.URL_PATH] = page
        frontend.async_register_built_in_panel(
            hass,
            _LOVELACE,
            sidebar_title=views.TITLE,
            sidebar_icon=views.ICON,
            frontend_url_path=views.URL_PATH,
            config={"mode": "yaml"},
            require_admin=False,
        )
    except Exception:  # no page, but the integration runs on
        if page is not None and dashboards.get(views.URL_PATH) is page:
            dashboards.pop(views.URL_PATH)
        _LOGGER.warning("Could not add the Ferroamp page to the sidebar", exc_info=True)
        return
    registered["page"] = page


@callback
def async_announce_change(hass: HomeAssistant) -> None:
    """A system started or stopped: open pages fetch the layout again."""
    registered = hass.data.get(_DATA)
    if registered is not None and registered["page"] is not None:
        registered["page"].announce()


@callback
def async_unregister(hass: HomeAssistant) -> None:
    """Take the page out of the sidebar, once no system is left."""
    registered = hass.data.pop(_DATA, None)
    if registered is None:
        return
    frontend.remove_extra_js_url(hass, registered["js"])
    page = registered["page"]
    if page is None:
        return
    frontend.async_remove_panel(hass, views.URL_PATH, warn_if_unknown=False)
    dashboards = _lovelace_dashboards(hass)
    if dashboards is not None and dashboards.get(views.URL_PATH) is page:
        dashboards.pop(views.URL_PATH)


async def async_sync(hass: HomeAssistant, version: str, *, starting: ConfigEntry | None = None,
                     stopping: ConfigEntry | None = None) -> None:
    """Put the page in the sidebar or take it out, as the systems' options say,
    and tell open pages to fetch the layout again."""
    if page_wanted(hass, starting=starting, stopping=stopping):
        await async_register(hass, version)
        async_announce_change(hass)
    else:
        async_unregister(hass)


async def async_rebuild(hass: HomeAssistant, version: str) -> None:
    """Build the page anew: out of the sidebar and back, with a new address for
    the cards, and open pages told to fetch the layout again."""
    async_unregister(hass)
    if page_wanted(hass):
        await async_register(hass, version, cache_key=str(int(time.time())))
        async_announce_change(hass)
