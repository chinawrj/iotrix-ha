"""D18 and guard configuration numbers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IoTrixRuntimeData
from .const import D18_FIELD, D18_MAX, D18_MIN
from .drivers import adapter_for
from .entity import GuardEntity, IoTrixEntity


class D18Number(IoTrixEntity, NumberEntity):
    _attr_name = "D18 Maximum Grid Current"
    _attr_icon = "mdi:current-ac"
    _attr_native_min_value = D18_MIN
    _attr_native_max_value = D18_MAX
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_mode = NumberMode.BOX

    def __init__(self, runtime: IoTrixRuntimeData, device: Any) -> None:
        super().__init__(runtime.hub, device, "d18_maximum_grid_current")
        self.guard = runtime.guard

    @property
    def native_value(self) -> float | None:
        return self.hub.numeric(self.device_id, D18_FIELD)

    async def async_set_native_value(self, value: float) -> None:
        confirmed = await self.hub.async_set_d18(self.device_id, value)
        await self.guard.async_manual_override(confirmed)


@dataclass(frozen=True, slots=True)
class GuardNumberSpec:
    key: str
    name: str
    minimum: float
    maximum: float
    step: float
    unit: str | None = None
    icon: str | None = None


GUARD_NUMBERS = (
    GuardNumberSpec(
        "trigger_current",
        "Trigger Discharge Current",
        10,
        200,
        1,
        UnitOfElectricCurrent.AMPERE,
        "mdi:current-dc",
    ),
    GuardNumberSpec(
        "target_current",
        "Target Discharge Current",
        5,
        190,
        1,
        UnitOfElectricCurrent.AMPERE,
        "mdi:target",
    ),
    GuardNumberSpec(
        "release_current",
        "Release Discharge Current",
        0,
        180,
        1,
        UnitOfElectricCurrent.AMPERE,
        "mdi:current-dc",
    ),
    GuardNumberSpec(
        "restore_target",
        "Restore D18 Target",
        0,
        D18_MAX,
        0.1,
        UnitOfElectricCurrent.AMPERE,
        "mdi:restore",
    ),
    GuardNumberSpec(
        "minimum_d18",
        "Minimum D18",
        0,
        D18_MAX,
        0.1,
        UnitOfElectricCurrent.AMPERE,
        "mdi:arrow-collapse-down",
    ),
    GuardNumberSpec(
        "conversion_efficiency",
        "Conversion Efficiency",
        60,
        100,
        1,
        PERCENTAGE,
        "mdi:percent",
    ),
    GuardNumberSpec(
        "pv_headroom",
        "PV Headroom",
        0,
        10,
        0.1,
        UnitOfElectricCurrent.AMPERE,
        "mdi:solar-power",
    ),
    GuardNumberSpec(
        "reduction_margin",
        "Reduction Margin",
        0,
        10,
        0.1,
        UnitOfElectricCurrent.AMPERE,
        "mdi:shield-plus",
    ),
    GuardNumberSpec(
        "minimum_controllable_power",
        "Minimum Controllable Power",
        0,
        5000,
        50,
        UnitOfPower.WATT,
        "mdi:transmission-tower-off",
    ),
    GuardNumberSpec(
        "recovery_headroom",
        "Recovery Demand Headroom",
        0,
        10,
        0.1,
        UnitOfElectricCurrent.AMPERE,
        "mdi:chart-bell-curve",
    ),
    GuardNumberSpec("trip_delay", "Trip Delay", 5, 600, 5, UnitOfTime.SECONDS, "mdi:timer-alert"),
    GuardNumberSpec(
        "minimum_write_interval",
        "Minimum D18 Write Interval",
        60,
        7200,
        60,
        UnitOfTime.SECONDS,
        "mdi:timer-lock",
    ),
    GuardNumberSpec(
        "recovery_observation",
        "Recovery Observation",
        60,
        7200,
        60,
        UnitOfTime.SECONDS,
        "mdi:timer-sand",
    ),
    GuardNumberSpec(
        "restore_verification",
        "Restore Verification",
        10,
        3600,
        10,
        UnitOfTime.SECONDS,
        "mdi:shield-check",
    ),
    GuardNumberSpec(
        "recovery_lock",
        "Recovery Lock After Rollback",
        60,
        14400,
        60,
        UnitOfTime.SECONDS,
        "mdi:lock-clock",
    ),
)


class GuardNumber(GuardEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(self, entry_id: str, guard: Any, spec: GuardNumberSpec) -> None:
        super().__init__(entry_id, guard, spec.key)
        self.spec = spec
        self._attr_name = spec.name
        self._attr_native_min_value = spec.minimum
        self._attr_native_max_value = spec.maximum
        self._attr_native_step = spec.step
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_icon = spec.icon

    @property
    def native_value(self) -> float:
        return float(self.guard.params[self.spec.key])

    async def async_set_native_value(self, value: float) -> None:
        await self.guard.async_set_param(self.spec.key, value)


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
    async_add_entities([GuardNumber(entry.entry_id, runtime.guard, spec) for spec in GUARD_NUMBERS])
