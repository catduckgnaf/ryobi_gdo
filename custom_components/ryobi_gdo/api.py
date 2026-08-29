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
    DEFAULT_HOST,
    DEVICE_GET_ENDPOINT,
    GARAGE_UPDATE_MSG,
    HOST_URI,
    LOGIN_ENDPOINT,
    REQUEST_TIMEOUT,
    WS_AUTH_OK,
    WS_OK,
)
from .websocket import (
    SIGNAL_CONNECTION_STATE,
    STATE_CONNECTED,
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
        session: aiohttp.ClientSession | None = None,
        device_id: str | None = None,
        host: str = DEFAULT_HOST,
    ) -> None:
        """Initialize the API object."""
        self.username = username
        self.password = password
        self.device_id = device_id
        self.host = host or DEFAULT_HOST
        self.is_local = self.clean_host != DEFAULT_HOST
        self.door_state: str | None = None
        self.light_state: bool | None = None
        self.battery_level: int | None = None
        self.api_key: str | None = None
        self._data: dict[str, Any] = {
            "server_type": "Local Server" if self.is_local else "Ryobi Cloud",
            "is_local": self.is_local,
            "server_host": self.host,
        }
        self.ws: RyobiWebSocket | None = None
        self.callback: abc.Callable | None = None
        self.socket_state: str | None = None
        self.ws_listening = False
        self._ws_listen_task: asyncio.Task | None = None
        self._modules: dict[str, str] = {}
        self.session = session

    @property
    def http_scheme(self) -> str:
        """Return http or https based on host."""
        if self.host.startswith("http://"):
            return "http"
        if self.host.startswith("https://"):
            return "https"
        clean = self.clean_host
        if ":" in clean or clean.startswith("127.") or clean.startswith("192.168.") or clean.startswith("10.") or clean.startswith("172.") or "localhost" in clean:
            return "http"
        return "https"

    @property
    def clean_host(self) -> str:
        """Return host without protocol prefix."""
        h = self.host.strip()
        if h.startswith("http://"):
            return h[7:]
        if h.startswith("https://"):
            return h[8:]
        if h.startswith("ws://"):
            return h[5:]
        if h.startswith("wss://"):
            return h[6:]
        return h

    def get_url(self, endpoint: str) -> str:
        """Construct full HTTP URL."""
        return f"{self.http_scheme}://{self.clean_host}/{endpoint}"

    async def _process_request(
        self, url: str, method: str, data: dict[str, str]
    ) -> dict | None:
        """Process HTTP requests."""
        if self.session is None:
            LOGGER.error("No aiohttp session available to process request")
            return None

        http_method = getattr(self.session, method.lower())
        LOGGER.debug("Connecting to %s using %s", url, method)
        reply = None
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with http_method(url, data=data) as response:
                    server_hdr = response.headers.get("X-Server", "")
                    if "Ryobi-Local-Server" in server_hdr or self.clean_host != DEFAULT_HOST:
                        self.is_local = True

                    raw_reply = await response.text()
                    try:
                        reply = json.loads(raw_reply)
                        if not isinstance(reply, dict):
                            reply = None
                        elif reply.get("server_type") == "local" or reply.get("local_server") is True:
                            self.is_local = True
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
        url = self.get_url(LOGIN_ENDPOINT)
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
        url = self.get_url(DEVICE_GET_ENDPOINT)
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
        url = self.get_url(DEVICE_GET_ENDPOINT)
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

    def _parse_garage_door(self, dtm: dict[str, Any]) -> None:
        """Parse core garage door state values."""
        if "garageDoor" not in self._modules:
            return
        gdo_key = self._modules["garageDoor"]
        gdo_at = dtm.get(gdo_key, {}).get("at", {})
        if "doorState" in gdo_at:
            raw_state = str(gdo_at["doorState"].get("value", "4"))
            self._data["door_state"] = self.DOOR_STATE.get(raw_state, "fault")
        if "sensorFlag" in gdo_at:
            self._data["safety"] = gdo_at["sensorFlag"].get("value")
        if "vacationMode" in gdo_at:
            self._data["vacationMode"] = gdo_at["vacationMode"].get("value")
        if "motionSensor" in gdo_at:
            self._data["motion"] = gdo_at["motionSensor"].get("value")

    def _parse_accessories(self, dtm: dict[str, Any]) -> None:
        """Parse accessory plug-in module values."""
        if "garageLight" in self._modules:
            light_at = dtm.get(self._modules["garageLight"], {}).get("at", {})
            if "lightState" in light_at:
                self._data["light_state"] = light_at["lightState"].get("value")

        if "backupCharger" in self._modules:
            charger_at = dtm.get(self._modules["backupCharger"], {}).get("at", {})
            if "chargeLevel" in charger_at:
                raw_level = charger_at["chargeLevel"].get("value")
                try:
                    lvl = int(raw_level)
                    self._data["battery_level"] = max(0, lvl) if lvl >= 0 else None
                except (ValueError, TypeError):
                    self._data["battery_level"] = None

        if "wifiModule" in self._modules:
            wifi_at = dtm.get(self._modules["wifiModule"], {}).get("at", {})
            if "rssi" in wifi_at:
                raw_rssi = wifi_at["rssi"].get("value")
                try:
                    self._data["wifi_rssi"] = int(raw_rssi)
                except (ValueError, TypeError):
                    self._data["wifi_rssi"] = None

        if "parkAssistLaser" in self._modules:
            laser_at = dtm.get(self._modules["parkAssistLaser"], {}).get("at", {})
            if "moduleState" in laser_at:
                self._data["park_assist"] = laser_at["moduleState"].get("value")

        if "inflator" in self._modules:
            inflator_at = dtm.get(self._modules["inflator"], {}).get("at", {})
            if "moduleState" in inflator_at:
                self._data["inflator"] = inflator_at["moduleState"].get("value")

        if "btSpeaker" in self._modules:
            speaker_at = dtm.get(self._modules["btSpeaker"], {}).get("at", {})
            if "moduleState" in speaker_at:
                self._data["bt_speaker"] = speaker_at["moduleState"].get("value")
            if "micEnable" in speaker_at:
                self._data["micStatus"] = speaker_at["micEnable"].get("value")

        if "fan" in self._modules:
            fan_at = dtm.get(self._modules["fan"], {}).get("at", {})
            if "speed" in fan_at:
                self._data["fan_speed"] = fan_at["speed"].get("value", 0)
            if "moduleState" in fan_at:
                self._data["fan"] = fan_at["moduleState"].get("value", 0)
            elif "speed" in fan_at:
                self._data["fan"] = 1 if self._data.get("fan_speed", 0) > 0 else 0

        if "camera" in self._modules or "securityCamera" in self._modules:
            cam_key = self._modules.get("camera") or self._modules.get("securityCamera")
            cam_at = dtm.get(cam_key, {}).get("at", {})
            if "moduleState" in cam_at:
                self._data["camera_state"] = bool(cam_at["moduleState"].get("value", 1))
            if "recordingState" in cam_at:
                self._data["camera_recording"] = bool(cam_at["recordingState"].get("value", 0))

    async def _index_modules(self, dtm: dict) -> bool:
        """Index and add modules to dictionary, ignoring empty ports."""
        module_list = [
            "garageDoor",
            "backupCharger",
            "garageLight",
            "wifiModule",
            "parkAssistLaser",
            "inflator",
            "btSpeaker",
            "fan",
            "camera",
            "securityCamera",
            "extCord",
        ]
        frame = {}
        try:
            for key, val in dtm.items():
                if isinstance(val, dict):
                    meta = val.get("metaData", {})
                    mod_id = meta.get("moduleId")
                    if mod_id == 255:
                        continue
                for module in module_list:
                    if module.lower() in key.lower():
                        frame[module] = key
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.error("Problem parsing module list: %s", err)
            return False
        self._modules = frame
        LOGGER.debug("Indexed active modules: %s", list(self._modules.keys()))
        return True

    def get_module(self, module: str) -> int:
        """Return module port number for device."""
        if module not in self._modules:
            LOGGER.warning("Module %s not found in indexed modules", module)
            if module in ("garageDoor", "garageLight"):
                return 7
            return 0
        val = str(self._modules[module])
        if "_" in val:
            parts = val.split("_")
            for part in parts:
                if part.isdigit():
                    return int(part)
        elif val.isdigit():
            return int(val)
        return 7 if module in ("garageDoor", "garageLight") else 0

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
        if self.api_key is None and not await self.get_api_key():
            raise APIKeyError("Could not retrieve API key for WebSocket")

        if not self.ws and self.session and self.api_key and self.device_id:
            self.ws = RyobiWebSocket(
                self._process_message,
                self.username,
                self.api_key,
                self.device_id,
                self.session,
                host=self.host,
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
            if msg in (STATE_CONNECTED, STATE_STARTING):
                self.ws_listening = True
            elif msg == STATE_STOPPED and error:
                LOGGER.error("Websocket stopped with error: %s", error)

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

            elif "garageLight" in key:
                if module_name == "lightState" and "value" in value_dict:
                    self._data["light_state"] = value_dict["value"]
                self._data["light_attributes"] = dict(value_dict)

            elif "parkAssistLaser" in key:
                if module_name == "moduleState" and "value" in value_dict:
                    self._data["park_assist"] = value_dict["value"]

            elif "btSpeaker" in key:
                if module_name == "moduleState" and "value" in value_dict:
                    self._data["bt_speaker"] = value_dict["value"]
                elif module_name in ("micEnable", "micEnabled") and "value" in value_dict:
                    self._data["micStatus"] = value_dict["value"]

            elif "inflator" in key:
                if module_name == "moduleState" and "value" in value_dict:
                    self._data["inflator"] = value_dict["value"]

            elif "backupCharger" in key:
                if module_name in ("chargeLevel", "batteryLevel") and "value" in value_dict:
                    self._data["battery_level"] = value_dict["value"]

            elif "wifiModule" in key:
                if module_name == "rssi" and "value" in value_dict:
                    self._data["wifi_rssi"] = value_dict["value"]

            elif "fan" in key:
                if module_name == "speed" and "value" in value_dict:
                    self._data["fan_speed"] = value_dict["value"]
                    self._data["fan"] = 1 if value_dict["value"] > 0 else 0
                elif module_name == "moduleState" and "value" in value_dict:
                    self._data["fan"] = value_dict["value"]

        if self.callback is not None:
            await self.callback()
