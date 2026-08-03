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
        "guard": {
            "enabled": bool(runtime.guard.params["enabled"]),
            "pair_ready": runtime.guard.pair_ready,
            "phase": runtime.guard.phase.value,
            "status": runtime.guard.status,
            "active": runtime.guard.active,
            "owns_limit": runtime.guard.owns_limit,
            "event_sequence": runtime.guard.event_sequence,
            "last_event_type": (
                runtime.guard.last_event.event_type
                if runtime.guard.last_event is not None
                else None
            ),
        },
    }
