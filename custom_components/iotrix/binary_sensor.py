"""BMS status sensors for dynamically discovered IoTrix devices."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IoTrixRuntimeData
from .drivers import adapter_for
from .entity import IoTrixEntity

BMS_PROBLEM_FIELDS = {
    "temperature_1_high": "sts_temp1_over",
    "temperature_2_low": "sts_temp2_low",
    "cell_overvoltage": "sts_cell_voltage_over",
    "cell_undervoltage": "sts_cell_voltage_low",
    "protection_309a": "sts_309_a_protection",
    "protection_309b": "sts_309_b_protection",
    "low_capacity": "sts_low_capacity",
    "mos_overtemperature": "sts_mos_temp_over",
    "charge_overvoltage": "sts_charging_voltage_over",
    "discharge_undervoltage": "sts_discharging_voltage_low",
    "temperature_2_high": "sts_temp2_over",
    "charge_overcurrent": "sts_charging_current_over",
    "discharge_overcurrent": "sts_discharging_current_over",
    "cell_difference_high": "sts_cell_voltage_diff_over",
}

BMS_ACTIVITY_FIELDS = {
    "mos_charging": "sts_mos_charging",
    "mos_discharging": "sts_mos_discharging",
    "balancing": "sts_mos_balance",
}


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "on", "yes", "active", "enabled"}
    return bool(value)


class BmsStateBinarySensor(IoTrixEntity, BinarySensorEntity):
    """Low-churn BMS protection/activity flag."""

    def __init__(self, hub: Any, device: Any, key: str, field: str, problem: bool) -> None:
        super().__init__(hub, device, key)
        self.field = field
        self._attr_name = key.replace("_", " ").title()
        self._attr_device_class = (
            BinarySensorDeviceClass.PROBLEM if problem else BinarySensorDeviceClass.RUNNING
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._last_value: bool | None = None

    @property
    def is_on(self) -> bool:
        return _truthy(self.hub.value(self.device_id, self.field))

    @callback
    def _handle_update(self) -> None:
        value = self.is_on
        if value != self._last_value:
            self._last_value = value
            self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime: IoTrixRuntimeData = entry.runtime_data
    known: set[tuple[str, str]] = set()

    @callback
    def add_discovered() -> None:
        entities: list[BinarySensorEntity] = []
        for device in runtime.hub.devices.values():
            adapter = adapter_for(device.driver)
            if adapter is None or adapter.role != "bms":
                continue
            for problem, fields in ((True, BMS_PROBLEM_FIELDS), (False, BMS_ACTIVITY_FIELDS)):
                for key, field in fields.items():
                    marker = (device.device_id, key)
                    if marker not in known:
                        known.add(marker)
                        entities.append(
                            BmsStateBinarySensor(runtime.hub, device, key, field, problem)
                        )
        if entities:
            async_add_entities(entities)

    add_discovered()
    entry.async_on_unload(runtime.hub.add_device_listener(add_discovered))
