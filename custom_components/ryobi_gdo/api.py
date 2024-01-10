"""API interface for Ryobi GDO."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import abc
from typing import Any, Callable

import aiohttp  # type: ignore
from aiohttp.client_exceptions import ServerConnectionError, ServerTimeoutError
import websockets

from homeassistant.const import (
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    STATE_OPENING,
)

from .const import (
    DEVICE_GET_ENDPOINT,
    DEVICE_SET_ENDPOINT,
    GARAGE_UPDATE_MSG,
    HOST_URI,
    LOGIN_ENDPOINT,
    SOCK_CLOSE,
    SOCK_CONNECTED,
    WS_AUTH_OK,
    WS_CMD_ACK,
    WS_OK,
)

LOGGER = logging.getLogger(__name__)

METHOD = "method"
PARAMS = "params"
RESULT = "result"


class RyobiApiClient:
    """Class for interacting with the Ryobi Garage Door Opener API."""

    DOOR_STATE = {
        "0": STATE_CLOSED,
        "1": STATE_OPEN,
        "2": STATE_CLOSING,
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
        self.ws = None
        self.callback: abc.Callable | None = None
        self.socket_state = None

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
        if self.socket_state != SOCK_CONNECTED:
            LOGGER.warning("Websocket not yet connected, unable to send command.")
            return

        ws_command = {
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
        LOGGER.debug("Sending command: %s value: %s", command, value)
        LOGGER.debug("Full message: %s", ws_command)
        await self.websocket_send(ws_command)

    async def ws_connect(self) -> None:
        """Connect to websocket."""
        if self.socket_state == SOCK_CONNECTED:
            LOGGER.debug("Websocket already connected.")
            return True

        LOGGER.debug("Websocket not connected, connecting now...")
        await self.open_websocket()
        await self.websocket_auth()
        await asyncio.sleep(0.5)
        await self.websocket_subscribe()

    async def ws_disconnect(self) -> bool:
        """Disconnect from websocket."""
        if self.socket_state != SOCK_CONNECTED:
            LOGGER.debug("Websocket already disconnected.")
            return True
        self.ws.close()
        self.socket_state = SOCK_CLOSE

    async def open_websocket(self) -> bool | None:
        """Connect WebSocket to Ryobi Server."""
        if self.api_key is None:
            result = await self.get_api_key()
            if not result:
                LOGGER.error("Problem refreshing API key.")
                return False

        header = {"Connection": "keep-alive, Upgrade", "handshakeTimeout": "10000"}
        url = f"wss://{HOST_URI}/{DEVICE_SET_ENDPOINT}"

        LOGGER.debug("Websocket connecting to %s", url)

        self.ws = websockets.connect(url, extra_heders=header)
        async with self.ws as websocket:
            try:
                async for message in websocket:
                    self.socket_state = SOCK_CONNECTED
                    await self._process_message(message)

            except websockets.ConnectionClosed as err:
                self.socket_state = SOCK_CLOSE
                LOGGER.error(
                    "Websocket closed, attempting to reconnect. Error: %s", err
                )
                await self.open_websocket()

    async def websocket_send(self, message: dict) -> bool:
        """Send websocket message."""
        json_message = json.dumps(message)
        LOGGER.debug("Websocket sending data: %s", json_message)

        try:
            self.ws.send(json_message)
            LOGGER.debug("Websocket message sent.")
            return True
        except websockets.ConnectionClosed as err:
            self.socket_state = SOCK_CLOSE
            LOGGER.error("Websocket error sending message: %s", err)
        return False

    async def _process_message(self, msg: dict) -> None:
        """Process websocket data."""
        message = json.loads(msg)
        LOGGER.debug("Websocket data: %s", message)

        if METHOD in message:
            if message[METHOD] == GARAGE_UPDATE_MSG:
                LOGGER.debug("Websocket garage door update message.")
                if PARAMS in message:
                    self.parse_message(message[PARAMS])

            elif message[METHOD] == WS_AUTH_OK:
                if message[PARAMS]["authorized"]:
                    LOGGER.debug("Websocket API key authorized.")
                else:
                    LOGGER.error("Websocket API key not authorized.")

        elif RESULT in message:
            if RESULT in message[RESULT]:
                if message[WS_CMD_ACK][RESULT] == WS_OK:
                    LOGGER.debug("Websocket result OK.")
            if "authorized" in message[WS_CMD_ACK]:
                if message[WS_CMD_ACK]["authorized"]:
                    LOGGER.debug("Websocket User authorization OK.")

        else:
            LOGGER.error("Websocket unknown message received: %s", message)

    def parse_message(self, data: dict) -> None:
        """Parse incoming updated data."""
        if self.device_id != data["varName"]:
            LOGGER.debug(
                "Websocket update for %s does not match %s",
                data["varName"],
                self.device_id,
            )
            return None

        for key in data:
            if key in ["topic", "varName", "id"]:
                continue

            LOGGER.debug("Websocket parsing update for item %s: %s", key, data[key])

            module_name = key.split(".")[1]

            if "garageDoor" in key:
                self._data["door_state"] = data["doorState"]["value"]
                attributes = {}
                for item in data[key]:
                    attributes[module_name][item] = data[key][item]
                self._data["door_attributes"] = attributes
            elif "garageLight" in key:
                self._data["light_state"] = data["light_state"]["value"]
                attributes = {}
                for item in data[key]:
                    attributes[module_name][item] = data[key][item]
                self._data["light_attributes"] = attributes

            else:
                LOGGER.error("Websocket data update unknown module: %s", key)

        if self.callback is not None:
            self.callback()

    async def websocket_auth(self) -> None:
        """Authenticate with Ryobi server."""
        LOGGER.debug("Websocket attempting authenticate with server.")
        auth_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "srvWebSocketAuth",
            "params": {"varName": self.username, "apiKey": self.api_key},
        }
        await self.websocket_send(auth_request)

    async def websocket_subscribe(self) -> None:
        """Send subscription for device updates."""
        LOGGER.debug("Websocket subscribing to notifications for %s", self.device_id)
        subscribe = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "wskSubscribe",
            "params": {"topic": self.device_id + ".wskAttributeUpdateNtfy"},
        }
        await self.websocket_send(subscribe)
