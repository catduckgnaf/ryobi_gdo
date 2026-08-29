"""Ryobi platform for the fan component."""

from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import RyobiConfigEntry
from .const import DOMAIN, FAN_SPEED_RANGE
from .coordinator import RyobiDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RyobiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ryobi fans, one entity per installed fan module."""
    coordinator = entry.runtime_data
    fan_keys = coordinator.client.module_instances("fan")

    if not fan_keys:
        LOGGER.debug("No fan module present on device %s", coordinator.device_id)
        return

    multiple = len(fan_keys) > 1
    async_add_entities(
        RyobiFan(coordinator, index, multiple) for index in range(len(fan_keys))
    )


class RyobiFan(CoordinatorEntity[RyobiDataUpdateCoordinator], FanEntity):
    """Representation of a Ryobi accessory fan."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:fan"
    _attr_supported_features = FanEntityFeature.SET_SPEED
    _attr_speed_count = int(FAN_SPEED_RANGE[1])

    def __init__(
        self,
        coordinator: RyobiDataUpdateCoordinator,
        index: int,
        multiple: bool,
    ) -> None:
        """Initialize the fan."""
        super().__init__(coordinator)
        self.device_id = coordinator.device_id
        self._index = index
        # Keep the first fan's unique_id stable so existing installs are not
        # migrated into a new entity when a second fan appears later.
        suffix = "fan" if index == 0 else f"fan_{index}"
        self._attr_unique_id = f"{self.device_id}_{suffix}"
        self._attr_name = f"Fan {index + 1}" if multiple else "Fan"

    @property
    def available(self) -> bool:
        """Return True if the backing fan module is still present."""
        if self._index >= len(self.coordinator.client.module_instances("fan")):
            return False
        return super().available

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
    def _speed(self) -> int:
        """Return the raw speed value reported for this fan."""
        raw = self.coordinator.data.get(f"fan_speed_{self._index}")
        if raw is None and self._index == 0:
            raw = self.coordinator.data.get("fan_speed")
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    @property
    def is_on(self) -> bool:
        """Return True if the fan is running."""
        state = self.coordinator.data.get(f"fan_{self._index}")
        if state is None and self._index == 0:
            state = self.coordinator.data.get("fan")
        if state is None:
            return self._speed > 0
        return bool(state == 1 or state is True)

    @property
    def percentage(self) -> int:
        """Return the current speed as a percentage."""
        if not self.is_on:
            return 0
        return ranged_value_to_percentage(FAN_SPEED_RANGE, self._speed)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the raw module speed so the state is unambiguous."""
        return {"speed_step": self._speed}

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed from a percentage."""
        if percentage == 0:
            await self.async_turn_off()
            return

        speed = math.ceil(percentage_to_ranged_value(FAN_SPEED_RANGE, percentage))
        speed = max(1, min(int(FAN_SPEED_RANGE[1]), speed))
        LOGGER.debug(
            "Setting fan %s speed to %s (%s%%) for device %s",
            self._index,
            speed,
            percentage,
            self.device_id,
        )
        await self.coordinator.send_command("fan", "speed", speed, index=self._index)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on, optionally at a given speed."""
        if percentage:
            await self.async_set_percentage(percentage)
            return
        await self.coordinator.send_command(
            "fan", "moduleState", 1, index=self._index
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        LOGGER.debug("Turning off fan %s for device %s", self._index, self.device_id)
        # Speed 0 is what the keypad sends on the final press of the cycle; the
        # moduleState write is a belt-and-braces follow-up for firmware that
        # tracks the two separately.
        await self.coordinator.send_command("fan", "speed", 0, index=self._index)
        await self.coordinator.send_command(
            "fan", "moduleState", 0, index=self._index
        )
        await self.coordinator.async_request_refresh()
