"""Pure estimators derived from cumulative IoTrix BMS counters."""

from __future__ import annotations

NOMINAL_BATTERY_VOLTAGE = 51.2


def remaining_capacity_ah(total_capacity_ah: float, state_of_charge: float) -> float:
    """Derive remaining amp-hours from total capacity and BMS state of charge."""
    bounded_soc = min(100.0, max(0.0, state_of_charge))
    return total_capacity_ah * bounded_soc / 100.0


def estimated_charge_capacity_ah(
    cycle_capacity_ah: float,
    remaining_capacity_ah: float,
    baseline_cycle_capacity_ah: float,
    baseline_remaining_capacity_ah: float,
) -> float:
    """Estimate charged amp-hours since a baseline using capacity conservation."""
    estimate = (cycle_capacity_ah - baseline_cycle_capacity_ah) + (
        remaining_capacity_ah - baseline_remaining_capacity_ah
    )
    return max(0.0, estimate)


def estimated_charge_energy_kwh(
    cycle_capacity_ah: float,
    remaining_capacity_ah: float,
    baseline_cycle_capacity_ah: float,
    baseline_remaining_capacity_ah: float,
) -> float:
    """Convert estimated charged capacity to energy at nominal pack voltage."""
    return (
        estimated_charge_capacity_ah(
            cycle_capacity_ah,
            remaining_capacity_ah,
            baseline_cycle_capacity_ah,
            baseline_remaining_capacity_ah,
        )
        * NOMINAL_BATTERY_VOLTAGE
        / 1000.0
    )
