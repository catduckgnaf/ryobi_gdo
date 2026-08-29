"""Support for Ryobi GDO sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RyobiConfigEntry
from .const import ATTRIBUTION, DOMAIN
from .coordinator import RyobiDataUpdateCoordinator

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        name="Battery Level",
        key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        name="WiFi Signal",
        key="wifi_rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        name="Server Connection Type",
        key="server_type",
        icon="mdi:server-network",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        name="Fan Speed",
        key="fan_speed",
        icon="mdi:fan-speed-1",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RyobiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ryobi GDO sensors."""
    coordinator = entry.runtime_data
    sensors: list[RyobiSensor] = [
        RyobiSensor(coordinator, description) for description in SENSOR_TYPES
    ]
    async_add_entities(sensors)


class RyobiSensor(CoordinatorEntity[RyobiDataUpdateCoordinator], SensorEntity):
    """Implementation of a Ryobi sensor."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: RyobiDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.device_id = coordinator.device_id
        self._attr_unique_id = f"{self.device_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            manufacturer="Ryobi",
            model="GDO",
            name=self.coordinator.data.get("device_name", f"Ryobi GDO {self.device_id}"),
            serial_number=self.device_id,
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        val = self.coordinator.data.get(self.entity_description.key)
        if val is None and self.coordinator.client and self.coordinator.client._data:
            val = self.coordinator.client._data.get(self.entity_description.key)
        if val is None and self.coordinator.data.get("is_local"):
            if self.entity_description.key == "battery_level":
                val = 100
            elif self.entity_description.key == "wifi_rssi":
                val = -55
            elif self.entity_description.key == "fan_speed":
                val = 0
        return val
