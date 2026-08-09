"""Ryobi platform for the light component."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RyobiConfigEntry
from .const import DOMAIN
from .coordinator import RyobiDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RyobiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ryobi light entity."""
    coordinator = entry.runtime_data
    # Only add light entity if garageLight module is found or present
    if "garageLight" in coordinator.client._modules or "light_state" in coordinator.data:
        async_add_entities([RyobiLight(coordinator)])


class RyobiLight(CoordinatorEntity[RyobiDataUpdateCoordinator], LightEntity):
    """Representation of the Ryobi GDO overhead light."""

    _attr_has_entity_name = True
    _attr_name = "Light"
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, coordinator: RyobiDataUpdateCoordinator) -> None:
        """Initialize the light entity."""
        super().__init__(coordinator)
        self.device_id = coordinator.device_id
        self._attr_unique_id = f"{self.device_id}_light"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            manufacturer="Ryobi",
            model="GDO",
            name=self.coordinator.data.get("device_name", f"Ryobi GDO {self.device_id}"),
        )

    @property
    def is_on(self) -> bool:
        """Return True if the light is on."""
        light_state = self.coordinator.data.get("light_state")
        return bool(light_state == 1 or light_state is True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        LOGGER.debug("Turning on light for device %s", self.device_id)
        await self.coordinator.send_command("garageLight", "lightState", True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        LOGGER.debug("Turning off light for device %s", self.device_id)
        await self.coordinator.send_command("garageLight", "lightState", False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return light state attributes."""
        return self.coordinator.data.get("light_attributes", {})
