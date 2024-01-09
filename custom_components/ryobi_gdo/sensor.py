"""Support for Ryobi GDO sensors."""

from __future__ import annotations

from typing import Any, Final, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_ATTRIBUTION, ATTRIBUTION, CONF_DEVICE_ID, COORDINATOR, DOMAIN

SENSOR_TYPES: Final[dict[str, SensorEntityDescription]] = {
    "battery_level": SensorEntityDescription(
        name="Battery Level",
        icon="mdi:battery",
        key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "wifi_rssi": SensorEntityDescription(
        name="WiFi Signal",
        icon="mdi:wifi",
        key="wifi_rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the OpenEVSE sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    sensors = []
    for sensor in SENSOR_TYPES:  # pylint: disable=consider-using-dict-items
        sensors.append(RyobiSensor(SENSOR_TYPES[sensor], coordinator, entry))

    async_add_entities(sensors, False)


class RyobiSensor(CoordinatorEntity, SensorEntity):
    """Implementation of an Ryobi sensor."""

    def __init__(
        self,
        sensor_description: SensorEntityDescription,
        coordinator: str,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config = config_entry
        self.entity_description = sensor_description
        self._name = sensor_description.name
        self.device_id = config_entry.data[CONF_DEVICE_ID]
        self._attr_name = f"ryobi_gdo_{self._name}_{self.device_id}"
        self._attr_unique_id = f"ryobi_gdo_{self._name}_{self.device_id}"

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
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        return self.coordinator.data[self.entity_description.key]

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self.entity_description.icon

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        data = self.coordinator.data
        if self.entity_description.key not in data or (
            self.entity_description.key in data
            and data[self.entity_description.key] is None
        ):
            return False
        return self.coordinator.last_update_success

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return sesnsor attributes."""
        attrs = {}
        attrs[ATTR_ATTRIBUTION] = ATTRIBUTION
        return attrs
