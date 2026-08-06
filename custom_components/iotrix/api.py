"""Async client for the IoTrix cloud API."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from aiohttp import (
    ClientError,
    ClientResponseError,
    ClientSession,
    ClientWebSocketResponse,
    WSServerHandshakeError,
)

from .const import D18_COMMAND, DEFAULT_WS_INTERVAL


class IoTrixApiError(Exception):
    """Base IoTrix API error."""


class IoTrixAuthError(IoTrixApiError):
    """The IoTrix token was rejected."""


def normalize_base_url(host: str) -> str:
    """Normalize a user supplied host without retaining a path or query."""
    value = host.strip()
    if not value:
        raise ValueError("host is empty")
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("host must be an HTTP(S) host")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")


class IoTrixApi:
    """Small API surface required by the Home Assistant integration."""

    def __init__(self, session: ClientSession, host: str, token: str) -> None:
        self._session = session
        self.base_url = normalize_base_url(host)
        self._token = token.strip()

    @property
    def host(self) -> str:
        """Return the non-secret normalized host."""
        return urlsplit(self.base_url).netloc

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
    ) -> Any:
        try:
            async with self._session.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers,
                json=json_body,
                timeout=20,
            ) as response:
                if response.status in {401, 403}:
                    raise IoTrixAuthError("IoTrix authentication failed")
                response.raise_for_status()
                return await response.json(content_type=None)
        except IoTrixAuthError:
            raise
        except (
            ClientResponseError,
            ClientError,
            TimeoutError,
            json.JSONDecodeError,
        ) as err:
            raise IoTrixApiError(f"IoTrix request failed: {type(err).__name__}") from err

    async def async_user(self) -> Mapping[str, Any]:
        """Return the authenticated cloud user."""
        payload = await self._request_json("GET", "/api/v1/user/me")
        if not isinstance(payload, Mapping):
            raise IoTrixApiError("IoTrix user response has an unexpected shape")
        return payload

    async def async_list_devices(self) -> Any:
        """Return the owned-device response without assuming a fixed count."""
        return await self._request_json("GET", "/api/v1/device/list-owned")

    async def async_execute_d18(self, device_id: str, driver: str, value: float) -> None:
        """Send the allow-listed D18 command."""
        body = {
            "driver": driver,
            "name": D18_COMMAND,
            "device_addr": 1,
            "params": [round(value, 1)],
        }
        payload = await self._request_json(
            "PUT", f"/api/v1/command/{device_id}/execute", json_body=body
        )
        root_code = payload.get("code") if isinstance(payload, Mapping) else None
        nested = payload.get("data") if isinstance(payload, Mapping) else None
        nested_code = nested.get("code") if isinstance(nested, Mapping) else None
        if root_code != 0 and nested_code != 0:
            raise IoTrixApiError("IoTrix rejected the D18 command")

    async def async_connect_websocket(self) -> ClientWebSocketResponse:
        """Open the realtime push channel.

        The URL is never logged because it contains the access token.
        """
        parsed = urlsplit(self.base_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        url = urlunsplit(
            (
                scheme,
                parsed.netloc,
                "/api/v1/realtime/subscribe",
                f"interval={DEFAULT_WS_INTERVAL}&token={self._token}",
                "",
            )
        )
        try:
            return await self._session.ws_connect(
                url,
                heartbeat=20,
                receive_timeout=65,
                timeout=20,
                max_msg_size=4 * 1024 * 1024,
            )
        except WSServerHandshakeError as err:
            if err.status in {401, 403}:
                raise IoTrixAuthError("IoTrix authentication failed") from err
            raise IoTrixApiError(
                f"IoTrix WebSocket connection failed: {type(err).__name__}"
            ) from err
        except (ClientError, TimeoutError) as err:
            raise IoTrixApiError(
                f"IoTrix WebSocket connection failed: {type(err).__name__}"
            ) from err


async def iter_json_messages(ws: ClientWebSocketResponse) -> AsyncIterator[Any]:
    """Yield decoded JSON frames from an IoTrix WebSocket."""
    async for message in ws:
        if message.type.name == "TEXT":
            try:
                yield json.loads(message.data)
            except (TypeError, ValueError):
                continue
        elif message.type.name in {"CLOSE", "CLOSED", "ERROR"}:
            break
