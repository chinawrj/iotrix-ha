"""IoTrix driver capability registry.

Devices are always discovered from the cloud. This module only describes the
fields supported by known driver protocols; it never contains account device
IDs or account-specific device counts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class DriverAdapter:
    """Capabilities of one IoTrix cloud driver."""

    role: str
    fields: tuple[str, ...]
    d18: bool = False


HYBRID_FIELDS: Final = (
    "_timestamp",
    "pv1_voltage",
    "pv2_voltage",
    "pv1_current",
    "pv2_current",
    "pv1_power",
    "pv2_power",
    "power",
    "mppt1_temp",
    "mppt2_temp",
    "dc_temp",
    "inverter_temp",
    "charging_current",
    "battery_voltage",
    "power_daily",
    "power_total",
    "soc",
    "grid_voltage",
    "inverter_grid_load_current",
    "inverter_out_voltage",
    "inverter_off_grid_load_current",
    "inverter_current",
    "grid_frequency",
    "power_factor",
    "grid_power",
    "load_power",
    "inverter_real_power",
    "solar_status",
    "battery_status",
    "grid_status",
    "load_status",
    "work_mode",
    "charging_priority",
    "inverter_status",
    "mppt_status",
    "sys_err",
    "warn_status",
    "protection_status",
    "err_status",
    "charging_limit_current",
    "battery_sum_current",
    "battery_sum_voltage",
    "ota_lock",
    "grid_power_ct_a",
    "used_grid_today",
    "bat_chg_energy_today",
    "bat_dischg_energy_today",
    "used_energy_today",
    "line_sell_energy_today",
    "load_consum_line_today",
    "version",
    "max_on_grid_current",
)

BMS_FIELDS: Final = (
    "_timestamp",
    "mos_temp",
    "temp1",
    "temp2",
    "sum_voltage",
    "sum_current",
    "sum_power",
    "soc",
    "cycle_count",
    "cycle_capacity",
    "cycle_daily",
    "rated_capacity",
    "real_capacity",
    "battery_count",
    "max_diff_voltage",
    "sts_temp1_over",
    "sts_temp2_low",
    "sts_cell_voltage_over",
    "sts_cell_voltage_low",
    "sts_309_a_protection",
    "sts_309_b_protection",
    "sts_low_capacity",
    "sts_mos_temp_over",
    "sts_charging_voltage_over",
    "sts_discharging_voltage_low",
    "sts_temp2_over",
    "sts_charging_current_over",
    "sts_discharging_current_over",
    "sts_cell_voltage_diff_over",
    "sts_mos_charging",
    "sts_mos_discharging",
    "sts_mos_balance",
    "cell_voltage_over_protection",
    "cell_voltage_low_protection",
    "balance_current",
    "sts_batt",
    "dev_addr",
)

DRIVERS: Final[dict[str, DriverAdapter]] = {
    "mppt_makeskyblue_v1": DriverAdapter("hybrid", HYBRID_FIELDS, d18=True),
    "bms_jikong_v2": DriverAdapter("bms", BMS_FIELDS),
}


def adapter_for(driver: str) -> DriverAdapter | None:
    """Return protocol capabilities for a cloud-returned driver."""
    return DRIVERS.get(driver)
