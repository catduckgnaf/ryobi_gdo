# pylint: disable=protected-access,redefined-outer-name
"""Offline transport regressions; never connect to an opener or cloud service."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

from custom_components.ryobi_gdo.websocket import (
    ERROR_AUTH_FAILURE,
    ERROR_TOO_MANY_RETRIES,
    ERROR_UNKNOWN,
    MAX_FAILED_ATTEMPTS,
    SIGNAL_CONNECTION_STATE,
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    STATE_STARTING,
    STATE_STOPPED,
    RyobiWebSocket,
)


@pytest.fixture
def transport():
    """Provide a transport whose session cannot perform real I/O."""
    return RyobiWebSocket(
        AsyncMock(), "test-user", "test-key", "test-device", session=Mock()
    )


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("tti.tiwiconnect.com", "wss://tti.tiwiconnect.com/api/wsrpc"),
        ("192.168.250.26:8443", "ws://192.168.250.26:8443/api/wsrpc"),
        ("http://local.test:8080", "ws://local.test:8080/api/wsrpc"),
        ("https://local.test", "wss://local.test/api/wsrpc"),
        ("ws://local.test", "ws://local.test/api/wsrpc"),
        ("wss://local.test", "wss://local.test/api/wsrpc"),
    ],
)
def test_transport_url(host, expected):
    """Preserve explicit security schemes and local versus cloud defaults."""
    transport = RyobiWebSocket(AsyncMock(), "u", "k", "d", session=Mock(), host=host)
    assert transport.url == expected


async def test_authentication_subscription_and_command_payloads(transport):
    """Verify serialized protocol payloads without transmitting commands."""
    socket = Mock(closed=False, send_str=AsyncMock())
    transport._ws_client = socket
    await transport.websocket_auth()
    await transport.websocket_subscribe()
    transport._state = STATE_CONNECTED
    await transport.send_message("7", "5", "lightState", 1)
    messages = [json.loads(call.args[0]) for call in socket.send_str.await_args_list]
    assert messages == [
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "srvWebSocketAuth",
            "params": {"varName": "test-user", "apiKey": "test-key"},
        },
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "wskSubscribe",
            "params": {"topic": "test-device.wskAttributeUpdateNtfy"},
        },
        {
            "jsonrpc": "2.0",
            "method": "gdoModuleCommand",
            "params": {
                "msgType": 16,
                "moduleType": 5,
                "portId": 7,
                "moduleMsg": {"lightState": 1},
                "topic": "test-device",
            },
        },
    ]


@pytest.mark.parametrize("closed", [None, True])
async def test_send_without_open_socket_returns_false(transport, closed):
    """Never report a disconnected transmission as successful."""
    socket = Mock(closed=True, send_str=AsyncMock())
    transport._ws_client = None if closed is None else socket
    assert await transport.websocket_send({"method": "test"}) is False
    socket.send_str.assert_not_awaited()


async def test_disconnected_command_is_not_sent(transport):
    """Do not dispatch module commands until connected."""
    transport.websocket_send = AsyncMock()
    await transport.send_message("7", "5", "lightState", 1)
    transport.websocket_send.assert_not_awaited()


async def test_send_failure_signals_disconnect(transport):
    """Return failure and propagate the error reason exactly once."""
    transport._ws_client = Mock(
        closed=False, send_str=AsyncMock(side_effect=ConnectionError("send failed"))
    )
    assert await transport.websocket_send({"method": "test"}) is False
    assert transport.state == STATE_DISCONNECTED
    transport.callback.assert_awaited_once_with(
        SIGNAL_CONNECTION_STATE, STATE_DISCONNECTED, "send failed"
    )
    assert transport._error_reason is None


async def test_close_closes_socket_once(transport):
    """Stop listening and close an existing connection."""
    transport._ws_client = Mock(closed=False, close=AsyncMock())
    await transport.close()
    assert transport.state == STATE_STOPPED
    transport._ws_client.close.assert_awaited_once()


@pytest.mark.parametrize(
    "status,reason", [(401, ERROR_AUTH_FAILURE), (503, ERROR_UNKNOWN)]
)
async def test_handshake_http_error_stops(transport, status, reason):
    """Surface rejected handshakes with the appropriate connection reason."""
    transport.session.ws_connect.side_effect = aiohttp.ClientResponseError(
        Mock(real_url="wss://example.test"), (), status=status
    )
    await transport.running()
    assert transport.state == STATE_STOPPED
    transport.callback.assert_any_await(SIGNAL_CONNECTION_STATE, STATE_STOPPED, reason)


@pytest.mark.parametrize("attempts", [0, 2, MAX_FAILED_ATTEMPTS])
async def test_connection_retry_backoff_and_limit(transport, attempts):
    """Retry with bounded delay and stop after exhausting the retry budget."""
    transport.failed_attempts = attempts
    transport.session.ws_connect.side_effect = aiohttp.ClientConnectionError("offline")
    with patch(
        "custom_components.ryobi_gdo.websocket.asyncio.sleep", new_callable=AsyncMock
    ) as sleep:
        await transport.running()
    if attempts == MAX_FAILED_ATTEMPTS:
        assert transport.state == STATE_STOPPED
        sleep.assert_not_awaited()
        transport.callback.assert_any_await(
            SIGNAL_CONNECTION_STATE, STATE_STOPPED, ERROR_TOO_MANY_RETRIES
        )
    else:
        assert transport.failed_attempts == attempts + 1
        assert transport.state == STATE_DISCONNECTED
        sleep.assert_awaited_once_with(min(2**attempts * 5, 120))


@pytest.mark.parametrize("attempts", [0, MAX_FAILED_ATTEMPTS])
@pytest.mark.parametrize("failed_method", ["srvWebSocketAuth", "wskSubscribe"])
async def test_auth_or_subscription_send_failure_never_connects(
    transport, failed_method, attempts
):
    """A failed setup write must not publish a connected state."""
    socket = Mock(closed=False, send_str=AsyncMock())
    socket.send_str.side_effect = [
        ConnectionError("offline") if failed_method == "srvWebSocketAuth" else None,
        ConnectionError("offline") if failed_method == "wskSubscribe" else None,
    ]
    socket.__aiter__ = Mock(return_value=_frames())
    context = AsyncMock()
    context.__aenter__.return_value = socket
    transport.session.ws_connect.return_value = context
    transport.failed_attempts = attempts

    with patch(
        "custom_components.ryobi_gdo.websocket.asyncio.sleep", new_callable=AsyncMock
    ) as sleep:
        await transport.running()

    if attempts == MAX_FAILED_ATTEMPTS:
        assert transport.state == STATE_STOPPED
    else:
        assert transport.failed_attempts == attempts + 1
        sleep.assert_any_await(5)
    assert transport.state != STATE_CONNECTED
    assert not any(
        call.args[1] == STATE_CONNECTED
        for call in transport.callback.await_args_list
        if call.args[0] == SIGNAL_CONNECTION_STATE
    )


async def test_receive_skips_bad_json_and_delivers_next_message(transport):
    """Malformed frames must not suppress subsequent valid telemetry."""
    socket = Mock(closed=False, send_str=AsyncMock())
    socket.__aiter__ = Mock(return_value=_frames())
    context = AsyncMock()
    context.__aenter__.return_value = socket
    transport.session.ws_connect.return_value = context
    with patch(
        "custom_components.ryobi_gdo.websocket.asyncio.sleep", new_callable=AsyncMock
    ):
        await transport.running()
    transport.callback.assert_any_await(SIGNAL_CONNECTION_STATE, STATE_STARTING, None)
    transport.callback.assert_any_await(SIGNAL_CONNECTION_STATE, STATE_CONNECTED, None)
    transport.callback.assert_any_await("data", {"method": "telemetry"})
    assert transport.state == STATE_DISCONNECTED
    assert socket.send_str.await_count == 2
    transport.session.ws_connect.assert_called_once_with(
        transport.url,
        heartbeat=15,
        headers={"Connection": "keep-alive, Upgrade", "handshakeTimeout": "10000"},
        receive_timeout=300,
    )


async def _frames():
    """Yield malformed JSON, valid telemetry and a closed frame."""
    yield SimpleNamespace(
        type=aiohttp.WSMsgType.TEXT, json=Mock(side_effect=ValueError("bad JSON"))
    )
    yield SimpleNamespace(
        type=aiohttp.WSMsgType.TEXT, json=lambda: {"method": "telemetry"}
    )
    yield SimpleNamespace(type=aiohttp.WSMsgType.CLOSED)


def test_redaction_preserves_original_payload(transport):
    """Hide API keys in logs without altering authentication on the wire."""
    payload = {"params": {"apiKey": "test-key", "varName": "test-user"}}
    assert (
        json.loads(transport.redact_api_key(payload))["params"]["apiKey"]
        == "***REDACTED***"
    )
    assert payload["params"]["apiKey"] == "test-key"
