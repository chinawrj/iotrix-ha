"""Sensors for dynamically discovered IoTrix cloud devices."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IoTrixRuntimeData
from .drivers import adapter_for
from .entity import IoTrixEntity
from .hub import numeric_value


@dataclass(frozen=True, kw_only=True)
class IoTrixSensorDescription(SensorEntityDescription):
    role: str
    field: str
    update_seconds: float = 5.0
    multiplier: float = 1.0


HYBRID_SENSORS = (
    IoTrixSensorDescription(
        key="pv_power",
        name="PV Power",
        role="hybrid",
        field="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IoTrixSensorDescription(
        key="battery_voltage",
        name="Battery Voltage",
        role="hybrid",
        field="battery_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IoTrixSensorDescription(
        key="charging_current",
        name="Charging Current",
        role="hybrid",
        field="charging_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IoTrixSensorDescription(
        key="grid_power",
        name="Grid-side Load Power",
        role="hybrid",
        field="grid_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IoTrixSensorDescription(
        key="load_power",
        name="UPS Load Power",
        role="hybrid",
        field="load_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IoTrixSensorDescription(
        key="inverter_temperature",
        name="Inverter Temperature",
        role="hybrid",
        field="inverter_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        update_seconds=30,
    ),
    IoTrixSensorDescription(
        key="grid_voltage",
        name="Grid Voltage",
        role="hybrid",
        field="grid_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IoTrixSensorDescription(
        key="grid_load_current",
        name="On-grid Output Current",
        role="hybrid",
        field="inverter_grid_load_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IoTrixSensorDescription(
        key="pv_energy_today",
        name="PV Energy Today",
        role="hybrid",
        field="power_daily",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        update_seconds=30,
    ),
    IoTrixSensorDescription(
        key="pv_energy_total",
        name="PV Energy Total",
        role="hybrid",
        field="power_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        update_seconds=60,
    ),
    IoTrixSensorDescription(
        key="battery_charge_energy_today",
        name="Battery Charge Energy Today",
        role="hybrid",
        field="bat_chg_energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        update_seconds=30,
    ),
    IoTrixSensorDescription(
        key="battery_discharge_energy_today",
        name="Battery Discharge Energy Today",
        role="hybrid",
        field="bat_dischg_energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        update_seconds=30,
    ),
    IoTrixSensorDescription(
        key="grid_energy_today",
        name="Grid Energy Today",
        role="hybrid",
        field="used_grid_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        update_seconds=30,
    ),
    IoTrixSensorDescription(
        key="load_energy_today",
        name="Load Energy Today",
        role="hybrid",
        field="used_energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        update_seconds=30,
    ),
    IoTrixSensorDescription(
        key="grid_export_energy_today",
        name="Grid Export Energy Today",
        role="hybrid",
        field="line_sell_energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        update_seconds=30,
    ),
)

BMS_SENSORS = (
    IoTrixSensorDescription(
        key="voltage",
        name="Voltage",
        role="bms",
        field="sum_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IoTrixSensorDescription(
        key="current",
        name="Current",
        role="bms",
        field="sum_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IoTrixSensorDescription(
        key="power",
        name="Power",
        role="bms",
        field="sum_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IoTrixSensorDescription(
        key="state_of_charge",
        name="State of Charge",
        role="bms",
        field="soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IoTrixSensorDescription(
        key="mos_temperature",
        name="MOS Temperature",
        role="bms",
        field="mos_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        update_seconds=30,
    ),
    IoTrixSensorDescription(
        key="maximum_cell_difference",
        name="Maximum Cell Difference",
        role="bms",
        field="max_diff_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        update_seconds=60,
    ),
    IoTrixSensorDescription(
        key="balance_current",
        name="Balance Current",
        role="bms",
        field="balance_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        update_seconds=30,
    ),
    IoTrixSensorDescription(
        key="cycle_capacity",
        name="Cycle Capacity",
        role="bms",
        field="cycle_capacity",
        native_unit_of_measurement="Ah",
        state_class=SensorStateClass.TOTAL_INCREASING,
        update_seconds=60,
    ),
    IoTrixSensorDescription(
        key="day_cycle_capacity",
        name="Day Cycle Capacity",
        role="bms",
        field="cycle_daily",
        native_unit_of_measurement="Ah",
        state_class=SensorStateClass.TOTAL_INCREASING,
        update_seconds=60,
    ),
    IoTrixSensorDescription(
        key="rated_capacity",
        name="Rated Capacity",
        role="bms",
        field="rated_capacity",
        native_unit_of_measurement="Ah",
        state_class=SensorStateClass.MEASUREMENT,
        update_seconds=60,
    ),
    IoTrixSensorDescription(
        key="real_capacity",
        name="Remaining Capacity",
        role="bms",
        field="real_capacity",
        native_unit_of_measurement="Ah",
        state_class=SensorStateClass.MEASUREMENT,
        update_seconds=30,
    ),
    IoTrixSensorDescription(
        key="cycle_count",
        name="Cycle Count",
        role="bms",
        field="cycle_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        update_seconds=60,
    ),
    IoTrixSensorDescription(
        key="estimated_cycle_energy_total",
        name="Estimated Cycle Energy Total",
        role="bms",
        field="cycle_capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        update_seconds=60,
        multiplier=0.0512,
    ),
)


@dataclass(frozen=True, slots=True)
class IoTrixTextDescription:
    key: str
    name: str
    field: str


HYBRID_TEXT_SENSORS = (
    IoTrixTextDescription("work_mode", "Work Mode", "work_mode"),
    IoTrixTextDescription("solar_status", "Solar Status", "solar_status"),
    IoTrixTextDescription("battery_status", "Battery Status", "battery_status"),
    IoTrixTextDescription("grid_status", "Grid Status", "grid_status"),
    IoTrixTextDescription("load_status", "Load Status", "load_status"),
    IoTrixTextDescription("charging_priority", "Charging Priority", "charging_priority"),
    IoTrixTextDescription("inverter_status", "Inverter Status", "inverter_status"),
    IoTrixTextDescription("mppt_status", "MPPT Status", "mppt_status"),
    IoTrixTextDescription("system_error", "System Error", "sys_err"),
    IoTrixTextDescription("warning_status", "Warning Status", "warn_status"),
    IoTrixTextDescription("protection_status", "Protection Status", "protection_status"),
    IoTrixTextDescription("error_status", "Error Status", "err_status"),
    IoTrixTextDescription("firmware_version", "Reported Firmware Version", "version"),
)


class IoTrixSensor(IoTrixEntity, SensorEntity):
    entity_description: IoTrixSensorDescription

    def __init__(self, hub: Any, device: Any, description: IoTrixSensorDescription) -> None:
        super().__init__(hub, device, description.key)
        self.entity_description = description
        self._last_write = 0.0
        self._timer: Any = None

    @property
    def native_value(self) -> float | None:
        value = numeric_value(self.hub.value(self.device_id, self.entity_description.field))
        return None if value is None else round(value * self.entity_description.multiplier, 4)

    @callback
    def _handle_update(self) -> None:
        elapsed = time.monotonic() - self._last_write
        delay = self.entity_description.update_seconds - elapsed
        if delay <= 0:
            self._last_write = time.monotonic()
            self.async_write_ha_state()
        elif self._timer is None:
            self._timer = self.hass.loop.call_later(delay, self._delayed_write)

    @callback
    def _delayed_write(self) -> None:
        self._timer = None
        self._last_write = time.monotonic()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        await super().async_will_remove_from_hass()


class IoTrixTextValueSensor(IoTrixEntity, SensorEntity):
    """Low-churn status value exposed only when its raw value changes."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hub: Any, device: Any, description: IoTrixTextDescription) -> None:
        super().__init__(hub, device, description.key)
        self.description = description
        self._attr_name = description.name
        self._last_value: str | None = None

    @property
    def native_value(self) -> str | None:
        value = self.hub.value(self.device_id, self.description.field)
        return None if value is None else str(value)

    @callback
    def _handle_update(self) -> None:
        value = self.native_value
        if value != self._last_value:
            self._last_value = value
            self.async_write_ha_state()


