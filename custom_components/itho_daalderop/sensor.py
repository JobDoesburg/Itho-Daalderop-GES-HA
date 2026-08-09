"""Sensors for Itho Daalderop integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
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
    """Set up Itho sensors."""
    coordinator: IthoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    serial_number = entry.data[CONF_SERIAL_NUMBER]

    profile = coordinator.profile

    sensors: list[SensorEntity] = [
        # Device Status Sensors
        IthoBoilerContentSensor(coordinator, serial_number),
        # Note: Device Mode is now a SELECT entity for better UX
        IthoDeviceStateSensor(coordinator, serial_number),
        IthoDevicePowerSensor(coordinator, serial_number),
        IthoSoftwareVersionSensor(coordinator, serial_number),
        IthoLegionellaTimerSensor(coordinator, serial_number),

        # Energy Sensors
        IthoEnergyConsumptionSensor(coordinator, serial_number),
        IthoEnergySavingSensor(coordinator, serial_number),

        # Target temperature from GetDeviceMode (available on all types,
        # read-only on Smartboilers)
        IthoTargetTemperatureSensor(coordinator, serial_number),
    ]

    if profile.supports_temperature:
        sensors.append(IthoDeviceTemperatureSensor(coordinator, serial_number))

    if profile.supports_pv:
        sensors.extend(
            [
                IthoPvPowerNetSensor(coordinator, serial_number),
                IthoPvPowerConsumptionSensor(coordinator, serial_number),
                IthoPvPowerProductionSensor(coordinator, serial_number),
                IthoPvEnabledSensor(coordinator, serial_number),
                IthoPvStartLimitSensor(coordinator, serial_number),
                IthoPvStopLimitSensor(coordinator, serial_number),
            ]
        )

    async_add_entities(sensors)


class IthoSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for Itho sensors."""

    def __init__(
        self,
        coordinator: IthoDataUpdateCoordinator,
        serial_number: str,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._serial_number = serial_number
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{serial_number}_{sensor_type}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial_number)},
            "name": f"Itho Boiler {serial_number}",
            "manufacturer": "Itho Daalderop",
            "model": coordinator.profile.model,
        }


class IthoBoilerContentSensor(IthoSensorBase):
    """Sensor for boiler water level."""

    def __init__(self, coordinator: IthoDataUpdateCoordinator, serial_number: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial_number, "boiler_content")
        self._attr_name = "Boiler Content"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_icon = "mdi:water-percent"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "device_status" in self.coordinator.data:
            value = self.coordinator.data["device_status"].get("boilerContent")
            if value is not None:
                return round(value * 100, 1)
        return None


class IthoDeviceModeSensor(IthoSensorBase):
    """Sensor for device mode."""

    def __init__(self, coordinator: IthoDataUpdateCoordinator, serial_number: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial_number, "device_mode")
        self._attr_name = "Device Mode"
        self._attr_icon = "mdi:heat-wave"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "device_mode" in self.coordinator.data:
            return self.coordinator.data["device_mode"].get("deviceMode")
        return None


class IthoDeviceStateSensor(IthoSensorBase):
    """Sensor for device state."""

    def __init__(self, coordinator: IthoDataUpdateCoordinator, serial_number: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial_number, "device_state")
        self._attr_name = "Device State"
        self._attr_icon = "mdi:information-outline"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "device_status" in self.coordinator.data:
            return self.coordinator.data["device_status"].get("deviceState")
        return None


class IthoDevicePowerSensor(IthoSensorBase):
    """Sensor for device power consumption."""

    def __init__(self, coordinator: IthoDataUpdateCoordinator, serial_number: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial_number, "device_power")
        self._attr_name = "Device Power"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "device_status" in self.coordinator.data:
            return self.coordinator.data["device_status"].get("devicePowerMeasured")
        return None


class IthoDeviceTemperatureSensor(IthoSensorBase):
    """Sensor for device temperature."""

    def __init__(self, coordinator: IthoDataUpdateCoordinator, serial_number: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial_number, "device_temperature")
        self._attr_name = "Water Temperature"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "device_status" in self.coordinator.data:
            return self.coordinator.data["device_status"].get("deviceTemperatureMeasured")
        return None


class IthoTargetTemperatureSensor(IthoSensorBase):
    """Sensor for the boiler's target temperature (from GetDeviceMode)."""

    def __init__(self, coordinator: IthoDataUpdateCoordinator, serial_number: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial_number, "target_temperature")
        self._attr_name = "Target Temperature"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:thermometer-check"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "device_mode" in self.coordinator.data:
            return self.coordinator.data["device_mode"].get("temperature")
        return None


