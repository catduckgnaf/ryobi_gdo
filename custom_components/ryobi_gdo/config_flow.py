"""Adds config flow for Ryobi GDO."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RyobiApiClient
from .const import CONF_DEVICE_ID, DOMAIN

LOGGER = logging.getLogger(__name__)


class RyobiFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Ryobi GDO."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._data: dict[str, Any] = {}
        self._discovered_devices: dict[str, str] = {}
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle initial step: Ryobi account credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = RyobiApiClient(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                session=session,
            )

            try:
                auth_ok = await client.get_api_key()
                if not auth_ok:
                    errors["base"] = "invalid_auth"
                else:
                    self._data.update(user_input)
                    self._discovered_devices = await client.get_devices()

                    if not self._discovered_devices:
                        return self.async_abort(reason="no_devices_found")

                    return await self.async_step_device()
            except Exception as err:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception in config flow: %s", err)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=(user_input or {}).get(CONF_USERNAME, ""),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                            autocomplete="username",
                        ),
                    ),
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                            autocomplete="current-password",
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_device(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle device selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            await self.async_set_unique_id(str(device_id))
            self._abort_if_unique_id_configured()

            device_title = self._discovered_devices.get(
                device_id, f"Ryobi GDO ({device_id})"
            )
            return self.async_create_entry(
                title=device_title,
                data={**self._data, CONF_DEVICE_ID: device_id},
            )

        options = [
            selector.SelectOptionDict(
                value=dev_id,
                label=f"{dev_name} ({dev_id})",
            )
            for dev_id, dev_name in self._discovered_devices.items()
        ]

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DEVICE_ID,
                        default=options[0]["value"] if options else None,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_user_2(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Backwards compatibility alias for device step."""
        return await self.async_step_device(user_input)

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],
    ) -> config_entries.ConfigFlowResult:
        """Handle reauthentication upon auth failure."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Dialog to confirm and update credentials during reauth."""
        errors: dict[str, str] = {}

        if user_input is not None and self._reauth_entry:
            username = self._reauth_entry.data[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            session = async_get_clientsession(self.hass)
            client = RyobiApiClient(
                username=username,
                password=password,
                session=session,
            )

            auth_ok = await client.get_api_key()
            if not auth_ok:
                errors["base"] = "invalid_auth"
            else:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={**self._reauth_entry.data, CONF_PASSWORD: password},
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                            autocomplete="current-password",
                        ),
                    ),
                }
            ),
            errors=errors,
        )
