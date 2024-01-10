"""DataUpdateCoordinator for ryobi_gdo."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RyobiApiClient
from .const import CONF_DEVICE_ID, COORDINATOR, DOMAIN

LOGGER = logging.getLogger(__name__)


class RyobiDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, interval: int, config: ConfigEntry):
        """Initialize."""
        self.interval = timedelta(seconds=interval)
        self.name = f"Ryobi GDO ({config.data.get(CONF_DEVICE_ID)})"
        self.config = config
        self.hass = hass
        self._data = {}
        self._client = RyobiApiClient(
            config.data.get(CONF_USERNAME),
            config.data.get(CONF_PASSWORD),
            config.data.get(CONF_DEVICE_ID),
        )
        self._client.callback = self.websocket_update

        LOGGER.debug("Data will be update every %s", self.interval)

        super().__init__(hass, LOGGER, name=self.name, update_interval=self.interval)

    async def _async_update_data(self):
        """Return data."""
        result = await self._client.update()
        if result:
            self._data = self._client._data
            await self._client.ws_connect()
            return self._data
        raise UpdateFailed()

    async def send_command(self, command, args):
        """Send command to GDO."""
        await self._client.send_message(command, args)

    @callback
    async def websocket_update(self):
        """Trigger processing updated websocket data."""
        LOGGER.debug("Websocket update.")
        self._data = self._client._data
        coordinator = self.hass.data[DOMAIN][self.config.entry_id][COORDINATOR]
        coordinator.async_set_updated_data(self._data)
