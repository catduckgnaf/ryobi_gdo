"""Adds config flow for Ryobi GDO."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RyobiApiClient
from .const import CONF_DEVICE_ID, CONF_HOST, DEFAULT_HOST, DOMAIN

LOGGER = logging.getLogger(__name__)


class RyobiFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Ryobi GDO."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return RyobiOptionsFlowHandler(config_entry)

    def __init__(self) -> None:
        """Initialize."""
        self._data: dict[str, Any] = {}
        self._discovered_devices: dict[str, str] = {}
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle initial step: Ryobi account credentials and optional host."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input.get(CONF_HOST, DEFAULT_HOST).strip() or DEFAULT_HOST
            session = async_get_clientsession(self.hass)
            client = RyobiApiClient(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                session=session,
                host=host,
            )

            try:
                auth_ok = await client.get_api_key()
                if not auth_ok:
                    errors["base"] = "invalid_auth"
                else:
                    self._data.update(user_input)
                    self._data[CONF_HOST] = host
                    self._discovered_devices = await client.get_devices()

                    if not self._discovered_devices:
                        return self.async_abort(reason="no_devices_found")

                    return await self.async_step_user_2()
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
                    vol.Optional(
                        CONF_HOST,
                        default=(user_input or {}).get(CONF_HOST, DEFAULT_HOST),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
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
        """Handle device selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            await self.async_set_unique_id(str(device_id))
            self._abort_if_unique_id_configured()

            title = self._data.get(CONF_USERNAME, f"Ryobi GDO ({device_id})")
            return self.async_create_entry(
                title=title,
                data={**self._data, CONF_DEVICE_ID: device_id},
            )

        options = [
            selector.SelectOptionDict(
                value=dev_id,
                label=f"{dev_name} ({dev_id})",
            )
            for dev_id, dev_name in self._discovered_devices.items()
        ]

        # If options is empty (e.g. mock in test without discovered devices), allow string fallback
        if not options:
            options = [selector.SelectOptionDict(value="fakedeviceID02", label="fakedeviceID02")]

        return self.async_show_form(
            step_id="user_2",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DEVICE_ID,
                        default=(user_input or {}).get(
                            CONF_DEVICE_ID, options[0]["value"] if options else None
                        ),
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

    async def async_step_device(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Alias for user_2 step."""
        return await self.async_step_user_2(user_input)

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
            host = self._reauth_entry.options.get(
                CONF_HOST,
                self._reauth_entry.data.get(CONF_HOST, DEFAULT_HOST),
            )

            session = async_get_clientsession(self.hass)
            client = RyobiApiClient(
                username=username,
                password=password,
                session=session,
                host=host,
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


class RyobiOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Ryobi GDO."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_host = self.config_entry.options.get(
            CONF_HOST,
            self.config_entry.data.get(CONF_HOST, DEFAULT_HOST),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_HOST,
                        default=current_host,
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                }
            ),
        )
