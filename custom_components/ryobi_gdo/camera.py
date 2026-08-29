"""Camera platform for Ryobi GDO."""

from __future__ import annotations

import logging

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RyobiConfigEntry
from .const import ATTRIBUTION, DOMAIN
from .coordinator import RyobiDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RyobiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ryobi camera."""
    coordinator = entry.runtime_data
    if (
        "camera" in coordinator.client.modules
        or "securityCamera" in coordinator.client.modules
    ):
        LOGGER.info(
            "Ryobi Security Camera module detected on device %s", coordinator.device_id
        )
        async_add_entities([RyobiCamera(coordinator)])
    else:
        LOGGER.debug(
            "No camera module attached to device %s, skipping camera platform",
            coordinator.device_id,
        )


class RyobiCamera(CoordinatorEntity[RyobiDataUpdateCoordinator], Camera):
    """Representation of a Ryobi Security Camera module."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    _attr_name = "Security Camera"
    _attr_icon = "mdi:cctv"

    def __init__(self, coordinator: RyobiDataUpdateCoordinator) -> None:
        """Initialize the camera."""
        super().__init__(coordinator)
        Camera.__init__(self)
        self.device_id = coordinator.device_id
        self._attr_unique_id = f"{self.device_id}_security_camera"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            manufacturer="Ryobi",
            model="GDO",
            name=self.coordinator.data.get(
                "device_name", f"Ryobi GDO {self.device_id}"
            ),
            serial_number=self.device_id,
        )

    @property
    def is_on(self) -> bool:
        """Return true if camera is on."""
        return self.coordinator.data.get("camera_state", True)

    @property
    def is_recording(self) -> bool:
        """Return true if the camera is recording."""
        return self.coordinator.data.get("camera_recording", False)

    @property
    def available(self) -> bool:
        """Return True if camera module is physically present and connected."""
        if (
            "camera" not in self.coordinator.client.modules
            and "securityCamera" not in self.coordinator.client.modules
        ):
            return False
        return super().available

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        url = self.coordinator.data.get("camera_image_url")
        if not url:
            host = self.coordinator.client.host
            url = f"{host}/api/camera/{self.device_id}/snapshot"
        try:
            async with self.coordinator.client.session.get(url, timeout=5) as response:
                if response.status == 200:
                    return await response.read()
        except Exception as err:  # pylint: disable=broad-exception-caught
            LOGGER.debug("Error fetching camera image: %s", err)
        return None
