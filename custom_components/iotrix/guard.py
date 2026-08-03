"""Conservative D18 guard running entirely inside Home Assistant."""

from __future__ import annotations

import asyncio
import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .api import IoTrixApiError
from .const import (
    D18_FIELD,
    D18_MAX,
    D18_MIN,
    EVENT_TYPE,
    GUARD_BMS_FRESH_SECONDS,
    GUARD_DEFAULTS,
    GUARD_EVALUATION_INTERVAL,
    GUARD_TELEMETRY_FRESH_SECONDS,
)
from .drivers import adapter_for
from .guard_math import (
    calculate_reduction,
    has_recovery_headroom,
    update_overcurrent_score,
)
from .hub import IoTrixHub


class GuardPhase(StrEnum):
    """D18 guard state-machine phase."""

    DISABLED = "disabled"
    ARMED = "armed"
    TRIP_PENDING = "trip_pending"
    LIMITED_HOLD = "limited_hold"
    RECOVERY_QUALIFY = "recovery_qualify"
    RESTORE_VERIFY = "restore_verify"
    RECOVERY_LOCK = "recovery_lock"


@dataclass(slots=True)
class GuardEvent:
    """One auditable state-machine event."""

    event_type: str
    sequence: int
    timestamp: str
    details: dict[str, Any]

    def compact(self) -> str:
        return json.dumps(
            {
                "algorithm": "grid_path_v2_ha",
                "sequence": self.sequence,
                "timestamp": self.timestamp,
                "type": self.event_type,
                **self.details,
            },
            separators=(",", ":"),
            ensure_ascii=False,
        )