class ZeroChargeEnergySensor(IoTrixEntity, SensorEntity):
    _attr_name = "Charge Energy Total Placeholder"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:battery-arrow-up-outline"

    def __init__(self, hub: Any, device: Any) -> None:
        super().__init__(hub, device, "charge_energy_zero_placeholder")

    @property
    def native_value(self) -> float:
        return 0.0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime: IoTrixRuntimeData = entry.runtime_data
    known: set[tuple[str, str]] = set()

    @callback
    def add_discovered() -> None:
        entities: list[SensorEntity] = []
        for device in runtime.hub.devices.values():
            adapter = adapter_for(device.driver)
            if adapter is None:
                continue
            descriptions = (
                HYBRID_SENSORS
                if adapter.role == "hybrid"
                else BMS_SENSORS
                if adapter.role == "bms"
                else ()
            )
            for description in descriptions:
                marker = (device.device_id, description.key)
                if marker not in known:
                    known.add(marker)
                    entities.append(IoTrixSensor(runtime.hub, device, description))
            if adapter.role == "hybrid":
                for description in HYBRID_TEXT_SENSORS:
                    marker = (device.device_id, description.key)
                    if marker not in known:
                        known.add(marker)
                        entities.append(IoTrixTextValueSensor(runtime.hub, device, description))
            if (
                adapter.role == "bms"
                and (marker := (device.device_id, "charge_energy_zero_placeholder")) not in known
            ):
                known.add(marker)
                entities.append(ZeroChargeEnergySensor(runtime.hub, device))
        if entities:
            async_add_entities(entities)

    add_discovered()
    entry.async_on_unload(runtime.hub.add_device_listener(add_discovered))
