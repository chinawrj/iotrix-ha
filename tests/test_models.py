from __future__ import annotations

from ._load import load

models = load("models")


def test_devices_are_dynamic_and_deduplicated() -> None:
    payload = {
        "data": [
            {
                "device_id": "cloud-a",
                "display_name": "Roof inverter",
                "device_type": "energy",
                "device_metadata": '{"driver":"mppt_makeskyblue_v1"}',
            },
            {
                "device_id": "cloud-b",
                "display_name": "Battery cabinet",
                "device_metadata": {"driver": "bms_jikong_v2"},
            },
            {
                "device_id": "cloud-c",
                "display_name": "Future device",
                "device_metadata": '{"driver":"future_v9"}',
            },
            {
                "device_id": "cloud-a",
                "display_name": "Renamed inverter",
                "device_metadata": '{"driver":"mppt_makeskyblue_v1"}',
            },
        ]
    }
    devices = models.parse_devices(payload)
    assert [device.device_id for device in devices] == ["cloud-a", "cloud-b", "cloud-c"]
    assert devices[0].name == "Renamed inverter"
    assert devices[2].driver == "future_v9"


def test_zero_devices_is_valid() -> None:
    assert models.parse_devices({"data": []}) == []
    assert models.parse_devices(None) == []
