"""Config flow for Itho Daalderop integration."""
from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any
from urllib.parse import urlencode

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import IthoApiClient, IthoApiAuthenticationError, IthoApiConnectionError, IthoApiTimeoutError
from .const import (
    APPLICATION_ID,
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_SERIAL_NUMBER,
    DOMAIN,
    REDIRECT_URI,
    SSO_INITIATE_URL,
)

_LOGGER = logging.getLogger(__name__)


class IthoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Itho Daalderop."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.serial_number: str | None = None
        self.azure_url: str | None = None
        self.access_token: str | None = None
        self.refresh_token: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - ask for serial number."""
        errors: dict[str, str] = {}

        if user_input is not None:
            serial_number = user_input[CONF_SERIAL_NUMBER].strip().upper()
            
            # Validate serial number
            if len(serial_number) < 5:
                errors[CONF_SERIAL_NUMBER] = "invalid_serial"
            else:
                self.serial_number = serial_number
                return await self.async_step_auth()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERIAL_NUMBER): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "serial_help": (
                    "Serienummer van je boiler "
                    "(bijv. VPR242600095 of GRB240230157)"
                )
            },
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Get Azure B2C login URL and open browser."""
        # Build SSO URL
        params = urlencode({
            "redirect": REDIRECT_URI,
            "application_id": APPLICATION_ID,
        })
        sso_url = f"{SSO_INITIATE_URL}?{params}"

        # Get Azure B2C URL
        session = async_get_clientsession(self.hass)
        
        try:
            _LOGGER.debug("Requesting SSO URL: %s", sso_url)
            async with session.get(sso_url, timeout=10) as response:
                _LOGGER.debug("SSO response status: %s", response.status)
                _LOGGER.debug("SSO response headers: %s", dict(response.headers))
                
                if response.status == 200:
                    # Force JSON parsing regardless of Content-Type header
                    # Server returns text/html but body is actually JSON
                    data = await response.json(content_type=None)
                    _LOGGER.debug("SSO response data keys: %s", list(data.keys()))
                    self.azure_url = data.get("sso")
                    
                    if not self.azure_url:
                        _LOGGER.error("No 'sso' key in response data: %s", data)
                        return self.async_abort(reason="no_azure_url")
                    
                    _LOGGER.debug("Azure B2C URL received: %s", self.azure_url[:50])
                    # Open browser and wait for callback
                    return await self.async_step_auth_callback()
                else:
                    # Non-200 status
                    text = await response.text()
                    _LOGGER.error(
                        "SSO server returned status %s. Response: %s",
                        response.status,
                        text[:500]
                    )
                    return self.async_abort(reason="cannot_connect")
                    
        except Exception as err:
            _LOGGER.error("Error getting Azure URL: %s (type: %s)", err, type(err).__name__)
            import traceback
            _LOGGER.error("Traceback: %s", traceback.format_exc())
            return self.async_abort(reason="cannot_connect")

    async def async_step_auth_callback(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the callback from Azure B2C login."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token_input = user_input.get("token", "").strip()
            
            _LOGGER.info("=== TOKEN INPUT DEBUG ===")
            _LOGGER.info("Token input length: %d", len(token_input))
            _LOGGER.info("Token starts with: %s", token_input[:30] if len(token_input) > 30 else token_input)
            _LOGGER.info("Token ends with: %s", token_input[-30:] if len(token_input) > 30 else token_input)
            _LOGGER.info("Token parts count: %d", len(token_input.split(".")))
            
            # Extract token from URL or use direct token
            token = self._extract_token_from_url(token_input)
            
            if not token:
                _LOGGER.error("Failed to extract token from input")
                _LOGGER.error("Input was: %s...", token_input[:100])
                errors["token"] = "invalid_token"
            else:
                # First validate it's a proper JWT
                token_data = self._decode_token(token)
                
                if not token_data:
                    _LOGGER.error("Token could not be decoded - invalid JWT format")
                    errors["token"] = "invalid_token"
                else:
                    _LOGGER.info("Token decoded successfully")
                    self.access_token = token
                    
                    # Extract refresh token from JWT payload
                    if token_data.get("refresh_token"):
                        self.refresh_token = token_data["refresh_token"]
                        _LOGGER.debug("Refresh token found in JWT")
                    else:
                        _LOGGER.warning("No refresh token found in JWT")
                    
                    # Log token expiry
                    expires_at = token_data.get("expires_at")
                    if expires_at:
                        _LOGGER.info("Token expires at: %s", expires_at)
                    
                    # Validate token with actual API call
                    _LOGGER.debug("Validating token with API call...")
                    success, error_key = await self._async_validate_token()
                    
                    if success:
                        _LOGGER.info("Token validation successful! Creating config entry")
                        # Create config entry
                        return self.async_create_entry(
                            title=f"Itho Boiler {self.serial_number}",
                            data={
                                CONF_SERIAL_NUMBER: self.serial_number,
                                CONF_ACCESS_TOKEN: self.access_token,
                                CONF_REFRESH_TOKEN: self.refresh_token,
                            },
                        )
                    else:
                        # Use specific error message from validation
                        _LOGGER.error("Token validation failed: %s", error_key)
                        errors["token"] = error_key or "invalid_token"

        # Show form with browser link
        return self.async_show_form(
            step_id="auth_callback",
            data_schema=vol.Schema(
                {
                    vol.Required("token"): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "login_url": self.azure_url or "https://itho-tussenlaag.bettywebblocks.com/sso/initiate",
            },
        )

    def _extract_token_from_url(self, token_input: str) -> str | None:
        """Extract JWT token from input.
        
        Supports:
        - Direct token paste: eyJ... (preferred)
        - Full callback URL: climateconnect://login?token=xxx
        """
        # Clean input
        token_input = token_input.strip()
        
        # Primary method: direct JWT token (starts with eyJ)
        if token_input.startswith("eyJ"):
            # Basic JWT validation - should have 3 parts separated by dots
            parts = token_input.split(".")
            if len(parts) == 3:
                _LOGGER.debug("Direct JWT token detected (length: %d)", len(token_input))
                return token_input
            else:
                _LOGGER.warning("Invalid JWT format - expected 3 parts, got %d", len(parts))
                return None
        
        # Fallback: try to extract from callback URL
        pattern = r"climateconnect://login/?[?]token=([A-Za-z0-9_\-\.]+)"
        match = re.search(pattern, token_input)
        
        if match:
            token = match.group(1)
            _LOGGER.debug("Token extracted from callback URL (length: %d)", len(token))
            return token
        
        _LOGGER.error("Could not extract token from input (must start with eyJ or be a callback URL): %s", token_input[:50])
        return None

    def _decode_token(self, token: str) -> dict[str, Any] | None:
        """Decode JWT token to extract refresh token."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            
            # Decode payload
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += "=" * padding
            
            decoded = base64.urlsafe_b64decode(payload)
            data = json.loads(decoded)
            
            return {
                "refresh_token": data.get("session", {}).get("refresh_token"),
                "expires_at": data.get("session", {}).get("expires_at"),
                "user": data.get("user", {}),
            }
            
        except Exception as err:
            _LOGGER.error("Error decoding token: %s", err)
            return None

    async def _async_validate_token(self) -> tuple[bool, str | None]:
        """Validate token by making a test API call.
        
        Returns:
            (success: bool, error_key: str | None)
        """
        if not self.access_token or not self.serial_number:
            _LOGGER.error("Missing access_token or serial_number")
            return False, "invalid_token"
        
        try:
            api_client = IthoApiClient(
                self.hass, self.serial_number, self.access_token
            )
            
            # Try to get device status
            _LOGGER.info("Testing API access with serial: %s", self.serial_number)
            _LOGGER.debug("Token length: %d characters", len(self.access_token))
            
            result = await api_client.async_get_device_status()
            _LOGGER.info("Token validation successful! Device status retrieved.")
            _LOGGER.debug("Device status keys: %s", list(result.keys()) if result else "None")
            return True, None
            
        except IthoApiAuthenticationError as err:
            _LOGGER.error("Authentication failed: %s", err)
            return False, "serial_not_linked"
            
        except IthoApiTimeoutError as err:
            _LOGGER.error("API timeout: %s", err)
            return False, "api_timeout"
            
        except IthoApiConnectionError as err:
            _LOGGER.error("Connection error: %s", err)
            return False, "cannot_connect"
            
        except Exception as err:
            _LOGGER.error("Unexpected validation error: %s", err)
            return False, "invalid_token"
