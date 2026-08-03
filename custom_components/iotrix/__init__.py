"""IoTrix Cloud integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import IoTrixApi, IoTrixApiError, IoTrixAuthError
from .const import (
    CONF_DEVICE_REFRESH_INTERVAL,
    CONF_HOST,
    CONF_TOKEN,
    DEFAULT_DEVICE_REFRESH_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .hub import IoTrixHub


@dataclass(slots=True)
class IoTrixRuntimeData:
    """Runtime objects owned by one config entry."""

    hub: IoTrixHub
    remove_device_listener: Any = None


def _device_firmware(device: Any) -> str | None:
    for key in ("fw_version", "firmware", "version", "fw_date"):
        value = device.userdata.get(key) or device.metadata.get(key)
        if value:
            return str(value)
    return None


def _register_devices(hass: HomeAssistant, entry: ConfigEntry, hub: IoTrixHub) -> None:
    """Mirror every cloud-returned IoTrix device into HA's device registry."""
    registry = dr.async_get(hass)
    for device in hub.devices.values():
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, device.device_id)},
            manufacturer="IoTrix",
            name=device.name,
            model=device.driver,
            sw_version=_device_firmware(device),
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one IoTrix cloud account."""
    api = IoTrixApi(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_TOKEN],
    )
    refresh_interval = int(
        entry.options.get(
            CONF_DEVICE_REFRESH_INTERVAL,
            entry.data.get(CONF_DEVICE_REFRESH_INTERVAL, DEFAULT_DEVICE_REFRESH_INTERVAL),
        )
    )
    hub = IoTrixHub(api, refresh_interval)
    try:
        await hub.async_setup()
    except IoTrixAuthError as err:
        raise ConfigEntryAuthFailed from err
    except IoTrixApiError as err:
        raise ConfigEntryNotReady from err
    runtime = IoTrixRuntimeData(hub=hub)
    entry.runtime_data = runtime

    _register_devices(hass, entry, hub)
    runtime.remove_device_listener = hub.add_device_listener(
        lambda: _register_devices(hass, entry, hub)
    )
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload without issuing cloud commands."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    runtime: IoTrixRuntimeData = entry.runtime_data
    if runtime.remove_device_listener is not None:
        runtime.remove_device_listener()
    await runtime.hub.async_shutdown()
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow stale cloud devices to be removed after discovery no longer returns them."""
    runtime: IoTrixRuntimeData = entry.runtime_data
    current_ids = {device.device_id for device in runtime.hub.devices.values()}
    return not any(
        identifier[1] in current_ids
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
    )
