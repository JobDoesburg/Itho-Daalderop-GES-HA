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
    the Device Mode select entity.
    """
    coordinator: IthoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    serial_number = entry.data[CONF_SERIAL_NUMBER]

    switches: list[SwitchEntity] = []

    if coordinator.profile.supports_boost:
        switches.append(IthoBoostSwitch(coordinator, serial_number))

    if coordinator.profile.supports_pv:
        switches.append(IthoPvEnabledSwitch(coordinator, serial_number))

    async_add_entities(switches)


class IthoBoostSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to control boiler boost mode.

    Boost is a capability of both boiler types, but activating it via the
    API does not work yet: the BoostBoiler endpoint rejects every known
    payload shape ("BoostBoilerRequestContract" validation error). Turning
    the switch on will log the API's error; the state readout does work.
    """

    def __init__(
        self, coordinator: IthoDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_boost"
        self._attr_name = "Boost Mode"
        self._attr_icon = "mdi:rocket-launch"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial_number)},
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if boost is active."""
        if self.coordinator.data and "device_status" in self.coordinator.data:
            return self.coordinator.data["device_status"].get("boostActive", False)
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on boost mode."""
        await self.coordinator.api_client.async_boost_boiler()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off boost mode.

        The API has no known way to cancel a boost; it ends on its own
        when the boiler reaches the boost temperature.
        """


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
