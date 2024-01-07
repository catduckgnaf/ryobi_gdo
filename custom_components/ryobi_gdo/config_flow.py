"""Adds config flow for Ryobi GDO."""
from __future__ import annotations

import voluptuous as vol
import aiohttp

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import (
    RyobiApiClient

)
from .const import DOMAIN, LOGGER

# ... (existing import statements)

class RyobiFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            try:
                await self._test_credentials(
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
            except Exception as ex:
                errors["base"] = "Authentication failed. Please check your credentials."
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                )
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

    async def _test_credentials(self, username: str, password: str) -> None:
        """Validate credentials and retrieve device IDs."""
        client = RyobiApiClient(
            username=username,
            password=password,
            session=async_create_clientsession(self.hass),
        )

        # Validate credentials
        await client.async_get_data()

        # Retrieve device IDs
        uandp = {'username': username, 'password': password}

        async with aiohttp.ClientSession() as session:
            # Perform login
            async with session.post('https://tti.tiwiconnect.com/api/login', data=uandp) as login_response:
                login_response.raise_for_status()  # Raise exception for non-2xx status codes
                login_result = await login_response.json()

                # Check if login was successful
                if login_result.get('success'):
                    # Perform devices request
                    async with session.get('https://tti.tiwiconnect.com/api/devices', params=uandp) as devices_response:
                        devices_response.raise_for_status()  # Raise exception for non-2xx status codes
                        devices_result = await devices_response.json()

                        # Check if devices request was successful
                        if devices_result.get('success'):
                            # Process the devices
                            for result in devices_result['result']:
                                if 'gdoMasterUnit' in result.get('deviceTypeIds', []):
                                    # Use Home Assistant logger
                                    self.logger.info(
                                        "%s - Device ID: %s",
                                        result['metaData']['name'],
                                        result['varName']
                                    )
                        else:
                            raise Exception("Failed to retrieve devices. Check your credentials and try again.")
                else:
                    raise Exception("Login failed. Check your credentials and try again.")
