"""Pure calculations used by the D18 battery guard."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(slots=True)
class D18Reduction:
    """A single conservative D18 reduction decision."""

    discharge_current: float = 0.0
    controllable_power: float = 0.0
    actual_grid_current: float = 0.0
    excess_battery_power: float = 0.0
    requested_ac_power_drop: float = 0.0
    pv_surplus_power: float = 0.0
    pv_floor_current: float = 0.0
    next_d18: float = 0.0
    should_reduce: bool = False
    uncontrollable_path: bool = False
    floor_limited: bool = False


def update_overcurrent_score(
    score_seconds: float,
    bms_current: float,
    trigger_current: float,
    release_current: float,
    elapsed_seconds: float,
    trip_delay_seconds: float,
) -> float:
    """Apply the existing conservative, leaky overcurrent memory."""
    if bms_current <= -trigger_current:
        return min(trip_delay_seconds, score_seconds + elapsed_seconds)
    if bms_current > -release_current:
        return max(0.0, score_seconds - max(0.001, elapsed_seconds / 2.0))
    return score_seconds


def actual_grid_current(
    grid_power: float, grid_voltage: float, measured_grid_current: float | None
) -> float:
    """Use the larger measured/inferred grid-path current."""
    measured = (
        measured_grid_current
        if measured_grid_current is not None
        and math.isfinite(measured_grid_current)
        and measured_grid_current >= 0
        else 0.0
    )
    inferred = (
        max(0.0, -grid_power) / grid_voltage
        if math.isfinite(grid_power) and math.isfinite(grid_voltage) and grid_voltage >= 180.0
        else 0.0
    )
    return max(measured, inferred)


def calculate_reduction(
    *,
    bms_current: float,
    bms_voltage: float,
    pv_power: float,
    ups_power: float,
    grid_power: float,
    grid_voltage: float,
    measured_grid_current: float | None,
    current_d18: float,
    target_bms_current: float,
    conversion_efficiency: float,
    minimum_d18: float,
    pv_headroom_current: float,
    reduction_margin_current: float,
    minimum_controllable_power: float,
) -> D18Reduction:
    """Calculate one D18 write while preserving useful PV headroom."""
    result = D18Reduction()
    safe_voltage = grid_voltage if 180.0 <= grid_voltage <= 270.0 else 230.0
    efficiency = min(1.0, max(0.60, conversion_efficiency))
    result.discharge_current = max(0.0, -bms_current)
    result.controllable_power = max(0.0, -grid_power)
    result.actual_grid_current = actual_grid_current(
        grid_power, safe_voltage, measured_grid_current
    )
    result.uncontrollable_path = (
        result.controllable_power < minimum_controllable_power or result.actual_grid_current < 0.05
    )
    result.excess_battery_power = max(0.0, result.discharge_current - target_bms_current) * max(
        0.0, bms_voltage
    )
    result.requested_ac_power_drop = result.excess_battery_power * efficiency
    result.pv_surplus_power = max(0.0, pv_power - max(0.0, ups_power))
    result.pv_floor_current = result.pv_surplus_power / safe_voltage + max(0.0, pv_headroom_current)

    if (
        result.uncontrollable_path
        or result.excess_battery_power <= 0.0
        or not math.isfinite(current_d18)
    ):
        result.next_d18 = current_d18
        return result

    target_grid_power = max(0.0, result.controllable_power - result.requested_ac_power_drop)
    scaled_current = (
        result.actual_grid_current * target_grid_power / max(1.0, result.controllable_power)
    )
    conservative_current = max(0.0, scaled_current - max(0.0, reduction_margin_current))
    floor_current = max(max(0.0, minimum_d18), result.pv_floor_current)
    rounded_candidate = math.floor(conservative_current * 10.0 + 0.0001) / 10.0
    rounded_floor = math.ceil(floor_current * 10.0 - 0.0001) / 10.0
    result.next_d18 = min(current_d18, max(rounded_candidate, rounded_floor))
    result.floor_limited = rounded_floor > rounded_candidate + 0.05
    result.should_reduce = result.next_d18 < current_d18 - 0.05
    return result


def has_recovery_headroom(
    *,
    grid_power: float,
    grid_voltage: float,
    measured_grid_current: float | None,
    limited_d18: float,
    headroom_current: float,
) -> bool:
    """Return true only when demand is demonstrably below the D18 ceiling."""
    if not math.isfinite(grid_power) or not math.isfinite(limited_d18):
        return False
    if grid_power >= 0.0:
        return True
    actual = actual_grid_current(grid_power, grid_voltage, measured_grid_current)
    return actual <= limited_d18 - max(0.0, headroom_current)
