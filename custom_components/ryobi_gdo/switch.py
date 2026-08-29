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
        icon="mdi:lightbulb",
    ),
    SwitchEntityDescription(
        name="Inflator",
        key="inflator",
        icon="mdi:tire",
    ),
    SwitchEntityDescription(
        name="Fan",
        key="fan",
        icon="mdi:fan",
    ),
    SwitchEntityDescription(
        name="Park Assist Laser",
        key="park_assist",
        icon="mdi:laser-pointer",
    ),
    SwitchEntityDescription(
        name="Bluetooth Speaker",
        key="bt_speaker",
        icon="mdi:speaker",
    ),
    SwitchEntityDescription(
        name="Microphone",
        key="micStatus",
        icon="mdi:microphone",
    ),
    SwitchEntityDescription(
        name="Vacation Mode",
        key="vacationMode",
        icon="mdi:wallet-travel",
    ),
)

KEY_TO_MODULE: dict[str, str] = {
    "light_state": "garageLight",
    "inflator": "inflator",
    "fan": "fan",
    "park_assist": "parkAssistLaser",
    "bt_speaker": "btSpeaker",
    "micStatus": "btSpeaker",
    "vacationMode": "garageDoor",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RyobiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ryobi switches."""
    coordinator = entry.runtime_data
    switches: list[RyobiSwitch] = []

    for description in SWITCH_TYPES:
        required_mod = KEY_TO_MODULE.get(description.key, description.key)
        if required_mod in coordinator.client._modules:
            switches.append(RyobiSwitch(coordinator, description))
        else:
            LOGGER.debug(
                "Skipping switch %s: module %s not present on device",
                description.name,
                required_mod,
            )

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
    def available(self) -> bool:
        """Return True if switch is available."""
        required_mod = KEY_TO_MODULE.get(self.entity_description.key, self.entity_description.key)
        if required_mod not in self.coordinator.client._modules:
            return False
        return super().available

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
    def is_on(self) -> bool:
        """Return True if the switch is on."""
        state = self.coordinator.data.get(self.entity_description.key)
        return bool(state == 1 or state is True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        LOGGER.debug("Turning off %s for device %s", self.entity_description.key, self.device_id)
        key = self.entity_description.key
        if key == "light_state":
            await self.coordinator.send_command("garageLight", "lightState", 0)
        elif key == "vacationMode":
            await self.coordinator.send_command("garageDoor", "vacationMode", 0)
        elif key == "micStatus":
            await self.coordinator.send_command("btSpeaker", "micEnable", 0)
        elif key == "bt_speaker":
            await self.coordinator.send_command("btSpeaker", "moduleState", 0)
        elif key == "park_assist":
            await self.coordinator.send_command("parkAssistLaser", "moduleState", 0)
        elif key == "fan":
            await self.coordinator.send_command("fan", "moduleState", 0)
        elif key == "inflator":
            await self.coordinator.send_command("inflator", "moduleState", 0)
        else:
            await self.coordinator.send_command(key, "moduleState", 0)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        LOGGER.debug("Turning on %s for device %s", self.entity_description.key, self.device_id)
        key = self.entity_description.key
        if key == "light_state":
            await self.coordinator.send_command("garageLight", "lightState", 1)
        elif key == "vacationMode":
            await self.coordinator.send_command("garageDoor", "vacationMode", 1)
        elif key == "micStatus":
            await self.coordinator.send_command("btSpeaker", "micEnable", 1)
        elif key == "bt_speaker":
            await self.coordinator.send_command("btSpeaker", "moduleState", 1)
        elif key == "park_assist":
            await self.coordinator.send_command("parkAssistLaser", "moduleState", 1)
        elif key == "fan":
            await self.coordinator.send_command("fan", "moduleState", 1)
        elif key == "inflator":
            await self.coordinator.send_command("inflator", "moduleState", 1)
        else:
            await self.coordinator.send_command(key, "moduleState", 1)
        await self.coordinator.async_request_refresh()
