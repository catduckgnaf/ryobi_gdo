"""DataUpdateCoordinator for ryobi_gdo."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RyobiApiClient
from .const import CONF_DEVICE_ID

LOGGER = logging.getLogger(__name__)


class RyobiDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Ryobi API and handling push updates."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, interval: int, entry: ConfigEntry) -> None:
        """Initialize."""
        self.interval = timedelta(seconds=interval)
        self.device_id = str(entry.data.get(CONF_DEVICE_ID, ""))
        self.name = f"Ryobi GDO ({self.device_id})"
        self.config_entry = entry
        self.hass = hass

        session = async_get_clientsession(hass)
        self.client = RyobiApiClient(
            username=str(entry.data.get(CONF_USERNAME, "")),
            password=str(entry.data.get(CONF_PASSWORD, "")),
            session=session,
            device_id=self.device_id,
        )
        self.client.callback = self.websocket_update

        super().__init__(hass, LOGGER, name=self.name, update_interval=self.interval)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest data from API."""
        try:
            result = await self.client.update()
            if not result:
                if self.client._data:
                    LOGGER.warning(
                        "Unable to refresh data for device %s from API, using cached data",
                        self.device_id,
                    )
                    return dict(self.client._data)
                raise UpdateFailed(f"Unable to refresh data for device {self.device_id}")
            return dict(self.client._data)
        except Exception as err:
            if self.client._data:
                LOGGER.warning(
                    "Error communicating with Ryobi API (%s), using cached data for %s",
                    err,
                    self.device_id,
                )
                return dict(self.client._data)
            raise UpdateFailed(f"Error communicating with Ryobi API: {err}") from err

    async def send_command(self, device: str, command: str, value: Any) -> None:
        """Send command to GDO via WebSocket."""
        await self._websocket_check()
        module = self.client.get_module(device)
        module_type = self.client.get_module_type(device)
        if self.client.ws is not None and self.client.ws.state == "connected":
            await self.client.ws.send_message(module, module_type, command, value)
        else:
            LOGGER.error("Websocket is not connected, unable to send command %s", command)

    async def _websocket_check(self) -> None:
        """Handle reconnection of websocket if not connected."""
        ws = self.client.ws
        if ws is not None and ws.state not in ("connected", "starting"):
            LOGGER.debug("Websocket inactive, ensuring reconnection")
            if ws.state != "stopped":
                await ws.close()
        if not self.client.ws_listening:
            LOGGER.debug("Attempting websocket reconnection")
            await self.client.ws_connect()

    async def websocket_update(self) -> None:
        """Trigger processing updated websocket data."""
        LOGGER.debug("Processing websocket data push")
        self.async_set_updated_data(dict(self.client._data))
