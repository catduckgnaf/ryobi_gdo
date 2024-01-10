"""API interface for Ryobi GDO."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp  # type: ignore
from aiohttp.client_exceptions import ServerConnectionError, ServerTimeoutError
import websockets

from homeassistant.const import (
    STATE_CLOSED,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    STATE_OPENING,
)

from .const import DEVICE_GET_ENDPOINT, DEVICE_SET_ENDPOINT, HOST_URI, LOGIN_ENDPOINT

LOGGER = logging.getLogger(__name__)


class RyobiApiClient:
    """Class for interacting with the Ryobi Garage Door Opener API."""

    DOOR_STATE = {
        "0": STATE_CLOSED,
        "1": STATE_OPEN,
        "3": STATE_OPENING,
    }

    LIGHT_STATE = {
        "False": STATE_OFF,
        "True": STATE_ON,
    }

    def __init__(self, username: str, password: str, device_id: str | None = None):
        """Initialize the API object."""
        self.username = username
        self.password = password
        self.device_id = device_id
        self.door_state = None
        self.light_state = None
        self.battery_level = None
        self.api_key = None
        self._data = {}

    async def _process_request(
        self, url: str, method: str, data: dict[str, str]
    ) -> Any:
        """Process HTTP requests."""
        async with aiohttp.ClientSession() as session:
            http_hethod = getattr(session, method)
            LOGGER.debug("Connecting to %s using %s", url, method)
            try:
                async with http_hethod(url, data=data) as response:
                    reply = await response.text()
                    try:
                        reply = json.loads(reply)
                    except ValueError:
                        LOGGER.warning(
                            "Reply was not in JSON format: %s", response.text()
                        )

                    if response.status in [404, 405, 500]:
                        LOGGER.warning("HTTP Error: %s", response.text())
            except (TimeoutError, ServerTimeoutError):
                LOGGER.error("Timeout connecting to %s", url)
            except ServerConnectionError:
                LOGGER.error("Problem connecting to server at %s", url)
            await session.close()
            return reply

    async def get_api_key(self) -> bool:
        """Get api_key from Ryobi."""
        auth_ok = False
        url = f"https://{HOST_URI}/{LOGIN_ENDPOINT}"
        data = {"username": self.username, "password": self.password}
        method = "post"
        request = await self._process_request(url, method, data)
        try:
            resp_meta = request["result"]["metaData"]
            self.api_key = resp_meta["wskAuthAttempts"][0]["apiKey"]
            auth_ok = True
        except KeyError:
            LOGGER.error("Exception while parsing Ryobi answer to get API key")
        return auth_ok

    async def check_device_id(self) -> bool:
        """Check device_id from Ryobi."""
        device_found = False
        url = f"https://{HOST_URI}/{DEVICE_GET_ENDPOINT}"
        data = {"username": self.username, "password": self.password}
        method = "get"
        request = await self._process_request(url, method, data)
        try:
            result = request["result"]
        except KeyError:
            return device_found
        if len(result) == 0:
            LOGGER.error("API error: empty result")
        else:
            for data in result:
                if data["varName"] == self.device_id:
                    device_found = True
        return device_found

    async def get_devices(self) -> list:
        """Return list of devices found."""
        devices = {}
        url = f"https://{HOST_URI}/{DEVICE_GET_ENDPOINT}"
        data = {"username": self.username, "password": self.password}
        method = "get"
        request = await self._process_request(url, method, data)
        try:
            result = request["result"]
        except KeyError:
            return devices
        if len(result) == 0:
            LOGGER.error("API error: empty result")
        else:
            for data in result:
                devices[data["varName"]] = data["metaData"]["name"]
        return devices

    async def update(self) -> bool:
        """Update door status from Ryobi."""
        if self.api_key is None:
            result = await self.get_api_key()
            if not result:
                LOGGER.error("Problem refreshing API key.")
                return False
        update_ok = False
        url = f"https://{HOST_URI}/{DEVICE_GET_ENDPOINT}/{self.device_id}"
        data = {"username": self.username, "password": self.password}
        method = "get"
        request = await self._process_request(url, method, data)
        try:
            dtm = request["result"][0]["deviceTypeMap"]
            door_state = dtm["garageDoor_7"]["at"]["doorState"]["value"]
            self._data["door_state"] = self.DOOR_STATE[str(door_state)]
            light_state = dtm["garageLight_7"]["at"]["lightState"]["value"]
            self._data["light_state"] = self.LIGHT_STATE[str(light_state)]
            self._data["battery_level"] = dtm["backupCharger_8"]["at"]["chargeLevel"][
                "value"
            ]
            self._data["wifi_rssi"] = dtm["wifiModule_9"]["at"]["rssi"]["value"]
            self._data["park_assist"] = dtm["parkAssistLaser_3"]["at"]["moduleState"][
                "value"
            ]
            update_ok = True
            LOGGER.debug("Data: %s", self._data)
        except KeyError as error:
            LOGGER.error("Exception while parsing answer to update device: %s", error)
        return update_ok

    def get_door_status(self):
        """Get current door status."""
        return self.door_state

    def get_battery_level(self):
        """Get current battery level."""
        return self.battery_level

    def get_light_status(self):
        """Get current light status."""
        return self.light_state

    def get_device_id(self):
        """Get device_id."""
        return self.device_id

    async def close_device(self):
        """Close Device."""
        return await self.send_message("doorCommand", 0)

    async def open_device(self):
        """Open Device."""
        return await self.send_message("doorCommand", 1)

    async def send_message(self, command, value):
        """Send message to API."""
        url = f"wss://{HOST_URI}/{DEVICE_SET_ENDPOINT}"
        LOGGER.debug("Connecting to %s", url)
        async with websockets.connect(url) as websocket:
            try:
                auth_mssg = json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "srvWebSocketAuth",
                        "params": {"varName": self.username, "apiKey": self.api_key},
                    }
                )
                LOGGER.debug("Sending websocket authentication.")
                await websocket.send(auth_mssg)
                reply = await websocket.recv()
                LOGGER.debug("Websocket auth reply: %s", reply)
            except Exception as ex:
                LOGGER.error("Exception during websocket authentification: %s", ex)
                await websocket.close()
                return

            try:
                pay_load = json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": "gdoModuleCommand",
                        "params": {
                            "msgType": 16,
                            "moduleType": 5,
                            "portId": 7,
                            "moduleMsg": {command: value},
                            "topic": self.device_id,
                        },
                    }
                )
                LOGGER.debug("Sending command: %s value: %s", command, value)
                LOGGER.debug("Full message: %s", pay_load)
                await websocket.send(pay_load)
                pay_load = ""
                reply = await websocket.recv()
                LOGGER.debug("Websocket command reply: %s", reply)
            except Exception as ex:
                LOGGER.error("Exception during sending message: %s", ex)
                await websocket.close()
                return
        await websocket.close()
