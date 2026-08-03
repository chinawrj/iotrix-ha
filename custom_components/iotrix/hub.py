"""Dynamic IoTrix device discovery and realtime push hub."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections import defaultdict
from collections.abc import Callable
from contextlib import suppress
from typing import Any

from .api import IoTrixApi, IoTrixApiError, iter_json_messages
from .const import D18_FIELD
from .drivers import adapter_for
from .models import IoTrixDevice, parse_devices

_LOGGER = logging.getLogger(__name__)

StateListener = Callable[[], None]
DeviceListener = Callable[[], None]


def numeric_value(value: Any) -> float | None:
    """Parse a finite IoTrix numeric value."""
    if isinstance(value, bool):
        return float(value)
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


class IoTrixHub:
    """Own the cloud connection for one IoTrix account config entry."""

    def __init__(self, api: IoTrixApi, refresh_interval: int = 300) -> None:
        self.api = api
        self.refresh_interval = max(60, refresh_interval)
        self.devices: dict[str, IoTrixDevice] = {}
        self.data: dict[str, dict[str, Any]] = defaultdict(dict)
        self.updated_at: dict[tuple[str, str], float] = {}
        self.connected = False
        self.last_message_monotonic: float | None = None
        self._listeners: dict[str | None, set[StateListener]] = defaultdict(set)
        self._device_listeners: set[DeviceListener] = set()
        self._tasks: set[asyncio.Task[Any]] = set()
        self._stop = asyncio.Event()
        self._ws = None
        self._d18_lock = asyncio.Lock()
        self._value_waiters: dict[tuple[str, str], list[tuple[float, asyncio.Future[float]]]] = (
            defaultdict(list)
        )

    async def async_setup(self) -> None:
        """Perform initial discovery before platforms are forwarded."""
        await self.async_refresh_devices()
        self._create_task(self._websocket_loop(), "iotrix websocket")
        self._create_task(self._device_refresh_loop(), "iotrix device discovery")

    async def async_shutdown(self) -> None:
        """Stop background activity without changing cloud state."""
        self._stop.set()
        if self._ws is not None:
            await self._ws.close()
        for task in tuple(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    def _create_task(self, coroutine: Any, name: str) -> None:
        task = asyncio.create_task(coroutine, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def async_refresh_devices(self) -> bool:
        """Refresh account devices and notify platforms when the set changes."""
        discovered = {d.device_id: d for d in parse_devices(await self.api.async_list_devices())}
        changed = discovered != self.devices
        self.devices = discovered
        if changed:
            for callback in tuple(self._device_listeners):
                callback()
        return changed

    async def _device_refresh_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.refresh_interval)
                return
            except TimeoutError:
                pass
            try:
                changed = await self.async_refresh_devices()
                if changed and self._ws is not None:
                    await self._ws.close()
            except IoTrixApiError as err:
                _LOGGER.warning("IoTrix device discovery refresh failed: %s", err)

    async def _websocket_loop(self) -> None:
        delay = 1.0
        while not self._stop.is_set():
            try:
                ws = await self.api.async_connect_websocket()
                self._ws = ws
                self.connected = True
                self._notify(None)
                await ws.send_json(self._subscription_payload())
                delay = 1.0
                async for payload in iter_json_messages(ws):
                    self._process_payload(payload)
            except asyncio.CancelledError:
                raise
            except IoTrixApiError as err:
                _LOGGER.warning("IoTrix realtime connection unavailable: %s", err)
            finally:
                self._ws = None
                if self.connected:
                    self.connected = False
                    self._notify(None)
            if self._stop.is_set():
                return
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
                return
            except TimeoutError:
                delay = min(60.0, delay * 2.0)

    def _subscription_payload(self) -> dict[str, Any]:
        args: list[dict[str, Any]] = []
        for device in self.devices.values():
            adapter = adapter_for(device.driver)
            if adapter is None:
                continue
            args.extend(
                {
                    "device_id": device.device_id,
                    "package": "data",
                    "name": field,
                    "driver": device.driver,
                }
                for field in adapter.fields
            )
        return {"op": "subscribe", "args": args}

    def _process_payload(self, payload: Any) -> None:
        if not isinstance(payload, list):
            return
        now = time.monotonic()
        touched: set[str] = set()
        for record in payload:
            if not isinstance(record, dict):
                continue
            device_id = str(record.get("device_id") or "")
            field = str(record.get("name") or "")
            if not device_id or not field or device_id not in self.devices:
                continue
            value = record.get("value")
            self.data[device_id][field] = value
            self.updated_at[(device_id, field)] = now
            touched.add(device_id)
            parsed = numeric_value(value)
            if parsed is not None:
                self._resolve_waiters(device_id, field, parsed)
        if touched:
            self.last_message_monotonic = now
            for device_id in touched:
                self._notify(device_id)

    def _resolve_waiters(self, device_id: str, field: str, value: float) -> None:
        key = (device_id, field)
        remaining: list[tuple[float, asyncio.Future[float]]] = []
        for target, future in self._value_waiters.pop(key, []):
            if not future.done() and abs(value - target) < 0.05:
                future.set_result(value)
            elif not future.done():
                remaining.append((target, future))
        if remaining:
            self._value_waiters[key] = remaining

    def value(self, device_id: str, field: str) -> Any:
        return self.data.get(device_id, {}).get(field)

    def numeric(self, device_id: str, field: str) -> float | None:
        return numeric_value(self.value(device_id, field))

    def field_age(self, device_id: str, field: str) -> float | None:
        updated = self.updated_at.get((device_id, field))
        return None if updated is None else max(0.0, time.monotonic() - updated)

    def add_listener(self, device_id: str | None, callback: StateListener) -> Callable[[], None]:
        self._listeners[device_id].add(callback)

        def remove() -> None:
            self._listeners[device_id].discard(callback)

        return remove

    def add_device_listener(self, callback: DeviceListener) -> Callable[[], None]:
        self._device_listeners.add(callback)

        def remove() -> None:
            self._device_listeners.discard(callback)

        return remove

    def _notify(self, device_id: str | None) -> None:
        callbacks = set(self._listeners.get(None, ()))
        if device_id is not None:
            callbacks.update(self._listeners.get(device_id, ()))
        for callback in tuple(callbacks):
            callback()

    async def async_set_d18(
        self,
        device_id: str,
        value: float,
        accepted_callback: Callable[[], None] | None = None,
    ) -> float:
        """Write D18 once and require authoritative realtime readback."""
        device = self.devices[device_id]
        adapter = adapter_for(device.driver)
        if adapter is None or not adapter.d18:
            raise IoTrixApiError("Device does not expose D18 control")
        target = round(value, 1)
        async with self._d18_lock:
            current = self.numeric(device_id, D18_FIELD)
            if current is not None and abs(current - target) < 0.05:
                return current
            loop = asyncio.get_running_loop()
            future: asyncio.Future[float] = loop.create_future()
            key = (device_id, D18_FIELD)
            self._value_waiters[key].append((target, future))
            try:
                await self.api.async_execute_d18(device_id, device.driver, target)
                if accepted_callback is not None:
                    accepted_callback()
                return await asyncio.wait_for(future, timeout=90)
            finally:
                with suppress(ValueError):
                    self._value_waiters[key].remove((target, future))
