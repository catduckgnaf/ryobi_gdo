"""Test the Ryobi fan platform."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.ryobi_gdo.fan import RyobiFan, async_setup_entry


@pytest.fixture
def coordinator():
    """Return a coordinator with two fan modules."""
    value = MagicMock()
    value.device_id = "fakedeviceID02"
    value.data = {
        "fan_0": 1,
        "fan_speed_0": 1,
        "fan_1": 1,
        "fan_speed_1": 3,
    }
    value.client.module_instances.return_value = ["fan_0", "fan_1"]
    value.send_command = AsyncMock()
    value.async_request_refresh = AsyncMock()
    return value


@pytest.mark.asyncio
async def test_setup_adds_one_named_entity_per_fan(coordinator):
    """Create one distinct fan entity for every installed module."""
    entities = []
    entry = SimpleNamespace(runtime_data=coordinator)

    await async_setup_entry(None, entry, entities.extend)

    assert [entity.unique_id for entity in entities] == [
        "fakedeviceID02_fan",
        "fakedeviceID02_fan_1",
    ]
    assert [entity.name for entity in entities] == ["Fan 1", "Fan 2"]


@pytest.mark.asyncio
async def test_fan_speed_and_toggle_commands_use_entity_index(coordinator):
    """Use the selected fan index for speed and toggle commands."""
    fan = RyobiFan(coordinator, index=1, multiple=True)

    assert fan.is_on is True
    assert fan.percentage == 100

    await fan.async_set_percentage(50)
    coordinator.send_command.assert_awaited_once_with(
        "fan", "speed", 2, index=1
    )

    coordinator.send_command.reset_mock()
    await fan.async_turn_on()
    coordinator.send_command.assert_awaited_once_with(
        "fan", "moduleState", 1, index=1
    )

    coordinator.send_command.reset_mock()
    await fan.async_turn_off()
    assert coordinator.send_command.await_args_list[0].args == (
        "fan",
        "speed",
        0,
    )
    assert coordinator.send_command.await_args_list[0].kwargs == {"index": 1}
    assert coordinator.send_command.await_args_list[1].args == (
        "fan",
        "moduleState",
        0,
    )
    assert coordinator.send_command.await_args_list[1].kwargs == {"index": 1}
