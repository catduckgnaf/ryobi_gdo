"""Ryobi platform for the cover component."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import STATE_CLOSED, STATE_CLOSING, STATE_OPENING
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
    """Set up the cover entities."""
    coordinator = entry.runtime_data
    async_add_entities([RyobiCover(coordinator)])


class RyobiCover(CoordinatorEntity[RyobiDataUpdateCoordinator], CoverEntity):
    """Representation of a Ryobi garage door cover."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(self, coordinator: RyobiDataUpdateCoordinator) -> None:
        """Initialize the cover entity."""
        super().__init__(coordinator)
        self.device_id = coordinator.device_id
        self._attr_unique_id = f"{self.device_id}_door"

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
    def is_opening(self) -> bool | None:
        """Return if the cover is opening or not."""
        state = self.coordinator.data.get("door_state")
        if state is None:
            return None
        return state == STATE_OPENING

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing or not."""
        state = self.coordinator.data.get("door_state")
        if state is None:
            return None
        return state == STATE_CLOSING

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        state = self.coordinator.data.get("door_state")
        if state is None:
            return None
        return state == STATE_CLOSED

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        LOGGER.debug("Closing garage door for device %s", self.device_id)
        await self.coordinator.send_command("garageDoor", "doorCommand", 0)
        await self.coordinator.async_request_refresh()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        LOGGER.debug("Opening garage door for device %s", self.device_id)
        await self.coordinator.send_command("garageDoor", "doorCommand", 1)
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return sensor attributes."""
        attrs = dict(self.coordinator.data.get("door_attributes", {}))
        attrs["device_id"] = self.device_id
        return attrs
