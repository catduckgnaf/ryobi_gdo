"""Websocket client for Ryobi GDO."""

from __future__ import annotations

import asyncio
from collections import abc
import copy
import json
import logging

import aiohttp

from .const import DEVICE_SET_ENDPOINT, HOST_URI

LOGGER = logging.getLogger(__name__)

MAX_FAILED_ATTEMPTS = 5

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

    def __init__(
        self,
        callback: abc.Callable,
        username: str,
        apikey: str,
        device: str,
        session: aiohttp.ClientSession,
        host: str = HOST_URI,
    ) -> None:
        """Initialize a RyobiWebSocket instance."""
        self.session = session
        self._host = host or HOST_URI
        self.url = self._get_ws_url()
        self._user = username
        self._apikey = apikey
        self._device_id = device
        self.callback = callback
        self._state: str | None = None
        self._error_reason: str | None = None
        self._ws_client: aiohttp.ClientWebSocketResponse | None = None
        self.failed_attempts = 0

    def _get_ws_url(self) -> str:
        """Construct WebSocket URL."""
        clean = self._host.strip()
        if clean.startswith("http://"):
            clean = clean[7:]
            scheme = "ws"
        elif clean.startswith("https://"):
            clean = clean[8:]
            scheme = "wss"
        elif clean.startswith("ws://"):
            clean = clean[5:]
            scheme = "ws"
        elif clean.startswith("wss://"):
            clean = clean[6:]
            scheme = "wss"
        elif ":" in clean or clean.startswith("127.") or clean.startswith("192.168.") or clean.startswith("10.") or clean.startswith("172.") or "localhost" in clean:
            scheme = "ws"
        else:
            scheme = "wss"
        return f"{scheme}://{clean}/{DEVICE_SET_ENDPOINT}"

    @property
    def state(self) -> str | None:
        """Return the current state."""
        return self._state

    async def _set_state(self, value: str) -> None:
        """Update connection state and invoke callback."""
        self._state = value
        LOGGER.debug("Websocket state: %s", value)
        await self.callback(SIGNAL_CONNECTION_STATE, value, self._error_reason)
        self._error_reason = None

    async def running(self) -> None:
        """Open a persistent websocket connection and act on events."""
        await self._set_state(STATE_STARTING)

        header = {"Connection": "keep-alive, Upgrade", "handshakeTimeout": "10000"}

        try:
            async with self.session.ws_connect(
                self.url,
                heartbeat=15,
                headers=header,
                receive_timeout=300,  # 5 minutes
            ) as ws_client:
                self._ws_client = ws_client

                # Auth to server and subscribe to topic
                if self._state != STATE_CONNECTED:
                    await self.websocket_auth()
                    await asyncio.sleep(0.5)
                    await self.websocket_subscribe()

                await self._set_state(STATE_CONNECTED)
                self.failed_attempts = 0

                async for message in ws_client:
                    if self._state == STATE_STOPPED:
                        break

                    if message.type == aiohttp.WSMsgType.TEXT:
                        try:
                            msg = message.json()
                            await self.callback("data", msg)
                        except (ValueError, TypeError) as parse_err:
                            LOGGER.warning("Failed to decode websocket JSON: %s", parse_err)

                    elif message.type == aiohttp.WSMsgType.CLOSED:
                        LOGGER.warning("Websocket connection closed by server")
                        break

                    elif message.type == aiohttp.WSMsgType.ERROR:
                        LOGGER.error("Websocket received error message: %s", ws_client.exception())
                        break

        except aiohttp.ClientResponseError as error:
            if error.status == 401:
                LOGGER.error("Credentials rejected: %s", error)
                self._error_reason = ERROR_AUTH_FAILURE
            else:
                LOGGER.error("Unexpected response received from server: %s", error)
                self._error_reason = ERROR_UNKNOWN
            await self._set_state(STATE_STOPPED)

        except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as error:
            if self.failed_attempts >= MAX_FAILED_ATTEMPTS:
                self._error_reason = ERROR_TOO_MANY_RETRIES
                await self._set_state(STATE_STOPPED)
            elif self._state != STATE_STOPPED:
                self.failed_attempts += 1
                retry_delay = min(2 ** (self.failed_attempts - 1) * 5, 120)
                LOGGER.warning(
                    "Websocket connection failed (attempt %d/%d), retrying in %ds: %s",
                    self.failed_attempts,
                    MAX_FAILED_ATTEMPTS,
                    retry_delay,
                    error,
                )
                await self._set_state(STATE_DISCONNECTED)
                await asyncio.sleep(retry_delay)

        except Exception as error:  # pylint: disable=broad-except
            if self._state != STATE_STOPPED:
                LOGGER.exception("Unexpected exception in websocket loop: %s", error)
                self._error_reason = ERROR_UNKNOWN
                await self._set_state(STATE_STOPPED)

        else:
            if self._state != STATE_STOPPED:
                LOGGER.debug("Websocket loop exited normally, disconnecting")
                await self._set_state(STATE_DISCONNECTED)
                await asyncio.sleep(5)

    async def listen(self) -> None:
        """Start the listening websocket loop."""
        self.failed_attempts = 0
        while self._state != STATE_STOPPED:
            await self.running()

    async def close(self) -> None:
        """Close the listening websocket."""
        await self._set_state(STATE_STOPPED)
        if self._ws_client and not self._ws_client.closed:
            await self._ws_client.close()

    async def websocket_auth(self) -> None:
        """Authenticate with Ryobi server."""
        LOGGER.debug("Websocket attempting to authenticate with server")
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
            "params": {"topic": f"{self._device_id}.wskAttributeUpdateNtfy"},
        }
        await self.websocket_send(subscribe)

    async def websocket_send(self, message: dict) -> bool:
        """Send websocket message."""
        json_message = json.dumps(message)
        LOGGER.debug("Websocket sending data: %s", self.redact_api_key(message))

        if not self._ws_client or self._ws_client.closed:
            LOGGER.error("Websocket client is not connected, cannot send message")
            return False

        try:
            await self._ws_client.send_str(json_message)
            LOGGER.debug("Websocket message sent successfully")
            return True
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.error("Websocket error sending message: %s", err)
            self._error_reason = str(err)
            await self._set_state(STATE_DISCONNECTED)
            return False

    def redact_api_key(self, message: dict) -> str:
        """Clear API key data from log output without modifying original dict."""
        safe_msg = copy.deepcopy(message)
        if "params" in safe_msg and isinstance(safe_msg["params"], dict):
            if "apiKey" in safe_msg["params"]:
                safe_msg["params"]["apiKey"] = "***REDACTED***"
        return json.dumps(safe_msg)

    async def send_message(self, *args) -> None:
        """Send command message to API."""
        if self._state != STATE_CONNECTED:
            LOGGER.warning("Websocket not connected, unable to send command")
            return

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
        await self.websocket_send(ws_command)
