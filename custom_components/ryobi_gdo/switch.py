"""Ryobi platform for the switch component."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_ID, COORDINATOR, DOMAIN

LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the OpenEVSE switches."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    switches = []
    switches.append(RyobiSwitch(hass, entry, coordinator))

    async_add_entities(switches, False)


class RyobiSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a ryobi switch."""

    def __init__(self, hass, config_entry: ConfigEntry, coordinator: str):
        """Initialize the switch."""
        super().__init__(coordinator)
        self.device_id = config_entry.data[CONF_DEVICE_ID]
        self._attr_name = f"ryobi_gdo_light_{self.device_id}"
        self._attr_unique_id = f"ryobi_gdo_light_{self.device_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            manufacturer="Ryobi",
            model="GDO",
            name="Ryobi Garage Door Opener",
        )

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._attr_name

    @property
    def is_on(self) -> bool:
        """Return if the light is off."""
        data = self.coordinator._data
        if data["light_state"] == STATE_ON:
            return True
        return False

    async def async_turn_off(self, **kwargs: Any):
        """Turn off light."""
        LOGGER.debug("Turning off light")
        await self.coordinator.send_command("lightState", False)

    async def async_turn_on(self, **kwargs):
        """Turn on light."""
        LOGGER.debug("Turning on light")
        await self.coordinator.send_command("lightState", True)
