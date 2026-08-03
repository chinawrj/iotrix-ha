from __future__ import annotations

from ._load import load

guard_math = load("guard_math")


def test_negative_bms_current_trips_with_leaky_memory() -> None:
    score = 0.0
    score = guard_math.update_overcurrent_score(score, -55, 50, 42, 20, 30)
    assert score == 20
    score = guard_math.update_overcurrent_score(score, -40, 50, 42, 10, 30)
    assert score == 15
    score = guard_math.update_overcurrent_score(score, -55, 50, 42, 15, 30)
    assert score == 30


def test_reduction_preserves_pv_floor() -> None:
    result = guard_math.calculate_reduction(
        bms_current=-60,
        bms_voltage=52,
        pv_power=5000,
        ups_power=1000,
        grid_power=-5000,
        grid_voltage=230,
        measured_grid_current=None,
        current_d18=30,
        target_bms_current=45,
        conversion_efficiency=0.9,
        minimum_d18=5,
        pv_headroom_current=0.5,
        reduction_margin_current=0.5,
        minimum_controllable_power=200,
    )
    assert result.should_reduce
    assert result.next_d18 >= 4000 / 230 + 0.5 - 0.11
    assert result.next_d18 < 30


def test_no_d18_action_when_grid_path_is_uncontrollable() -> None:
    result = guard_math.calculate_reduction(
        bms_current=-70,
        bms_voltage=52,
        pv_power=1000,
        ups_power=1000,
        grid_power=0,
        grid_voltage=230,
        measured_grid_current=0,
        current_d18=9.3,
        target_bms_current=45,
        conversion_efficiency=0.9,
        minimum_d18=5,
        pv_headroom_current=0.5,
        reduction_margin_current=0.5,
        minimum_controllable_power=200,
    )
    assert result.uncontrollable_path
    assert not result.should_reduce
    assert result.next_d18 == 9.3


def test_recovery_requires_demand_below_cap() -> None:
    assert guard_math.has_recovery_headroom(
        grid_power=-1000,
        grid_voltage=230,
        measured_grid_current=None,
        limited_d18=9.3,
        headroom_current=1.0,
    )
    assert not guard_math.has_recovery_headroom(
        grid_power=-2100,
        grid_voltage=230,
        measured_grid_current=None,
        limited_d18=9.3,
        headroom_current=1.0,
    )
