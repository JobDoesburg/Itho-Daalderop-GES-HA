"""Binary sensor platform for Itho Daalderop integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IthoDataUpdateCoordinator
from .const import CONF_SERIAL_NUMBER, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Itho binary sensors."""
    coordinator: IthoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    serial_number = entry.data[CONF_SERIAL_NUMBER]

    async_add_entities([IthoBoostActiveBinarySensor(coordinator, serial_number)])


class IthoBoostActiveBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for boost state.

    Read-only: the BoostBoiler API endpoint's request format is unknown, so
    boost can only be activated from the Climate Connect app for now.
    """

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self, coordinator: IthoDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_boost_active"
        self._attr_name = "Boost Active"
        self._attr_icon = "mdi:rocket-launch"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial_number)},
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if boost is active."""
        if self.coordinator.data and "device_status" in self.coordinator.data:
            return self.coordinator.data["device_status"].get("boostActive")
        return None
