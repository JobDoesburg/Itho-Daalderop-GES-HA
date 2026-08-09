"""Diagnostics support for Itho Daalderop.

Download via Settings -> Devices & Services -> Itho Daalderop -> Download
diagnostics. Contains the raw API responses, which is exactly what is needed
to add support for new boiler types (e.g. GRB Smartboilers).
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import IthoDataUpdateCoordinator
from .const import CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN, DOMAIN

TO_REDACT = {CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: IthoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "profile": asdict(coordinator.profile),
        "coordinator_data": coordinator.data,
        "last_update_success": coordinator.last_update_success,
    }
