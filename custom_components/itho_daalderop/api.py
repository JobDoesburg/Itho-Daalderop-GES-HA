"""API client for Itho Daalderop."""
import asyncio
import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientTimeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_BASE_URL

_LOGGER = logging.getLogger(__name__)

# Timeout configuration - API is very slow (16+ seconds)
TIMEOUT = ClientTimeout(total=120, connect=60, sock_connect=60, sock_read=60)

# Retry configuration for transient failures
MAX_RETRIES = 2
RETRY_DELAY = 2  # seconds


class IthoApiError(Exception):
    """Base exception for Itho API errors."""


class IthoApiAuthenticationError(IthoApiError):
    """Authentication error."""


class IthoApiConnectionError(IthoApiError):
    """Connection error."""


class IthoApiTimeoutError(IthoApiError):
    """Timeout error."""


class IthoApiClient:
    """API client for Itho Daalderop boiler."""

    def __init__(self, hass: HomeAssistant, serial_number: str, access_token: str) -> None:
        """Initialize the API client."""
        self.hass = hass
        self.serial_number = serial_number
        self.access_token = access_token
        self._session = async_get_clientsession(hass)

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        retries: int = MAX_RETRIES,
    ) -> dict[str, Any]:
        """Make an API request with retry logic and proper error handling."""
        url = f"{API_BASE_URL}/{endpoint}"
        
        for attempt in range(retries + 1):
            try:
                _LOGGER.debug(
                    "API request: %s %s (attempt %d/%d)",
                    method,
                    endpoint,
                    attempt + 1,
                    retries + 1,
                )
                
                async with self._session.request(
                    method,
                    url,
                    headers=self._get_headers(),
                    params=params,
                    json=json_data,
                    timeout=TIMEOUT,
                ) as response:
                    # Handle authentication errors
                    if response.status == 401:
                        raise IthoApiAuthenticationError(
                            "Authentication failed. Token may be expired."
                        )

                    # Include the response body in errors: the API explains
                    # why a call failed (e.g. unsupported mode for this device)
                    if response.status >= 400:
                        body = (await response.text())[:500]
                        _LOGGER.error(
                            "API error %s on %s: %s", response.status, endpoint, body
                        )

                    # Raise for other HTTP errors
                    response.raise_for_status()
                    
                    # Parse and validate response
                    data = await response.json()
                    
                    # Validate response structure
                    if not isinstance(data, dict):
                        raise IthoApiError(f"Invalid response format: expected dict, got {type(data)}")
                    
                    # Return result or empty dict if no result key
                    return data.get("result", {})
                    
            except asyncio.TimeoutError as err:
                # Don't retry on timeout - API is just slow
                _LOGGER.error("API timeout for %s (API takes ~16s per call)", endpoint)
                raise IthoApiTimeoutError(f"Timeout calling {endpoint}") from err
                
            except ClientResponseError as err:
                if err.status == 401:
                    raise IthoApiAuthenticationError(
                        "Authentication failed. Token may be expired."
                    ) from err
                    
                # Don't retry on 4xx errors (client errors)
                if 400 <= err.status < 500:
                    _LOGGER.error("Client error %s: %s", err.status, err.message)
                    raise IthoApiError(f"API error {err.status}: {err.message}") from err
                
                # Retry on 5xx errors (server errors)
                if attempt < retries:
                    _LOGGER.warning(
                        "Server error %s, retrying in %ds... (attempt %d/%d)",
                        err.status,
                        RETRY_DELAY,
                        attempt + 1,
                        retries + 1,
                    )
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                    
                raise IthoApiError(f"Server error {err.status}: {err.message}") from err
                
            except ClientError as err:
                # Retry on network errors
                if attempt < retries:
                    _LOGGER.warning(
                        "Network error: %s, retrying in %ds... (attempt %d/%d)",
                        err,
                        RETRY_DELAY,
                        attempt + 1,
                        retries + 1,
                    )
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                    
                raise IthoApiConnectionError(f"Connection failed: {err}") from err
                
            except Exception as err:
                _LOGGER.error("Unexpected error calling %s: %s", endpoint, err)
                raise IthoApiError(f"Unexpected error: {err}") from err
        
        # Should never reach here, but just in case
        raise IthoApiError(f"Failed to call {endpoint} after {retries + 1} attempts")

    async def async_get_device_status(self) -> dict[str, Any]:
        """Get device status from API."""
        return await self._make_request(
            "GET",
            "GetDeviceStatus",
            params={"serialNumber": self.serial_number},
        )

    async def async_get_device_mode(self) -> dict[str, Any]:
        """Get device mode from API."""
        return await self._make_request(
            "GET",
            "GetDeviceMode",
            params={"serialNumber": self.serial_number},
        )

    async def async_get_pv_settings(self) -> dict[str, Any]:
        """Get PV settings from API."""
        return await self._make_request(
            "GET",
            "GetDevicePVSettings",
            params={"serialNumber": self.serial_number},
        )

    async def async_get_energy_consumption(self) -> dict[str, Any]:
        """Get energy consumption from API."""
        return await self._make_request(
            "GET",
            "GetEnergyConsumption",
            params={"serialNumber": self.serial_number},
        )

    async def async_set_device_mode(self, mode: str, schedule: str | None = None) -> bool:
        """Set device mode."""
        payload = {
            "serialNumber": self.serial_number,
            "deviceMode": mode,
        }
        
        if schedule:
            payload["deviceSchedule"] = schedule

        try:
            await self._make_request(
                "POST",
                "UpdateDeviceMode",
                json_data=payload,
            )
            return True
        except IthoApiError as err:
            _LOGGER.error("Failed to set device mode: %s", err)
            return False

    async def async_boost_boiler(self) -> bool:
        """Activate boiler boost."""
        payload = {
            "serialNumber": self.serial_number,
        }

        try:
            await self._make_request(
                "POST",
                "BoostBoiler",
                json_data=payload,
            )
            return True
        except IthoApiError as err:
            _LOGGER.error("Failed to boost boiler: %s", err)
            return False

    async def async_set_temperature(self, temperature: float) -> bool:
        """Set target temperature."""
        payload = {
            "serialNumber": self.serial_number,
            "temperature": temperature,
        }

        try:
            await self._make_request(
                "POST",
                "UpdateDeviceTemperature",
                json_data=payload,
            )
            return True
        except IthoApiError as err:
            _LOGGER.error("Failed to set temperature: %s", err)
            return False

    async def async_set_pv_settings(
        self,
        pv_enabled: bool | None = None,
        pv_start_limit: float | None = None,
        pv_stop_limit: float | None = None,
        pv_setpoint: float | None = None,
    ) -> bool:
        """Update PV settings.
        
        Args:
            pv_enabled: Enable/disable PV function
            pv_start_limit: Start heating when PV surplus exceeds this (kW)
            pv_stop_limit: Stop heating when PV surplus drops below this (kW)
            pv_setpoint: Target temperature for PV mode (°C)
        """
        # Build payload with only provided values
        payload = {
            "serialNumber": self.serial_number,
        }
        
        if pv_enabled is not None:
            payload["pvEnabled"] = pv_enabled
        if pv_start_limit is not None:
            payload["pvStartLimit"] = pv_start_limit
        if pv_stop_limit is not None:
            payload["pvStopLimit"] = pv_stop_limit
        if pv_setpoint is not None:
            payload["pvSetpoint"] = pv_setpoint

        try:
            await self._make_request(
                "POST",
                "UpdateDevicePVSettings",
                json_data=payload,
            )
            return True
        except IthoApiError as err:
            _LOGGER.error("Failed to update PV settings: %s", err)
            return False

