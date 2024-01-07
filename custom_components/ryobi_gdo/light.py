"""
Ryobi platform for the light component.
For more details about this platform, please refer to the documentation
https://home-assistant.io/components/cover.ryobi_gdo/
"""
import logging
import time
import voluptuous as vol
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, STATE_UNKNOWN, STATE_CLOSED)

"""REQUIREMENTS = ['py-ryobi-gdo==0.0.27']"""

DOMAIN = "ryobi_gdo"
_LOGGER = logging.getLogger(__name__)

CONF_DEVICE_ID = 'device_id'

class RyobiLight(LightEntity):
    """Representation of a ryobi light."""

    def __init__(self, hass, ryobi_door):
        """Initialize the light."""
        self.ryobi_door = ryobi_door
        self._name = 'ryobi_gdo_light_{}'.format(ryobi_door.get_device_id())
        self._light_state = None
        self.device_id = ryobi_door.get_device_id()
        self._attr_unique_id = 'ryobi_gdo_light_{}'.format(ryobi_door.get_device_id())
      
    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        return DeviceInfo( 
            identifiers = {(DOMAIN, self.device_id)},
            manufacturer = "Ryobi",
            model = "GDO",
            name = "Ryobi Garage Door Opener",
        )

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    @property
    def is_on(self):
        """Return if the light is off."""

        if self._light_state == "on":
            return True
        else:
            return False

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return 'light'

    def turn_off(self, **kwargs):
        """Turn off light."""
        _LOGGER.debug("Turning off light")
        self.ryobi_door.send_message("lightState", False)
        self._light_state = "off"
        time.sleep(5)
        self.update()
        
    def turn_on(self, **kwargs):
        """Turn on light."""
        _LOGGER.debug("Turning on light")
        self.ryobi_door.send_message("lightState", True)
        time.sleep(5)
        self.update()


    def update(self):
        """Update status from the light."""
        _LOGGER.debug("Updating Ryobi Light status")
        self.ryobi_door.update()
        self._light_state = self.ryobi_door.get_light_status()
        _LOGGER.debug(self._light_state)
