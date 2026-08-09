"""Number platform for Itho Daalderop."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower, UnitOfTemperature
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
    """Set up Itho number entities."""
    coordinator: IthoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    serial_number = entry.data[CONF_SERIAL_NUMBER]

    profile = coordinator.profile

    numbers: list[NumberEntity] = []

    if profile.supports_temperature_setpoint:
        numbers.append(IthoTemperatureSetpointNumber(coordinator, serial_number))

    if profile.supports_pv:
        numbers.extend(
            [
                IthoPvStartLimitNumber(coordinator, serial_number),
                IthoPvStopLimitNumber(coordinator, serial_number),
                IthoPvSetpointNumber(coordinator, serial_number),
            ]
        )

    async_add_entities(numbers)


class IthoNumberBase(CoordinatorEntity, NumberEntity):
    """Base class for Itho number entities."""

    def __init__(
        self,
        coordinator: IthoDataUpdateCoordinator,
        serial_number: str,
        key: str,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._serial_number = serial_number
        self._key = key
        self._attr_unique_id = f"{serial_number}_{key}"
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._serial_number)},
            "name": f"Itho Boiler {self._serial_number}",
            "manufacturer": "Itho Daalderop",
            "model": self.coordinator.profile.model,
        }


class IthoTemperatureSetpointNumber(IthoNumberBase):
    """Number entity for target temperature setpoint."""

    def __init__(self, coordinator: IthoDataUpdateCoordinator, serial_number: str) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, serial_number, "temperature_setpoint")
        self._attr_name = "Temperatuur Instelling"
        self._attr_icon = "mdi:thermometer"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_min_value = 10.0
        self._attr_native_max_value = 75.0
        self._attr_native_step = 1.0

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self.coordinator.data and "device_mode" in self.coordinator.data:
            return self.coordinator.data["device_mode"].get("temperature")
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Update the value."""
        _LOGGER.info("Setting temperature setpoint to %s°C", value)
        # The setpoint travels in the UpdateDeviceMode payload, so the
        # current mode is sent along unchanged
        current_mode = "SmartControl"
        if self.coordinator.data and "device_mode" in self.coordinator.data:
            current_mode = self.coordinator.data["device_mode"].get(
                "deviceMode", current_mode
            )
        success = await self.coordinator.api_client.async_set_temperature(
            value, current_mode
        )
        if success:
            if self.coordinator.data and "device_mode" in self.coordinator.data:
                self.coordinator.data["device_mode"]["temperature"] = value
                self.coordinator.async_set_updated_data(self.coordinator.data)
        else:
            _LOGGER.error("Failed to update temperature setpoint")


class IthoPvStartLimitNumber(IthoNumberBase):
    """Number entity for PV start limit."""

    def __init__(self, coordinator: IthoDataUpdateCoordinator, serial_number: str) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, serial_number, "pv_start_limit")
        self._attr_name = "PV Start Limit"
        self._attr_icon = "mdi:solar-power-variant"
        self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
        self._attr_mode = NumberMode.BOX
        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 10.0
        self._attr_native_step = 0.1

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self.coordinator.data and "pv_settings" in self.coordinator.data:
            return self.coordinator.data["pv_settings"].get("pvStartLimit")
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Update the value."""
        _LOGGER.info("Setting PV start limit to %s kW", value)
        success = await self.coordinator.api_client.async_set_pv_settings(
            pv_start_limit=value
        )
        if success:
            # Only refresh settings, not full device status - reduces API calls
            await self.coordinator.async_refresh_settings()
        else:
            _LOGGER.error("Failed to update PV start limit")


class IthoPvStopLimitNumber(IthoNumberBase):
    """Number entity for PV stop limit."""

    def __init__(self, coordinator: IthoDataUpdateCoordinator, serial_number: str) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, serial_number, "pv_stop_limit")
        self._attr_name = "PV Stop Limit"
        self._attr_icon = "mdi:solar-power-variant-outline"
        self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
        self._attr_mode = NumberMode.BOX
        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 10.0
        self._attr_native_step = 0.1

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self.coordinator.data and "pv_settings" in self.coordinator.data:
            return self.coordinator.data["pv_settings"].get("pvStopLimit")
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Update the value."""
        _LOGGER.info("Setting PV stop limit to %s kW", value)
        success = await self.coordinator.api_client.async_set_pv_settings(
            pv_stop_limit=value
        )
        if success:
            await self.coordinator.async_refresh_settings()
        else:
            _LOGGER.error("Failed to update PV stop limit")


class IthoPvSetpointNumber(IthoNumberBase):
    """Number entity for PV target temperature."""

    def __init__(self, coordinator: IthoDataUpdateCoordinator, serial_number: str) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, serial_number, "pv_setpoint")
        self._attr_name = "PV Target Temperature"
        self._attr_icon = "mdi:thermometer"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_mode = NumberMode.BOX
        self._attr_native_min_value = 40.0
        self._attr_native_max_value = 90.0
        self._attr_native_step = 1.0

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self.coordinator.data and "pv_settings" in self.coordinator.data:
            return self.coordinator.data["pv_settings"].get("pvSetpoint")
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Update the value."""
        _LOGGER.info("Setting PV target temperature to %s°C", value)
        success = await self.coordinator.api_client.async_set_pv_settings(
            pv_setpoint=value
        )
        if success:
            await self.coordinator.async_refresh_settings()
        else:
            _LOGGER.error("Failed to update PV target temperature")
