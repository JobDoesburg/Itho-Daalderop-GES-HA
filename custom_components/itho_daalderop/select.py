"""Select platform for Itho Daalderop integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IthoDataUpdateCoordinator
from .const import CONF_SERIAL_NUMBER, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Itho select entities."""
    coordinator: IthoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    serial_number = entry.data[CONF_SERIAL_NUMBER]

    selects = [
        IthoDeviceModeSelect(coordinator, serial_number),
    ]

    async_add_entities(selects)


class IthoDeviceModeSelect(CoordinatorEntity, SelectEntity):
    """Select entity for device operation mode."""

    def __init__(
        self, coordinator: IthoDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator)
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_device_mode"
        self._attr_name = "Device Mode"
        self._attr_icon = "mdi:state-machine"
        # Available modes depend on the boiler type (e.g. Smartboilers
        # have no Continuous mode)
        self._attr_options = list(coordinator.profile.modes)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial_number)},
        }

    @property
    def current_option(self) -> str | None:
        """Return the current selected mode."""
        if self.coordinator.data and "device_mode" in self.coordinator.data:
            mode = self.coordinator.data["device_mode"].get("deviceMode")
            _LOGGER.debug("Current device mode from API: %s", mode)
            return mode
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected mode."""
        _LOGGER.info("Setting device mode to: %s", option)
        
        success = await self.coordinator.api_client.async_set_device_mode(option)

        if success:
            # Don't re-read immediately: the API returns the old mode for up
            # to ~30s after a write, which would revert the UI selection
            self.coordinator.apply_mode_optimistically(option)
        else:
            _LOGGER.error("Failed to set device mode to %s", option)
