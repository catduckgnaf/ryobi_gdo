# pylint: disable=protected-access,redefined-outer-name
"""Offline command-path regressions, from cover service to socket send."""

from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ryobi_gdo.const import DOMAIN
from custom_components.ryobi_gdo.coordinator import RyobiDataUpdateCoordinator
from custom_components.ryobi_gdo.cover import RyobiCover
from custom_components.ryobi_gdo.websocket import STATE_CONNECTED, RyobiWebSocket


@pytest.fixture
async def coordinator(hass):
    """Build the actual command path with only the network boundary mocked."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": "test-user",
            "password": "test-password",
            "device_id": "test-device",
        },
    )
    entry.add_to_hass(hass)
    result = RyobiDataUpdateCoordinator(hass, 30, entry)
    result._websocket_check = AsyncMock()
    result.async_request_refresh = AsyncMock()
    result.async_set_updated_data({"door_state": "closed"})
    result.client.ws = RyobiWebSocket(
        AsyncMock(), "test-user", "test-key", "test-device", session=Mock()
    )
    result.client.ws._state = STATE_CONNECTED
    result.client.ws._ws_client = Mock(closed=False, send_str=AsyncMock())
    return result


@pytest.mark.parametrize(
    "failure", ["missing", "disconnected", "closed", "send_error", "connect_error"]
)
async def test_cover_open_surfaces_delivery_failure(coordinator, failure):
    """A failed transmission must not look like a successful HA service call."""
    if failure == "missing":
        coordinator.client.ws = None
    elif failure == "disconnected":
        coordinator.client.ws._state = "disconnected"
    elif failure == "closed":
        coordinator.client.ws._ws_client.closed = True
    elif failure == "send_error":
        coordinator.client.ws._ws_client.send_str.side_effect = ConnectionError(
            "offline"
        )
    else:
        coordinator._websocket_check.side_effect = ConnectionError("offline")

    with pytest.raises(HomeAssistantError):
        await RyobiCover(coordinator).async_open_cover()

    coordinator.async_request_refresh.assert_not_awaited()
    assert coordinator.data["door_state"] == "closed"


async def test_cover_open_does_not_invent_physical_state(coordinator):
    """A socket write permits refresh, not an optimistic claim of door movement."""
    await RyobiCover(coordinator).async_open_cover()
    coordinator.client.ws._ws_client.send_str.assert_awaited_once()
    coordinator.async_request_refresh.assert_awaited_once()
    assert coordinator.data["door_state"] == "closed"
