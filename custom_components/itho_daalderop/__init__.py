"""The Itho Daalderop integration."""
from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import IthoApiClient
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_SERIAL_NUMBER,
    DOMAIN,
    MODE_SETTLE_SECONDS,
    UPDATE_INTERVAL,
    DeviceProfile,
    get_device_profile,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Service schemas
SERVICE_BOOST_BOILER = "boost_boiler"
SERVICE_SET_SCHEDULE = "set_schedule"

BOOST_BOILER_SCHEMA = vol.Schema(
    {
        vol.Optional("activate", default=True): cv.boolean,
    }
)

SET_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("schedule"): dict,  # Schedule object with day:hour:temp mappings
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Itho Daalderop from a config entry."""
    serial_number = entry.data[CONF_SERIAL_NUMBER]
    access_token = entry.data[CONF_ACCESS_TOKEN]

    # Create API client
    api_client = IthoApiClient(hass, serial_number, access_token)

    # Create update coordinator with the capability profile for this boiler type
    profile = get_device_profile(serial_number)
    _LOGGER.info(
        "Setting up %s (%s) with profile: %s", serial_number, profile.model, profile
    )
    coordinator = IthoDataUpdateCoordinator(hass, api_client, profile)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    async def handle_boost_boiler(call: ServiceCall) -> None:
        """Handle boost boiler service call."""
        activate = call.data.get("activate", True)
        _LOGGER.info("Boost boiler service called: activate=%s", activate)
        
        # Get coordinator from first entry (assumes single device)
        coordinators = list(hass.data[DOMAIN].values())
        if coordinators:
            coordinator = coordinators[0]
            await coordinator.api_client.async_boost_boiler()
            await coordinator.async_request_refresh()
    
    async def handle_set_schedule(call: ServiceCall) -> None:
        """Handle set schedule service call."""
        schedule = call.data.get("schedule")
        _LOGGER.info("Set schedule service called with schedule: %s", schedule)
        
        # Get coordinator from first entry (assumes single device)
        coordinators = list(hass.data[DOMAIN].values())
        if coordinators:
            coordinator = coordinators[0]
            # Set to Schedule mode with the provided schedule
            success = await coordinator.api_client.async_set_device_mode(
                mode="Schedule",
                schedule=schedule
            )
            if success:
                await coordinator.async_refresh_settings()
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_BOOST_BOILER,
        handle_boost_boiler,
        schema=BOOST_BOILER_SCHEMA,
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SCHEDULE,
        handle_set_schedule,
        schema=SET_SCHEDULE_SCHEMA,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        
        # Remove services if this was the last entry
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_BOOST_BOILER)
            hass.services.async_remove(DOMAIN, SERVICE_SET_SCHEDULE)

    return unload_ok


class IthoDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Itho data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: IthoApiClient,
        profile: DeviceProfile,
    ) -> None:
        """Initialize."""
        self.api_client = api_client
        self.profile = profile
        self._update_count = 0  # Track updates for selective polling
        self._force_full_refresh = False  # Force fetch all data on next update
        self._pending_mode: str | None = None  # Mode written but possibly not yet visible
        self._mode_written_at: float = 0.0

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def async_force_refresh(self) -> None:
        """Force a full refresh of all data on next update."""
        self._force_full_refresh = True
        await self.async_request_refresh()

    def apply_mode_optimistically(self, mode: str) -> None:
        """Reflect a mode change in local state without re-reading the API.

        UpdateDeviceMode is eventually consistent: the POST returns 204
        immediately, but GetDeviceMode keeps returning the old mode for up
        to ~30s. Re-reading right after a write reverts the UI to the stale
        value. Instead, update local state; polls within the settle window
        keep trusting this value (see _async_update_data), after which the
        API is authoritative again.
        """
        self._pending_mode = mode
        self._mode_written_at = time.monotonic()
        if self.data:
            self.data.setdefault("device_mode", {})["deviceMode"] = mode
            self.data.setdefault("device_status", {})["deviceMode"] = mode
            self.async_set_updated_data(self.data)
        # Make the next poll refetch settings so the change is confirmed
        self._force_full_refresh = True

    async def async_refresh_settings(self) -> None:
        """Refresh only settings data (mode + PV) without waiting for next poll."""
        try:
            device_mode = await self.api_client.async_get_device_mode()
            pv_settings = (
                await self.api_client.async_get_pv_settings()
                if self.profile.supports_pv
                else {}
            )

            # Update data without triggering full refresh
            if self.data:
                self.data["device_mode"] = device_mode
                self.data["pv_settings"] = pv_settings
                self.async_set_updated_data(self.data)
            
            _LOGGER.debug("Settings data refreshed after user change")
        except Exception as err:
            _LOGGER.warning("Failed to refresh settings: %s", err)

    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            self._update_count += 1
            
            # Always fetch critical real-time data (device status)
            device_status = await self.api_client.async_get_device_status()
            
            # Fetch settings only every 5th update OR when forced
            # Settings (mode, PV) rarely change - only when user changes them
            should_fetch_settings = (
                self._update_count % 5 == 1 
                or not self.data 
                or self._force_full_refresh
            )
            
            if should_fetch_settings:
                _LOGGER.debug(
                    "Fetching settings data (update #%d, forced=%s)",
                    self._update_count,
                    self._force_full_refresh
                )
                device_mode = await self.api_client.async_get_device_mode()
                # PV endpoints are only meaningful for boilers with the PV
                # function (GES); skip the slow API call for other types
                pv_settings = (
                    await self.api_client.async_get_pv_settings()
                    if self.profile.supports_pv
                    else {}
                )
                energy_today = await self._async_fetch_energy_today()
                self._force_full_refresh = False  # Reset flag
            else:
                # Reuse previous settings data
                device_mode = self.data.get("device_mode", {}) if self.data else {}
                pv_settings = self.data.get("pv_settings", {}) if self.data else {}
                energy_today = self.data.get("energy_today", {}) if self.data else {}

            # A recently written mode wins over API reads that may still be
            # stale (a poll can land inside the ~30s propagation window)
            if self._pending_mode is not None:
                if time.monotonic() - self._mode_written_at < MODE_SETTLE_SECONDS:
                    device_status = {**device_status, "deviceMode": self._pending_mode}
                    device_mode = {**device_mode, "deviceMode": self._pending_mode}
                else:
                    self._pending_mode = None

            return {
                "device_status": device_status,
                "device_mode": device_mode,
                "pv_settings": pv_settings,
                "energy_today": energy_today,
            }
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def _async_fetch_energy_today(self) -> dict[str, Any]:
        """Fetch today's energy consumption and costs.

        GetDeviceStatus.energyConsumption is not a daily total (it reports
        a much smaller rolling value); the app's daily figure comes from
        GetEnergyConsumption. Summing the buckets tolerates the API
        returning more than one.
        """
        try:
            start_of_day = dt_util.start_of_local_day()
            start_ms = int(start_of_day.timestamp() * 1000)
            end_ms = int(dt_util.now().timestamp() * 1000)

            result = await self.api_client.async_get_energy_consumption(
                start_ms, end_ms
            )
            # Buckets are UTC days and the response includes the bucket
            # overlapping startDate, i.e. usually yesterday too — keep only
            # buckets whose local date is today
            today = dt_util.now().date()
            data = [
                entry
                for entry in result.get("data", [])
                if dt_util.as_local(
                    dt_util.utc_from_timestamp(entry.get("timeStamp", 0) / 1000)
                ).date()
                == today
            ]
            return {
                "consumption": sum(entry.get("consumption") or 0 for entry in data),
                "costs": sum(entry.get("costs") or 0 for entry in data),
            }
        except Exception as err:
            _LOGGER.warning("Failed to fetch energy consumption: %s", err)
            # Keep previous value rather than blanking the sensor
            return self.data.get("energy_today", {}) if self.data else {}
