"""Ryobi garage door opener integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import ISSUE_URL, PLATFORMS, VERSION
from .coordinator import RyobiDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)

RyobiConfigEntry = ConfigEntry[RyobiDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: RyobiConfigEntry) -> bool:
    """Set up Ryobi GDO from a config entry."""
    LOGGER.info(
        "Ryobi GDO integration version %s starting. Issue tracker: %s",
        VERSION,
        ISSUE_URL,
    )

    coordinator = RyobiDataUpdateCoordinator(hass, interval=60, entry=entry)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Start websocket listener
    await coordinator.client.ws_connect()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RyobiConfigEntry) -> bool:
    """Unload a config entry."""
    LOGGER.debug("Unloading Ryobi GDO integration for entry: %s", entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator = entry.runtime_data
        await coordinator.client.ws_disconnect()

    return unload_ok
