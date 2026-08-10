"""Binary sensor platform for Ryobi GDO."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RyobiConfigEntry
from .const import DOMAIN
from .coordinator import RyobiDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class RyobiBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Ryobi binary sensor entities."""

    required_module: str | None = None


BINARY_SENSORS: tuple[RyobiBinarySensorEntityDescription, ...] = (
    RyobiBinarySensorEntityDescription(
        name="Motion",
        key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
        required_module="garageDoor",
    ),
    RyobiBinarySensorEntityDescription(
        name="Safety Sensor",
        key="safety",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:laser-pointer",
        required_module="garageDoor",
    ),
    RyobiBinarySensorEntityDescription(
        name="Vacation Mode",
        key="vacationMode",
        icon="mdi:wallet-travel",
        required_module="garageDoor",
        entity_registry_enabled_default=False,
    ),
    RyobiBinarySensorEntityDescription(
        name="Park Assist Laser",
        key="park_assist",
        icon="mdi:laser-pointer",
        required_module="parkAssistLaser",
    ),
    RyobiBinarySensorEntityDescription(
        name="Bluetooth Speaker",
        key="bt_speaker",
        icon="mdi:speaker",
        required_module="btSpeaker",
        entity_registry_enabled_default=False,
    ),
    RyobiBinarySensorEntityDescription(
        name="Microphone",
        key="micStatus",
        icon="mdi:microphone",
        required_module="btSpeaker",
        entity_registry_enabled_default=False,
    ),
    RyobiBinarySensorEntityDescription(
        name="Server Connection",
        key="websocket",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        required_module=None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RyobiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Define the binary_sensor platform."""
    coordinator = entry.runtime_data
    binary_sensors: list[RyobiBinarySensor] = []

    for description in BINARY_SENSORS:
        # Check module presence
        if (
            description.required_module is None
            or description.required_module in coordinator.client._modules
            or description.key in coordinator.data
        ):
            binary_sensors.append(RyobiBinarySensor(coordinator, description))

    async_add_entities(binary_sensors)


class RyobiBinarySensor(
    CoordinatorEntity[RyobiDataUpdateCoordinator], BinarySensorEntity
):
    """Ryobi GDO binary sensor class."""

    _attr_has_entity_name = True
    entity_description: RyobiBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: RyobiDataUpdateCoordinator,
        description: RyobiBinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.device_id = coordinator.device_id
        self._key = description.key
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
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on."""
        if self._key == "websocket":
            return bool(self.coordinator.client.ws_listening)

        val = self.coordinator.data.get(self._key)
        if val is None:
            return None
        return bool(val == 1 or val is True)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        if self._key == "websocket":
            is_local = bool(self.coordinator.client.is_local)
            server_type = "Local Server" if is_local else "Ryobi Cloud"
            return {
                "server_type": server_type,
                "is_local": is_local,
                "server_host": self.coordinator.client.host,
                "websocket_listening": bool(self.coordinator.client.ws_listening),
            }
        return {}
