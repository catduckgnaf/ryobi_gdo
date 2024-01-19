"""Ryobi platform for the cover component."""

from __future__ import annotations

import logging
from typing import Final

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityDescription,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_CLOSED, STATE_CLOSING, STATE_OPENING
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_ID, COORDINATOR, DOMAIN

LOGGER = logging.getLogger(__name__)

COVER_TYPES: Final[dict[str, CoverEntityDescription]] = {
    "garage_door": CoverEntityDescription(
        name="Garage Door",
        key="door_state",
        device_class=CoverDeviceClass.GARAGE,
    ),
}

SUPPORTED_FEATURES = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the cover entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    covers = []
    for cover in COVER_TYPES:  # pylint: disable=consider-using-dict-items
        covers.append(RyobiCover(COVER_TYPES[cover], coordinator, entry))

    async_add_entities(covers, False)


class RyobiCover(CoordinatorEntity, CoverEntity):
    """Representation of a ryobi cover."""

    def __init__(
        self,
        sensor_description: CoverEntityDescription,
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
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening or not."""
        if self.coordinator.data[self.entity_description.key] is None:
            return None
        return bool(self.coordinator.data[self.entity_description.key] == STATE_OPENING)

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing or not."""
        if self.coordinator.data[self.entity_description.key] is None:
            return None
        return bool(self.coordinator.data[self.entity_description.key] == STATE_CLOSING)

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        if self.coordinator.data[self.entity_description.key] is None:
            return None
        return bool(self.coordinator.data[self.entity_description.key] == STATE_CLOSED)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_FEATURES

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        LOGGER.debug("Closing garage door")
        await self.coordinator.send_command("garageDoor", "doorCommand", 0)

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        LOGGER.debug("Opening garage door")
        await self.coordinator.send_command("garageDoor", "doorCommand", 1)

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return sesnsor attributes."""
        attrs = {}
        if "door_attributes" in self.coordinator.data:
            attrs.update(self.coordinator.data["door_attributes"])
        return attrs
