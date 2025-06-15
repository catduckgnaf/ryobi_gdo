"""Ryobi platform for the switch component."""

import logging
from typing import Any, cast, Final

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_ID, COORDINATOR, DOMAIN

LOGGER = logging.getLogger(__name__)

SWITCH_TYPES: Final[dict[str, SwitchEntityDescription]] = {
    "light": SwitchEntityDescription(
        name="Light",
        key="light_state",
    ),
    "inflator": SwitchEntityDescription(
        name="Inflator",
        key="inflator",
        entity_registry_enabled_default=False,
    ),
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the OpenEVSE switches."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    switches = []
    for switch in SWITCH_TYPES:
        switches.append(RyobiSwitch(hass, entry, coordinator, SWITCH_TYPES[switch]))

    async_add_entities(switches, False)


class RyobiSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a ryobi switch."""

    def __init__(
        self,
        hass,
        config_entry: ConfigEntry,
        coordinator: str,
        description: SwitchEntityDescription,
    ):
        """Initialize the switch."""
        super().__init__(coordinator)
        self.device_id = config_entry.data[CONF_DEVICE_ID]
        self.coordinator = coordinator
        self._type = description.key
        self._attr_name = f"{coordinator.data['device_name']} {description.name}"
        self._attr_unique_id = f"ryobi_gdo_{description.name}_{self.device_id}"

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
    def name(self) -> str:
        """Return the name of the entity."""
        return self._attr_name

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True if self.coordinator.client.ws_listening else False

    @property
    def is_on(self) -> bool:
        """Return if the light is off."""
        data = self.coordinator._data
        if self._type not in data:
            return False
        return cast(bool, data[self._type] == 1)

    async def async_turn_off(self, **kwargs: dict[str, Any]):
        """Turn off light."""
        if self._type == "light_state":
            LOGGER.debug("Turning off light")
            await self.coordinator.send_command("garageLight", "lightState", False)
        elif self._type == "inflator":
            LOGGER.debug("Turning off inflator")
            await self.coordinator.send_command("inflator", "moduleState", False)
            # FIX: Use async_request_refresh() to ask the coordinator to update.
            await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: dict[str, Any]):
        """Turn on light."""
        if self._type == "light_state":
            LOGGER.debug("Turning on light")
            await self.coordinator.send_command("garageLight", "lightState", True)
        elif self._type == "inflator":
            LOGGER.debug("Turning on inflator")
            await self.coordinator.send_command("inflator", "moduleState", True)
            # FIX: Use async_request_refresh() to ask the coordinator to update.
            await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return sesnsor attributes."""
        attrs = {}
        if self._type == "light_state":
            if "light_attributes" in self.coordinator.data:
                attrs.update(self.coordinator.data["light_attributes"])
        return attrs
