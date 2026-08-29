"""Ryobi garage door opener integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import ISSUE_URL, PLATFORMS, VERSION
from .coordinator import RyobiDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    RyobiConfigEntry = ConfigEntry[RyobiDataUpdateCoordinator]
else:
    # ConfigEntry became runtime-subscriptable in Home Assistant 2024.6.
    RyobiConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: RyobiConfigEntry) -> bool:
    """Set up Ryobi GDO from a config entry."""
    LOGGER.info(
        "Ryobi GDO integration version %s starting. Issue tracker: %s",
        VERSION,
        ISSUE_URL,
    )

    coordinator = RyobiDataUpdateCoordinator(hass, interval=60, entry=entry)
    entry.runtime_data = coordinator

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Start websocket listener
    await coordinator.client.ws_connect()

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_reload_entry(hass: HomeAssistant, entry: RyobiConfigEntry) -> None:
    """Reload config entry on options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: RyobiConfigEntry) -> bool:
    """Unload a config entry."""
    LOGGER.debug("Unloading Ryobi GDO integration for entry: %s", entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and hasattr(entry, "runtime_data") and entry.runtime_data is not None:
        coordinator = entry.runtime_data
        if coordinator.client:
            await coordinator.client.ws_disconnect()

    return unload_ok
