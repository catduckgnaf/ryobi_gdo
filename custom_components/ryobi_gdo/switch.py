"""Ryobi platform for the switch component."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RyobiConfigEntry
from .const import DOMAIN
from .coordinator import RyobiDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        name="Light",
        key="light_state",
    ),
    SwitchEntityDescription(
        name="Inflator",
        key="inflator",
        icon="mdi:tire",
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RyobiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ryobi switches."""
    coordinator = entry.runtime_data
    switches: list[RyobiSwitch] = []

    for description in SWITCH_TYPES:
        if description.key in coordinator.client._modules or description.key in coordinator.data:
            switches.append(RyobiSwitch(coordinator, description))

    async_add_entities(switches)


class RyobiSwitch(CoordinatorEntity[RyobiDataUpdateCoordinator], SwitchEntity):
    """Representation of a Ryobi accessory switch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RyobiDataUpdateCoordinator,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
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
        )

    @property
    def is_on(self) -> bool:
        """Return True if the switch is on."""
        state = self.coordinator.data.get(self.entity_description.key)
        return bool(state == 1 or state is True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        LOGGER.debug("Turning off %s for device %s", self.entity_description.key, self.device_id)
        if self.entity_description.key == "light_state":
            await self.coordinator.send_command("garageLight", "lightState", False)
        else:
            await self.coordinator.send_command(self.entity_description.key, "moduleState", False)
            await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        LOGGER.debug("Turning on %s for device %s", self.entity_description.key, self.device_id)
        if self.entity_description.key == "light_state":
            await self.coordinator.send_command("garageLight", "lightState", True)
        else:
            await self.coordinator.send_command(self.entity_description.key, "moduleState", True)
            await self.coordinator.async_request_refresh()
