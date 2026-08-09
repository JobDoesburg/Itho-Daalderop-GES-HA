"""Water heater platform for Itho Daalderop integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IthoDataUpdateCoordinator
from .const import (
    CONF_SERIAL_NUMBER,
    DEVICE_MODES,
    DOMAIN,
    MODE_CONTINUOUS,
    MODE_HOLIDAY,
    MODE_SCHEDULE,
    MODE_SMART_CONTROL,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Itho water heater."""
    coordinator: IthoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    serial_number = entry.data[CONF_SERIAL_NUMBER]

    async_add_entities([IthoWaterHeater(coordinator, serial_number)])


class IthoWaterHeater(CoordinatorEntity, WaterHeaterEntity):
    """Representation of an Itho Daalderop water heater."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 10.0
    _attr_max_temp = 75.0
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )

    def __init__(
        self, coordinator: IthoDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the water heater."""
        super().__init__(coordinator)
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_water_heater"
        self._attr_name = f"Itho Boiler {serial_number}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial_number)},
            "name": f"Itho Boiler {serial_number}",
            "manufacturer": "Itho Daalderop",
            "model": "Water Heater",
        }

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.coordinator.data and "device_status" in self.coordinator.data:
            return self.coordinator.data["device_status"].get("deviceTemperatureMeasured")
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        if self.coordinator.data and "device_status" in self.coordinator.data:
            return self.coordinator.data["device_status"].get("deviceTemperatureSetpoint")
        return None

    @property
    def current_operation(self) -> str | None:
        """Return current operation mode."""
        if self.coordinator.data and "device_mode" in self.coordinator.data:
            mode = self.coordinator.data["device_mode"].get("deviceMode")
            # Map to Home Assistant standard modes
            if mode == MODE_SMART_CONTROL:
                return "eco"
            elif mode == MODE_SCHEDULE:
                return "auto"
            elif mode == MODE_CONTINUOUS:
                return "heat_pump"
            elif mode == MODE_HOLIDAY:
                return "off"
        return None

    @property
    def operation_list(self) -> list[str]:
        """Return the list of available operation modes."""
        return ["eco", "auto", "heat_pump", "off"]

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get("temperature")
        if temperature is not None:
            await self.coordinator.api_client.async_set_temperature(temperature)
            # Temperature change is reflected in device_status, will be updated on next poll
            # No immediate refresh needed - reduces API calls

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        # Map Home Assistant modes to Itho modes
        mode_mapping = {
            "eco": MODE_SMART_CONTROL,
            "auto": MODE_SCHEDULE,
            "heat_pump": MODE_CONTINUOUS,
            "off": MODE_HOLIDAY,
        }
        
        itho_mode = mode_mapping.get(operation_mode)
        if itho_mode:
            success = await self.coordinator.api_client.async_set_device_mode(itho_mode)
            if success:
                # Don't re-read immediately: the API returns the old mode
                # for up to ~30s after a write
                self.coordinator.apply_mode_optimistically(itho_mode)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {}
        
        if self.coordinator.data:
            if "device_status" in self.coordinator.data:
                status = self.coordinator.data["device_status"]
                attrs["boiler_content"] = f"{status.get('boilerContent', 0) * 100:.0f}%"
                attrs["device_state"] = status.get("deviceState")
                attrs["power"] = status.get("devicePowerMeasured")
                attrs["software_version"] = status.get("deviceSoftwareVersion")
                attrs["legionella_timer"] = status.get("legionellaPreventionTimer")
                
            if "pv_settings" in self.coordinator.data:
                pv = self.coordinator.data["pv_settings"]
                attrs["pv_enabled"] = pv.get("pvEnabled")
                attrs["pv_start_limit"] = pv.get("pvStartLimit")
                attrs["pv_stop_limit"] = pv.get("pvStopLimit")
        
        return attrs
