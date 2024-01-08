"""Adds config flow for Ryobi GDO."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector

from .api import RyobiApiClient
from .const import DOMAIN, LOGGER


class RyobiFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
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
        client = RyobiApiClient(username=username, password=password)

        # Validate credentials
        return await client.get_api_key()
