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
from homeassistant.components.light import (
    LightEntity, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, STATE_UNKNOWN, STATE_CLOSED)

"""REQUIREMENTS = ['py-ryobi-gdo==0.0.27']"""

DOMAIN = "ryobi_gdo"
_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

CONF_DEVICE_ID = 'device_id'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
})

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Ryobi lights."""
    from .py_ryobi_gdo import RyobiGDO as ryobi_door
    lights = []

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    devices = config.get(CONF_DEVICE_ID)

    for device_id in devices:
        my_door = ryobi_door(username, password, device_id)
        _LOGGER.debug("Getting the API key")
        if my_door.get_api_key() is False:
            _LOGGER.error("Wrong credentials, no API key retrieved")
            return
        _LOGGER.debug("Checking if the device ID is present")
        if my_door.check_device_id() is False:
            _LOGGER.error("%s not in your device list", device_id)
            return
        _LOGGER.debug("Adding device %s to lights", device_id)
        lights.append(RyobiLight(hass, my_door))
    if lights:
        _LOGGER.debug("Adding lights")
        add_entities(lights, True)


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
