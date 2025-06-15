"""API interface for Ryobi GDO."""

from __future__ import annotations

import asyncio
from collections import abc
import json
import logging

import aiohttp  # type: ignore
from aiohttp.client_exceptions import ServerConnectionError, ServerTimeoutError

from homeassistant.const import (
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import callback

from .const import (
    DEVICE_GET_ENDPOINT,
    GARAGE_UPDATE_MSG,
    HOST_URI,
    LOGIN_ENDPOINT,
    WS_AUTH_OK,
    WS_CMD_ACK,
    WS_OK,
)
from .websocket import (
    RyobiWebSocket,
    SIGNAL_CONNECTION_STATE,
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    STATE_STARTING,
    STATE_STOPPED,
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
        "4": "fault",
    }

    # FIX: Modified constructor to accept aiohttp session from Home Assistant
    def __init__(self, username: str, password: str, session: aiohttp.ClientSession, device_id: str | None = None):
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
        self.ws_listening = False
        self._ws_listen_task = None
        self._modules = {}
        # FIX: Store the session passed from Home Assistant
        self.session = session

    # FIX: Modified to use the shared aiohttp session
    async def _process_request(
        self, url: str, method: str, data: dict[str, str]
    ) -> dict | None:
        """Process HTTP requests."""
        http_hethod = getattr(self.session, method)
        LOGGER.debug("Connecting to %s using %s", url, method)
        reply = None
        try:
            async with http_hethod(url, data=data) as response:
                rawReply = await response.text()
                try:
                    reply = json.loads(rawReply)
                    if not isinstance(reply, dict):
                        reply = None
                except ValueError:
                    LOGGER.warning("Reply was not in JSON format: %s", rawReply)

                if response.status in [404, 405, 500]:
                    LOGGER.warning("HTTP Error: %s", rawReply)
        except (TimeoutError, ServerTimeoutError):
            LOGGER.error("Timeout connecting to %s", url)
        except ServerConnectionError:
            LOGGER.error("Problem connecting to server at %s", url)
        return reply

    async def get_api_key(self) -> bool:
        """Get api_key from Ryobi."""
        auth_ok = False
        url = f"https://{HOST_URI}/{LOGIN_ENDPOINT}"
        data = {"username": self.username, "password": self.password}
        method = "post"
        request = await self._process_request(url, method, data)
        if request is None:
            return auth_ok
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
        if request is None:
            return device_found
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
        if request is None:
            return devices
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

        # Reconnect logic
        if self.ws and not self.ws_listening:
            await self.ws_connect()

        update_ok = False
        url = f"https://{HOST_URI}/{DEVICE_GET_ENDPOINT}/{self.device_id}"
        data = {"username": self.username, "password": self.password}
        method = "get"
        request = await self._process_request(url, method, data)
        if request is None:
            return update_ok
        try:
            dtm = request["result"][0]["deviceTypeMap"]
            # Parse the modules
            result = await self._index_modules(dtm)

            LOGGER.debug("Modules indexed: %s", self._modules)

            # Parse initial values while we setup the websocket for push updates
            if result:
                if "garageDoor" in self._modules:
                    door_state = dtm[self._modules["garageDoor"]]["at"]["doorState"][
                        "value"
                    ]
                    self._data["door_state"] = self.DOOR_STATE[str(door_state)]
                    self._data["saftey"] = dtm[self._modules["garageDoor"]]["at"][
                        "sensorFlag"
                    ]["value"]
                    self._data["vacationMode"] = dtm[self._modules["garageDoor"]]["at"][
                        "vacationMode"
                    ]["value"]
                    if "motionSensor" in dtm[self._modules["garageDoor"]]["at"]:
                        self._data["motion"] = dtm[self._modules["garageDoor"]]["at"][
                            "motionSensor"
                        ]["value"]
                if "garageLight" in self._modules:
                    self._data["light_state"] = dtm[self._modules["garageLight"]]["at"][
                        "lightState"
                    ]["value"]
                if "backupCharger" in self._modules:
                    self._data["battery_level"] = dtm[self._modules["backupCharger"]][
                        "at"
                    ]["chargeLevel"]["value"]
                if "wifiModule" in self._modules:
                    self._data["wifi_rssi"] = dtm[self._modules["wifiModule"]]["at"][
                        "rssi"
                    ]["value"]
                if "parkAssistLaser" in self._modules:
                    self._data["park_assist"] = dtm[self._modules["parkAssistLaser"]][
                        "at"
                    ]["moduleState"]["value"]
                if "inflator" in self._modules:
                    self._data["inflator"] = dtm[self._modules["inflator"]]["at"][
                        "moduleState"
                    ]["value"]
                if "btSpeaker" in self._modules:
                    self._data["bt_speaker"] = dtm[self._modules["btSpeaker"]]["at"][
                        "moduleState"
                    ]["value"]
                    self._data["micStatus"] = dtm[self._modules["btSpeaker"]]["at"][
                        "micEnable"
                    ]["value"]
                if "fan" in self._modules:
                    self._data["fan"] = dtm[self._modules["fan"]]["at"]["speed"][
                        "value"
                    ]

            if "name" in request["result"][0]["metaData"]:
                self._data["device_name"] = request["result"][0]["metaData"]["name"]
            update_ok = True
            LOGGER.debug("Data: %s", self._data)
            if not self.ws:
                # Start websocket listening
                # FIX: Pass the shared session to the websocket client
                self.ws = RyobiWebSocket(
                    self._process_message, self.username, self.api_key, self.device_id, self.session
                )
        except KeyError as error:
            LOGGER.error("Exception while parsing answer to update device: %s", error)
        return update_ok

    async def _index_modules(self, dtm: dict) -> bool:
        """Index and add modules to dictorary."""
        # Known modules
        module_list = [
            "garageDoor",
            "backupCharger",
            "garageLight",
            "wifiModule",
            "parkAssistLaser",
            "inflator",
            "btSpeaker",
            "fan",
        ]
        frame = {}
        try:
            for key in dtm:
                for module in module_list:
                    if module in key:
                        frame[module] = key
        except Exception as err:
            LOGGER.error("Problem parsing module list: %s", err)
            return False
        self._modules.update(frame)
        return True

    def get_module(self, module: str) -> int:
        """Return module number for device."""
        return self._modules[module].split("_")[1]

    def get_module_type(self, module: str) -> int:
        """Return module type for device."""
        module_type = {
            "garageDoor": 5,
            "backupCharger": 6,
            "garageLight": 5,
            "wifiModule": 7,
            "parkAssistLaser": 1,
            "inflator": 4,
            "btSpeaker": 2,
            "fan": 3,
        }
        return module_type[module]

    async def ws_connect(self) -> None:
        """Connect to websocket."""
        if self.api_key is None:
            LOGGER.error("Problem refreshing API key.")
            raise APIKeyError

        assert self.ws
        if self.ws_listening:
            LOGGER.debug("Websocket already connected.")
            return

        LOGGER.debug("Websocket not connected, connecting now...")
        await self.open_websocket()

    async def ws_disconnect(self) -> bool:
        """Disconnect from websocket."""
        assert self.ws
        if not self.ws_listening:
            LOGGER.debug("Websocket already disconnected.")
        await self.ws.close()

    async def open_websocket(self) -> None:
        """Connect WebSocket to Ryobi Server."""
        try:
            LOGGER.debug("Attempting to find running loop...")
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
            LOGGER.debug("Using new event loop...")

        if not self.ws_listening:
            self._ws_listen_task = loop.create_task(self.ws.listen())

    @callback
    async def _process_message(
        self, msg_type: str, msg: dict, error: str | None = None
    ) -> None:
        """Process websocket data and handle websocket signaling."""
        LOGGER.debug(
            "Websocket callback msg_type: %s msg: %s err: %s", msg_type, msg, error
        )
        if msg_type == SIGNAL_CONNECTION_STATE:
            self.ws_listening = False
            if msg == STATE_CONNECTED:
                LOGGER.debug("Websocket to %s successful", self.ws.url)
                self.ws_listening = True
            elif msg == STATE_STARTING:
                # Mark websocket as starting to prevent duplicate
                # connection attempts while negotiating
                LOGGER.debug("Websocket to %s starting", self.ws.url)
                self.ws_listening = True
            elif msg == STATE_DISCONNECTED:
                LOGGER.debug(
                    "Websocket to %s disconnected",
                    self.ws.url,
                )
            # Stopped websockets without errors are expected during shutdown
            # and ignored
            elif msg == STATE_STOPPED and error:
                LOGGER.error(
                    "Websocket to %s failed, aborting [Error: %s]",
                    self.ws.url,
                    error,
                )
            # Flag websocket as not listening
            # STATE_STOPPED with no error
            else:
                LOGGER.debug("Websocket state: %s error: %s", msg, error)
            if self.callback is not None:
                await self.callback()

        elif msg_type == "data":
            message = msg
            LOGGER.debug("Websocket data: %s", message)

            if METHOD in message:
                if message[METHOD] == GARAGE_UPDATE_MSG:
                    LOGGER.debug("Websocket update message.")
                    if PARAMS in message:
                        await self.parse_message(message[PARAMS])

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
        else:
            LOGGER.debug("Unknown message from websocket: %s type: %s", msg, msg_type)

    async def parse_message(self, data: dict) -> None:
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

            # Garage Door updates
            if "garageDoor" in key:
                if module_name == "doorState":
                    self._data["door_state"] = self.DOOR_STATE[str(data[key]["value"])]
                elif module_name == "motionSensor":
                    self._data["motion"] = data[key]["value"]
                elif module_name == "vacationMode":
                    self._data["vacationMode"] = data[key]["value"]
                elif module_name == "sensorFlag":
                    self._data["safety"] = data[key]["value"]
                attributes = {}
                for item in data[key]:
                    attributes[item] = data[key][item]
                self._data["door_attributes"] = attributes

            # Garage Light updates
            elif "garageLight" in key:
                if module_name == "lightState":
                    self._data["light_state"] = data[key]["value"]
                attributes = {}
                for item in data[key]:
                    attributes[item] = data[key][item]
                self._data["light_attributes"] = attributes

            # Park Assist updates
            elif "parkAssistLaser" in key:
                if module_name == "moduleState":
                    self._data["park_assist"] = data[key]["value"]

            # Bluetooth Speaker Updates
            elif "btSpeaker" in key:
                if module_name == "moduleState":
                    self._data["bt_speaker"] = data[key]["value"]
                elif module_name == "micEnabled":
                    self._data["micStatus"] = data[key]["value"]

            # Inflator module
            elif "inflator" in key:
                if module_name == "moduleState":
                    self._data["inflator"] = data[key]["value"]

            # fan module
            elif "fan" in key:
                if module_name == "speed":
                    self._data["fan"] = data[key]["value"]
            else:
                LOGGER.error("Websocket data update unknown module: %s", key)

        if self.callback is not None:
            await self.callback()




class APIKeyError(Exception):
    """Exception for missing API key."""