class D18Guard:
    """Pair one cloud-discovered inverter with one cloud-discovered BMS."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        hub: IoTrixHub,
        hybrid_id: str | None,
        bms_id: str | None,
    ) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.hub = hub
        self.configured_hybrid_id = hybrid_id
        self.configured_bms_id = bms_id
        self.hybrid_id: str | None = None
        self.bms_id: str | None = None
        self.params: dict[str, float | bool] = dict(GUARD_DEFAULTS)
        self.phase = GuardPhase.DISABLED
        self.status = "Disabled"
        self.active = False
        self.owns_limit = False
        self.baseline_d18: float | None = None
        self.limited_d18: float | None = None
        self.last_event: GuardEvent | None = None
        self.event_sequence = 0
        self._listeners: set[Callable[[], None]] = set()
        self._event_listeners: set[Callable[[GuardEvent], None]] = set()
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"iotrix.guard.{entry_id}")
        self._unsub_timer: Callable[[], None] | None = None
        self._unsub_devices: Callable[[], None] | None = None
        self._lock = asyncio.Lock()
        self._last_eval = time.monotonic()
        self._last_action: float | None = None
        self._overcurrent_score = 0.0
        self._recovery_elapsed = 0.0
        self._restore_verify_elapsed = 0.0
        self._recovery_lock_elapsed = 0.0

    async def async_setup(self) -> None:
        """Restore HA-side state and begin evaluating fresh push data."""
        stored = await self._store.async_load() or {}
        stored_params = stored.get("params")
        if isinstance(stored_params, dict):
            for key, default in GUARD_DEFAULTS.items():
                if key in stored_params and isinstance(stored_params[key], type(default)):
                    self.params[key] = stored_params[key]
                elif key in stored_params and isinstance(default, float):
                    try:
                        self.params[key] = float(stored_params[key])
                    except (TypeError, ValueError):
                        pass
        self.owns_limit = bool(stored.get("owns_limit", False))
        self.baseline_d18 = self._finite_or_none(stored.get("baseline_d18"))
        self.limited_d18 = self._finite_or_none(stored.get("limited_d18"))
        self.event_sequence = int(stored.get("event_sequence", 0) or 0)
        self._resolve_pair()
        if not bool(self.params["enabled"]):
            self.phase = GuardPhase.DISABLED
            self.status = "Disabled"
        elif self.owns_limit:
            self.phase = GuardPhase.LIMITED_HOLD
            self.status = "Limited hold - restored ownership"
        else:
            self.phase = GuardPhase.ARMED
            self.status = "Armed - waiting for telemetry"
        self._unsub_devices = self.hub.add_device_listener(self._handle_devices_changed)
        self._unsub_timer = async_track_time_interval(
            self.hass,
            lambda _now: self.hass.async_create_task(self.async_evaluate()),
            GUARD_EVALUATION_INTERVAL,
        )
        await self._record_event(
            "boot_snapshot",
            {
                "guard_enabled": bool(self.params["enabled"]),
                "owns_limit": self.owns_limit,
                "hybrid_id": self.hybrid_id,
                "bms_id": self.bms_id,
            },
        )

    async def async_shutdown(self) -> None:
        if self._unsub_timer is not None:
            self._unsub_timer()
        if self._unsub_devices is not None:
            self._unsub_devices()
        await self._save()

    @staticmethod
    def _finite_or_none(value: Any) -> float | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if math.isfinite(parsed) else None

    def _resolve_pair(self) -> None:
        def select(configured: str | None, role: str) -> str | None:
            if configured in self.hub.devices:
                adapter = adapter_for(self.hub.devices[configured].driver)
                if adapter is not None and adapter.role == role:
                    return configured
            candidates = [
                device.device_id
                for device in self.hub.devices.values()
                if (adapter := adapter_for(device.driver)) is not None
                and adapter.role == role
                and (role != "hybrid" or adapter.d18)
            ]
            return candidates[0] if len(candidates) == 1 else None

        self.hybrid_id = select(self.configured_hybrid_id, "hybrid")
        self.bms_id = select(self.configured_bms_id, "bms")

    def _handle_devices_changed(self) -> None:
        previous = (self.hybrid_id, self.bms_id)
        self._resolve_pair()
        if previous != (self.hybrid_id, self.bms_id):
            self._notify()

    @property
    def pair_ready(self) -> bool:
        return self.hybrid_id is not None and self.bms_id is not None

    def add_listener(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._listeners.add(callback)

        def remove() -> None:
            self._listeners.discard(callback)

        return remove

    def add_event_listener(self, callback: Callable[[GuardEvent], None]) -> Callable[[], None]:
        self._event_listeners.add(callback)

        def remove() -> None:
            self._event_listeners.discard(callback)

        return remove

    def _notify(self) -> None:
        for callback in tuple(self._listeners):
            callback()

    def _set_status(self, status: str, *, active: bool | None = None) -> None:
        changed = status != self.status
        self.status = status
        if active is not None and active != self.active:
            self.active = active
            changed = True
        if changed:
            self._notify()

    async def async_set_param(self, key: str, value: float | bool) -> None:
        if key not in GUARD_DEFAULTS:
            raise ValueError(f"Unknown guard parameter: {key}")
        default = GUARD_DEFAULTS[key]
        self.params[key] = bool(value) if isinstance(default, bool) else float(value)
        if key == "enabled":
            self._overcurrent_score = 0.0
            self._recovery_elapsed = 0.0
            if not bool(value):
                self.phase = GuardPhase.DISABLED
                self._set_status("Disabled", active=False)
                await self._record_event("guard_disabled", {"d18_unchanged": True})
            else:
                self.phase = GuardPhase.LIMITED_HOLD if self.owns_limit else GuardPhase.ARMED
                self._set_status(
                    "Limited hold - guard re-enabled"
                    if self.owns_limit
                    else "Armed - waiting for telemetry",
                    active=self.owns_limit,
                )
                await self._record_event("guard_enabled", {"owns_limit": self.owns_limit})
        await self._save()
        self._notify()

    async def async_manual_override(self, confirmed_d18: float) -> None:
        """Release guard ownership after a user-initiated, confirmed D18 write."""
        previously_owned = self.owns_limit
        self.owns_limit = False
        self.baseline_d18 = None
        self.limited_d18 = None
        self.phase = GuardPhase.ARMED if bool(self.params["enabled"]) else GuardPhase.DISABLED
        self._overcurrent_score = 0.0
        self._recovery_elapsed = 0.0
        self._restore_verify_elapsed = 0.0
        self._set_status(
            "Armed - manual D18 confirmed" if bool(self.params["enabled"]) else "Disabled",
            active=False,
        )
        await self._record_event(
            "manual_confirmed",
            {"confirmed": confirmed_d18, "released_guard_ownership": previously_owned},
        )

    def _settings_valid(self) -> bool:
        p = self.params
        return (
            float(p["release_current"]) < float(p["target_current"]) < float(p["trigger_current"])
            and D18_MIN <= float(p["restore_target"]) <= D18_MAX
            and D18_MIN <= float(p["minimum_d18"]) <= float(p["restore_target"])
            and 60.0 <= float(p["conversion_efficiency"]) <= 100.0
            and float(p["trip_delay"]) >= 5.0
            and float(p["minimum_write_interval"]) >= 60.0
            and float(p["recovery_observation"]) >= 60.0
            and float(p["restore_verification"]) >= 10.0
            and float(p["recovery_lock"]) >= 60.0
        )

    def _telemetry(self) -> dict[str, float] | None:
        if not self.pair_ready or not self.hub.connected:
            return None
        assert self.hybrid_id is not None and self.bms_id is not None
        required = {
            "bms_current": (self.bms_id, "sum_current", GUARD_BMS_FRESH_SECONDS),
            "bms_voltage": (self.bms_id, "sum_voltage", GUARD_BMS_FRESH_SECONDS),
            "pv_power": (self.hybrid_id, "power", GUARD_TELEMETRY_FRESH_SECONDS),
            "grid_power": (self.hybrid_id, "grid_power", GUARD_TELEMETRY_FRESH_SECONDS),
            "ups_power": (self.hybrid_id, "load_power", GUARD_TELEMETRY_FRESH_SECONDS),
            "d18": (self.hybrid_id, D18_FIELD, GUARD_TELEMETRY_FRESH_SECONDS),
        }
        result: dict[str, float] = {}
        for name, (device_id, field, freshness) in required.items():
            value = self.hub.numeric(device_id, field)
            age = self.hub.field_age(device_id, field)
            if value is None or age is None or age > freshness:
                return None
            result[name] = value
        result["grid_voltage"] = self.hub.numeric(self.hybrid_id, "grid_voltage") or 230.0
        measured = self.hub.numeric(self.hybrid_id, "inverter_grid_load_current")
        if measured is not None:
            result["grid_current"] = measured
        return result

    async def async_evaluate(self) -> None:
        if self._lock.locked():
            return
        async with self._lock:
            now = time.monotonic()
            elapsed = min(5.0, max(0.001, now - self._last_eval))
            self._last_eval = now
            if not bool(self.params["enabled"]):
                return
            if not self.pair_ready:
                self._set_status("Paused - select one inverter and one BMS", active=False)
                return
            if not self._settings_valid():
                self._recovery_elapsed = 0.0
                self._set_status("Invalid guard settings", active=False)
                return
            telemetry = self._telemetry()
            if telemetry is None:
                self._recovery_elapsed = 0.0
                # A restore verification only advances with fresh telemetry.
                self._set_status("Paused - telemetry is not fresh", active=self.owns_limit)
                return

            current = telemetry["bms_current"]
            d18 = telemetry["d18"]
            self._overcurrent_score = update_overcurrent_score(
                self._overcurrent_score,
                current,
                float(self.params["trigger_current"]),
                float(self.params["release_current"]),
                elapsed,
                float(self.params["trip_delay"]),
            )
            action_ready = self._last_action is None or now - self._last_action >= float(
                self.params["minimum_write_interval"]
            )

            if self.phase == GuardPhase.RESTORE_VERIFY:
                self._restore_verify_elapsed += elapsed
                self._set_status("Restore verification window", active=True)
                if (
                    self._overcurrent_score >= float(self.params["trip_delay"])
                    and bool(self.params["emergency_rollback"])
                    and self.limited_d18 is not None
                ):
                    await self._write_d18(
                        self.limited_d18,
                        "rollback",
                        {
                            "reason": "restore_overcurrent",
                            "bms_current": current,
                            "interval_bypass": True,
                        },
                        bypass_interval=True,
                    )
                    return
                if self._restore_verify_elapsed >= float(self.params["restore_verification"]):
                    await self._record_event("restore_verified", {"bms_current": current})
                    self.owns_limit = False
                    self.baseline_d18 = None
                    self.limited_d18 = None
                    self.phase = GuardPhase.ARMED
                    self._set_status("Armed - restore verified", active=False)
                    await self._save()
                return

            if self.phase == GuardPhase.RECOVERY_LOCK:
                self._recovery_lock_elapsed += elapsed
                self._set_status("Recovery locked after failed restore", active=True)
                if self._recovery_lock_elapsed < float(self.params["recovery_lock"]):
                    return
                self.phase = GuardPhase.LIMITED_HOLD
                self._recovery_elapsed = 0.0
                await self._record_event("recovery_lock_expired", {})

            if current <= -float(self.params["trigger_current"]):
                self._recovery_elapsed = 0.0
                if self.phase != GuardPhase.TRIP_PENDING:
                    self.phase = GuardPhase.TRIP_PENDING
                    self._set_status("Timing sustained BMS discharge", active=False)
                    await self._record_event(
                        "trip_started",
                        {
                            "bms_current": current,
                            "trigger": -float(self.params["trigger_current"]),
                            "delay": float(self.params["trip_delay"]),
                        },
                    )
                if self._overcurrent_score < float(self.params["trip_delay"]):
                    return
                self._set_status("Overcurrent detected", active=True)
                if not action_ready:
                    self._set_status("Limiting - waiting for action interval", active=True)
                    return
                reduction = calculate_reduction(
                    bms_current=current,
                    bms_voltage=telemetry["bms_voltage"],
                    pv_power=telemetry["pv_power"],
                    ups_power=telemetry["ups_power"],
                    grid_power=telemetry["grid_power"],
                    grid_voltage=telemetry["grid_voltage"],
                    measured_grid_current=telemetry.get("grid_current"),
                    current_d18=d18,
                    target_bms_current=float(self.params["target_current"]),
                    conversion_efficiency=float(self.params["conversion_efficiency"]) / 100.0,
                    minimum_d18=float(self.params["minimum_d18"]),
                    pv_headroom_current=float(self.params["pv_headroom"]),
                    reduction_margin_current=float(self.params["reduction_margin"]),
                    minimum_controllable_power=float(self.params["minimum_controllable_power"]),
                )
                if reduction.uncontrollable_path:
                    already_blocked = self.status == "Overcurrent - D18 path unavailable"
                    self._set_status("Overcurrent - D18 path unavailable", active=True)
                    if not already_blocked:
                        await self._record_event(
                            "blocked_uncontrollable",
                            {
                                "bms_current": current,
                                "grid_power": telemetry["grid_power"],
                            },
                        )
                elif reduction.should_reduce:
                    await self._write_d18(
                        reduction.next_d18,
                        "limit",
                        {
                            "bms_current": current,
                            "battery_voltage": telemetry["bms_voltage"],
                            "pv_power": telemetry["pv_power"],
                            "ups_power": telemetry["ups_power"],
                            "grid_power": telemetry["grid_power"],
                            "grid_current": reduction.actual_grid_current,
                            "pv_floor": reduction.pv_floor_current,
                            "floor_limited": reduction.floor_limited,
                        },
                    )
                else:
                    self._set_status(
                        "PV/minimum floor prevents further limit"
                        if reduction.floor_limited
                        else "Overcurrent - no effective D18 reduction",
                        active=True,
                    )
                return

            if self.owns_limit:
                self.phase = GuardPhase.LIMITED_HOLD
                self._set_status("Limited hold", active=True)
                if not bool(self.params["auto_restore"]):
                    self._recovery_elapsed = 0.0
                    self._set_status("Limited hold - automatic restore disabled", active=True)
                    return
                if self._overcurrent_score > 0.0:
                    self._recovery_elapsed = 0.0
                    self._set_status("Cooling anti-oscillation memory", active=True)
                    return
                if not action_ready:
                    self._recovery_elapsed = 0.0
                    self._set_status("Limited hold - minimum write interval", active=True)
                    return
                safe = current > -float(self.params["release_current"])
                headroom = has_recovery_headroom(
                    grid_power=telemetry["grid_power"],
                    grid_voltage=telemetry["grid_voltage"],
                    measured_grid_current=telemetry.get("grid_current"),
                    limited_d18=d18,
                    headroom_current=float(self.params["recovery_headroom"]),
                )
                if safe and headroom:
                    if self._recovery_elapsed == 0.0:
                        self.phase = GuardPhase.RECOVERY_QUALIFY
                        await self._record_event(
                            "recovery_started",
                            {
                                "bms_current": current,
                                "grid_power": telemetry["grid_power"],
                                "limited_d18": d18,
                                "observe": float(self.params["recovery_observation"]),
                            },
                        )
                    self._recovery_elapsed += elapsed
                    self._set_status("Recovery qualification - demand below cap", active=True)
                    if self._recovery_elapsed >= float(self.params["recovery_observation"]):
                        baseline = self.baseline_d18 or float(self.params["restore_target"])
                        restore = min(baseline, float(self.params["restore_target"]))
                        await self._write_d18(
                            restore,
                            "restore",
                            {
                                "bms_current": current,
                                "grid_power": telemetry["grid_power"],
                                "limited_d18": d18,
                                "baseline": baseline,
                            },
                        )
                    return
                self._recovery_elapsed = 0.0
                self._set_status(
                    "Limited hold - BMS current not safe"
                    if not safe
                    else "Limited hold - on-grid demand still at cap",
                    active=True,
                )
                return

            self.phase = GuardPhase.ARMED
            self._set_status(
                "Armed - manual low D18 is not guard-owned"
                if d18 < float(self.params["restore_target"]) - 0.05
                else "Armed",
                active=False,
            )

    async def _write_d18(
        self,
        target: float,
        kind: str,
        details: dict[str, Any],
        *,
        bypass_interval: bool = False,
    ) -> None:
        if self.hybrid_id is None:
            return
        before = self.hub.numeric(self.hybrid_id, D18_FIELD)
        if before is None:
            return
        now = time.monotonic()
        if (
            not bypass_interval
            and self._last_action is not None
            and now - self._last_action < float(self.params["minimum_write_interval"])
        ):
            return
        self._last_action = now
        await self._record_event(
            f"{kind}_requested", {"before": before, "requested": target, **details}
        )

        async def record_accepted() -> None:
            await self._record_event(f"{kind}_accepted", {"before": before, "requested": target})

        def accepted() -> None:
            self.hass.async_create_task(record_accepted())

        try:
            confirmed = await self.hub.async_set_d18(
                self.hybrid_id, target, accepted_callback=accepted
            )
        except (IoTrixApiError, TimeoutError) as err:
            await self._record_event(
                f"{kind}_failed",
                {"before": before, "requested": target, "error": type(err).__name__},
            )
            self._set_status("D18 command failed", active=self.owns_limit)
            return
        await self._record_event(
            f"{kind}_confirmed",
            {"before": before, "requested": target, "confirmed": confirmed},
        )
        if kind == "limit":
            if not self.owns_limit:
                self.baseline_d18 = before
            self.owns_limit = True
            self.limited_d18 = confirmed
            self.phase = GuardPhase.LIMITED_HOLD
            self._recovery_elapsed = 0.0
            self._set_status("Limited hold - D18 readback confirmed", active=True)
        elif kind == "restore":
            self.phase = GuardPhase.RESTORE_VERIFY
            self._restore_verify_elapsed = 0.0
            self._overcurrent_score = 0.0
            self._set_status("Restore verification window", active=True)
        elif kind == "rollback":
            self.limited_d18 = confirmed
            self.phase = GuardPhase.RECOVERY_LOCK
            self._recovery_lock_elapsed = 0.0
            self._overcurrent_score = 0.0
            self._set_status("Recovery locked after rollback", active=True)
        await self._save()

    async def _record_event(self, event_type: str, details: dict[str, Any]) -> None:
        self.event_sequence += 1
        event = GuardEvent(
            event_type=event_type,
            sequence=self.event_sequence,
            timestamp=datetime.now(UTC).isoformat(),
            details=details,
        )
        self.last_event = event
        event_data = {
            "event_type": event_type,
            "sequence": event.sequence,
            "timestamp": event.timestamp,
            "hybrid_device_id": self.hybrid_id,
            "bms_device_id": self.bms_id,
            **details,
        }
        self.hass.bus.async_fire(EVENT_TYPE, event_data)
        for callback in tuple(self._event_listeners):
            callback(event)
        self._notify()
        await self._save()

    async def _save(self) -> None:
        await self._store.async_save(
            {
                "params": self.params,
                "owns_limit": self.owns_limit,
                "baseline_d18": self.baseline_d18,
                "limited_d18": self.limited_d18,
                "event_sequence": self.event_sequence,
            }
        )