class IthoSoftwareVersionSensor(IthoSensorBase):
    """Sensor for software version."""

    def __init__(self, coordinator: IthoDataUpdateCoordinator, serial_number: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial_number, "software_version")
        self._attr_name = "Software Version"
        self._attr_icon = "mdi:package-variant"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "device_status" in self.coordinator.data:
            return self.coordinator.data["device_status"].get("deviceSoftwareVersion")
        return None


class IthoLegionellaTimerSensor(IthoSensorBase):
    """Sensor for legionella prevention timer."""

    def __init__(self, coordinator: IthoDataUpdateCoordinator, serial_number: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial_number, "legionella_timer")
        self._attr_name = "Legionella Prevention Timer"
        self._attr_native_unit_of_measurement = UnitOfTime.HOURS
        self._attr_icon = "mdi:timer-outline"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "device_status" in self.coordinator.data:
            return self.coordinator.data["device_status"].get("legionellaPreventionTimer")
        return None


class IthoPvPowerNetSensor(IthoSensorBase):
    """Sensor for PV net power."""

    def __init__(self, coordinator: IthoDataUpdateCoordinator, serial_number: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial_number, "pv_power_net")
        self._attr_name = "PV Net Power"
        self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "device_status" in self.coordinator.data:
            return self.coordinator.data["device_status"].get("pvPowerNet")
        return None


class IthoPvEnabledSensor(IthoSensorBase):
    """Sensor for PV enabled status."""

    def __init__(self, coordinator: IthoDataUpdateCoordinator, serial_number: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial_number, "pv_enabled")
        self._attr_name = "PV Enabled"
        self._attr_icon = "mdi:solar-power"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "pv_settings" in self.coordinator.data:
            enabled = self.coordinator.data["pv_settings"].get("pvEnabled")
            return "On" if enabled else "Off"
        return None


class IthoPvStartLimitSensor(IthoSensorBase):
    """Sensor for PV start limit."""

    def __init__(self, coordinator: IthoDataUpdateCoordinator, serial_number: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial_number, "pv_start_limit")
        self._attr_name = "PV Start Limit"
        self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "pv_settings" in self.coordinator.data:
            return self.coordinator.data["pv_settings"].get("pvStartLimit")
        return None


class IthoPvStopLimitSensor(IthoSensorBase):
    """Sensor for PV stop limit."""

    def __init__(self, coordinator: IthoDataUpdateCoordinator, serial_number: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial_number, "pv_stop_limit")
        self._attr_name = "PV Stop Limit"
        self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "pv_settings" in self.coordinator.data:
            return self.coordinator.data["pv_settings"].get("pvStopLimit")
        return None


class IthoEnergyConsumptionSensor(IthoSensorBase):
    """Sensor for energy consumption."""

    def __init__(self, coordinator: IthoDataUpdateCoordinator, serial_number: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial_number, "energy_consumption")
        self._attr_name = "Energy Consumption"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "device_status" in self.coordinator.data:
            return self.coordinator.data["device_status"].get("energyConsumption")
        return None


class IthoEnergySavingSensor(IthoSensorBase):
    """Sensor for energy saving."""

    def __init__(self, coordinator: IthoDataUpdateCoordinator, serial_number: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial_number, "energy_saving")
        self._attr_name = "Energy Saving"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_icon = "mdi:leaf"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "device_status" in self.coordinator.data:
            return self.coordinator.data["device_status"].get("energySaving")
        return None


class IthoPvPowerConsumptionSensor(IthoSensorBase):
    """Sensor for PV power consumption."""

    def __init__(self, coordinator: IthoDataUpdateCoordinator, serial_number: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial_number, "pv_power_consumption")
        self._attr_name = "PV Power Consumption"
        self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:transmission-tower-import"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "device_status" in self.coordinator.data:
            return self.coordinator.data["device_status"].get("pvPowerConsumption")
        return None


class IthoPvPowerProductionSensor(IthoSensorBase):
    """Sensor for PV power production."""

    def __init__(self, coordinator: IthoDataUpdateCoordinator, serial_number: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial_number, "pv_power_production")
        self._attr_name = "PV Power Production"
        self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:solar-power-variant"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "device_status" in self.coordinator.data:
            return self.coordinator.data["device_status"].get("pvPowerProduction")
        return None
