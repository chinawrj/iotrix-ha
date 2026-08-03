from __future__ import annotations

import asyncio

import pytest

from ._load import load

api_module = load("api")


def test_host_normalization_strips_paths_and_forces_explicit_scheme() -> None:
    assert api_module.normalize_base_url("api.example.test/foo?q=1") == "https://api.example.test"
    assert api_module.normalize_base_url("http://lan.test:8080/") == "http://lan.test:8080"
    with pytest.raises(ValueError):
        api_module.normalize_base_url("ftp://example.test")


def test_only_d18_command_shape_is_emitted() -> None:
    class FakeApi(api_module.IoTrixApi):
        def __init__(self) -> None:
            self.calls = []

        async def _request_json(self, method, path, *, json_body=None):
            self.calls.append((method, path, json_body))
            return {"code": 0}

    api = FakeApi()
    asyncio.run(api.async_execute_d18("dynamic-device", "mppt_makeskyblue_v1", 12.34))
    assert api.calls == [
        (
            "PUT",
            "/api/v1/command/dynamic-device/execute",
            {
                "driver": "mppt_makeskyblue_v1",
                "name": "ctrl_max_on_grid_current",
                "device_addr": 1,
                "params": [12.3],
            },
        )
    ]
