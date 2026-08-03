"""Manual IoTrix controls."""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IoTrixRuntimeData
from .const import D18_FIELD, D18_MAX, D18_MIN
from .drivers import adapter_for
from .entity import IoTrixEntity


class D18Number(IoTrixEntity, NumberEntity):
    """The inverter's native D18 setting; never changed automatically."""

    _attr_name = "D18 Maximum Grid Current"
    _attr_icon = "mdi:current-ac"
    _attr_native_min_value = D18_MIN
    _attr_native_max_value = D18_MAX
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_mode = NumberMode.BOX

    def __init__(self, runtime: IoTrixRuntimeData, device: Any) -> None:
        super().__init__(runtime.hub, device, "d18_maximum_grid_current")

    @property
    def native_value(self) -> float | None:
        return self.hub.numeric(self.device_id, D18_FIELD)

    async def async_set_native_value(self, value: float) -> None:
        await self.hub.async_set_d18(self.device_id, value)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime: IoTrixRuntimeData = entry.runtime_data
    known: set[str] = set()

    @callback
    def add_discovered() -> None:
        entities: list[NumberEntity] = []
        for device in runtime.hub.devices.values():
            adapter = adapter_for(device.driver)
            if adapter is not None and adapter.d18 and device.device_id not in known:
                known.add(device.device_id)
                entities.append(D18Number(runtime, device))
        if entities:
            async_add_entities(entities)

    add_discovered()
    entry.async_on_unload(runtime.hub.add_device_listener(add_discovered))
