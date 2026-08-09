"""API interface for Ryobi GDO."""

from __future__ import annotations

import asyncio
from collections import abc
import json
import logging
from typing import Any

import aiohttp

from homeassistant.const import (
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)

from .const import (
    DEVICE_GET_ENDPOINT,
    GARAGE_UPDATE_MSG,
    HOST_URI,
    LOGIN_ENDPOINT,
    REQUEST_TIMEOUT,
    WS_AUTH_OK,
    WS_CMD_ACK,
    WS_OK,
)
from .websocket import (
    SIGNAL_CONNECTION_STATE,
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    STATE_STARTING,
    STATE_STOPPED,
    RyobiWebSocket,
)

LOGGER = logging.getLogger(__name__)

METHOD = "method"
PARAMS = "params"
RESULT = "result"


class RyobiApiError(Exception):
    """Base exception for Ryobi API errors."""


class RyobiAuthError(RyobiApiError):
    """Exception for authentication errors."""


class RyobiConnectionError(RyobiApiError):
    """Exception for connection errors."""


class APIKeyError(RyobiAuthError):
    """Exception for missing API key."""


class RyobiApiClient:
    """Class for interacting with the Ryobi Garage Door Opener API."""

    DOOR_STATE = {
        "0": STATE_CLOSED,
        "1": STATE_OPEN,
        "2": STATE_CLOSING,
        "3": STATE_OPENING,
        "4": "fault",
    }

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        device_id: str | None = None,
    ) -> None:
        """Initialize the API object."""
        self.username = username
        self.password = password
        self.device_id = device_id
        self.door_state: str | None = None
        self.light_state: bool | None = None
        self.battery_level: int | None = None
        self.api_key: str | None = None
        self._data: dict[str, Any] = {}
        self.ws: RyobiWebSocket | None = None
        self.callback: abc.Callable | None = None
        self.socket_state: str | None = None
        self.ws_listening = False
        self._ws_listen_task: asyncio.Task | None = None
        self._modules: dict[str, str] = {}
        self.session = session

    async def _process_request(
        self, url: str, method: str, data: dict[str, str]
    ) -> dict | None:
        """Process HTTP requests."""
        http_method = getattr(self.session, method.lower())
        LOGGER.debug("Connecting to %s using %s", url, method)
        reply = None
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with http_method(url, data=data) as response:
                    raw_reply = await response.text()
                    try:
                        reply = json.loads(raw_reply)
                        if not isinstance(reply, dict):
                            reply = None
                    except ValueError:
                        LOGGER.warning("Reply was not in JSON format: %s", raw_reply)

                    if response.status in [401, 403]:
                        LOGGER.warning("Authentication failed on %s: %s", url, raw_reply)
                        return None
                    if response.status in [404, 405, 500]:
                        LOGGER.warning("HTTP Error %s: %s", response.status, raw_reply)
        except TimeoutError:
            LOGGER.error("Timeout connecting to %s", url)
        except aiohttp.ClientError as err:
            LOGGER.error("Client error connecting to %s: %s", url, err)
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected error during HTTP request to %s: %s", url, err)
        return reply

    async def get_api_key(self) -> bool:
        """Get API key from Ryobi."""
        url = f"https://{HOST_URI}/{LOGIN_ENDPOINT}"
        data = {"username": self.username, "password": self.password}
        request = await self._process_request(url, "post", data)
        if request is None:
            return False
        try:
            resp_meta = request["result"]["metaData"]
            self.api_key = resp_meta["wskAuthAttempts"][0]["apiKey"]
            return True
        except (KeyError, IndexError, TypeError) as err:
            LOGGER.error("Failed to parse API key from response: %s", err)
            return False

    async def check_device_id(self) -> bool:
        """Check if configured device_id exists on Ryobi account."""
        url = f"https://{HOST_URI}/{DEVICE_GET_ENDPOINT}"
        data = {"username": self.username, "password": self.password}
        request = await self._process_request(url, "get", data)
        if request is None:
            return False
        try:
            result = request.get("result", [])
            for device in result:
                if device.get("varName") == self.device_id:
                    return True
        except (KeyError, TypeError):
            return False
        return False

    async def get_devices(self) -> dict[str, str]:
        """Return dict of devices found: {varName: friendly_name}."""
        devices: dict[str, str] = {}
        url = f"https://{HOST_URI}/{DEVICE_GET_ENDPOINT}"
        data = {"username": self.username, "password": self.password}
        request = await self._process_request(url, "get", data)
        if request is None:
            return devices
        try:
            result = request.get("result", [])
            for device in result:
                var_name = device.get("varName")
                meta_data = device.get("metaData", {})
                name = meta_data.get("name", var_name)
                if var_name:
                    devices[var_name] = name
        except (KeyError, TypeError) as err:
            LOGGER.error("Error parsing device list: %s", err)
        return devices

    async def update(self) -> bool:
        """Update door status and module metadata from Ryobi."""
        if self.api_key is None:
            result = await self.get_api_key()
            if not result:
                LOGGER.error("Problem obtaining API key")
                return False

        if not self.device_id:
            LOGGER.error("No device ID configured")
            return False

        url = f"https://{HOST_URI}/{DEVICE_GET_ENDPOINT}/{self.device_id}"
        data = {"username": self.username, "password": self.password}
        request = await self._process_request(url, "get", data)
        if request is None:
            return False

        try:
            result_list = request.get("result", [])
            if not result_list:
                LOGGER.error("Empty result received for device %s", self.device_id)
                return False

            first_result = result_list[0]
            dtm = first_result.get("deviceTypeMap", {})

            # Parse and index installed modules
            await self._index_modules(dtm)
            LOGGER.debug("Modules indexed for %s: %s", self.device_id, self._modules)

            if "garageDoor" in self._modules:
                gdo_key = self._modules["garageDoor"]
                gdo_at = dtm.get(gdo_key, {}).get("at", {})
                if "doorState" in gdo_at:
                    raw_state = str(gdo_at["doorState"].get("value", "4"))
                    self._data["door_state"] = self.DOOR_STATE.get(raw_state, "fault")
                if "sensorFlag" in gdo_at:
                    # FIX: Corrected typo 'saftey' -> 'safety'
                    self._data["safety"] = gdo_at["sensorFlag"].get("value")
                if "vacationMode" in gdo_at:
                    self._data["vacationMode"] = gdo_at["vacationMode"].get("value")
                if "motionSensor" in gdo_at:
                    self._data["motion"] = gdo_at["motionSensor"].get("value")

            if "garageLight" in self._modules:
                light_key = self._modules["garageLight"]
                light_at = dtm.get(light_key, {}).get("at", {})
                if "lightState" in light_at:
                    self._data["light_state"] = light_at["lightState"].get("value")

            if "backupCharger" in self._modules:
                charger_key = self._modules["backupCharger"]
                charger_at = dtm.get(charger_key, {}).get("at", {})
                if "chargeLevel" in charger_at:
                    self._data["battery_level"] = charger_at["chargeLevel"].get("value")

            if "wifiModule" in self._modules:
                wifi_key = self._modules["wifiModule"]
                wifi_at = dtm.get(wifi_key, {}).get("at", {})
                if "rssi" in wifi_at:
                    self._data["wifi_rssi"] = wifi_at["rssi"].get("value")

            if "parkAssistLaser" in self._modules:
                laser_key = self._modules["parkAssistLaser"]
                laser_at = dtm.get(laser_key, {}).get("at", {})
                if "moduleState" in laser_at:
                    self._data["park_assist"] = laser_at["moduleState"].get("value")

            if "inflator" in self._modules:
                inflator_key = self._modules["inflator"]
                inflator_at = dtm.get(inflator_key, {}).get("at", {})
                if "moduleState" in inflator_at:
                    self._data["inflator"] = inflator_at["moduleState"].get("value")

            if "btSpeaker" in self._modules:
                speaker_key = self._modules["btSpeaker"]
                speaker_at = dtm.get(speaker_key, {}).get("at", {})
                if "moduleState" in speaker_at:
                    self._data["bt_speaker"] = speaker_at["moduleState"].get("value")
                if "micEnable" in speaker_at:
                    self._data["micStatus"] = speaker_at["micEnable"].get("value")

            if "fan" in self._modules:
                fan_key = self._modules["fan"]
                fan_at = dtm.get(fan_key, {}).get("at", {})
                if "speed" in fan_at:
                    self._data["fan"] = fan_at["speed"].get("value")

            if "metaData" in first_result and "name" in first_result["metaData"]:
                self._data["device_name"] = first_result["metaData"]["name"]
            else:
                self._data.setdefault("device_name", f"Ryobi GDO {self.device_id}")

            LOGGER.debug("Updated data: %s", self._data)

            if not self.ws and self.api_key and self.device_id:
                self.ws = RyobiWebSocket(
                    self._process_message,
                    self.username,
                    self.api_key,
                    self.device_id,
                    self.session,
                )

            return True

        except (KeyError, IndexError, TypeError) as error:
            LOGGER.error("Exception while parsing update response: %s", error)
            return False

    async def _index_modules(self, dtm: dict) -> bool:
        """Index and add modules to dictionary."""
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
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.error("Problem parsing module list: %s", err)
            return False
        self._modules.update(frame)
        return True

    def get_module(self, module: str) -> int:
        """Return module port number for device."""
        if module not in self._modules:
            LOGGER.warning("Module %s not found in indexed modules", module)
            return 0
        return int(self._modules[module].split("_")[1])

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
        return module_type.get(module, 0)

    async def ws_connect(self) -> None:
        """Connect to websocket."""
        if self.api_key is None:
            result = await self.get_api_key()
            if not result:
                raise APIKeyError("Could not retrieve API key for WebSocket")

        if not self.ws:
            self.ws = RyobiWebSocket(
                self._process_message,
                self.username,
                self.api_key,
                self.device_id,  # type: ignore[arg-type]
                self.session,
            )

        if self.ws_listening:
            LOGGER.debug("Websocket already listening")
            return

        LOGGER.debug("Websocket not connected, initiating connection")
        await self.open_websocket()

    async def ws_disconnect(self) -> None:
        """Disconnect from websocket."""
        if self.ws:
            await self.ws.close()
        if self._ws_listen_task and not self._ws_listen_task.done():
            self._ws_listen_task.cancel()
        self.ws_listening = False

    async def open_websocket(self) -> None:
        """Connect WebSocket to Ryobi Server."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

        if not self.ws_listening and self.ws:
            self._ws_listen_task = loop.create_task(self.ws.listen())

    async def _process_message(
        self, msg_type: str, msg: Any, error: str | None = None
    ) -> None:
        """Process websocket data and handle connection signaling."""
        LOGGER.debug("Websocket callback msg_type: %s, msg: %s, err: %s", msg_type, msg, error)

        if msg_type == SIGNAL_CONNECTION_STATE:
            self.ws_listening = False
            if msg == STATE_CONNECTED:
                LOGGER.debug("Websocket connection established")
                self.ws_listening = True
            elif msg == STATE_STARTING:
                LOGGER.debug("Websocket connection starting")
                self.ws_listening = True
            elif msg == STATE_DISCONNECTED:
                LOGGER.debug("Websocket disconnected")
            elif msg == STATE_STOPPED and error:
                LOGGER.error("Websocket stopped with error: %s", error)
            else:
                LOGGER.debug("Websocket state changed: %s", msg)

            if self.callback is not None:
                await self.callback()

        elif msg_type == "data" and isinstance(msg, dict):
            message = msg
            if METHOD in message:
                if message[METHOD] == GARAGE_UPDATE_MSG and PARAMS in message:
                    await self.parse_message(message[PARAMS])
                elif message[METHOD] == WS_AUTH_OK:
                    authorized = message.get(PARAMS, {}).get("authorized", False)
                    if authorized:
                        LOGGER.debug("Websocket API key authorized")
                    else:
                        LOGGER.error("Websocket API key authorization failed")
            elif RESULT in message:
                result_obj = message.get(RESULT, {})
                if isinstance(result_obj, dict):
                    if result_obj.get(RESULT) == WS_OK:
                        LOGGER.debug("Websocket command ACK OK")
                    if result_obj.get("authorized"):
                        LOGGER.debug("Websocket user authorization OK")
        else:
            LOGGER.debug("Unknown websocket event: %s type: %s", msg, msg_type)

    async def parse_message(self, data: dict) -> None:
        """Parse incoming updated data from WebSocket push."""
        if not isinstance(data, dict):
            return

        if self.device_id and data.get("varName") != self.device_id:
            LOGGER.debug(
                "Websocket update for %s ignored (expected %s)",
                data.get("varName"),
                self.device_id,
            )
            return

        for key, value_dict in data.items():
            if key in ["topic", "varName", "id"] or not isinstance(value_dict, dict):
                continue

            LOGGER.debug("Websocket parsing update for item %s: %s", key, value_dict)
            parts = key.split(".")
            module_name = parts[1] if len(parts) > 1 else key

            # Garage Door updates
            if "garageDoor" in key:
                if module_name == "doorState" and "value" in value_dict:
                    self._data["door_state"] = self.DOOR_STATE.get(
                        str(value_dict["value"]), "fault"
                    )
                elif module_name == "motionSensor" and "value" in value_dict:
                    self._data["motion"] = value_dict["value"]
                elif module_name == "vacationMode" and "value" in value_dict:
                    self._data["vacationMode"] = value_dict["value"]
                elif module_name == "sensorFlag" and "value" in value_dict:
                    self._data["safety"] = value_dict["value"]
                self._data["door_attributes"] = dict(value_dict)

            # Garage Light updates
            elif "garageLight" in key:
                if module_name == "lightState" and "value" in value_dict:
                    self._data["light_state"] = value_dict["value"]
                self._data["light_attributes"] = dict(value_dict)

            # Park Assist updates
            elif "parkAssistLaser" in key:
                if module_name == "moduleState" and "value" in value_dict:
                    self._data["park_assist"] = value_dict["value"]

            # Bluetooth Speaker Updates (handling micEnable / micEnabled)
            elif "btSpeaker" in key:
                if module_name == "moduleState" and "value" in value_dict:
                    self._data["bt_speaker"] = value_dict["value"]
                elif module_name in ("micEnable", "micEnabled") and "value" in value_dict:
                    self._data["micStatus"] = value_dict["value"]

            # Inflator module
            elif "inflator" in key:
                if module_name == "moduleState" and "value" in value_dict:
                    self._data["inflator"] = value_dict["value"]

            # Fan module
            elif "fan" in key:
                if module_name == "speed" and "value" in value_dict:
                    self._data["fan"] = value_dict["value"]

        if self.callback is not None:
            await self.callback()
