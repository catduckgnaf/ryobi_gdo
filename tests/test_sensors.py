"""Test Ryobi sensors."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ryobi_gdo.const import DOMAIN
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN

CONFIG_DATA = {
    "name": "Test GDO",
    "username": "TestUser",
    "password": "FakePassword",
    "device_id": "fakedeviceID02",
}


async def test_sensors(hass, mock_device, mock_api_key, mock_ws_start):
    """Test setup_entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=CONFIG_DATA["name"],
        data=CONFIG_DATA,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == 1
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 2
    assert len(hass.states.async_entity_ids(COVER_DOMAIN)) == 1
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert DOMAIN in hass.config.components
    state = hass.states.get("sensor.ryobi_gdo_battery_level_fakedeviceid02")
    assert state
    assert state.state == "0"
    state = hass.states.get("sensor.ryobi_gdo_wifi_signal_fakedeviceid02")
    assert state
    assert state.state == "-50"
