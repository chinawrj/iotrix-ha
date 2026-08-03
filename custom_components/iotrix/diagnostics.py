"""Privacy-safe diagnostics for IoTrix Cloud."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import IoTrixRuntimeData


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return useful state without token, device IDs, or account identifiers."""
    runtime: IoTrixRuntimeData = entry.runtime_data
    return {
        "connected": runtime.hub.connected,
        "device_count": len(runtime.hub.devices),
        "devices": [
            {"name": device.name, "driver": device.driver, "type": device.device_type}
            for device in runtime.hub.devices.values()
        ],
    }
