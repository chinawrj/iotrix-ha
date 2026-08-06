"""Entity helpers for dynamically discovered IoTrix devices."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .hub import IoTrixHub
from .models import IoTrixDevice


class IoTrixEntity(Entity):
    """Base class bound to one cloud-returned physical device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub: IoTrixHub, device: IoTrixDevice, key: str) -> None:
        self.hub = hub
        self.device_id = device.device_id
        self._attr_unique_id = f"{device.device_id}_{key}"
        self._remove_listener: Callable[[], None] | None = None

    @property
    def available(self) -> bool:
        return self.hub.connected and self.device_id in self.hub.devices

    @property
    def device_info(self) -> DeviceInfo:
        device = self.hub.devices.get(self.device_id)
        if device is None:
            return DeviceInfo(identifiers={(DOMAIN, self.device_id)})
        firmware = next(
            (
                str(value)
                for key in ("fw_version", "firmware", "version", "fw_date")
                if (value := device.userdata.get(key) or device.metadata.get(key))
            ),
            None,
        )
        return DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            manufacturer="IoTrix",
            name=device.name,
            model=device.driver,
            sw_version=firmware,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._remove_listener = self.hub.add_listener(self.device_id, self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener is not None:
            self._remove_listener()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
