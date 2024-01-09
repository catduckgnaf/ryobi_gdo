"""Ryobi platform for the switch component."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.helpers.entity import DeviceInfo

from .const import CONF_DEVICE_ID, COORDINATOR, DOMAIN, LOGGER
from .coordinator import RyobiDataUpdateCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the OpenEVSE switches."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    switches = []
    switches.append(RyobiSwitch(hass, entry, coordinator))

    async_add_entities(switches, False)


class RyobiSwitch(SwitchEntity):
    """Representation of a ryobi light."""

    def __init__(
        self, hass, config_entry: ConfigEntry, coordinator: RyobiDataUpdateCoordinator
    ):
        """Initialize the light."""
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

    async def turn_off(self, **kwargs: Any):
        """Turn off light."""
        LOGGER.debug("Turning off light")
        self.coordinator.send_message("lightState", False)

    async def turn_on(self, **kwargs):
        """Turn on light."""
        LOGGER.debug("Turning on light")
        self.coordinator.send_message("lightState", True)
