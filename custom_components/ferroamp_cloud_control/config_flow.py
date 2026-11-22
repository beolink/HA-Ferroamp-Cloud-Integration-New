"""Config, re-authentication and options flow for Ferroamp Cloud Control.

The e-mail and password go to Ferroamp's login page once; what is stored
is the offline refresh token it hands out, the facility id and the e-mail
(shown again when the login has to be renewed). Never the password.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import protocol
from .api import AuthError, CloudError, FerroampCloud, login
from .const import (
    CONF_EMAIL,
    CONF_FACILITY_ID,
    CONF_PREFIX,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_SHOW_PAGE,
    DEFAULT_PREFIX,
    DEFAULT_SCAN_INTERVAL_S,
    DEFAULT_SHOW_PAGE,
    DOMAIN,
    MIN_SCAN_INTERVAL_S,
)

_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
_EMAIL = TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL))


class FerroampCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._email: str | None = None
        self._prefix = DEFAULT_PREFIX
        self._refresh_token: str | None = None
        self._facilities: list[dict[str, Any]] = []

    async def _login(self, email: str, password: str) -> dict[str, str]:
        """Log in; on success keep the token and return no errors."""
        try:
            tokens = await login(email, password)
        except AuthError:
            return {"base": "invalid_auth"}
        except CloudError:
            return {"base": "cannot_connect"}
        self._email = email
        self._refresh_token = tokens["refresh_token"]
        return {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._prefix = user_input[CONF_PREFIX].strip() or DEFAULT_PREFIX
            errors = await self._login(user_input[CONF_EMAIL].strip(), user_input["password"])
            if not errors:
                client = FerroampCloud(async_get_clientsession(self.hass), self._refresh_token)
                try:
                    self._facilities = protocol.parse_facilities(await client.query(protocol.FACILITIES))
                except (AuthError, CloudError):
                    errors = {"base": "cannot_connect"}
                else:
                    # A token rotated during the facility read is the one to keep.
                    self._refresh_token = client.refresh_token
                    if not self._facilities:
                        errors = {"base": "no_facilities"}
                    elif len(self._facilities) == 1:
                        return await self._create(self._facilities[0])
                    else:
                        return await self.async_step_facility()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL, default=self._email or ""): _EMAIL,
                vol.Required("password"): _PASSWORD,
                vol.Required(CONF_PREFIX, default=self._prefix): str,
            }),
            errors=errors,
        )

    async def async_step_facility(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            chosen = next(f for f in self._facilities if str(f["id"]) == user_input[CONF_FACILITY_ID])
            return await self._create(chosen)
        options = [
            {"value": str(f["id"]), "label": f"{f['name']} ({f['id']})"} for f in self._facilities
        ]
        return self.async_show_form(
            step_id="facility",
            data_schema=vol.Schema({
                vol.Required(CONF_FACILITY_ID): SelectSelector(SelectSelectorConfig(options=options)),
            }),
        )

    async def _create(self, facility: dict[str, Any]) -> ConfigFlowResult:
        await self.async_set_unique_id(str(facility["id"]))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=facility["name"],
            data={
                CONF_FACILITY_ID: facility["id"],
                CONF_REFRESH_TOKEN: self._refresh_token,
                CONF_EMAIL: self._email,
                CONF_PREFIX: self._prefix,
            },
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        self._email = entry_data.get(CONF_EMAIL)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            errors = await self._login(user_input[CONF_EMAIL].strip(), user_input["password"])
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_REFRESH_TOKEN: self._refresh_token, CONF_EMAIL: self._email},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL, default=self._email or ""): _EMAIL,
                vol.Required("password"): _PASSWORD,
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> FerroampCloudOptionsFlow:
        return FerroampCloudOptionsFlow()


class FerroampCloudOptionsFlow(OptionsFlow):
    """Two things to do: change the settings, or build the Ferroamp page anew."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="init", menu_options=["settings", "rebuild_page"])

    async def async_step_settings(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            # A changed option reloads the entry (__init__.py), and the
            # reload shows or hides the page.
            return self.async_create_entry(data={**self.config_entry.options, **user_input})
        cur = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=int(cur.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_S)),
                ): NumberSelector(NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL_S, max=300, step=5,
                    mode=NumberSelectorMode.BOX, unit_of_measurement="s")),
                vol.Required(
                    CONF_SHOW_PAGE, default=bool(cur.get(CONF_SHOW_PAGE, DEFAULT_SHOW_PAGE)),
                ): bool,
            }),
        )

    async def async_step_rebuild_page(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Take the page out and put it back, with a new address for its cards
        so every browser loads them afresh. Imported here: page.py pulls in
        Home Assistant's frontend, which the pure tests do without."""
        from homeassistant.loader import async_get_integration

        from . import page

        if user_input is not None:
            if not page.page_wanted(self.hass):
                return self.async_abort(reason="page_hidden")
            integration = await async_get_integration(self.hass, DOMAIN)
            await page.async_rebuild(self.hass, str(integration.version))
            return self.async_abort(reason="page_rebuilt")
        return self.async_show_form(step_id="rebuild_page", data_schema=vol.Schema({}))
