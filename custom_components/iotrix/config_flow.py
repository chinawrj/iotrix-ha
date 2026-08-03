"""Config flow for IoTrix Cloud."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import IoTrixApi, IoTrixApiError, IoTrixAuthError
from .const import (
    CONF_DEVICE_REFRESH_INTERVAL,
    CONF_HOST,
    CONF_TOKEN,
    DEFAULT_DEVICE_REFRESH_INTERVAL,
    DOMAIN,
)
from .models import IoTrixDevice, parse_devices


async def _validate(
    hass: Any, data: dict[str, Any]
) -> tuple[IoTrixApi, dict[str, Any], list[IoTrixDevice]]:
    api = IoTrixApi(async_get_clientsession(hass), data[CONF_HOST], data[CONF_TOKEN])
    user = await api.async_user()
    devices = parse_devices(await api.async_list_devices())
    return api, user, devices


class IoTrixConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure one IoTrix account."""

    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                api, user, devices = await _validate(self.hass, user_input)
            except IoTrixAuthError:
                errors["base"] = "invalid_auth"
            except IoTrixApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                account_id = str(user.get("id") or user.get("user_id") or "account")
                await self.async_set_unique_id(f"{api.base_url}:{account_id}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=str(
                        user.get("username")
                        or user.get("name")
                        or f"IoTrix ({len(devices)} devices)"
                    ),
                    data={CONF_HOST: api.base_url, CONF_TOKEN: user_input[CONF_TOKEN]},
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default="https://www.iotrix.cn"): str,
                vol.Required(CONF_TOKEN): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Start token replacement after an authentication failure."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Validate and store a replacement token."""
        errors: dict[str, str] = {}
        assert self._reauth_entry is not None
        if user_input is not None:
            data = {
                CONF_HOST: self._reauth_entry.data[CONF_HOST],
                CONF_TOKEN: user_input[CONF_TOKEN],
            }
            try:
                await _validate(self.hass, data)
            except IoTrixAuthError:
                errors["base"] = "invalid_auth"
            except IoTrixApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(self._reauth_entry, data_updates=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return IoTrixOptionsFlow()


class IoTrixOptionsFlow(config_entries.OptionsFlow):
    """Configure cloud device-discovery refresh behavior."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        schema = {
            vol.Required(
                CONF_DEVICE_REFRESH_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_DEVICE_REFRESH_INTERVAL, DEFAULT_DEVICE_REFRESH_INTERVAL
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=60, max=3600, step=60, mode=selector.NumberSelectorMode.BOX
                )
            )
        }
        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))
