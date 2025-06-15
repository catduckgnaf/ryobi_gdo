"""Websocket client for Ryobi GDO."""

from __future__ import annotations

import asyncio
from collections import abc
import json
import logging

import aiohttp  # type: ignore

from .const import DEVICE_SET_ENDPOINT, HOST_URI

LOGGER = logging.getLogger(__name__)

MAX_FAILED_ATTEMPTS = 5
INFO_LOOP_RUNNING = "Event loop already running, not creating new one."

# Websocket errors
ERROR_AUTH_FAILURE = "Authorization failure"
ERROR_TOO_MANY_RETRIES = "Too many retries"
ERROR_UNKNOWN = "Unknown"

# Websocket Signals
SIGNAL_CONNECTION_STATE = "websocket_state"
STATE_CONNECTED = "connected"
STATE_DISCONNECTED = "disconnected"
STATE_STARTING = "starting"
STATE_STOPPED = "stopped"


class RyobiWebSocket:
    """Represent a websocket connection to Ryobi servers."""

    # FIX: Modified constructor to accept aiohttp session
    def __init__(self, callback, username: str, apikey: str, device: str, session: aiohttp.ClientSession) -> None:
        """Initialize a RyobiWebSocket instance."""
        # FIX: Use the passed session instead of creating a new one
        self.session = session
        self.url = f"wss://{HOST_URI}/{DEVICE_SET_ENDPOINT}"
        self._user = username
        self._apikey = apikey
        self._device_id = device
        self.callback: abc.Callable = callback
        self._state = None
        self._error_reason = None
        self._ws_client = None
        self.failed_attempts = 0

    @property
    def state(self) -> str | None:
        """Return the current state."""
        return self._state

    @state.setter
    async def state(self, value) -> None:
        """Set the state."""
        self._state = value
        LOGGER.debug("Websocket state: %s", value)
        await self.callback(SIGNAL_CONNECTION_STATE, value, self._error_reason)
        self._error_reason = None

    async def running(self):
        """Open a persistent websocket connection and act on events."""
        await RyobiWebSocket.state.fset(self, STATE_STARTING)

        header = {"Connection": "keep-alive, Upgrade", "handshakeTimeout": "10000"}

        try:
            async with self.session.ws_connect(
                self.url,
                heartbeat=15,
                headers=header,
                receive_timeout=5 * 60,  # Should see something from Ryobi about every 5 minutes
            ) as ws_client:
                self._ws_client = ws_client

                # Auth to server and subscribe to topic
                if self._state != STATE_CONNECTED:
                    await self.websocket_auth()
                    await asyncio.sleep(0.5)
                    await self.websocket_subscribe()

                await RyobiWebSocket.state.fset(self, STATE_CONNECTED)
                self.failed_attempts = 0

                async for message in ws_client:
                    if self._state == STATE_STOPPED:
                        break

                    if message.type == aiohttp.WSMsgType.TEXT:
                        msg = message.json()
                        await self.callback("data", msg)

                    elif message.type == aiohttp.WSMsgType.CLOSED:
                        LOGGER.warning("Websocket connection closed")
                        break

                    elif message.type == aiohttp.WSMsgType.ERROR:
                        LOGGER.error("Websocket error")
                        break
        except aiohttp.ClientResponseError as error:
            if error.status == 401:
                LOGGER.error("Credentials rejected: %s", error)
                self._error_reason = ERROR_AUTH_FAILURE
            else:
                LOGGER.error("Unexpected response received: %s", error)
                self._error_reason = ERROR_UNKNOWN
            await RyobiWebSocket.state.fset(self, STATE_STOPPED)
        except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as error:
            if self.failed_attempts >= MAX_FAILED_ATTEMPTS:
                self._error_reason = ERROR_TOO_MANY_RETRIES
                await RyobiWebSocket.state.fset(self, STATE_STOPPED)
            elif self._state != STATE_STOPPED:
                retry_delay = min(2 ** (self.failed_attempts - 1) * 30, 300)
                self.failed_attempts += 1
                LOGGER.error(
                    "Websocket connection failed, retrying in %ds: %s",
                    retry_delay,
                    error,
                )
                await RyobiWebSocket.state.fset(self, STATE_DISCONNECTED)
                await asyncio.sleep(retry_delay)
        except Exception as error:  # pylint: disable=broad-except
            if self._state != STATE_STOPPED:
                LOGGER.exception("Unexpected exception occurred: %s", error)
                self._error_reason = ERROR_UNKNOWN
                await RyobiWebSocket.state.fset(self, STATE_STOPPED)
        else:
            if self._state != STATE_STOPPED:
                LOGGER.debug(
                    "Websocket msgType: %s CloseCode: %s",
                    str(aiohttp.WSMsgType.name),
                    str(aiohttp.WSCloseCode.name),
                )
                await RyobiWebSocket.state.fset(self, STATE_DISCONNECTED)
                await asyncio.sleep(5)

    async def listen(self):
        """Start the listening websocket."""
        self.failed_attempts = 0
        while self._state != STATE_STOPPED:
            await self.running()

    async def close(self):
        """Close the listening websocket."""
        await RyobiWebSocket.state.fset(self, STATE_STOPPED)

    async def websocket_auth(self) -> None:
        """Authenticate with Ryobi server."""
        LOGGER.debug("Websocket attempting authenticate with server.")
        auth_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "srvWebSocketAuth",
            "params": {"varName": self._user, "apiKey": self._apikey},
        }
        await self.websocket_send(auth_request)

    async def websocket_subscribe(self) -> None:
        """Send subscription for device updates."""
        LOGGER.debug("Websocket subscribing to notifications for %s", self._device_id)
        subscribe = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "wskSubscribe",
            "params": {"topic": self._device_id + ".wskAttributeUpdateNtfy"},
        }
        await self.websocket_send(subscribe)

    async def websocket_send(self, message: dict) -> bool:
        """Send websocket message."""
        json_message = json.dumps(message)
        LOGGER.debug("Websocket sending data: %s", self.redact_api_key(message))

        try:
            await self._ws_client.send_str(json_message)
            LOGGER.debug("Websocket message sent.")
            return True
        except Exception as err:
            LOGGER.error("Websocket error sending message: %s", err)
            self._error_reason = err
            await RyobiWebSocket.state.fset(self, STATE_DISCONNECTED)
        return False

    def redact_api_key(self, message: dict) -> dict:
        """Clear API key data from logs."""
        if "params" in message:
            if "apiKey" in message["params"]:
                message["params"]["apiKey"] = ""
        return json.dumps(message)

    async def send_message(self, *args):
        """Send message to API."""
        if self._state != STATE_CONNECTED:
            LOGGER.warning("Websocket not yet connected, unable to send command.")
            return

        LOGGER.debug("Send message args: %s", args)

        ws_command = {
            "jsonrpc": "2.0",
            "method": "gdoModuleCommand",
            "params": {
                "msgType": 16,
                "moduleType": int(args[1]),
                "portId": int(args[0]),
                "moduleMsg": {args[2]: args[3]},
                "topic": self._device_id,
            },
        }
        LOGGER.debug(
            "Sending command: %s value: %s portId: %s moduleType: %s",
            args[2],
            args[3],
            args[0],
            args[1],
        )
        LOGGER.debug("Full message: %s", ws_command)
        await self.websocket_send(ws_command)
