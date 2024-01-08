"""Adds config flow for Ryobi GDO."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector

from .api import RyobiApiClient
from .const import DOMAIN, CONF_DEVICE_ID


class RyobiFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Ryobit GDO."""
    
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._data = {}

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            result = await self._test_credentials(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
            )
            if not result:
                errors["base"] = "Authentication failed. Please check your credentials."
            else:
                self._data.update(user_input)
                return await self.async_step_user_2()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=(user_input or {}).get(CONF_USERNAME),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT
                        ),
                    ),
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_user_2(
        self,
        user_input: dict | None = None,
    ) -> config_entries.FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(
                title=self._data[CONF_USERNAME],
                data=self._data,
            )
        device_list = await self._get_device_ids(
            self._data[CONF_USERNAME], self._data[CONF_PASSWORD]
        )
        return self.async_show_form(
            step_id="user_2",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DEVICE_ID,
                        default=(user_input or {}).get(CONF_DEVICE_ID),
                    ): vol.In(device_list),
                }
            ),
            errors=errors,
        )

    async def _test_credentials(self, username: str, password: str) -> bool:
        """Validate credentials and retrieve device IDs."""
        client = RyobiApiClient(username=username, password=password)

        # Validate credentials
        return await client.get_api_key()

    async def _get_device_ids(self, username: str, password: str) -> list:
        """Return list of device IDs."""
        client = RyobiApiClient(username=username, password=password)

        # Get the devices associated with account
        return await client.get_devices()
