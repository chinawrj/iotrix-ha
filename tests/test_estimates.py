from __future__ import annotations

import pytest

from ._load import load

estimates = load("estimates")


def test_remaining_capacity_is_derived_from_soc() -> None:
    assert estimates.remaining_capacity_ah(320.0, 23.0) == pytest.approx(73.6)


@pytest.mark.parametrize(("soc", "expected"), [(-1.0, 0.0), (101.0, 320.0)])
def test_remaining_capacity_bounds_soc(soc: float, expected: float) -> None:
    assert estimates.remaining_capacity_ah(320.0, soc) == expected


def test_charge_estimate_when_remaining_capacity_decreases() -> None:
    assert estimates.estimated_charge_capacity_ah(859.0, 43.0, 849.0, 50.0) == 3.0
    assert estimates.estimated_charge_energy_kwh(859.0, 43.0, 849.0, 50.0) == pytest.approx(0.1536)


def test_charge_estimate_for_pure_discharge() -> None:
    assert estimates.estimated_charge_capacity_ah(859.0, 40.0, 849.0, 50.0) == 0.0


def test_charge_estimate_when_remaining_capacity_increases() -> None:
    assert estimates.estimated_charge_capacity_ah(859.0, 55.0, 849.0, 50.0) == 15.0


def test_charge_estimate_does_not_report_negative_since_baseline() -> None:
    assert estimates.estimated_charge_capacity_ah(854.0, 43.0, 849.0, 50.0) == 0.0
