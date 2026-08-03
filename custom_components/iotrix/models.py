"""Data models returned by the IoTrix cloud."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


def _json_mapping(value: Any) -> dict[str, Any]:
    """Turn IoTrix JSON-in-a-string fields into dictionaries."""
    if isinstance(value, Mapping):
        return dict(value)
    if not isinstance(value, str) or not value:
        return {}
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return dict(decoded) if isinstance(decoded, Mapping) else {}


@dataclass(frozen=True, slots=True)
class IoTrixDevice:
    """A physical device discovered from an IoTrix account."""

    device_id: str
    name: str
    device_type: str
    driver: str
    owner_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    userdata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, raw: Mapping[str, Any]) -> IoTrixDevice:
        """Build a device from /api/v1/device/list-owned."""
        metadata = _json_mapping(raw.get("device_metadata"))
        userdata = _json_mapping(raw.get("device_userdata"))
        driver = str(metadata.get("driver") or userdata.get("driver") or "unknown")
        return cls(
            device_id=str(raw.get("device_id") or ""),
            name=str(raw.get("display_name") or raw.get("device_id") or "IoTrix device"),
            device_type=str(raw.get("device_type") or "unknown"),
            driver=driver,
            owner_id=str(raw.get("owner_id") or ""),
            metadata=metadata,
            userdata=userdata,
        )


def parse_devices(payload: Any) -> list[IoTrixDevice]:
    """Parse and de-duplicate a cloud device response."""
    if isinstance(payload, Mapping):
        payload = payload.get("data")
    if not isinstance(payload, list):
        return []
    devices: dict[str, IoTrixDevice] = {}
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        device = IoTrixDevice.from_api(item)
        if device.device_id:
            devices[device.device_id] = device
    return list(devices.values())
