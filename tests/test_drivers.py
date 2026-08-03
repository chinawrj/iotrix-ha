from __future__ import annotations

from ._load import load

drivers = load("drivers")


def test_driver_registry_describes_capabilities_not_accounts() -> None:
    hybrid = drivers.adapter_for("mppt_makeskyblue_v1")
    bms = drivers.adapter_for("bms_jikong_v2")
    assert hybrid.role == "hybrid" and hybrid.d18
    assert bms.role == "bms" and not bms.d18
    assert drivers.adapter_for("future-driver") is None


def test_high_churn_and_cell_fields_are_intentionally_omitted() -> None:
    assert "cell_voltage" not in drivers.BMS_FIELDS
    assert "work_time" not in drivers.BMS_FIELDS
    assert "sys_time" not in drivers.BMS_FIELDS
    assert "max_diff_voltage" in drivers.BMS_FIELDS
