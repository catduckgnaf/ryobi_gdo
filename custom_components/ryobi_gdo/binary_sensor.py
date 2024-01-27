"""Binary sensor platform for Ryobi GDO."""

import logging
from typing import Final, cast

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_ID, COORDINATOR, DOMAIN

LOGGER = logging.getLogger(__name__)

BINARY_SENSORS: Final[dict[str, BinarySensorEntityDescription]] = {
    "park_assist": BinarySensorEntityDescription(
        name="Park Assist",
        icon="mdi:parking",
        key="park_assist",
    ),
    "inflator": BinarySensorEntityDescription(
        name="Inflator",
        icon="mdi:car-tire-alert",
        key="inflator",
        entity_registry_enabled_default=False,
    ),
    "motion": BinarySensorEntityDescription(
        name="Motion",
        key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
        entity_registry_enabled_default=False,
    ),
    "vacationMode": BinarySensorEntityDescription(
        name="Vacation Mode",
        key="vacationMode",
        icon="mdi:wallet-travel",
        entity_registry_enabled_default=False,
    ),
    "sensorFlag": BinarySensorEntityDescription(
        name="Safety Sensor",
        key="saftey",
        icon="mdi:laser-pointer",
        entity_registry_enabled_default=False,
    ),
    "btSpeaker": BinarySensorEntityDescription(
        name="Bluetooth Speaker",
        key="bt_speaker",
        icon="mdi:speaker",
        entity_registry_enabled_default=False,
    ),
    "micStatus": BinarySensorEntityDescription(
        name="Microphone",
        key="micStatus",
        icon="mdi:microphone",
        entity_registry_enabled_default=False,
    ),
    "websocket": BinarySensorEntityDescription(
        name="Server Connection",
        key="websocket",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
}


async def async_setup_entry(hass, entry, async_add_devices):
    """Define the binary_sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    binary_sensors = []
    for binary_sensor in BINARY_SENSORS:
        binary_sensors.append(
            RyobiBinarySensor(BINARY_SENSORS[binary_sensor], entry, coordinator)
        )

    async_add_devices(binary_sensors, False)


class RyobiBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """ryobi_gdo binary_sensor class."""

    def __init__(
        self,
        sensor_description: BinarySensorEntityDescription,
        config_entry: ConfigEntry,
        coordinator: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config = config_entry
        self.entity_description = sensor_description
        self._name = sensor_description.name
        self._key = sensor_description.key
        self.device_id = config_entry.data[CONF_DEVICE_ID]

        self._attr_name = f"{coordinator.data['device_name']} {self._name}"
        self._attr_unique_id = f"ryobi_gdo_{self._name}_{self.device_id}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if self._key == "websocket":
            return True  # This sensor should always be available
        return True if self._key in self.coordinator.data else False

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self.entity_description.icon

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
    def is_on(self) -> bool:
        """Return True if the service is on."""
        data = self.coordinator.data
        if self._key == "websocket":
            return self.coordinator.client.ws_listening
        if self._key not in data:
            LOGGER.info("binary_sensor [%s] not supported.", self._key)
            return None
        LOGGER.debug("binary_sensor [%s]: %s", self._name, data[self._key])
        return cast(bool, data[self._key] == 1)
