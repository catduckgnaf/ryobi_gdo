"""Test module indexing and fan state handling."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.ryobi_gdo.api import RyobiApiClient
from custom_components.ryobi_gdo.coordinator import RyobiDataUpdateCoordinator


@pytest.fixture
def client() -> RyobiApiClient:
    """Return a client for module parsing tests."""
    return RyobiApiClient(
        username="TestUser",
        password="FakePassword",
        device_id="fakedeviceID02",
    )


@pytest.mark.asyncio
async def test_index_modules_tracks_fans_and_skips_empty_ports(client):
    """Index all active fan instances while ignoring empty module ports."""
    dtm = {
        "fan_1": {},
        "fan_0": {},
        "fan_2": {"at": {"moduleId": {"value": 255}}},
        "modulePort_4": {"at": {"moduleId": {"value": 255}}},
    }

    assert await client._index_modules(dtm)

    assert client.modules == {"fan": "fan_0"}
    assert client.module_instances("fan") == ["fan_0", "fan_1"]
    assert client.get_module("fan") == 0
    assert client.get_module("fan", 1) == 1
    assert client.get_module("fan", 2) == 0


@pytest.mark.asyncio
async def test_parse_accessories_keeps_each_fan_state_separate(client):
    """Parse speed and state values independently for multiple fans."""
    await client._index_modules(
        {
            "fan_0": {},
            "fan_1": {},
        }
    )
    dtm = {
        "fan_0": {
            "at": {
                "speed": {"value": 1},
                "moduleState": {"value": 1},
            }
        },
        "fan_1": {
            "at": {
                "speed": {"value": 3},
                "moduleState": {"value": 1},
            }
        },
    }

    client._parse_accessories(dtm)

    assert client.data["fan_speed_0"] == 1
    assert client.data["fan_0"] == 1
    assert client.data["fan_speed_1"] == 3
    assert client.data["fan_1"] == 1
    assert client.data["fan_speed"] == 1
    assert client.data["fan"] == 1


@pytest.mark.asyncio
async def test_parse_message_routes_fan_updates_by_instance(client):
    """Route WebSocket updates to the fan that generated them."""
    await client._index_modules(
        {
            "fan_0": {},
            "fan_1": {},
        }
    )
    client._parse_accessories(
        {
            "fan_0": {"at": {"speed": {"value": 1}}},
            "fan_1": {"at": {"speed": {"value": 3}}},
        }
    )

    await client.parse_message(
        {
            "varName": "fakedeviceID02",
            "fan_1.speed": {"value": 0},
        }
    )

    assert client.data["fan_speed_0"] == 1
    assert client.data["fan_0"] == 1
    assert client.data["fan_speed_1"] == 0
    assert client.data["fan_1"] == 0


@pytest.mark.asyncio
async def test_send_command_forwards_module_instance_index():
    """Send fan commands to the selected module port."""
    coordinator = object.__new__(RyobiDataUpdateCoordinator)
    coordinator.client = MagicMock()
    coordinator.device_id = "fakedeviceID02"
    coordinator._websocket_check = AsyncMock()
    coordinator.client.get_module.return_value = 1
    coordinator.client.get_module_type.return_value = 3
    coordinator.client.ws.state = "connected"
    coordinator.client.ws.send_message = AsyncMock()

    await coordinator.send_command("fan", "speed", 2, index=1)

    coordinator.client.get_module.assert_called_once_with("fan", 1)
    coordinator.client.ws.send_message.assert_awaited_once_with(1, 3, "speed", 2)
