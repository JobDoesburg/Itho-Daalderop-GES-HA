"""Switch platform for Itho Daalderop integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up Itho switches.

    Note: the operation mode (including standby/holiday) is controlled via
    the Device Mode select entity. There is no boost switch because the
    BoostBoiler API endpoint's request format is still unknown; boost state
    is exposed as a binary sensor instead.
    """
    coordinator: IthoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    serial_number = entry.data[CONF_SERIAL_NUMBER]

    switches: list[SwitchEntity] = []

    if coordinator.profile.supports_pv:
        switches.append(IthoPvEnabledSwitch(coordinator, serial_number))

    async_add_entities(switches)


class IthoPvEnabledSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to enable/disable PV function."""

    def __init__(
        self, coordinator: IthoDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_pv_enabled"
        self._attr_name = "PV Function"
        self._attr_icon = "mdi:solar-power"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial_number)},
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if PV function is enabled."""
        if self.coordinator.data and "pv_settings" in self.coordinator.data:
            return self.coordinator.data["pv_settings"].get("pvEnabled", False)
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable PV function."""
        success = await self.coordinator.api_client.async_set_pv_settings(
            pv_enabled=True
        )
        if success:
            await self.coordinator.async_refresh_settings()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable PV function."""
        success = await self.coordinator.api_client.async_set_pv_settings(
            pv_enabled=False
        )
        if success:
            await self.coordinator.async_refresh_settings()
