"""Select platform for Itho Daalderop integration."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IthoDataUpdateCoordinator
from .const import CONF_SERIAL_NUMBER, DOMAIN, MODE_FROM_LABEL, MODE_LABELS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Itho select entities."""
    coordinator: IthoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    serial_number = entry.data[CONF_SERIAL_NUMBER]

    async_add_entities([IthoDeviceModeSelect(coordinator, serial_number)])


class IthoDeviceModeSelect(CoordinatorEntity, SelectEntity):
    """Select entity for the device operation mode.

    Options use the same names as the Climate Connect app; they map to the
    API mode values via MODE_LABELS (Smart=SmartControl, Schedule=Schedule,
    Always on=Continuous, Standby=Holiday).
    """

    def __init__(
        self, coordinator: IthoDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator)
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_device_mode"
        self._attr_name = "Device Mode"
        self._attr_icon = "mdi:state-machine"
        self._attr_options = [MODE_LABELS[mode] for mode in coordinator.profile.modes]
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial_number)},
        }

    @property
    def current_option(self) -> str | None:
        """Return the current selected mode."""
        if self.coordinator.data and "device_mode" in self.coordinator.data:
            mode = self.coordinator.data["device_mode"].get("deviceMode")
            return MODE_LABELS.get(mode, mode)
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected mode."""
        mode = MODE_FROM_LABEL.get(option, option)
        _LOGGER.info("Setting device mode to: %s (%s)", option, mode)

        success = await self.coordinator.api_client.async_set_device_mode(mode)

        if success:
            # Don't re-read immediately: the API returns the old mode for up
            # to ~30s after a write, which would revert the UI selection
            self.coordinator.apply_mode_optimistically(mode)
        else:
            _LOGGER.error("Failed to set device mode to %s", option)
