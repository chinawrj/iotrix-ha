from __future__ import annotations

import asyncio

from ._load import load

api_module = load("api")
hub_module = load("hub")


def test_websocket_auth_failure_requests_reauthentication_once() -> None:
    class FakeApi:
        async def async_connect_websocket(self):
            raise api_module.IoTrixAuthError("rejected")

    calls = 0

    def request_reauthentication() -> None:
        nonlocal calls
        calls += 1

    hub = hub_module.IoTrixHub(FakeApi(), auth_failed_callback=request_reauthentication)

    asyncio.run(hub._websocket_loop())
    hub._handle_auth_failure()

    assert calls == 1
    assert hub.connected is False
